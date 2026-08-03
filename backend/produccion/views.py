from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from maestros import recetas
from maestros.models import Especificacion, Producto, Receta, Silo
from usuarios.permisos import EscribeProduccion

from . import dominio
from .models import (
    Analisis,
    ControlProceso,
    ControlProcesoLectura,
    Lote,
)
from .serializers import (
    AnalisisSerializer,
    ControlProcesoLecturaSerializer,
    ControlProcesoSerializer,
    LoteDetalleSerializer,
    LoteSerializer,
)


class LoteViewSet(viewsets.ModelViewSet):
    # `prefetch_related` trae los análisis de todos los lotes en una sola
    # consulta. Sin esto, calcular la calidad de un listado dispararía una
    # consulta por lote.
    queryset = (
        Lote.objects.select_related("producto", "producto__mandante")
        .prefetch_related("analisis")
    )
    serializer_class = LoteSerializer
    permission_classes = [EscribeProduccion]

    def get_serializer_class(self):
        # Todo lo que opera sobre UN lote devuelve el lote entero, con sus
        # análisis. Devolver menos en la respuesta de un PATCH obliga a quien
        # llama a pedir el lote otra vez, y si no lo hace se queda con una
        # ficha a medias: fue exactamente lo que rompió el panel de Producción
        # al cerrar un lote.
        if self.action in ("retrieve", "update", "partial_update"):
            return LoteDetalleSerializer

        return super().get_serializer_class()

    def get_serializer_context(self):
        contexto = super().get_serializer_context()
        # Las especificaciones se cargan una vez y las comparten todos los
        # lotes del listado.
        contexto["especificaciones"] = list(Especificacion.objects.all())
        return contexto

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        producto = parametros.get("producto")
        if producto:
            consulta = consulta.filter(producto_id=producto)

        mandante = parametros.get("mandante")
        if mandante:
            consulta = consulta.filter(producto__mandante_id=mandante)

        estado = parametros.get("estado")
        if estado:
            consulta = consulta.filter(estado=estado)

        desde = parametros.get("desde")
        if desde:
            consulta = consulta.filter(fecha__gte=desde)

        hasta = parametros.get("hasta")
        if hasta:
            consulta = consulta.filter(fecha__lte=hasta)

        buscar = parametros.get("buscar")
        if buscar:
            consulta = consulta.filter(codigo_lote__icontains=buscar)

        calidad = parametros.get("calidad")
        if calidad:
            consulta = consulta.filter(id__in=self._ids_con_calidad(consulta, calidad))

        return consulta

    def create(self, request, *args, **kwargs):
        """
        Abre un proceso: crea el lote y le asigna su leche de una vez.

        Van juntos a propósito. Si el lote se creara primero y la asignación
        fuera un segundo paso, un fallo entre medio dejaría un lote abierto
        sin materia prima — y nadie vuelve a completar lo que ya parece
        creado. La asignación al inicio es justamente lo que da trazabilidad;
        posponerla la convierte en documentación retroactiva.

        `asignaciones` es opcional: un lote histórico se carga sin ella, y el
        aviso al declararlo producido recuerda que quedó sin trazar.
        """
        lineas = request.data.get("asignaciones") or []

        if lineas and not isinstance(lineas, list):
            return Response(
                {"detail": 'Formato: "asignaciones": [{"silo": 3, "litros": 60000}]'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            respuesta = super().create(request, *args, **kwargs)

            if lineas:
                lote = Lote.objects.get(pk=respuesta.data["id"])
                creados = self._crear_asignaciones(lote, lineas)

                if isinstance(creados, Response):
                    # Se sale por excepción y no por return: dentro de un
                    # `atomic`, volver normalmente confirma la transacción y
                    # dejaría el lote creado sin su leche.
                    raise serializers.ValidationError(creados.data)

                respuesta.data["asignacion"] = self._estado_asignacion(lote)

        return respuesta

    @action(detail=False, methods=["get"], url_path="codigo-sugerido")
    def codigo_sugerido(self, request):
        """
        El código que le tocaría a un lote nuevo, según el POE.009.02.

        Se **sugiere**, no se impone: la respuesta trae el código y el
        operador puede cambiarlo. El histórico de planta trae códigos que no
        siguen el patrón y hay que poder registrarlos, así que el generador
        avisa y no restringe — la misma razón por la que `codigo_lote_valido`
        no cuelga del `clean()` del modelo.

        `segunda_produccion` no se pregunta: se deduce de si ya existe un lote
        de ese producto y esa fecha. Preguntarlo sería pedirle al operador un
        dato que el sistema ya tiene, y equivocarse ahí repite un código.
        """
        producto_id = request.query_params.get("producto")
        fecha_texto = request.query_params.get("fecha")

        if not producto_id or not fecha_texto:
            return Response(
                {"detail": "Indica el producto y la fecha."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fecha = parse_date(fecha_texto)

        if fecha is None:
            return Response(
                {"detail": f"Fecha no reconocida: {fecha_texto!r} (usa AAAA-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        producto = get_object_or_404(Producto, pk=producto_id)

        # El correlativo distingue dos lotes del mismo producto el mismo día.
        # Se cuenta lo que ya existe en vez de preguntarlo: pedirle al
        # operador un dato que el sistema tiene es como se repite un código.
        anteriores = Lote.objects.filter(producto=producto, fecha=fecha).count()
        correlativo = anteriores + 1

        codigo = dominio.generar_codigo_lote(fecha, producto.codigo, correlativo)

        if codigo is None:
            # 200 con `codigo: null`: el formulario sigue abierto y el
            # operador escribe el código a mano. Un 400 se leería como si el
            # lote no se pudiera crear, y sí se puede.
            return Response(
                {
                    "codigo": None,
                    "correlativo": correlativo,
                    "motivo": (
                        f"«{producto.nombre}» no tiene código de producto (SKU) "
                        "cargado en Maestros, y el SKU es parte del código de "
                        "lote. Escríbelo a mano o completa el maestro."
                    ),
                }
            )

        return Response(
            {
                "codigo": codigo,
                "correlativo": correlativo,
                "motivo": (
                    f"Es el lote n.º {correlativo} de este producto en la fecha."
                    if anteriores
                    else None
                ),
            }
        )

    @action(detail=True, methods=["get", "post"])
    def asignacion(self, request, pk=None):
        """
        La leche que este lote tomó de los silos.

        Aquí empieza la trazabilidad. La leche se mezcla dentro del silo, así
        que lo único que se puede afirmar de un lote es de qué estanques salió
        y cuánto de cada uno; el vínculo con las recepciones concretas es un
        conjunto de candidatas, no una cadena (MODELO_DATOS.md §2.5).

        Los litros **los declara Producción**, no los deriva el sistema. El
        libro mayor registra lo que realmente se tomó del estanque; lo que la
        receta dice que debería haberse tomado es otra cosa, y guardar la
        estimación en lugar del hecho haría que el saldo del silo dejara de
        ser un saldo.

        Se admiten varias líneas porque un producto puede mezclar leche de más
        de un silo, que es lo normal cuando ninguno alcanza solo.
        """
        lote = self.get_object()

        if request.method == "GET":
            return Response(self._estado_asignacion(lote))

        lineas = request.data.get("asignaciones")

        if not isinstance(lineas, list) or not lineas:
            return Response(
                {
                    "detail": (
                        "Hay que indicar de qué silos se tomó la leche: "
                        '[{"silo": 3, "litros": 60000}, ...]'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        bloqueo = self._por_que_no_se_puede_asignar(lote)
        if bloqueo:
            return Response({"detail": bloqueo}, status=status.HTTP_409_CONFLICT)

        creados = self._crear_asignaciones(lote, lineas)

        if isinstance(creados, Response):
            return creados

        return Response(self._estado_asignacion(lote))

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"asignacion/(?P<movimiento_id>\d+)",
    )
    def quitar_asignacion(self, request, pk=None, movimiento_id=None):
        """
        Quita una línea de asignación.

        Solo mientras el lote sigue **en proceso**: hasta ahí la asignación se
        está armando y borrar una línea es corregir un borrador. Después es
        histórico, y un asiento del libro mayor no se borra — se corrige con
        un ajuste que deja rastro.
        """
        from recepcion.models import MovimientoSilo

        lote = self.get_object()

        if lote.estado != Lote.Estado.EN_PROCESO:
            return Response(
                {
                    "detail": (
                        f"Un lote {lote.get_estado_display().lower()} ya no cambia "
                        "su asignación. Corrija con un ajuste de silo, que deja "
                        "rastro."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        movimiento = get_object_or_404(
            MovimientoSilo,
            pk=movimiento_id,
            tipo=MovimientoSilo.Tipo.SALIDA,
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=lote.id,
        )
        movimiento.delete()

        return Response(self._estado_asignacion(lote))

    @action(detail=True, methods=["get"])
    def trazabilidad(self, request, pk=None):
        """
        De qué recepciones pudo salir este lote.

        Devuelve un **conjunto** de recepciones candidatas por silo, no una
        cadena: son las que habían ingresado a ese estanque antes de que el
        lote consumiera. Prometer un vínculo exacto sería falso, porque dentro
        del silo la leche ya está mezclada.
        """
        from recepcion.dominio import trazabilidad_lote
        from recepcion.models import MovimientoSilo, Recepcion

        lote = self.get_object()

        tramos = trazabilidad_lote(lote.id, MovimientoSilo.objects.all())

        ids = {r for tramo in tramos for r in tramo["recepciones"]}
        recepciones = {
            r.id: {
                "id": r.id,
                "fecha": r.fecha,
                "guia": r.guia,
                "litros": r.litros,
                "procedencia": r.procedencia,
                "vehiculo": r.vehiculo.placa if r.vehiculo else None,
            }
            for r in Recepcion.objects.filter(id__in=ids).select_related("vehiculo")
        }

        silos = {
            s.id: s.codigo
            for s in Silo.objects.filter(id__in=[t["silo_id"] for t in tramos])
        }

        return Response(
            {
                "lote": lote.codigo_lote,
                "tramos": [
                    {
                        "silo": tramo["silo_id"],
                        "silo_codigo": silos.get(tramo["silo_id"]),
                        "litros": tramo["litros"],
                        "fecha_hora": tramo["fecha_hora"],
                        "recepciones": [
                            recepciones[r] for r in tramo["recepciones"] if r in recepciones
                        ],
                    }
                    for tramo in tramos
                ],
                # Se dice explícitamente para que nadie lea la lista como una
                # cadena de origen única.
                "nota": (
                    "Las recepciones son candidatas: la leche se mezcla dentro "
                    "del silo y no hay vínculo uno a uno."
                ),
            }
        )

    # ------------------------------------------------------------- ayudantes

    def _crear_asignaciones(self, lote, lineas):
        """
        Crea las líneas de asignación, todas o ninguna.

        Se valida **antes** de escribir nada. Devolver un `Response` desde
        dentro de `transaction.atomic()` NO revierte —salir por return es una
        salida normal, no un error—, así que media asignación quedaría
        guardada: el silo descontado y el lote sin la leche que decía tener.
        """
        from recepcion.models import MovimientoSilo

        preparadas = []

        for linea in lineas:
            silo_id = linea.get("silo")
            crudo = linea.get("litros")

            if not silo_id or crudo in (None, ""):
                return Response(
                    {"detail": "Cada línea necesita un silo y sus litros."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                litros = Decimal(str(crudo))
            except (InvalidOperation, TypeError):
                return Response(
                    {"detail": f"Litros no numéricos: {crudo!r}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if litros <= 0:
                return Response(
                    {"detail": "Los litros asignados deben ser mayores que cero."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            preparadas.append((silo_id, litros, linea.get("fecha_hora")))

        with transaction.atomic():
            return [
                MovimientoSilo.objects.create(
                    silo_id=silo_id,
                    tipo=MovimientoSilo.Tipo.SALIDA,
                    litros=litros,
                    # La hora acota la trazabilidad: solo cuentan las
                    # recepciones que ya estaban en el silo. Se puede declarar
                    # para cargar una asignación con retraso sin arrastrar
                    # leche que llegó después.
                    fecha_hora=fecha_hora or timezone.now(),
                    origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
                    origen_id=lote.id,
                    motivo=f"Asignación de leche al lote {lote.codigo_lote}",
                )
                for silo_id, litros, fecha_hora in preparadas
            ]

    def _por_que_no_se_puede_asignar(self, lote) -> str | None:
        """
        Un lote liberado o histórico no cambia de qué leche salió.

        Cambiarlo después de que Calidad firmó dejaría esa firma respaldando
        un producto hecho con otra materia prima, que es exactamente lo que la
        trazabilidad existe para impedir.
        """
        from calidad.models import Liberacion

        if not Lote.TRANSICIONES.get(lote.estado, []):
            return (
                f"Un lote {lote.get_estado_display().lower()} es histórico: su "
                "asignación de leche ya no cambia."
            )

        liberacion = Liberacion.objects.filter(lote=lote).first()

        if liberacion is not None and liberacion.liberado:
            return (
                "El lote está liberado: cambiar de qué leche salió dejaría la "
                "firma de Calidad respaldando otra materia prima. Retire antes "
                f"la liberación en expedientes/{lote.id}/revisar/."
            )

        return None

    def _estado_asignacion(self, lote):
        """
        Lo asignado, lo que la receta esperaba, y cómo se comparan.

        Los dos números se llevan aparte a propósito: **lo asignado es el
        hecho** —lo que salió del estanque— y **lo teórico es la expectativa**.
        Se informa, no se bloquea: una merma mayor de la prevista es algo que
        explicar, no algo que impedir.

        Sobre los dos indicadores, porque el nombre importa:

        - `consumo_pct` es asignado / teórico. Por debajo de 100 se usó menos
          leche de la prevista; por encima, más. En ese orden y no al revés:
          la razón inversa sube cuando se consume menos, y un número que crece
          al gastar menos se lee como un logro cuando muchas veces solo
          significa que falta cargar una línea.
        - `litros_por_kg` es el rendimiento como lo mide la planta: cuánta
          leche costó cada kilo. Al lado va el de la receta, que es contra lo
          que se compara.
        """
        from recepcion.models import MovimientoSilo

        lineas = MovimientoSilo.objects.filter(
            tipo=MovimientoSilo.Tipo.SALIDA,
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=lote.id,
        ).select_related("silo")

        asignado = float(sum(l.litros for l in lineas))
        teorico = self._litros_de_receta(lote)
        kg = float(lote.kg_producidos or 0)

        return {
            "lote": lote.codigo_lote,
            "estado": lote.estado,
            "editable": self._por_que_no_se_puede_asignar(lote) is None,
            "motivo_bloqueo": self._por_que_no_se_puede_asignar(lote),
            "lineas": [
                {
                    "id": l.id,
                    "silo": l.silo_id,
                    "silo_codigo": l.silo.codigo,
                    "litros": float(l.litros),
                    "fecha_hora": l.fecha_hora,
                }
                for l in lineas
            ],
            "asignado": asignado,
            # None cuando el producto no tiene receta vigente: no se inventa.
            "teorico": teorico,
            "diferencia": (asignado - teorico) if teorico is not None else None,
            "consumo_pct": (
                round(asignado / teorico * 100, 1)
                if teorico else None
            ),
            # Rendimiento real: sin kilos declarados todavía no hay tal cosa.
            "litros_por_kg": round(asignado / kg, 2) if kg and asignado else None,
            "litros_por_kg_receta": (
                round(teorico / kg, 2) if kg and teorico else None
            ),
        }

    @staticmethod
    def _litros_de_receta(lote) -> float | None:
        """
        Litros que la receta vigente dice que cuesta este lote.

        Sin kilos declarados no hay expectativa que calcular: la receta dice
        cuánta leche cuesta *cada kilo*, y mientras el lote está en proceso
        todavía no se sabe cuántos serán.
        """
        if lote.kg_producidos is None:
            return None

        return recetas.litros_de_leche(
            list(Producto.objects.all()),
            list(Receta.objects.prefetch_related("componentes")),
            lote.producto_id,
            lote.kg_producidos,
            lote.fecha,
        )

    @staticmethod
    def _ids_con_calidad(consulta, resultado):
        """
        IDs de los lotes cuyo veredicto de calidad es el pedido.

        El resultado se calcula, no se guarda (MODELO_DATOS.md §2.2), así que
        no se puede filtrar con SQL: hay que evaluar en Python y devolver los
        IDs para que el filtrado y la paginación sigan ocurriendo en la base.

        Coste: recorre los lotes que pasaron los demás filtros. Con el
        histórico previsto (~954 lotes) es asumible. Si algún día pesa, la
        salida no es persistir el veredicto —eso rompería la reevaluación del
        histórico— sino cachear por lote e invalidar al cambiar la spec.
        """
        especificaciones = list(Especificacion.objects.all())

        return [
            lote.id
            for lote in consulta.prefetch_related("analisis")
            if dominio.resultado_calidad_lote(
                lote, list(lote.analisis.all()), especificaciones
            ).resultado
            == resultado
        ]


class AnalisisViewSet(viewsets.ModelViewSet):
    queryset = Analisis.objects.select_related("lote")
    serializer_class = AnalisisSerializer
    permission_classes = [EscribeProduccion]

    def get_queryset(self):
        consulta = super().get_queryset()

        lote = self.request.query_params.get("lote")
        if lote:
            consulta = consulta.filter(lote_id=lote)

        return consulta


@api_view(["GET"])
def resumen(request):
    """
    Indicadores del panel general.

    Acepta `desde` y `hasta` (YYYY-MM-DD) para acotar el periodo.

    El cumplimiento de calidad viaja SIEMPRE con su cobertura: un 90 % sobre 3
    lotes de 40 no es una buena noticia, y el panel tiene que poder decirlo.
    """
    lotes = (
        Lote.objects.select_related("producto", "producto__mandante")
        .prefetch_related("analisis")
        .exclude(estado=Lote.Estado.ANULADO)
    )

    desde = request.query_params.get("desde")
    if desde:
        lotes = lotes.filter(fecha__gte=desde)

    hasta = request.query_params.get("hasta")
    if hasta:
        lotes = lotes.filter(fecha__lte=hasta)

    lotes = list(lotes)
    especificaciones = list(Especificacion.objects.all())

    por_resultado = Counter()
    kg_por_producto = defaultdict(float)
    kg_por_mandante = defaultdict(float)

    for lote in lotes:
        resultado = dominio.resultado_calidad_lote(
            lote, list(lote.analisis.all()), especificaciones
        )
        por_resultado[resultado.resultado] += 1

        # Un lote en proceso todavía no declaró kilos. Suma cero: no es que
        # haya producido nada, es que aún no se sabe.
        kilos = float(lote.kg_producidos or 0)
        kg_por_producto[lote.producto.nombre] += kilos
        kg_por_mandante[lote.producto.mandante.nombre] += kilos

    evaluados = por_resultado[dominio.CONFORME] + por_resultado[dominio.NO_CONFORME]

    return Response(
        {
            "lotes": len(lotes),
            "kg_producidos": float(
                Lote.objects.filter(id__in=[l.id for l in lotes]).aggregate(
                    total=Sum("kg_producidos")
                )["total"]
                or 0
            ),
            "calidad": {
                "conforme": por_resultado[dominio.CONFORME],
                "no_conforme": por_resultado[dominio.NO_CONFORME],
                "sin_analisis": por_resultado[dominio.SIN_ANALISIS],
                "sin_especificacion": por_resultado[dominio.SIN_ESPECIFICACION],
                # Cobertura: sobre cuántos lotes se pudo emitir un veredicto.
                "evaluados": evaluados,
                "cobertura": round(evaluados / len(lotes) * 100, 1) if lotes else None,
                "cumplimiento": (
                    round(por_resultado[dominio.CONFORME] / evaluados * 100, 1)
                    if evaluados
                    else None
                ),
            },
            "kg_por_producto": [
                {"nombre": nombre, "kg": kg}
                for nombre, kg in sorted(
                    kg_por_producto.items(), key=lambda par: -par[1]
                )
            ],
            "kg_por_mandante": [
                {"nombre": nombre, "kg": kg}
                for nombre, kg in sorted(
                    kg_por_mandante.items(), key=lambda par: -par[1]
                )
            ],
        }
    )


class ControlProcesoViewSet(viewsets.ModelViewSet):
    """
    Control de proceso de un equipo para un lote, con el PCC 1 de uperización.

    Es un registro de inocuidad además de uno de producción: sus lecturas
    deciden si el lote se puede liberar (`calidad.dominio.bloqueos_de_inocuidad`).
    """

    queryset = ControlProceso.objects.select_related("lote", "equipo").prefetch_related(
        "lecturas"
    )
    serializer_class = ControlProcesoSerializer
    permission_classes = [EscribeProduccion]

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        lote = parametros.get("lote")
        if lote:
            consulta = consulta.filter(lote_id=lote)

        equipo = parametros.get("equipo")
        if equipo:
            consulta = consulta.filter(equipo=equipo)

        fecha = parametros.get("fecha")
        if fecha:
            consulta = consulta.filter(fecha=fecha)

        return consulta


class ControlProcesoLecturaViewSet(viewsets.ModelViewSet):
    queryset = ControlProcesoLectura.objects.select_related("control")
    serializer_class = ControlProcesoLecturaSerializer
    permission_classes = [EscribeProduccion]

    def get_queryset(self):
        consulta = super().get_queryset()

        control = self.request.query_params.get("control")
        if control:
            consulta = consulta.filter(control_id=control)

        return consulta


@api_view(["GET"])
def catalogos_inocuidad(request):
    """
    Opciones de los formularios de control de proceso y monitoreo PPRO.

    Igual que en maestros: el modelo es la fuente de verdad y la pantalla no
    lleva su propia copia. Incluye los **parámetros del PCC 1** para que la
    captura los rotule igual que el dominio los evalúa — si la pantalla los
    renombrara, el control dejaría de encontrarlos y el PCC pasaría a no
    vigilar nada en silencio.
    """
    from inocuidad.models import MonitoreoPPRO, PproLectura
    from maestros.models import Equipo

    def opciones(choices):
        return [{"valor": v, "etiqueta": e} for v, e in choices]

    def equipos(*tipos):
        """
        Equipos del maestro como opciones. El `valor` es el **id**, que es lo
        que la referencia guarda.

        Qué máquinas admite cada formulario se decide aquí y no en la
        pantalla: un control de proceso se lleva en un evaporador o en una
        torre —no en una envasadora—, y si el filtro viviera en el cliente
        sería una segunda copia de esa regla, libre de discrepar.
        """
        consulta = Equipo.objects.filter(activo=True)

        if tipos:
            consulta = consulta.filter(tipo__in=tipos)

        return [
            {"valor": e.id, "etiqueta": e.nombre, "codigo": e.codigo}
            for e in consulta.order_by("orden", "nombre")
        ]

    return Response(
        {
            "equipo_control": equipos(Equipo.Tipo.EVAPORADOR, Equipo.Tipo.TORRE),
            # El PPRO se monitorea en cualquier máquina: presión de aire en las
            # torres, cuerpos extraños en las envasadoras, y el detector de
            # metales no cuelga de ninguna.
            "equipo_ppro": equipos(),
            "turno": opciones(Lote.Turno.choices),
            "tipo_ppro": opciones(MonitoreoPPRO.Tipo.choices),
            "resultado_ppro": opciones(PproLectura.Resultado.choices),
            "pcc1": {
                "temperatura": dominio.PCC1_TEMPERATURA,
                "caudal": dominio.PCC1_CAUDAL,
            },
        }
    )
