from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso, RegistroEquipo
from inventario.models import CicloCIP
from maestros.models import DocumentoLiberacion, Equipo, Mandante, Producto, Silo
from produccion.models import Lote, OrdenProduccion
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import (
    CorridaSecado, EjecucionProceso, EtapaProceso, Proceso, RutaProducto, SalidaProceso,
)
from .servicios import (
    AVISO_INSPECCION_PREOPERATIVA, CODIGO_INSPECCION_PREOPERATIVA,
    MENSAJE_INICIO_SECADO_EN_PUESTO, iniciar_secado, motivos_para_iniciar_secado,
    preparar_continuacion,
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

        self.assertEqual([c["id"] for c in por_lote.data["results"]], [corrida.pk])
        self.assertEqual(por_estado.data["results"], [])


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
