from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso, RegistroEquipo
from inventario.models import CicloCIP
from maestros.models import DocumentoLiberacion, Equipo, Mandante, Producto, Silo
from produccion.models import Lote, OrdenProduccion
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from inventario.servicios import motivo_equipo_no_habilitado

from .models import (
    CorridaSecado, EjecucionProceso, EntradaProceso, EtapaProceso, Proceso, RutaProducto,
    SalidaProceso,
)
from .servicios import (
    AVISO_INSPECCION_PREOPERATIVA, CODIGO_INSPECCION_PREOPERATIVA,
    MENSAJE_INICIO_SECADO_EN_PUESTO, disponible_de_salida, iniciar_secado,
    motivos_para_iniciar_secado, preparar_continuacion, transicionar_ejecucion,
)


class BasePuestoSecado(TestCase):
    """
    Un concentrado liberado por Calidad, en un silo, cuya siguiente etapa es
    Secado, y dos torres libres. Es lo que el puesto ve al empezar el turno.
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(rut="PSEC-1", nombre="Empresa puesto secado")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="PSEC", nombre="Planta puesto secado"
        )
        self.secador = self._usuario("secador-puesto", PerfilUsuario.Area.SECADO)
        self.condensador = self._usuario("condensador-puesto", PerfilUsuario.Area.CONDENSACION)
        self.calidad = self._usuario("calidad-puesto", PerfilUsuario.Area.CALIDAD, Rol.CALIDAD)
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Mandante puesto", codigo_cliente="psc"
        )
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Leche entera en polvo", familia=Producto.Familia.POLVO,
        )
        proceso = Proceso.objects.create(codigo="polvo-puesto-sec", nombre="Polvo puesto")
        self.etapa_evaporacion = EtapaProceso.objects.create(
            proceso=proceso, codigo="ev", nombre="Evaporación",
            tipo=EtapaProceso.Tipo.EVAPORACION, orden=1,
        )
        self.etapa_secado = EtapaProceso.objects.create(
            proceso=proceso, codigo="sec", nombre="Secado",
            tipo=EtapaProceso.Tipo.SECADO, orden=2,
        )
        self.ruta = RutaProducto.objects.create(
            sucursal=self.planta, producto=self.producto, proceso=proceso, prioridad=1,
        )
        self.evaporador = Equipo.objects.create(
            sucursal=self.planta, codigo="ev-ps", nombre="Evaporador PS",
            tipo=Equipo.Tipo.EVAPORADOR,
        )
        self.torre = Equipo.objects.create(
            sucursal=self.planta, codigo="e1-ps", nombre="Torre PS 1",
            tipo=Equipo.Tipo.TORRE, sigla="P1",
        )
        self.otra_torre = Equipo.objects.create(
            sucursal=self.planta, codigo="e2-ps", nombre="Torre PS 2",
            tipo=Equipo.Tipo.TORRE, sigla="P2",
        )
        self.silo = Silo.objects.create(
            sucursal=self.planta, codigo="CONC-PS", tipo=Silo.Tipo.SILO, capacidad_l=50000,
        )
        self.orden = OrdenProduccion.objects.create(
            sucursal=self.planta, codigo="OP-PS-1", producto=self.producto,
            cantidad_planificada=Decimal("1000"), unidad="l",
            estado=OrdenProduccion.Estado.EN_PROCESO,
        )
        self.lote = self._lote("CCAA6279PS-01")
        self.salida = self._concentrado(self.lote)
        self.liberacion = self.salida.liberacion_calidad
        # El documento de la inspección es por empresa (`documento_liberacion_
        # codigo_unico`). Se crea el de esta empresa con `update_or_create`:
        # las migraciones siembran el catálogo de otra organización también en
        # la base de pruebas (trampa de CLAUDE.md), y no se borra.
        self.inspeccion, _ = DocumentoLiberacion.objects.update_or_create(
            empresa=self.empresa, codigo=CODIGO_INSPECCION_PREOPERATIVA,
            defaults={
                "nombre": "Inspección Pre-operativa E1-E2", "area": "secado",
                "frecuencia": "por_ciclo",
                "plantilla": [
                    {"clave": "responsable", "etiqueta": "Responsable", "tipo": "texto", "req": True},
                ],
            },
        )

    def _usuario(self, nombre, area, rol=Rol.PRODUCCION):
        usuario = User.objects.create_user(nombre)
        PerfilUsuario.objects.create(
            usuario=usuario, empresa=self.empresa, sucursal=self.planta, area=area, rol=rol,
        )
        return usuario

    def _lote(self, codigo):
        return Lote.objects.create(
            sucursal=self.planta, codigo_lote=codigo, producto=self.producto,
            orden=self.orden, fecha=timezone.localdate(), estado=Lote.Estado.EN_PROCESO,
        )

    def _concentrado(self, lote, cantidad="1000"):
        evaporacion = EjecucionProceso.objects.create(
            codigo=f"EJ-EV-{lote.codigo_lote}", etapa=self.etapa_evaporacion,
            sucursal=self.planta, equipo=self.evaporador,
            estado=EjecucionProceso.Estado.CERRADA,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=evaporacion, lote=lote, silo=self.silo, producto=self.producto,
            ruta_producto=self.ruta, destino=SalidaProceso.Destino.PENDIENTE,
            cantidad=Decimal(cantidad), unidad="L",
        )
        LiberacionProceso.objects.create(salida=salida, estado=LiberacionProceso.Estado.LIBERADO)
        return salida

    def cliente(self, usuario=None):
        cliente = APIClient()
        cliente.force_authenticate(usuario or self.secador)
        return cliente

    def preparar(self, cantidad="600", torre=None, salida=None):
        ejecucion = preparar_continuacion(
            salida_id=(salida or self.salida).pk, etapa_id=self.etapa_secado.pk,
            equipo_id=(torre or self.torre).pk, cantidad=cantidad, usuario=self.secador,
        )
        return ejecucion.corrida_secado

    def inspeccion_de(self, torre, *, fecha=None, valores=None):
        return RegistroEquipo.objects.create(
            sucursal=self.planta, documento=self.inspeccion, equipo=torre,
            fecha=fecha or timezone.localdate(),
            estado=RegistroEquipo.Estado.COMPLETADO,
            valores={"responsable": "Ana"} if valores is None else valores,
        )


class IniciarSecadoTests(BasePuestoSecado):
    def test_sin_motivos_una_preparada_se_puede_iniciar(self):
        corrida = self.preparar()
        self.assertEqual(motivos_para_iniciar_secado(corrida), [])

        respuesta = self.cliente().post(f"/api/procesos/secados/{corrida.pk}/iniciar/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertIsNotNone(corrida.ejecucion.inicio)

    def test_el_aviso_de_inspeccion_queda_en_el_evento_de_inicio(self):
        corrida = self.preparar()

        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)

        evento = corrida.ejecucion.eventos.get(estado_nuevo=EjecucionProceso.Estado.EJECUCION)
        self.assertIn(AVISO_INSPECCION_PREOPERATIVA, evento.motivo)

    def test_una_torre_en_cip_no_inicia_y_la_ejecucion_sigue_preparada(self):
        corrida = self.preparar()
        CicloCIP.objects.create(
            sucursal=self.planta, area=PerfilUsuario.Area.SECADO, equipo=self.torre,
            inicio=timezone.now() - timedelta(hours=1), estado=CicloCIP.Estado.EN_CURSO,
        )
        motivos = motivos_para_iniciar_secado(corrida)
        self.assertTrue(any("CIP" in motivo for motivo in motivos))

        respuesta = self.cliente().post(f"/api/procesos/secados/{corrida.pk}/iniciar/")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(respuesta.data["message"], motivos[0])
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)

    def test_un_aseo_observado_avisa_pero_no_impide_iniciar(self):
        corrida = self.preparar()
        CicloCIP.objects.create(
            sucursal=self.planta, area=PerfilUsuario.Area.SECADO, equipo=self.torre,
            inicio=timezone.now() - timedelta(hours=3), estado=CicloCIP.Estado.OBSERVADO,
        )
        self.assertEqual(motivos_para_iniciar_secado(corrida), [])

    def test_un_aseo_observado_queda_marcado_en_el_lote_al_iniciar(self):
        """La ficha del lote lee la marca para su paso «Aseo» (DetalleLote)."""
        corrida = self.preparar()
        CicloCIP.objects.create(
            sucursal=self.planta, area=PerfilUsuario.Area.SECADO, equipo=self.torre,
            inicio=timezone.now() - timedelta(hours=3), estado=CicloCIP.Estado.OBSERVADO,
        )

        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)

        self.lote.refresh_from_db()
        self.assertIn(
            "[ADVERTENCIA ASEO AL INICIO] El último aseo de Torre PS 1 quedó observado.",
            self.lote.observacion,
        )

    def test_un_aseo_conforme_no_marca_el_lote(self):
        corrida = self.preparar()
        CicloCIP.objects.create(
            sucursal=self.planta, area=PerfilUsuario.Area.SECADO, equipo=self.torre,
            inicio=timezone.now() - timedelta(hours=3), estado=CicloCIP.Estado.COMPLETADO,
            verificacion=CicloCIP.Verificacion.CONFORME,
        )

        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)

        self.lote.refresh_from_db()
        self.assertNotIn("[ADVERTENCIA ASEO", self.lote.observacion)

    def test_si_calidad_rechazo_el_concentrado_no_inicia(self):
        corrida = self.preparar()
        self.liberacion.estado = LiberacionProceso.Estado.RECHAZADO
        self.liberacion.save(update_fields=["estado"])

        motivos = motivos_para_iniciar_secado(corrida)

        self.assertTrue(any("rechazó" in motivo for motivo in motivos))
        with self.assertRaises(ValidationError) as error:
            iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)
        self.assertEqual(error.exception.messages[0], motivos[0])

    def test_una_corrida_ya_iniciada_no_vuelve_a_iniciar(self):
        corrida = self.preparar()
        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)

        respuesta = self.cliente().post(f"/api/procesos/secados/{corrida.pk}/iniciar/")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)

    def test_sin_permiso_de_secado_responde_403(self):
        corrida = self.preparar()

        respuesta = self.cliente(self.condensador).post(
            f"/api/procesos/secados/{corrida.pk}/iniciar/"
        )

        self.assertEqual(respuesta.status_code, 403)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)


class PrepararSecadoTests(BasePuestoSecado):
    def test_preparar_continuacion_hacia_secado_exige_el_permiso_de_secado(self):
        antes = EjecucionProceso.objects.count()

        respuesta = self.cliente(self.condensador).post(
            f"/api/procesos/salidas/{self.salida.pk}/preparar-continuacion/",
            {"etapa": self.etapa_secado.pk, "equipo": self.torre.pk, "cantidad": "100"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(EjecucionProceso.objects.count(), antes)

    def test_un_lote_se_seca_en_una_sola_corrida(self):
        self.preparar(cantidad="400")

        with self.assertRaises(ValidationError) as error:
            self.preparar(cantidad="300", torre=self.otra_torre)

        self.assertIn("ya tiene una corrida de Secado", error.exception.messages[0])

    def test_una_torre_en_cip_no_se_prepara(self):
        """Misma regla que la alimentación externa: `motivo_equipo_no_habilitado`."""
        CicloCIP.objects.create(
            sucursal=self.planta, area=PerfilUsuario.Area.SECADO, equipo=self.torre,
            inicio=timezone.now() - timedelta(hours=1), estado=CicloCIP.Estado.EN_CURSO,
        )
        antes = EjecucionProceso.objects.count()

        with self.assertRaises(ValidationError) as error:
            self.preparar()

        self.assertEqual(
            error.exception.messages[0], motivo_equipo_no_habilitado(self.torre)
        )
        self.assertEqual(EjecucionProceso.objects.count(), antes)

    def test_una_salida_sin_lote_no_se_prepara_para_secado(self):
        self.salida.lote = None
        self.salida.save(update_fields=["lote"])

        with self.assertRaises(ValidationError) as error:
            self.preparar()

        self.assertIn("no tiene lote", error.exception.messages[0])


class PuestoSecadoTests(BasePuestoSecado):
    def puesto(self, usuario=None):
        respuesta = self.cliente(usuario).get("/api/procesos/secados/puesto/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return respuesta.data

    def fila(self, datos, torre):
        return next(item for item in datos["torres"] if item["equipo_id"] == torre.pk)

    def test_una_torre_sin_ejecucion_esta_disponible(self):
        fila = self.fila(self.puesto(), self.torre)
        self.assertEqual(fila["estado"], "disponible")
        self.assertIsNone(fila["corrida"])
        self.assertEqual(fila["motivos_para_iniciar"], [])
        self.assertEqual(fila["motivos_para_tomar"], [])

    def test_una_torre_disponible_en_cip_dice_por_que_no_se_toma(self):
        CicloCIP.objects.create(
            sucursal=self.planta, area=PerfilUsuario.Area.SECADO, equipo=self.torre,
            inicio=timezone.now() - timedelta(hours=1), estado=CicloCIP.Estado.EN_CURSO,
        )
        datos = self.puesto()
        fila = self.fila(datos, self.torre)
        self.assertEqual(fila["estado"], "disponible")
        self.assertEqual(fila["motivos_para_tomar"], [motivo_equipo_no_habilitado(self.torre)])
        self.assertEqual(fila["resolver_en"], "/calidad/inocuidad")
        self.assertEqual(self.fila(datos, self.otra_torre)["motivos_para_tomar"], [])

    def test_una_preparada_lista_para_iniciar(self):
        corrida = self.preparar(cantidad="600")
        fila = self.fila(self.puesto(), self.torre)
        self.assertEqual(fila["estado"], "preparada")
        self.assertEqual(fila["corrida"]["id"], corrida.pk)
        self.assertEqual(fila["corrida"]["lote_codigo"], self.lote.codigo_lote)
        self.assertEqual(fila["corrida"]["origen"], self.silo.codigo)
        self.assertEqual(fila["corrida"]["cantidad"], "600.000")
        self.assertEqual(fila["motivos_para_iniciar"], [])
        self.assertIsNone(fila["resolver_en"])

    def test_una_preparada_con_motivo_dice_por_que_y_donde_se_resuelve(self):
        self.preparar()
        CicloCIP.objects.create(
            sucursal=self.planta, area=PerfilUsuario.Area.SECADO, equipo=self.torre,
            inicio=timezone.now() - timedelta(hours=1), estado=CicloCIP.Estado.EN_CURSO,
        )
        fila = self.fila(self.puesto(), self.torre)
        self.assertIn("CIP", fila["motivos_para_iniciar"][0])
        self.assertEqual(fila["resolver_en"], "/calidad/inocuidad")

    def test_el_concentrado_rechazado_aparece_como_motivo(self):
        self.preparar()
        self.liberacion.estado = LiberacionProceso.Estado.RECHAZADO
        self.liberacion.save(update_fields=["estado"])
        fila = self.fila(self.puesto(), self.torre)
        self.assertTrue(any("rechazó" in motivo for motivo in fila["motivos_para_iniciar"]))
        self.assertEqual(fila["resolver_en"], "/calidad")

    def test_cip_y_rechazo_juntos_se_resuelven_donde_dice_el_primer_motivo(self):
        self.preparar()
        CicloCIP.objects.create(
            sucursal=self.planta, area=PerfilUsuario.Area.SECADO, equipo=self.torre,
            inicio=timezone.now() - timedelta(hours=1), estado=CicloCIP.Estado.EN_CURSO,
        )
        self.liberacion.estado = LiberacionProceso.Estado.RECHAZADO
        self.liberacion.save(update_fields=["estado"])

        fila = self.fila(self.puesto(), self.torre)

        self.assertIn("CIP", fila["motivos_para_iniciar"][0])
        self.assertTrue(any("rechazó" in motivo for motivo in fila["motivos_para_iniciar"]))
        self.assertEqual(fila["resolver_en"], "/calidad/inocuidad")

    def test_sin_saldo_no_se_resuelve_en_calidad(self):
        corrida = self.preparar(cantidad="600")
        otra = EjecucionProceso.objects.create(
            codigo="EJ-OTRA-TOMA", etapa=self.etapa_secado, sucursal=self.planta,
            equipo=self.otra_torre, estado=EjecucionProceso.Estado.EJECUCION,
            inicio=timezone.now(),
        )
        EntradaProceso.objects.create(
            ejecucion=otra, silo=self.silo, salida_origen=self.salida,
            cantidad=Decimal("600"), unidad="L",
        )

        fila = self.fila(self.puesto(), self.torre)

        self.assertEqual(fila["corrida"]["id"], corrida.pk)
        self.assertIn("ya no tiene saldo", fila["motivos_para_iniciar"][0])
        self.assertIsNone(fila["resolver_en"])

    def test_en_ejecucion_pausada_o_bloqueada_esta_en_curso(self):
        corrida = self.preparar()
        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)
        for estado in ("ejecucion", "pausada", "bloqueada"):
            EjecucionProceso.objects.filter(pk=corrida.ejecucion_id).update(estado=estado)
            with self.subTest(estado=estado):
                fila = self.fila(self.puesto(), self.torre)
                self.assertEqual(fila["estado"], "en_curso")
                self.assertEqual(fila["corrida"]["ejecucion_estado"], estado)

    def test_inspeccion_completa_de_hoy_no_avisa(self):
        self.inspeccion_de(self.torre)
        fila = self.fila(self.puesto(), self.torre)
        self.assertNotIn(AVISO_INSPECCION_PREOPERATIVA, fila["avisos"])
        self.assertFalse(fila["falta_inspeccion"])

    def test_sin_inspeccion_de_hoy_avisa(self):
        fila = self.fila(self.puesto(), self.torre)
        self.assertIn(AVISO_INSPECCION_PREOPERATIVA, fila["avisos"])
        self.assertTrue(fila["falta_inspeccion"])

    def test_la_inspeccion_de_ayer_no_cubre_hoy(self):
        self.inspeccion_de(self.torre, fecha=timezone.localdate() - timedelta(days=1))
        self.assertIn(AVISO_INSPECCION_PREOPERATIVA, self.fila(self.puesto(), self.torre)["avisos"])

    def test_una_inspeccion_incompleta_no_cubre(self):
        self.inspeccion_de(self.torre, valores={})
        self.assertIn(AVISO_INSPECCION_PREOPERATIVA, self.fila(self.puesto(), self.torre)["avisos"])

    def test_la_inspeccion_de_otra_torre_no_cubre_esta(self):
        self.inspeccion_de(self.otra_torre)
        self.assertIn(AVISO_INSPECCION_PREOPERATIVA, self.fila(self.puesto(), self.torre)["avisos"])

    def test_polvo_pendiente_en_calidad_se_informa_y_la_torre_queda_libre(self):
        lote = self._lote("CCAA6278PS-01")
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-SEC-CAL", etapa=self.etapa_secado, sucursal=self.planta,
            equipo=self.torre, estado=EjecucionProceso.Estado.CERRADA,
        )
        corrida = CorridaSecado.objects.create(ejecucion=ejecucion, orden=self.orden, lote=lote)
        salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=lote, producto=self.producto,
            naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
            destino=SalidaProceso.Destino.PENDIENTE, cantidad=Decimal("300"), unidad="kg",
        )
        LiberacionProceso.objects.create(salida=salida)
        fila = self.fila(self.puesto(), self.torre)
        self.assertEqual(fila["estado"], "disponible")
        self.assertEqual(fila["en_calidad"], {"id": corrida.pk, "lote_codigo": lote.codigo_lote})

    def test_concentrados_solo_con_saldo_y_secado_como_siguiente_etapa(self):
        datos = self.puesto()
        self.assertEqual([c["salida_id"] for c in datos["concentrados"]], [self.salida.pk])
        concentrado = datos["concentrados"][0]
        self.assertEqual(concentrado["etapa_id"], self.etapa_secado.pk)
        self.assertEqual(concentrado["disponible"], "1000.000")

        self.preparar(cantidad="400")
        # Con saldo (600 L) pero su lote ya tiene corrida: no se vuelve a ofrecer.
        self.assertEqual(self.puesto()["concentrados"], [])

    def test_los_concentrados_que_no_van_a_secado_no_se_recorren_uno_a_uno(self):
        """
        El histórico de salidas liberadas crece cada día: las que no siguen a
        Secado se descartan en la consulta, no una por una en Python.
        """
        proceso = Proceso.objects.create(codigo="crema-puesto-sec", nombre="Crema")
        evaporacion = EtapaProceso.objects.create(
            proceso=proceso, codigo="ev-cr", nombre="Evaporación crema",
            tipo=EtapaProceso.Tipo.EVAPORACION, orden=1,
        )
        EtapaProceso.objects.create(
            proceso=proceso, codigo="env-cr", nombre="Envasado crema",
            tipo=EtapaProceso.Tipo.ENVASADO, orden=2,
        )
        ruta = RutaProducto.objects.create(
            sucursal=self.planta, producto=self.producto, proceso=proceso, prioridad=2,
        )

        def salida_sin_secado(numero):
            lote = self._lote(f"CCAA6279CR-{numero:02d}")
            ejecucion = EjecucionProceso.objects.create(
                codigo=f"EJ-CR-{numero}", etapa=evaporacion, sucursal=self.planta,
                equipo=self.evaporador, estado=EjecucionProceso.Estado.CERRADA,
            )
            salida = SalidaProceso.objects.create(
                ejecucion=ejecucion, lote=lote, silo=self.silo, producto=self.producto,
                ruta_producto=ruta, destino=SalidaProceso.Destino.PENDIENTE,
                cantidad=Decimal("500"), unidad="L",
            )
            LiberacionProceso.objects.create(
                salida=salida, estado=LiberacionProceso.Estado.LIBERADO,
            )

        salida_sin_secado(1)
        with CaptureQueriesContext(connection) as una:
            datos = self.puesto()
        for numero in range(2, 7):
            salida_sin_secado(numero)
        with CaptureQueriesContext(connection) as seis:
            otra_vez = self.puesto()

        self.assertEqual([c["salida_id"] for c in datos["concentrados"]], [self.salida.pk])
        self.assertEqual([c["salida_id"] for c in otra_vez["concentrados"]], [self.salida.pk])
        self.assertEqual(len(seis.captured_queries), len(una.captured_queries))

    def test_no_se_ofrece_un_concentrado_sin_liberar(self):
        self.liberacion.estado = LiberacionProceso.Estado.PENDIENTE
        self.liberacion.save(update_fields=["estado"])
        self.assertEqual(self.puesto()["concentrados"], [])

    def test_corridas_de_hoy_sin_huerfanos(self):
        corrida = self.preparar()
        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)
        huerfano_lote = self._lote("CCAA6279PS-99")
        huerfana = EjecucionProceso.objects.create(
            codigo="EJ-SEC-HUERFANA", etapa=self.etapa_secado, sucursal=self.planta,
            equipo=self.otra_torre, estado=EjecucionProceso.Estado.CANCELADA,
        )
        CorridaSecado.objects.create(ejecucion=huerfana, orden=self.orden, lote=huerfano_lote)

        datos = self.puesto()

        self.assertEqual(
            [(c["id"], c["equipo"], c["estado"]) for c in datos["corridas_de_hoy"]],
            [(corrida.pk, self.torre.codigo, "ejecucion")],
        )
        self.assertEqual(self.fila(datos, self.otra_torre)["estado"], "disponible")

    def test_calidad_lee_el_puesto(self):
        self.assertIn("torres", self.puesto(self.calidad))

    def test_el_historial_filtra_en_el_servidor(self):
        corrida = self.preparar()
        otro = self._lote("CCAA6280PS-01")
        self.preparar(salida=self._concentrado(otro), torre=self.otra_torre)

        por_lote = self.cliente().get("/api/procesos/secados/", {"q": self.lote.codigo_lote})
        por_estado = self.cliente().get("/api/procesos/secados/", {"estado": "ejecucion"})
        preparadas = self.cliente().get("/api/procesos/secados/", {"estado": "preparacion"})

        self.assertEqual([c["id"] for c in por_lote.data["results"]], [corrida.pk])
        self.assertEqual(por_estado.data["results"], [])
        # Control positivo: el filtro de estado sí deja pasar lo que coincide.
        self.assertEqual(
            sorted(c["id"] for c in preparadas.data["results"]),
            sorted(CorridaSecado.objects.values_list("pk", flat=True)),
        )
        self.assertEqual(len(preparadas.data["results"]), 2)


class InicioGenericoCerradoTests(BasePuestoSecado):
    def transicionar(self, ejecucion, estado, motivo=""):
        ejecucion.refresh_from_db()
        return self.cliente().post(
            f"/api/procesos/ejecuciones/{ejecucion.pk}/transicionar/",
            {"estado": estado, "version": ejecucion.version, "motivo": motivo},
            format="json",
        )

    def test_transicionar_no_inicia_una_preparada_de_secado(self):
        corrida = self.preparar()

        respuesta = self.transicionar(corrida.ejecucion, "ejecucion")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(respuesta.data["message"], MENSAJE_INICIO_SECADO_EN_PUESTO)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)

    def test_pausar_y_reanudar_siguen_por_transicionar(self):
        corrida = self.preparar()
        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)

        pausa = self.transicionar(corrida.ejecucion, "pausada")
        reanudar = self.transicionar(corrida.ejecucion, "ejecucion")

        self.assertEqual(pausa.status_code, 200, pausa.data)
        self.assertEqual(reanudar.status_code, 200, reanudar.data)

    def test_la_bandeja_operativa_no_ofrece_iniciar_una_preparada_de_secado(self):
        corrida = self.preparar()

        bandeja = self.cliente().get("/api/procesos/ejecuciones/operativas/")

        fila = next(item for item in bandeja.data if item["id"] == corrida.ejecucion_id)
        self.assertNotIn("ejecucion", fila["acciones_permitidas"])
        self.assertIn("cancelada", fila["acciones_permitidas"])


class CancelarPreparacionTests(BasePuestoSecado):
    """
    Una torre preparada se puede soltar sin iniciarla: la preparación se
    deshace y el concentrado vuelve a ofrecerse entero, porque no llegó a
    entrar a la torre.
    """

    def cancelar(self, corrida, motivo="Se tomó el concentrado equivocado.", usuario=None):
        return self.cliente(usuario).post(
            f"/api/procesos/secados/{corrida.pk}/cancelar-preparacion/",
            {"motivo": motivo}, format="json",
        )

    def test_cancelar_libera_la_torre_y_el_concentrado_se_vuelve_a_tomar(self):
        corrida = self.preparar(cantidad="600")
        ejecucion_id = corrida.ejecucion_id

        respuesta = self.cancelar(corrida)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        ejecucion = EjecucionProceso.objects.get(pk=ejecucion_id)
        self.assertEqual(ejecucion.estado, EjecucionProceso.Estado.CANCELADA)
        evento = ejecucion.eventos.get(estado_nuevo=EjecucionProceso.Estado.CANCELADA)
        self.assertEqual(evento.motivo, "Se tomó el concentrado equivocado.")
        self.assertEqual(disponible_de_salida(self.salida), Decimal("1000"))
        datos = self.cliente().get("/api/procesos/secados/puesto/").data
        fila = next(item for item in datos["torres"] if item["equipo_id"] == self.torre.pk)
        self.assertEqual(fila["estado"], "disponible")
        self.assertEqual(
            [(c["salida_id"], c["disponible"]) for c in datos["concentrados"]],
            [(self.salida.pk, "1000.000")],
        )
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.ejecucion_id, self.salida.ejecucion_id)

        otra = self.preparar(cantidad="1000", torre=self.otra_torre)
        iniciar_secado(corrida_id=otra.pk, usuario=self.secador)

        otra.ejecucion.refresh_from_db()
        self.assertEqual(otra.ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertEqual(otra.lote_id, self.lote.pk)

    def test_cancelar_por_la_transicion_generica_tambien_libera_el_concentrado(self):
        corrida = self.preparar(cantidad="600")
        ejecucion = corrida.ejecucion

        transicionar_ejecucion(
            ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
            usuario=self.secador, motivo="Cancelada desde la bandeja.",
        )

        self.assertFalse(CorridaSecado.objects.filter(lote=self.lote).exists())
        self.assertEqual(disponible_de_salida(self.salida), Decimal("1000"))
        self.preparar(cantidad="1000")

    def test_sin_motivo_no_cancela(self):
        corrida = self.preparar()

        respuesta = self.cancelar(corrida, motivo="   ")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(respuesta.data["message"], "Indica el motivo de la cancelación.")
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)

    def test_una_corrida_iniciada_no_se_cancela_como_preparacion(self):
        corrida = self.preparar()
        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)

        respuesta = self.cancelar(corrida)

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("solo se cancela una torre preparada", respuesta.data["message"].lower())
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertEqual(disponible_de_salida(self.salida), Decimal("400"))

    def test_sin_permiso_de_secado_responde_403(self):
        corrida = self.preparar()

        respuesta = self.cancelar(corrida, usuario=self.condensador)

        self.assertEqual(respuesta.status_code, 403)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)

    def test_una_corrida_cancelada_despues_de_iniciar_sigue_consumiendo(self):
        """Lo que entró a la torre ya no vuelve al silo aunque se cancele."""
        corrida = self.preparar(cantidad="600")
        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)

        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
            usuario=self.secador, motivo="Falla de la torre.",
        )

        self.assertEqual(disponible_de_salida(self.salida), Decimal("400"))
        self.assertTrue(CorridaSecado.objects.filter(pk=corrida.pk).exists())

    def test_la_corrida_no_se_crea_por_la_api_generica(self):
        respuesta = self.cliente().post("/api/procesos/secados/", {}, format="json")

        self.assertEqual(respuesta.status_code, 405)
        self.assertEqual(
            str(respuesta.data["detail"]), "La corrida de Secado nace en el puesto de Secado."
        )


class SaldoTrasCancelarTests(BasePuestoSecado):
    """
    Una preparación cancelada no consumió nada: el concentrado vuelve con su
    saldo completo en todas las cuentas, no solo en `disponible_de_salida`.
    """

    def cancelar_preparacion(self, cantidad="1000"):
        corrida = self.preparar(cantidad=cantidad)
        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
            usuario=self.secador, motivo="Torre equivocada.",
        )
        return corrida

    def test_la_salida_vuelve_a_salidas_disponibles(self):
        self.cancelar_preparacion()

        respuesta = self.cliente().get("/api/procesos/salidas/disponibles/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        filas = respuesta.data if isinstance(respuesta.data, list) else respuesta.data["results"]
        self.assertIn(self.salida.pk, [fila["id"] for fila in filas])

    def test_la_salida_vuelve_a_contar_en_materiales_listos(self):
        from .consultas_planta import contar_materiales_listos

        antes = contar_materiales_listos()
        self.cancelar_preparacion()

        self.assertEqual(contar_materiales_listos(), antes)

    def test_una_toma_vigente_sigue_restando_en_materiales_listos(self):
        from .consultas_planta import contar_materiales_listos

        antes = contar_materiales_listos()
        self.preparar(cantidad="1000")

        self.assertEqual(contar_materiales_listos(), antes - 1)

    def test_una_salida_cuya_toma_se_cancelo_puede_cambiar_de_destino(self):
        from uuid import uuid4

        from .servicios import definir_destino_salida

        self.cancelar_preparacion()
        self.salida.refresh_from_db()

        salida = definir_destino_salida(
            salida_id=self.salida.pk, destino=SalidaProceso.Destino.DESPACHO_DIRECTO,
            destino_anterior=self.salida.destino, operacion_id=uuid4(),
            usuario=self.secador,
        )

        self.assertEqual(salida.destino, SalidaProceso.Destino.DESPACHO_DIRECTO)

    def test_una_salida_con_toma_vigente_no_cambia_de_destino(self):
        from uuid import uuid4

        from .servicios import definir_destino_salida

        self.preparar(cantidad="600")
        self.salida.refresh_from_db()

        with self.assertRaisesMessage(ValidationError, "ya fue consumida"):
            definir_destino_salida(
                salida_id=self.salida.pk, destino=SalidaProceso.Destino.DESPACHO_DIRECTO,
                destino_anterior=self.salida.destino, operacion_id=uuid4(),
                usuario=self.secador,
            )


class OrdenDeCandadosAlCancelarTests(BasePuestoSecado):
    """
    Cancelar por la transición genérica toma los candados en el mismo orden
    que `iniciar_secado` y `cancelar_preparacion_secado`: primero la corrida,
    después la ejecución. Con el orden cruzado, un inicio y una cancelación
    simultáneos podían esperarse el uno al otro hasta el deadlock.
    """

    def test_la_transicion_generica_bloquea_la_corrida_antes_que_la_ejecucion(self):
        corrida = self.preparar()
        tabla_corrida = CorridaSecado._meta.db_table
        tabla_ejecucion = EjecucionProceso._meta.db_table

        with CaptureQueriesContext(connection) as consultas:
            transicionar_ejecucion(
                ejecucion_id=corrida.ejecucion_id,
                estado_nuevo=EjecucionProceso.Estado.CANCELADA,
                usuario=self.secador, motivo="Cancelada desde la bandeja.",
            )

        candados = [
            consulta["sql"] for consulta in consultas.captured_queries
            if "FOR UPDATE" in consulta["sql"]
        ]
        primero_corrida = next(
            i for i, sql in enumerate(candados) if f'FROM "{tabla_corrida}"' in sql
        )
        primero_ejecucion = next(
            i for i, sql in enumerate(candados) if f'FROM "{tabla_ejecucion}"' in sql
        )
        self.assertLess(primero_corrida, primero_ejecucion)


class AnularLoteSueltaLaTorreTests(BasePuestoSecado):
    """
    Caso 3 de «La pantalla ofrece lo que el backend va a rechazar»: anular el
    lote cierra su ejecución. Antes la torre preparada quedaba ocupada por una
    corrida de un lote que ya no existía para nadie.
    """

    def test_anular_el_lote_de_una_torre_preparada_la_deja_disponible(self):
        corrida = self.preparar(cantidad="600")
        ejecucion_id = corrida.ejecucion_id

        respuesta = self.cliente().patch(
            f"/api/produccion/lotes/{self.lote.pk}/",
            {"estado": "anulado", "motivo_anulacion": "El concentrado no sirve."},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        ejecucion = EjecucionProceso.objects.get(pk=ejecucion_id)
        self.assertEqual(ejecucion.estado, EjecucionProceso.Estado.CANCELADA)
        datos = self.cliente().get("/api/procesos/secados/puesto/").data
        fila = next(item for item in datos["torres"] if item["equipo_id"] == self.torre.pk)
        self.assertEqual(fila["estado"], "disponible")
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.estado, Lote.Estado.ANULADO)
        self.assertEqual(self.lote.observacion.count("[ANULACIÓN]"), 1)
