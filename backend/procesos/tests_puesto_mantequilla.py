from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso
from inventario.models import CicloCIP
from maestros.models import Equipo, Mandante, Producto, Silo
from produccion.models import Lote, OrdenProduccion
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import (
    CorridaMantequilla, EjecucionProceso, EntradaProceso, EtapaProceso, Proceso,
    RutaProducto, SalidaProceso,
)
from .servicios import (
    MENSAJE_MANTEQUILLA_EN_PUESTO, MENSAJE_SALIDA_DE_LOTE_ANULADO, RESOLVER_CALIDAD,
    RESOLVER_CIP, RESOLVER_PLANIFICACION, RESOLVER_SILOS, iniciar_mantequilla,
    kg_crema_disponible, motivos_para_iniciar_mantequilla,
    motivos_tipados_para_iniciar_mantequilla, preparar_continuacion,
)


class BasePuestoMantequilla(TestCase):
    """
    Una crema liberada de 1.000 kg, una OP programada, un lote de mazada libre
    y dos mantequeras libres: lo que el puesto ve al empezar el turno.

    Las migraciones siembran equipos en la base de pruebas (la
    `linea_mantequilla`, ya mantequera) y `filtrar_por_scope` ya no aísla por
    empresa: las aserciones se hacen sobre los objetos de esta fixture, nunca
    sobre listas completas.
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(rut="PMAN-1", nombre="Empresa puesto mantequilla")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="PMAN", nombre="Planta puesto mantequilla"
        )
        self.condensador = self._usuario("condensador-pman", PerfilUsuario.Area.CONDENSACION)
        self.secador = self._usuario("secador-pman", PerfilUsuario.Area.SECADO)
        self.calidad = self._usuario("calidad-pman", PerfilUsuario.Area.CALIDAD, Rol.CALIDAD)
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Mandante puesto mantequilla", codigo_cliente="pmn"
        )
        self.producto_crema = Producto.objects.create(
            mandante=mandante, nombre="Crema PM", familia=Producto.Familia.CREMA,
            naturaleza=Producto.Naturaleza.INTERMEDIO, unidad_base=Producto.Unidad.KG,
        )
        self.producto_mantequilla = Producto.objects.create(
            mandante=mandante, nombre="Mantequilla PM", categoria=Producto.Categoria.MANTEQUILLA,
            naturaleza=Producto.Naturaleza.TERMINADO, unidad_base=Producto.Unidad.KG,
        )
        self.producto_suero = Producto.objects.create(
            mandante=mandante, nombre="Mazada PM", categoria=Producto.Categoria.SUERO,
            naturaleza=Producto.Naturaleza.INTERMEDIO, unidad_base=Producto.Unidad.KG,
        )
        proceso = Proceso.objects.create(codigo="mantequilla-puesto", nombre="Mantequilla del puesto")
        self.etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="batir-pm", nombre="Batido",
            tipo=EtapaProceso.Tipo.MANTEQUILLA, orden=1, requiere_calidad=True,
        )
        RutaProducto.objects.create(
            sucursal=self.planta, producto=self.producto_mantequilla, proceso=proceso,
            destino_final=RutaProducto.DestinoFinal.ENVASADO,
        )
        origen = Proceso.objects.create(codigo="descremar-pm", nombre="Origen de la crema PM")
        self.etapa_origen = EtapaProceso.objects.create(
            proceso=origen, codigo="descremar-pm", nombre="Descremación",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=1,
        )
        self.mantequera = self._mantequera("mant-pm1", "Mantequera PM 1", "P1")
        self.otra_mantequera = self._mantequera("mant-pm2", "Mantequera PM 2", "P2")
        self.orden = OrdenProduccion.objects.create(
            sucursal=self.planta, codigo="OP-PM-1", producto=self.producto_mantequilla,
            cantidad_planificada=400, unidad="kg", estado=OrdenProduccion.Estado.PROGRAMADA,
        )
        self.crema = self.lote_crema("CR-PM-1")
        self.suero = Lote.objects.create(
            sucursal=self.planta, codigo_lote="MAZ-PM-1", producto=self.producto_suero,
            fecha=date(2026, 10, 8),
        )
        self._correlativo = 0

    def _usuario(self, nombre, area, rol=Rol.PRODUCCION):
        usuario = User.objects.create_user(nombre)
        PerfilUsuario.objects.create(
            usuario=usuario, empresa=self.empresa, sucursal=self.planta, area=area, rol=rol,
        )
        return usuario

    def _mantequera(self, codigo, nombre, sigla):
        return Equipo.objects.create(
            sucursal=self.planta, codigo=codigo, nombre=nombre, sigla=sigla,
            tipo=Equipo.Tipo.MANTEQUERA,
        )

    def lote_crema(self, codigo, *, kg="1000", liberacion=LiberacionProceso.Estado.LIBERADO,
                   silo=None, analisis=None):
        """
        Un lote de crema producido por Descremación, con su salida. Con
        `liberacion=None` la salida no tiene decisión de Calidad
        («trazabilidad incompleta»).
        """
        lote = Lote.objects.create(
            sucursal=self.planta, codigo_lote=codigo, producto=self.producto_crema,
            fecha=date(2026, 10, 8), estado=Lote.Estado.PRODUCIDO, kg_producidos=Decimal(kg),
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo=f"EJ-ORIGEN-{codigo}", etapa=self.etapa_origen, sucursal=self.planta,
            estado=EjecucionProceso.Estado.CERRADA,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=lote, producto=self.producto_crema, silo=silo,
            naturaleza=SalidaProceso.Naturaleza.COPRODUCTO,
            clasificacion=SalidaProceso.Clasificacion.INTERMEDIO,
            destino=SalidaProceso.Destino.SIGUIENTE_PROCESO,
            cantidad=Decimal(kg), unidad="L" if silo else "kg",
        )
        if liberacion is not None:
            LiberacionProceso.objects.create(salida=salida, analisis_silo=analisis, estado=liberacion)
        return lote

    def crema_en_tk(self, codigo, *, kg="1000", segunda_firma=True, densidad="1000"):
        """Una crema liberada que está en un TK con su análisis (densidad incluida)."""
        tk = Silo.objects.create(
            sucursal=self.planta, codigo=f"TK-{codigo}", tipo=Silo.Tipo.TK_CREMA, capacidad_l=5000,
        )
        MovimientoSilo.objects.create(
            silo=tk, tipo=MovimientoSilo.Tipo.INGRESO, litros=Decimal(kg),
            fecha_hora=timezone.now() - timedelta(hours=2),
            origen_tipo=MovimientoSilo.OrigenTipo.DESCREMACION,
        )
        analisis = AnalisisSilo.objects.create(
            silo=tk, tomado_en=timezone.now() - timedelta(hours=1),
            grasa=Decimal("40"), sng=Decimal("5"), densidad=Decimal(densidad),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO, analista=self.condensador,
            visualizado_por=self.calidad if segunda_firma else None,
        )
        return self.lote_crema(codigo, kg=kg, silo=tk, analisis=analisis), tk

    def corrida_heredada(self, codigo="EJ-MANT-HEREDADA"):
        """Una corrida del modal anterior: ejecución en `borrador`, sin la mantequera tomada."""
        ejecucion = EjecucionProceso.objects.create(
            codigo=codigo, etapa=self.etapa, sucursal=self.planta,
            equipo=self.mantequera, responsable=self.condensador,
        )
        salida = Lote.objects.create(
            sucursal=self.planta, codigo_lote=f"LOTE-{codigo}", producto=self.producto_mantequilla,
            orden=self.orden, fecha=date(2026, 10, 8), estado=Lote.Estado.EN_PROCESO,
            ejecucion=ejecucion,
        )
        return CorridaMantequilla.objects.create(
            ejecucion=ejecucion, orden=self.orden, lote_crema=self.crema,
            lote_mantequilla=salida, kg_crema=Decimal("60"),
        )

    def cip(self, equipo, estado=CicloCIP.Estado.EN_CURSO, horas=1):
        return CicloCIP.objects.create(
            sucursal=self.planta, area=PerfilUsuario.Area.CONDENSACION, equipo=equipo,
            inicio=timezone.now() - timedelta(hours=horas), estado=estado,
        )

    def cliente(self, usuario=None):
        cliente = APIClient()
        cliente.force_authenticate(usuario or self.condensador)
        return cliente

    def datos_preparar(self, **cambios):
        self._correlativo += 1
        datos = {
            "orden": self.orden.pk, "lote_crema": self.crema.pk, "equipo": self.mantequera.pk,
            "codigo_lote_mantequilla": f"MANT-PM-{self._correlativo}", "kg_crema": "60",
        }
        datos.update(cambios)
        return datos

    def preparar(self, usuario=None, **cambios):
        return self.cliente(usuario).post(
            "/api/procesos/mantequillas/crear-guiada/", self.datos_preparar(**cambios), format="json",
        )

    def preparada(self, **cambios):
        respuesta = self.preparar(**cambios)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return self.recargar(respuesta.data["id"])

    def en_curso(self, **cambios):
        corrida = self.preparada(**cambios)
        iniciar_mantequilla(corrida_id=corrida.pk, usuario=self.condensador)
        return self.recargar(corrida.pk)

    def recargar(self, corrida_id):
        return CorridaMantequilla.objects.select_related(
            "ejecucion__etapa", "ejecucion__equipo", "orden", "lote_crema__producto",
            "lote_mantequilla", "lote_suero",
        ).get(pk=corrida_id)


class PrepararMantequillaTests(BasePuestoMantequilla):
    def test_preparar_crea_lote_ejecucion_preparada_y_corrida_sin_mover_crema(self):
        corrida = self.preparada(lote_suero=self.suero.pk)

        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.BORRADOR)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
        self.assertEqual(corrida.ejecucion.equipo, self.mantequera)
        self.assertEqual(corrida.ejecucion.codigo, f"EJ-MANT-{corrida.lote_mantequilla_id}")
        self.assertEqual(corrida.lote_mantequilla.estado, Lote.Estado.EN_PROCESO)
        self.assertEqual(corrida.lote_suero, self.suero)
        # Hasta iniciar, la crema no entró a la mantequera.
        self.assertFalse(EntradaProceso.objects.filter(lote=self.crema).exists())

    def test_una_mantequera_ocupada_no_se_prepara_y_no_deja_nada(self):
        self.preparada()

        respuesta = self.preparar()

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("ocupad", str(respuesta.data))
        self.assertEqual(Lote.objects.filter(producto=self.producto_mantequilla).count(), 1)
        self.assertEqual(EjecucionProceso.objects.filter(equipo=self.mantequera).count(), 1)

    def test_una_mantequera_en_cip_no_se_prepara(self):
        self.cip(self.mantequera)

        respuesta = self.preparar()

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("CIP", str(respuesta.data))
        self.assertFalse(Lote.objects.filter(producto=self.producto_mantequilla).exists())

    def test_una_linea_no_es_mantequera(self):
        linea = Equipo.objects.create(
            sucursal=self.planta, codigo="linea-pm", nombre="Línea PM", tipo=Equipo.Tipo.LINEA,
        )

        respuesta = self.preparar(equipo=linea.pk)

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("no es una mantequera", str(respuesta.data))

    def test_no_prepara_mas_crema_que_la_disponible_contando_otra_preparada(self):
        self.preparada(kg_crema="600")

        respuesta = self.preparar(equipo=self.otra_mantequera.pk, kg_crema="500")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("400.000 kg disponibles", str(respuesta.data))
        self.assertFalse(EjecucionProceso.objects.filter(equipo=self.otra_mantequera).exists())

    def test_una_crema_pendiente_de_calidad_no_se_prepara(self):
        pendiente = self.lote_crema("CR-PM-PEND", liberacion=LiberacionProceso.Estado.PENDIENTE)

        respuesta = self.preparar(lote_crema=pendiente.pk)

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("todavía no está liberado por Calidad", str(respuesta.data))

    def test_las_condiciones_del_tk_no_frenan_la_preparacion(self):
        crema, _tk = self.crema_en_tk("CR-PM-SINFIRMA", segunda_firma=False)

        self.preparada(lote_crema=crema.pk, kg_crema="200")

    def test_un_suero_tomado_por_una_corrida_viva_no_se_prepara(self):
        self.preparada(lote_suero=self.suero.pk)

        respuesta = self.preparar(equipo=self.otra_mantequera.pk, lote_suero=self.suero.pk)

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("no puede recibir el suero", str(respuesta.data))

    def test_preparar_continuacion_no_crea_una_mantequilla_sin_corrida(self):
        salida = SalidaProceso.objects.get(lote=self.crema)
        antes = EjecucionProceso.objects.count()

        with self.assertRaisesMessage(ValidationError, MENSAJE_MANTEQUILLA_EN_PUESTO):
            preparar_continuacion(
                salida_id=salida.pk, etapa_id=self.etapa.pk, equipo_id=self.mantequera.pk,
                cantidad="10", usuario=self.condensador,
            )

        self.assertEqual(EjecucionProceso.objects.count(), antes)

    def test_secado_no_prepara(self):
        respuesta = self.preparar(usuario=self.secador)

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Lote.objects.filter(producto=self.producto_mantequilla).exists())


class IniciarMantequillaTests(BasePuestoMantequilla):
    def iniciar(self, corrida, usuario=None):
        return self.cliente(usuario).post(f"/api/procesos/mantequillas/{corrida.pk}/iniciar/")

    def test_sin_motivos_inicia_con_una_entrada(self):
        corrida = self.preparada()
        self.assertEqual(motivos_para_iniciar_mantequilla(corrida), [])

        respuesta = self.iniciar(corrida)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.EN_PROCESO)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertEqual(corrida.ejecucion.entradas.count(), 1)
        self.assertEqual(corrida.orden.estado, OrdenProduccion.Estado.EN_PROCESO)

    def test_la_crema_del_tk_sale_al_iniciar_y_no_al_preparar(self):
        crema, tk = self.crema_en_tk("CR-PM-TK")
        corrida = self.preparada(lote_crema=crema.pk, kg_crema="200")
        salidas = MovimientoSilo.objects.filter(silo=tk, tipo=MovimientoSilo.Tipo.SALIDA)
        self.assertFalse(salidas.exists())

        iniciar_mantequilla(corrida_id=corrida.pk, usuario=self.condensador)

        self.assertEqual(salidas.get().litros, Decimal("200.00"))

    def test_un_tk_sin_segunda_firma_se_resuelve_en_silos(self):
        crema, _tk = self.crema_en_tk("CR-PM-FIRMA", segunda_firma=False)
        corrida = self.preparada(lote_crema=crema.pk, kg_crema="200")

        motivo, resolver_en = motivos_tipados_para_iniciar_mantequilla(corrida)[0]

        self.assertIn("firma de realización y visualización", motivo)
        self.assertEqual(resolver_en, RESOLVER_SILOS)
        respuesta = self.iniciar(corrida)
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn(motivo, str(respuesta.data))
        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
        self.assertFalse(corrida.ejecucion.entradas.exists())

    def test_una_mantequera_en_cip_se_resuelve_en_inocuidad(self):
        corrida = self.preparada()
        self.cip(self.mantequera)

        motivo, resolver_en = motivos_tipados_para_iniciar_mantequilla(corrida)[0]

        self.assertIn("CIP", motivo)
        self.assertEqual(resolver_en, RESOLVER_CIP)

    def test_una_orden_cancelada_se_resuelve_en_planificacion(self):
        corrida = self.preparada()
        OrdenProduccion.objects.filter(pk=self.orden.pk).update(
            estado=OrdenProduccion.Estado.CANCELADA,
        )

        motivo, resolver_en = motivos_tipados_para_iniciar_mantequilla(self.recargar(corrida.pk))[0]

        self.assertIn("OP-PM-1", motivo)
        self.assertEqual(resolver_en, RESOLVER_PLANIFICACION)

    def test_una_crema_que_perdio_la_liberacion_se_resuelve_en_calidad(self):
        corrida = self.preparada()
        LiberacionProceso.objects.filter(salida__lote=self.crema).update(
            estado=LiberacionProceso.Estado.PENDIENTE,
        )

        motivo, resolver_en = motivos_tipados_para_iniciar_mantequilla(corrida)[0]

        self.assertIn("todavía no está liberado por Calidad", motivo)
        self.assertEqual(resolver_en, RESOLVER_CALIDAD)

    def test_un_lote_de_crema_anulado_no_se_inicia(self):
        corrida = self.preparada()
        Lote.objects.filter(pk=self.crema.pk).update(estado=Lote.Estado.ANULADO)

        self.assertEqual(
            motivos_tipados_para_iniciar_mantequilla(self.recargar(corrida.pk)),
            [(MENSAJE_SALIDA_DE_LOTE_ANULADO.format(codigo=self.crema.codigo_lote), None)],
        )

    def test_los_motivos_son_lo_que_rechaza_iniciar(self):
        corrida = self.preparada()
        OrdenProduccion.objects.filter(pk=self.orden.pk).update(
            estado=OrdenProduccion.Estado.CANCELADA,
        )
        motivos = motivos_para_iniciar_mantequilla(self.recargar(corrida.pk))
        self.assertTrue(motivos)

        with self.assertRaises(ValidationError) as error:
            iniciar_mantequilla(corrida_id=corrida.pk, usuario=self.condensador)

        self.assertEqual(error.exception.messages[0], motivos[0])

    def test_un_aseo_observado_avisa_y_queda_en_el_evento(self):
        corrida = self.preparada()
        self.cip(self.mantequera, estado=CicloCIP.Estado.OBSERVADO, horas=3)
        self.assertEqual(motivos_para_iniciar_mantequilla(corrida), [])

        iniciar_mantequilla(corrida_id=corrida.pk, usuario=self.condensador)

        evento = corrida.ejecucion.eventos.get(estado_nuevo=EjecucionProceso.Estado.EJECUCION)
        self.assertIn("Advertencia no bloqueante de aseo", evento.motivo)

    def test_una_corrida_heredada_en_borrador_no_esta_preparada(self):
        corrida = self.corrida_heredada()

        motivos = motivos_para_iniciar_mantequilla(corrida)

        self.assertEqual(motivos, ["EJ-MANT-HEREDADA no está preparada: está borrador."])

    def test_una_corrida_iniciada_no_vuelve_a_iniciar(self):
        corrida = self.en_curso()

        self.assertEqual(self.iniciar(corrida).status_code, 400)

    def test_secado_no_inicia(self):
        corrida = self.preparada()

        self.assertEqual(self.iniciar(corrida, self.secador).status_code, 403)
        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)


class CremaDeTkYDisponibleTests(BasePuestoMantequilla):
    def test_una_crema_cuyo_tk_no_esta_liberado_no_se_prepara(self):
        # Otra salida del lote está liberada, pero la del TK —de la que se lee
        # la densidad y sale la crema— todavía espera a Calidad.
        crema, tk = self.crema_en_tk("CR-PM-TKPEND")
        LiberacionProceso.objects.filter(salida__lote=crema, salida__silo=tk).update(
            estado=LiberacionProceso.Estado.PENDIENTE,
        )
        SalidaProceso.objects.create(
            ejecucion=SalidaProceso.objects.get(lote=crema).ejecucion, lote=crema,
            producto=self.producto_crema, cantidad=Decimal("1000"), unidad="kg",
        )
        LiberacionProceso.objects.create(
            salida=SalidaProceso.objects.get(lote=crema, silo__isnull=True),
            estado=LiberacionProceso.Estado.LIBERADO,
        )

        respuesta = self.preparar(lote_crema=crema.pk, kg_crema="200")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("todavía no está liberado por Calidad", str(respuesta.data))

    def test_una_corrida_heredada_en_borrador_no_compromete_crema(self):
        self.corrida_heredada()

        self.assertEqual(kg_crema_disponible(self.crema), Decimal("1000"))

    def test_una_corrida_preparada_compromete_su_crema(self):
        self.preparada(kg_crema="60")

        self.assertEqual(kg_crema_disponible(self.crema), Decimal("940"))


class OrdenDeCandadosMantequillaTests(BasePuestoMantequilla):
    """
    Iniciar toma la orden antes que la crema, y la crema antes que la
    mantequera: el orden de «Preparar» (`crear_mantequilla_guiada`). Con la
    orden al final, un inicio y una preparación sobre la misma orden y la
    misma crema podían esperarse el uno al otro hasta el deadlock.
    """

    def test_iniciar_bloquea_orden_luego_crema_luego_mantequera(self):
        corrida = self.preparada()
        tablas = {
            "orden": OrdenProduccion._meta.db_table,
            "lote": Lote._meta.db_table,
            "equipo": Equipo._meta.db_table,
        }

        with CaptureQueriesContext(connection) as consultas:
            iniciar_mantequilla(corrida_id=corrida.pk, usuario=self.condensador)

        candados = [
            consulta["sql"] for consulta in consultas.captured_queries
            if "FOR UPDATE" in consulta["sql"]
        ]

        def primero(tabla):
            return next(
                (i for i, sql in enumerate(candados) if f'FROM "{tabla}"' in sql), None,
            )

        orden, lote, equipo = (primero(tablas[clave]) for clave in ("orden", "lote", "equipo"))
        # `transicionar_ejecucion` toma la mantequera (`adquirir_equipo`).
        self.assertIsNotNone(orden)
        self.assertIsNotNone(lote)
        self.assertIsNotNone(equipo)
        self.assertLess(orden, lote)
        self.assertLess(lote, equipo)
