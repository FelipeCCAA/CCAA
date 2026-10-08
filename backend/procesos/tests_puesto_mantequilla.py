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

from .dominio import SITUACIONES_MANTEQUILLA, situacion_mantequilla
from .models import (
    CorridaMantequilla, EjecucionProceso, EntradaProceso, EtapaProceso, Proceso,
    RutaProducto, SalidaProceso,
)
from .servicios import (
    MENSAJE_INICIO_MANTEQUILLA_EN_PUESTO, MENSAJE_MANTEQUILLA_EN_PUESTO,
    MENSAJE_MOTIVO_CANCELACION, MENSAJE_SALIDA_DE_LOTE_ANULADO, RESOLVER_CALIDAD,
    RESOLVER_CIP, RESOLVER_PLANIFICACION, RESOLVER_SILOS, iniciar_mantequilla,
    kg_crema_disponible, motivos_crema_para_mantequilla, motivos_para_iniciar_mantequilla,
    motivos_tipados_para_iniciar_mantequilla, preparar_continuacion, transicionar_ejecucion,
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


class InicioGenericoCerradoMantequillaTests(BasePuestoMantequilla):
    def transicionar(self, ejecucion, estado, motivo=""):
        ejecucion.refresh_from_db()
        return self.cliente().post(
            f"/api/procesos/ejecuciones/{ejecucion.pk}/transicionar/",
            {"estado": estado, "version": ejecucion.version, "motivo": motivo},
            format="json",
        )

    def test_transicionar_no_inicia_una_preparada(self):
        corrida = self.preparada()

        respuesta = self.transicionar(corrida.ejecucion, "ejecucion")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(respuesta.data["message"], MENSAJE_INICIO_MANTEQUILLA_EN_PUESTO)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)

    def test_pausar_y_reanudar_siguen_por_transicionar(self):
        corrida = self.en_curso()

        pausa = self.transicionar(corrida.ejecucion, "pausada")
        reanudar = self.transicionar(corrida.ejecucion, "ejecucion")

        self.assertEqual(pausa.status_code, 200, pausa.data)
        self.assertEqual(reanudar.status_code, 200, reanudar.data)

    def test_la_bandeja_no_ofrece_iniciar_una_preparada(self):
        corrida = self.preparada()

        bandeja = self.cliente().get("/api/procesos/ejecuciones/operativas/")

        fila = next(item for item in bandeja.data if item["id"] == corrida.ejecucion_id)
        self.assertNotIn("ejecucion", fila["acciones_permitidas"])
        self.assertIn("cancelada", fila["acciones_permitidas"])

    def test_el_alta_directa_de_corridas_sigue_cerrada(self):
        self.assertEqual(
            self.cliente().post("/api/procesos/mantequillas/", {}, format="json").status_code, 405,
        )


class CancelarPreparacionMantequillaTests(BasePuestoMantequilla):
    def cancelar(self, corrida, motivo="Crema equivocada", usuario=None):
        return self.cliente(usuario).post(
            f"/api/procesos/mantequillas/{corrida.pk}/cancelar-preparacion/",
            {"motivo": motivo}, format="json",
        )

    def test_cancelar_anula_corrida_y_lote_y_suelta_la_mantequera(self):
        corrida = self.preparada(lote_suero=self.suero.pk)

        respuesta = self.cancelar(corrida)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data, {
            "ejecucion_id": corrida.ejecucion_id,
            "ejecucion_codigo": corrida.ejecucion.codigo,
            "estado": EjecucionProceso.Estado.CANCELADA,
        })
        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.ANULADA)
        self.assertEqual(corrida.motivo_anulacion, "Crema equivocada.")
        self.assertEqual(corrida.lote_mantequilla.estado, Lote.Estado.ANULADO)
        self.assertIn(
            "[ANULACIÓN] Preparación de Mantequilla cancelada: Crema equivocada.",
            corrida.lote_mantequilla.observacion,
        )
        # El suero conserva el rastro en la corrida anulada, pero queda libre:
        # la misma mantequera, la misma crema y el mismo suero se preparan otra vez.
        self.assertEqual(corrida.lote_suero, self.suero)
        self.preparada(lote_suero=self.suero.pk)

    def test_sin_motivo_no_cancela(self):
        corrida = self.preparada()

        respuesta = self.cancelar(corrida, motivo="  ")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(respuesta.data["message"], MENSAJE_MOTIVO_CANCELACION)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)

    def test_una_corrida_en_curso_no_se_cancela_desde_el_puesto(self):
        corrida = self.en_curso()

        respuesta = self.cancelar(corrida)

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("se cierra registrando su balance", respuesta.data["message"])

    def test_cancelar_desde_la_bandeja_generica_deja_lo_mismo(self):
        corrida = self.preparada()

        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
            usuario=self.condensador, motivo="Desde la bandeja",
        )

        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.ANULADA)
        self.assertEqual(corrida.motivo_anulacion, "Desde la bandeja.")
        self.assertEqual(corrida.lote_mantequilla.estado, Lote.Estado.ANULADO)
        self.preparada()

    def test_una_corrida_en_curso_cancelada_por_la_bandeja_queda_anulada(self):
        corrida = self.en_curso()

        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
            usuario=self.condensador, motivo="Falla eléctrica",
        )

        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.ANULADA)
        self.assertEqual(corrida.lote_mantequilla.estado, Lote.Estado.ANULADO)
        self.assertIn("Corrida de Mantequilla cancelada", corrida.lote_mantequilla.observacion)

    def test_anular_el_lote_por_el_patch_deja_lo_mismo_y_marca_una_vez(self):
        corrida = self.preparada()

        respuesta = self.cliente().patch(
            f"/api/produccion/lotes/{corrida.lote_mantequilla_id}/",
            {"estado": "anulado", "motivo_anulacion": "Lote abierto por error"}, format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.ANULADA)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.CANCELADA)
        self.assertEqual(corrida.lote_mantequilla.estado, Lote.Estado.ANULADO)
        self.assertEqual(corrida.lote_mantequilla.observacion.count("[ANULACIÓN]"), 1)

    def test_una_preparacion_heredada_en_borrador_se_cancela(self):
        corrida = self.corrida_heredada()

        respuesta = self.cancelar(corrida)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.ANULADA)
        self.assertEqual(corrida.lote_mantequilla.estado, Lote.Estado.ANULADO)


class PermisosMantequillaTests(BasePuestoMantequilla):
    """Secado escribe lotes, pero no opera la etapa Mantequilla: 403 en cada acción, nada escrito."""

    def test_secado_no_prepara_inicia_cancela_revisa_ni_cierra(self):
        preparada = self.preparada()
        en_curso = self.en_curso(equipo=self.otra_mantequera.pk)
        secado = self.cliente(self.secador)
        cierre = {"kg_mantequilla": "31", "kg_suero": "28", "kg_merma": "1"}

        self.assertEqual(self.preparar(usuario=self.secador).status_code, 403)
        for ruta, cuerpo in (
            (f"/api/procesos/mantequillas/{preparada.pk}/iniciar/", {}),
            (f"/api/procesos/mantequillas/{preparada.pk}/cancelar-preparacion/", {"motivo": "No"}),
            (f"/api/procesos/mantequillas/{en_curso.pk}/revisar-cierre/", cierre),
            (f"/api/procesos/mantequillas/{en_curso.pk}/cerrar/", cierre),
        ):
            with self.subTest(ruta=ruta):
                self.assertEqual(secado.post(ruta, cuerpo, format="json").status_code, 403)

        self.assertEqual(self.recargar(preparada.pk).ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
        self.assertEqual(self.recargar(en_curso.pk).estado, CorridaMantequilla.Estado.EN_PROCESO)
        self.assertEqual(Lote.objects.filter(producto=self.producto_mantequilla).count(), 2)


class SituacionesMantequillaTests(TestCase):
    def test_cada_corrida_tiene_una_situacion_y_gana_la_primera(self):
        casos = {
            ("borrador", "preparacion"): "preparada",
            ("en_proceso", "ejecucion"): "en_curso",
            ("en_proceso", "pausada"): "en_curso",
            ("pendiente_calidad", "pendiente_control"): "esperando_calidad",
            ("cerrada", "cerrada"): "terminada",
            ("anulada", "cancelada"): "anulada",
            # Heredada del modal anterior, o huérfana: no es «Preparada».
            ("borrador", "borrador"): "borrador",
            ("borrador", "cancelada"): "borrador",
        }
        for (estado, ejecucion), esperada in casos.items():
            with self.subTest(estado=estado, ejecucion=ejecucion):
                self.assertEqual(situacion_mantequilla(estado, ejecucion)[0], esperada)

    def test_el_catalogo_es_la_tabla(self):
        self.assertEqual(
            [fila[0] for fila in SITUACIONES_MANTEQUILLA],
            ["preparada", "en_curso", "esperando_calidad", "terminada", "anulada", "borrador"],
        )


class PuestoMantequillaTests(BasePuestoMantequilla):
    def puesto(self, usuario=None):
        respuesta = self.cliente(usuario).get("/api/procesos/mantequillas/puesto/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return respuesta.data

    def fila(self, datos, equipo):
        return next(item for item in datos["mantequeras"] if item["equipo_id"] == equipo.pk)

    def por_id(self, filas, *objetos):
        propios = {objeto.pk for objeto in objetos}
        return {fila["id"]: fila for fila in filas if fila["id"] in propios}

    def cerrar(self, corrida):
        # Sin lote de suero en la corrida: todo lo que no es mantequilla es merma.
        respuesta = self.cliente().post(
            f"/api/procesos/mantequillas/{corrida.pk}/cerrar/",
            {"kg_mantequilla": "59", "kg_merma": "1"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

    def test_una_mantequera_sin_ejecucion_esta_disponible(self):
        fila = self.fila(self.puesto(), self.mantequera)

        self.assertEqual(fila["estado"], "disponible")
        self.assertEqual(fila["tipo"], "mantequera")
        self.assertIsNone(fila["corrida"])
        self.assertEqual(fila["motivos_para_tomar"], [])
        self.assertIsNone(fila["en_calidad"])

    def test_una_preparada_trae_su_corrida_y_puede_iniciarse(self):
        corrida = self.preparada(lote_suero=self.suero.pk)

        fila = self.fila(self.puesto(), self.mantequera)

        self.assertEqual(fila["estado"], "preparada")
        self.assertEqual(fila["corrida"], {
            "id": corrida.pk, "estado": "borrador",
            "ejecucion_id": corrida.ejecucion_id, "ejecucion_codigo": corrida.ejecucion.codigo,
            "ejecucion_estado": "preparacion", "orden_codigo": "OP-PM-1",
            "producto": "Mantequilla PM", "lote_mantequilla": corrida.lote_mantequilla.codigo_lote,
            "lote_crema": "CR-PM-1", "kg_crema": "60.000", "lote_suero": "MAZ-PM-1",
            "iniciada_en": None,
        })
        self.assertEqual(fila["motivos_para_iniciar"], [])
        self.assertIsNone(fila["resolver_en"])

    def test_los_motivos_dicen_donde_se_resuelven(self):
        crema, _tk = self.crema_en_tk("CR-PM-FIRMA", segunda_firma=False)
        self.preparada(lote_crema=crema.pk, kg_crema="200")
        self.preparada(equipo=self.otra_mantequera.pk)
        self.cip(self.otra_mantequera)

        datos = self.puesto()

        sin_firma = self.fila(datos, self.mantequera)
        self.assertIn("firma de realización y visualización", sin_firma["motivos_para_iniciar"][0])
        self.assertEqual(sin_firma["resolver_en"], "/silos")
        en_cip = self.fila(datos, self.otra_mantequera)
        self.assertIn("CIP", en_cip["motivos_para_iniciar"][0])
        self.assertEqual(en_cip["resolver_en"], "/calidad/inocuidad")

    def test_una_crema_sin_liberar_y_una_orden_cancelada_dicen_donde(self):
        self.preparada()
        LiberacionProceso.objects.filter(salida__lote=self.crema).update(
            estado=LiberacionProceso.Estado.PENDIENTE,
        )
        self.assertEqual(self.fila(self.puesto(), self.mantequera)["resolver_en"], "/calidad")

        OrdenProduccion.objects.filter(pk=self.orden.pk).update(
            estado=OrdenProduccion.Estado.CANCELADA,
        )
        fila = self.fila(self.puesto(), self.mantequera)
        # La orden se comprueba antes que la crema: es el primer motivo.
        self.assertIn("OP-PM-1", fila["motivos_para_iniciar"][0])
        self.assertEqual(fila["resolver_en"], "/planificacion")

    def test_una_mantequera_en_cip_no_se_toma(self):
        self.cip(self.mantequera)

        fila = self.fila(self.puesto(), self.mantequera)

        self.assertEqual(fila["estado"], "disponible")
        self.assertIn("CIP", fila["motivos_para_tomar"][0])
        self.assertEqual(fila["resolver_en"], "/calidad/inocuidad")

    def test_un_aseo_observado_es_aviso_no_motivo(self):
        self.preparada()
        self.cip(self.mantequera, estado=CicloCIP.Estado.OBSERVADO, horas=3)

        fila = self.fila(self.puesto(), self.mantequera)

        self.assertEqual(fila["motivos_para_iniciar"], [])
        self.assertTrue(fila["avisos"])

    def test_ejecucion_en_curso_pausada_o_bloqueada_esta_en_curso(self):
        # «En curso manda sobre preparada» no se puede sembrar: la base impide
        # dos ocupaciones del mismo equipo (Desviación 11).
        corrida = self.en_curso()
        for estado in ("ejecucion", "pausada", "bloqueada"):
            EjecucionProceso.objects.filter(pk=corrida.ejecucion_id).update(estado=estado)
            with self.subTest(estado=estado):
                fila = self.fila(self.puesto(), self.mantequera)
                self.assertEqual(fila["estado"], "en_curso")
                self.assertEqual(fila["corrida"]["ejecucion_estado"], estado)
                self.assertEqual(fila["motivos_para_iniciar"], [])

    def test_un_huerfano_con_ejecucion_terminada_no_ocupa(self):
        corrida = self.preparada()
        EjecucionProceso.objects.filter(pk=corrida.ejecucion_id).update(
            estado=EjecucionProceso.Estado.CANCELADA,
        )

        datos = self.puesto()

        self.assertEqual(self.fila(datos, self.mantequera)["estado"], "disponible")
        self.assertEqual(self.por_id(datos["corridas_de_hoy"], corrida), {})

    def test_en_calidad_la_mantequera_queda_libre_y_lo_informa(self):
        corrida = self.en_curso()
        self.cerrar(corrida)

        fila = self.fila(self.puesto(), self.mantequera)

        self.assertEqual(fila["estado"], "disponible")
        self.assertEqual(fila["en_calidad"], {
            "id": corrida.pk, "ejecucion_codigo": corrida.ejecucion.codigo,
            "lote_mantequilla": corrida.lote_mantequilla.codigo_lote,
        })

    def test_una_linea_ocupada_por_mantequilla_aparece_y_una_ajena_no(self):
        linea = Equipo.objects.create(
            sucursal=self.planta, codigo="linea-pm-vieja", nombre="Línea vieja", tipo=Equipo.Tipo.LINEA,
        )
        ajena = Equipo.objects.create(
            sucursal=self.planta, codigo="linea-pm-ajena", nombre="Línea ajena", tipo=Equipo.Tipo.LINEA,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-MANT-VIEJA", etapa=self.etapa, sucursal=self.planta, equipo=linea,
            responsable=self.condensador, estado=EjecucionProceso.Estado.PREPARACION,
        )

        datos = self.puesto()

        fila = self.fila(datos, linea)
        self.assertEqual(fila["tipo"], "linea")
        self.assertEqual(fila["estado"], "preparada")
        self.assertIn(f"{ejecucion.codigo} no tiene corrida de mantequilla", fila["motivos_para_iniciar"][0])
        self.assertNotIn(ajena.pk, [item["equipo_id"] for item in datos["mantequeras"]])

    def test_cremas_restan_las_otras_preparadas_y_no_ofrecen_la_agotada(self):
        self.preparada(kg_crema="600")
        crema = self.por_id(self.puesto()["cremas"], self.crema)[self.crema.pk]
        self.assertEqual(crema["disponible_kg"], "400.000")
        self.assertIsNone(crema["tk"])

        self.preparada(equipo=self.otra_mantequera.pk, kg_crema="400")

        self.assertEqual(self.por_id(self.puesto()["cremas"], self.crema), {})

    def test_cremas_traen_su_tk(self):
        crema, tk = self.crema_en_tk("CR-PM-TK")

        fila = self.por_id(self.puesto()["cremas"], crema)[crema.pk]

        self.assertEqual(fila["tk"], tk.codigo)

    def test_cremas_pendientes_de_calidad_explican_por_que_no_aparecen(self):
        pendiente = self.lote_crema("CR-PM-PEND", liberacion=LiberacionProceso.Estado.PENDIENTE)
        sin_decision = self.lote_crema("CR-PM-SIN", liberacion=None)

        datos = self.puesto()

        self.assertEqual(self.por_id(datos["cremas"], pendiente, sin_decision), {})
        explicadas = self.por_id(datos["cremas_pendientes_calidad"], pendiente, sin_decision)
        self.assertEqual(explicadas[pendiente.pk]["estado_calidad"], "pendiente")
        self.assertEqual(explicadas[sin_decision.pk]["estado_calidad"], "trazabilidad_incompleta")
        self.assertEqual(explicadas[pendiente.pk]["etapa_origen"], "Descremación")

    def test_sueros_ofrecen_de_nuevo_el_de_una_corrida_anulada(self):
        corrida = self.preparada(lote_suero=self.suero.pk)
        self.assertEqual(self.por_id(self.puesto()["sueros"], self.suero), {})

        self.cliente().post(
            f"/api/procesos/mantequillas/{corrida.pk}/cancelar-preparacion/",
            {"motivo": "Suero equivocado"}, format="json",
        )

        self.assertIn(self.suero.pk, self.por_id(self.puesto()["sueros"], self.suero))

    def test_ordenes_programadas_o_en_proceso(self):
        cancelada = OrdenProduccion.objects.create(
            sucursal=self.planta, codigo="OP-PM-CAN", producto=self.producto_mantequilla,
            cantidad_planificada=10, unidad="kg", estado=OrdenProduccion.Estado.CANCELADA,
        )

        ordenes = self.por_id(self.puesto()["ordenes"], self.orden, cancelada)

        self.assertEqual(list(ordenes), [self.orden.pk])

    def test_corridas_de_hoy_sin_huerfanos_y_con_su_situacion(self):
        en_curso = self.en_curso()
        huerfana = self.preparada(equipo=self.otra_mantequera.pk)
        EjecucionProceso.objects.filter(pk=huerfana.ejecucion_id).update(
            estado=EjecucionProceso.Estado.CANCELADA,
        )

        propias = self.por_id(self.puesto()["corridas_de_hoy"], en_curso, huerfana)

        self.assertEqual(list(propias), [en_curso.pk])
        self.assertEqual(propias[en_curso.pk]["situacion"], "en_curso")
        self.assertEqual(propias[en_curso.pk]["situacion_etiqueta"], "En la mantequera")
        self.assertEqual(propias[en_curso.pk]["lote_crema"], "CR-PM-1")

    def test_calidad_lee_el_puesto(self):
        datos = self.puesto(self.calidad)

        self.assertIn("mantequeras", datos)
        self.assertEqual(
            [estado["valor"] for estado in datos["estados"]],
            [fila[0] for fila in SITUACIONES_MANTEQUILLA],
        )

    def test_el_historial_filtra_en_el_servidor(self):
        primera = self.en_curso()
        segunda = self.preparada(equipo=self.otra_mantequera.pk)
        url = "/api/procesos/mantequillas/"

        por_lote = self.cliente().get(url, {"q": segunda.lote_mantequilla.codigo_lote})
        en_curso = self.cliente().get(url, {"estado": "en_curso"})
        preparadas = self.cliente().get(url, {"estado": "preparada"})
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        futuras = self.cliente().get(url, {"desde": manana})

        self.assertEqual(list(self.por_id(por_lote.data["results"], primera, segunda)), [segunda.pk])
        self.assertEqual(list(self.por_id(en_curso.data["results"], primera, segunda)), [primera.pk])
        self.assertEqual(list(self.por_id(preparadas.data["results"], primera, segunda)), [segunda.pk])
        self.assertEqual(self.por_id(futuras.data["results"], primera, segunda), {})
        fila = self.por_id(en_curso.data["results"], primera)[primera.pk]
        self.assertEqual(fila["ejecucion_estado"], "ejecucion")
        self.assertEqual(fila["situacion_etiqueta"], "En la mantequera")


class CremasDelPuestoMantequillaTests(BasePuestoMantequilla):
    """
    La lista `cremas` ofrece exactamente lo que «Preparar» acepta: la misma
    liberación (la de la salida del TK si la crema está en uno) y el mismo
    disponible (`kg_crema_disponible`), calculados en la consulta y no por fila.
    """

    def puesto(self):
        respuesta = self.cliente().get("/api/procesos/mantequillas/puesto/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return respuesta.data

    def crema_tk_pendiente_y_otra_salida_liberada(self, codigo):
        crema, tk = self.crema_en_tk(codigo)
        LiberacionProceso.objects.filter(salida__lote=crema, salida__silo=tk).update(
            estado=LiberacionProceso.Estado.PENDIENTE,
        )
        otra = SalidaProceso.objects.create(
            ejecucion=SalidaProceso.objects.get(lote=crema).ejecucion, lote=crema,
            producto=self.producto_crema, cantidad=Decimal("1000"), unidad="kg",
        )
        LiberacionProceso.objects.create(salida=otra, estado=LiberacionProceso.Estado.LIBERADO)
        return crema

    def test_una_crema_cuyo_tk_espera_calidad_no_se_ofrece_aunque_otra_salida_este_liberada(self):
        crema = self.crema_tk_pendiente_y_otra_salida_liberada("CR-PM-TKPEND")

        datos = self.puesto()

        self.assertEqual([fila["id"] for fila in datos["cremas"] if fila["id"] == crema.pk], [])
        explicada = [fila for fila in datos["cremas_pendientes_calidad"] if fila["id"] == crema.pk]
        self.assertEqual([fila["estado_calidad"] for fila in explicada], ["pendiente"])

    def test_la_lista_es_lo_que_acepta_preparar(self):
        agotada = self.lote_crema("CR-PM-AGOT")
        EntradaProceso.objects.create(
            ejecucion=SalidaProceso.objects.get(lote=agotada).ejecucion, lote=agotada,
            cantidad=Decimal("1000"), unidad="kg",
        )
        anulada = self.lote_crema("CR-PM-ANUL")
        Lote.objects.filter(pk=anulada.pk).update(estado=Lote.Estado.ANULADO)
        en_proceso = self.lote_crema("CR-PM-PROC")
        Lote.objects.filter(pk=en_proceso.pk).update(estado=Lote.Estado.EN_PROCESO)
        en_tk, _tk = self.crema_en_tk("CR-PM-TKOK")
        lotes = [
            self.crema, agotada, anulada, en_proceso, en_tk,
            self.crema_tk_pendiente_y_otra_salida_liberada("CR-PM-TKPEND"),
            self.lote_crema("CR-PM-PEND", liberacion=LiberacionProceso.Estado.PENDIENTE),
            self.lote_crema("CR-PM-RECH", liberacion=LiberacionProceso.Estado.RECHAZADO),
            self.lote_crema("CR-PM-SIN", liberacion=None),
        ]
        self.preparada(kg_crema="300")

        ofrecidas = {fila["id"]: fila for fila in self.puesto()["cremas"]}

        for lote in lotes:
            lote.refresh_from_db()
            with self.subTest(lote=lote.codigo_lote):
                acepta = motivos_crema_para_mantequilla(lote, Decimal("0.001")) == []
                self.assertEqual(lote.pk in ofrecidas, acepta)
                if acepta:
                    self.assertEqual(
                        ofrecidas[lote.pk]["disponible_kg"], str(kg_crema_disponible(lote)),
                    )
        self.assertEqual(ofrecidas[self.crema.pk]["disponible_kg"], "700.000")
        self.assertEqual(ofrecidas[en_tk.pk]["tk"], "TK-CR-PM-TKOK")

    def test_las_consultas_no_crecen_con_las_cremas_ni_los_sueros(self):
        def cremas(desde, hasta):
            for numero in range(desde, hasta):
                self.lote_crema(f"CR-PM-N{numero}")
                self.crema_en_tk(f"CR-PM-T{numero}")
                self.lote_crema(f"CR-PM-P{numero}", liberacion=LiberacionProceso.Estado.PENDIENTE)
                Lote.objects.create(
                    sucursal=self.planta, codigo_lote=f"MAZ-PM-N{numero}",
                    producto=self.producto_suero, fecha=date(2026, 10, 8),
                )

        cremas(1, 2)
        with CaptureQueriesContext(connection) as una:
            self.puesto()
        cremas(2, 7)
        with CaptureQueriesContext(connection) as seis:
            datos = self.puesto()

        self.assertIn("CR-PM-N6", [fila["codigo"] for fila in datos["cremas"]])
        self.assertEqual(len(seis.captured_queries), len(una.captured_queries))
