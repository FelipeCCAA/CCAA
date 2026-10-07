from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from inventario.models import CicloCIP
from maestros.models import Equipo, Especificacion, Mandante, Producto, Silo
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import (
    CorridaDescremacion, EjecucionProceso, EtapaProceso, Proceso, ReservaSiloProceso,
)
from .servicios import (
    MENSAJE_INICIO_DESCREMADO_EN_PUESTO, MENSAJE_MOTIVO_CANCELACION, RESOLVER_CIP,
    RESOLVER_SILOS, iniciar_descremacion, motivos_para_iniciar_descremacion,
    motivos_tipados_para_iniciar_descremacion, transicionar_ejecucion,
)


class BasePuestoDescremado(TestCase):
    """
    Un silo de leche entera con 20.000 L y un análisis confirmado con las dos
    firmas, dos TK de descremada, dos de crema y dos descremadoras libres: lo
    que el puesto ve al empezar el turno.

    Las migraciones siembran equipos y silos en la base de pruebas, y
    `filtrar_por_scope` ya no aísla por empresa: las aserciones se hacen sobre
    los objetos de esta fixture, nunca sobre listas completas.
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(rut="PDES-1", nombre="Empresa puesto descremado")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="PDES", nombre="Planta puesto descremado"
        )
        self.condensador = self._usuario("condensador-pdes", PerfilUsuario.Area.CONDENSACION)
        self.secador = self._usuario("secador-pdes", PerfilUsuario.Area.SECADO)
        self.calidad = self._usuario("calidad-pdes", PerfilUsuario.Area.CALIDAD, Rol.CALIDAD)
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Intermedios puesto descremado", codigo_cliente="pdd"
        )
        self.producto_descremada = Producto.objects.create(
            mandante=mandante, nombre="Descremada intermedia PD",
            familia=Producto.Familia.LIQUIDO, naturaleza=Producto.Naturaleza.INTERMEDIO,
            tipo=Producto.TipoProducto.DESCREMADA, unidad_base=Producto.Unidad.L,
        )
        self.producto_crema = Producto.objects.create(
            mandante=mandante, nombre="Crema intermedia PD",
            familia=Producto.Familia.CREMA, naturaleza=Producto.Naturaleza.INTERMEDIO,
            categoria=Producto.Categoria.CREMA, unidad_base=Producto.Unidad.KG,
        )
        for producto, minimo, maximo in (
            (self.producto_descremada, 0, 0.2), (self.producto_crema, 35, 45),
        ):
            Especificacion.objects.create(
                producto=producto, tipo_analisis=Especificacion.TipoAnalisis.SILO,
                version=1, vigente_desde=timezone.localdate(),
                rangos={"mg": {"min": minimo, "max": maximo}},
            )
        proceso = Proceso.objects.create(codigo="descremar-puesto", nombre="Descremado del puesto")
        self.etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="des-pd", nombre="Descremar",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=1,
        )
        self.descremadora = self._equipo("des-pd1", "Descremadora PD 1")
        self.otra_descremadora = self._equipo("des-pd2", "Descremadora PD 2")
        self.origen = self._silo("SILO-PD", Silo.Tipo.SILO, 30000)
        self.tk_descremada = self._silo("TK-LD-PD", Silo.Tipo.TK_LD, 30000)
        self.otro_tk_descremada = self._silo("TK-LD-PD2", Silo.Tipo.TK_LD, 30000)
        self.tk_crema = self._silo("TK-CR-PD", Silo.Tipo.TK_CREMA, 5000)
        self.otro_tk_crema = self._silo("TK-CR-PD2", Silo.Tipo.TK_CREMA, 5000)
        MovimientoSilo.objects.create(
            silo=self.origen, tipo=MovimientoSilo.Tipo.INGRESO, litros=20000,
            fecha_hora=timezone.now() - timedelta(hours=3),
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
        )
        self.analisis = self.analizar(self.origen, minutos=120)

    def _usuario(self, nombre, area, rol=Rol.PRODUCCION):
        usuario = User.objects.create_user(nombre)
        PerfilUsuario.objects.create(
            usuario=usuario, empresa=self.empresa, sucursal=self.planta, area=area, rol=rol,
        )
        return usuario

    def _equipo(self, codigo, nombre):
        return Equipo.objects.create(
            sucursal=self.planta, codigo=codigo, nombre=nombre, tipo=Equipo.Tipo.DESCREMADORA,
        )

    def _silo(self, codigo, tipo, capacidad):
        return Silo.objects.create(
            sucursal=self.planta, codigo=codigo, tipo=tipo, capacidad_l=capacidad,
        )

    def analizar(self, silo, *, minutos=60, grasa="2.61", sng="8.70", segunda_firma=True):
        return AnalisisSilo.objects.create(
            silo=silo, tomado_en=timezone.now() - timedelta(minutes=minutos),
            grasa=None if grasa is None else Decimal(grasa),
            sng=None if sng is None else Decimal(sng),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO, analista=self.condensador,
            visualizado_por=self.calidad if segunda_firma else None,
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
        datos = {
            "etapa": self.etapa.pk, "equipo": self.descremadora.pk,
            "silo_entera": self.origen.pk, "litros_entrada": "1000",
            "silo_descremada": self.tk_descremada.pk, "estanque_crema": self.tk_crema.pk,
            "producto_descremada": self.producto_descremada.pk,
            "producto_crema": self.producto_crema.pk,
            "litros_descremada_plan": "970", "litros_crema_plan": "25",
            "plan_confirmado": True,
        }
        datos.update(cambios)
        return datos

    def preparar(self, usuario=None, **cambios):
        return self.cliente(usuario).post(
            "/api/procesos/descremaciones/crear-guiada/",
            self.datos_preparar(**cambios), format="json",
        )

    def preparada(self, **cambios):
        respuesta = self.preparar(**cambios)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return CorridaDescremacion.objects.select_related("ejecucion").get(pk=respuesta.data["id"])

    def en_curso(self, **cambios):
        corrida = self.preparada(**cambios)
        iniciar_descremacion(corrida_id=corrida.pk, usuario=self.condensador)
        corrida.refresh_from_db()
        corrida.ejecucion.refresh_from_db()
        return corrida

    def reservas(self, corrida, estado=ReservaSiloProceso.Estado.ACTIVA):
        return ReservaSiloProceso.objects.filter(ejecucion_id=corrida.ejecucion_id, estado=estado)


class PrepararDescremadoTests(BasePuestoDescremado):
    def test_preparar_crea_corrida_tres_reservas_y_toma_la_descremadora(self):
        corrida = self.preparada()

        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.BORRADOR)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
        self.assertEqual(corrida.ejecucion.equipo, self.descremadora)
        self.assertEqual(corrida.ejecucion.codigo, f"EJ-DES-{corrida.pk}")
        self.assertEqual(
            set(self.reservas(corrida).values_list("tipo", "silo_id", "cantidad_planificada")),
            {
                (ReservaSiloProceso.Tipo.ORIGEN, self.origen.pk, Decimal("1000")),
                (ReservaSiloProceso.Tipo.DESTINO, self.tk_descremada.pk, Decimal("970")),
                (ReservaSiloProceso.Tipo.DESTINO, self.tk_crema.pk, Decimal("25")),
            },
        )
        # Preparar no mueve leche ni registra entrada: eso es iniciar.
        self.assertFalse(corrida.ejecucion.entradas.exists())

    def test_el_servidor_elige_el_analisis_y_asigna_el_codigo(self):
        nuevo = self.analizar(self.origen, minutos=30, grasa="2.70")

        corrida = self.preparada(codigo="DES-TECLEADO", analisis_entrada=self.analisis.pk)

        self.assertEqual(corrida.analisis_entrada, nuevo)
        self.assertEqual(corrida.grasa_entrada, Decimal("2.70"))
        self.assertNotEqual(corrida.ejecucion.codigo, "DES-TECLEADO")

    def test_sin_segunda_firma_igual_se_prepara(self):
        # La firma es motivo de inicio, no de preparación (como Evaporación).
        self.analizar(self.origen, minutos=30, segunda_firma=False)

        self.preparada()

    def test_sin_composicion_no_se_prepara(self):
        self.analizar(self.origen, minutos=30, grasa=None)

        respuesta = self.preparar()

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("grasa y SNG", str(respuesta.data))
        self.assertFalse(CorridaDescremacion.objects.filter(silo_entera=self.origen).exists())

    def test_un_tk_sin_capacidad_no_deja_nada_escrito(self):
        self.tk_crema.capacidad_l = 10
        self.tk_crema.save(update_fields=["capacidad_l"])

        respuesta = self.preparar()

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("no tiene capacidad", str(respuesta.data))
        self.assertFalse(CorridaDescremacion.objects.filter(silo_entera=self.origen).exists())
        self.assertFalse(ReservaSiloProceso.objects.filter(silo=self.tk_crema).exists())
        self.assertFalse(EjecucionProceso.objects.filter(equipo=self.descremadora).exists())

    def test_una_descremadora_ocupada_no_se_prepara(self):
        self.preparada()

        respuesta = self.preparar(
            silo_descremada=self.otro_tk_descremada.pk, estanque_crema=self.otro_tk_crema.pk,
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("ocupad", str(respuesta.data))
        self.assertEqual(EjecucionProceso.objects.filter(equipo=self.descremadora).count(), 1)

    def test_un_tk_reservado_por_otra_preparacion_no_se_asigna(self):
        primera = self.preparada()

        respuesta = self.preparar(
            equipo=self.otra_descremadora.pk, estanque_crema=self.otro_tk_crema.pk,
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn(f"ya está reservado por {primera.ejecucion.codigo}", str(respuesta.data))
        self.assertFalse(EjecucionProceso.objects.filter(equipo=self.otra_descremadora).exists())

    def test_una_descremadora_en_cip_no_se_prepara(self):
        self.cip(self.descremadora)

        respuesta = self.preparar()

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("CIP", str(respuesta.data))

    def test_secado_no_prepara(self):
        respuesta = self.preparar(usuario=self.secador)

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(EjecucionProceso.objects.filter(equipo=self.descremadora).exists())


class IniciarDescremadoTests(BasePuestoDescremado):
    def iniciar(self, corrida, usuario=None):
        return self.cliente(usuario).post(f"/api/procesos/descremaciones/{corrida.pk}/iniciar/")

    def test_sin_motivos_inicia_con_una_entrada_y_sin_reservas_nuevas(self):
        corrida = self.preparada()
        self.assertEqual(motivos_para_iniciar_descremacion(corrida), [])

        respuesta = self.iniciar(corrida)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida.refresh_from_db()
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.EN_CURSO)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertEqual(corrida.ejecucion.entradas.count(), 1)
        self.assertEqual(
            ReservaSiloProceso.objects.filter(ejecucion_id=corrida.ejecucion_id).count(), 3,
        )

    def test_sin_segunda_firma_no_inicia_y_se_resuelve_en_silos(self):
        self.analizar(self.origen, minutos=30, segunda_firma=False)
        corrida = self.preparada()

        motivo, resolver_en = motivos_tipados_para_iniciar_descremacion(corrida)[0]

        self.assertIn("firma de realización y visualización", motivo)
        self.assertEqual(resolver_en, RESOLVER_SILOS)
        respuesta = self.iniciar(corrida)
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertIn(motivo, str(respuesta.data))
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
        self.assertFalse(corrida.ejecucion.entradas.exists())

    def test_una_descremadora_en_cip_se_resuelve_en_inocuidad(self):
        corrida = self.preparada()
        self.cip(self.descremadora)

        motivo, resolver_en = motivos_tipados_para_iniciar_descremacion(corrida)[0]

        self.assertIn("CIP", motivo)
        self.assertEqual(resolver_en, RESOLVER_CIP)

    def test_un_analisis_mas_nuevo_impide_iniciar_con_la_composicion_vieja(self):
        corrida = self.preparada()
        self.analizar(self.origen, minutos=10, grasa="2.90")

        self.assertEqual(
            motivos_tipados_para_iniciar_descremacion(corrida),
            [(
                f"El análisis con que se preparó {corrida.ejecucion.codigo} ya no es el "
                f"vigente de {self.origen.codigo}: cancela la preparación y vuelve a "
                "prepararla con la composición actual.",
                None,
            )],
        )

    def test_los_motivos_son_lo_que_rechaza_iniciar(self):
        corrida = self.preparada()
        self.tk_crema.estado = Silo.Estado.EN_CIP
        self.tk_crema.save(update_fields=["estado"])
        motivos = motivos_para_iniciar_descremacion(corrida)
        self.assertTrue(motivos)

        with self.assertRaises(ValidationError) as error:
            iniciar_descremacion(corrida_id=corrida.pk, usuario=self.condensador)

        self.assertEqual(error.exception.messages[0], motivos[0])

    def test_un_aseo_observado_avisa_y_queda_en_el_evento(self):
        corrida = self.preparada()
        self.cip(self.descremadora, estado=CicloCIP.Estado.OBSERVADO, horas=3)
        self.assertEqual(motivos_para_iniciar_descremacion(corrida), [])

        iniciar_descremacion(corrida_id=corrida.pk, usuario=self.condensador)

        evento = corrida.ejecucion.eventos.get(estado_nuevo=EjecucionProceso.Estado.EJECUCION)
        self.assertIn("Advertencia no bloqueante de aseo", evento.motivo)

    def test_una_corrida_iniciada_no_vuelve_a_iniciar(self):
        corrida = self.en_curso()

        self.assertEqual(self.iniciar(corrida).status_code, 409)

    def test_secado_no_inicia(self):
        corrida = self.preparada()

        self.assertEqual(self.iniciar(corrida, self.secador).status_code, 403)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)


class InicioGenericoCerradoDescremadoTests(BasePuestoDescremado):
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
        self.assertEqual(respuesta.data["message"], MENSAJE_INICIO_DESCREMADO_EN_PUESTO)
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

    def test_el_alta_directa_de_corridas_esta_cerrada(self):
        respuesta = self.cliente().post("/api/procesos/descremaciones/", {}, format="json")

        self.assertEqual(respuesta.status_code, 405)

    def test_el_alta_generica_de_ejecuciones_esta_cerrada(self):
        respuesta = self.cliente().post(
            "/api/procesos/ejecuciones/",
            {"codigo": "EJ-DES-GENERICA", "etapa": self.etapa.pk, "equipo": self.descremadora.pk},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 405)
        self.assertFalse(EjecucionProceso.objects.filter(codigo="EJ-DES-GENERICA").exists())


class CancelarPreparacionDescremadoTests(BasePuestoDescremado):
    def cancelar(self, corrida, motivo="TK equivocado", usuario=None):
        return self.cliente(usuario).post(
            f"/api/procesos/descremaciones/{corrida.pk}/cancelar-preparacion/",
            {"motivo": motivo}, format="json",
        )

    def corrida_heredada(self):
        """Una corrida `borrador` del modal viejo: ejecución en borrador, sin reservas."""
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-DES-HEREDADA", etapa=self.etapa, sucursal=self.planta,
            equipo=self.descremadora, responsable=self.condensador,
        )
        return CorridaDescremacion.objects.create(
            ejecucion=ejecucion, silo_entera=self.origen, analisis_entrada=self.analisis,
            litros_entrada=Decimal("1000"), grasa_entrada=Decimal("2.61"),
            sng_entrada=Decimal("8.70"), silo_descremada=self.tk_descremada,
            estanque_crema=self.tk_crema, producto_descremada=self.producto_descremada,
            producto_crema=self.producto_crema, litros_descremada_plan=Decimal("970"),
            litros_crema_plan=Decimal("25"), plan_confirmado_por=self.condensador,
            plan_confirmado_en=timezone.now(),
        )

    def test_cancelar_suelta_reservas_y_maquina_y_anula_la_corrida(self):
        corrida = self.preparada()

        respuesta = self.cancelar(corrida)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data, {
            "ejecucion_id": corrida.ejecucion_id,
            "ejecucion_codigo": corrida.ejecucion.codigo,
            "estado": EjecucionProceso.Estado.CANCELADA,
        })
        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.ANULADA)
        self.assertEqual(corrida.motivo_anulacion, "TK equivocado.")
        self.assertEqual(
            set(ReservaSiloProceso.objects.filter(ejecucion_id=corrida.ejecucion_id)
                .values_list("estado", flat=True)),
            {ReservaSiloProceso.Estado.LIBERADA},
        )
        # La misma descremadora y los mismos TK se vuelven a preparar.
        self.preparada()

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
        self.assertIn("se cierra registrando sus salidas", respuesta.data["message"])

    def test_cancelar_desde_la_bandeja_generica_deja_lo_mismo(self):
        corrida = self.preparada()

        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
            usuario=self.condensador, motivo="Desde la bandeja",
        )

        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.ANULADA)
        self.assertEqual(corrida.motivo_anulacion, "Desde la bandeja.")
        self.assertFalse(self.reservas(corrida).exists())

    def test_una_corrida_en_curso_cancelada_por_la_bandeja_queda_anulada(self):
        corrida = self.en_curso()

        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
            usuario=self.condensador, motivo="Falla eléctrica",
        )

        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.ANULADA)

    def test_una_preparacion_heredada_en_borrador_se_cancela(self):
        corrida = self.corrida_heredada()

        respuesta = self.cancelar(corrida)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.ANULADA)

    def test_secado_no_cancela(self):
        corrida = self.preparada()

        self.assertEqual(self.cancelar(corrida, usuario=self.secador).status_code, 403)
        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.BORRADOR)
