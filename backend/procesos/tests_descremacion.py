from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso
from maestros.models import Equipo, Especificacion, Mandante, Producto, Silo
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .dominio import calcular_balance_descremacion
from .models import (
    CorridaDescremacion, EjecucionProceso, EtapaProceso, Proceso, RutaProducto,
    ReservaSiloProceso, SalidaProceso,
)
from .servicios import (
    cerrar_descremacion, iniciar_descremacion, preparar_continuacion,
    transicionar_ejecucion,
)


class BalanceDescremacionTests(TestCase):
    def test_calcula_las_dos_salidas_sin_inventar_una_tolerancia(self):
        balance = calcular_balance_descremacion(1000, 4, 8.7, 0.1, 40)

        self.assertAlmostEqual(balance.crema_esperada_l, Decimal("97.74436"), places=4)
        self.assertAlmostEqual(balance.descremada_esperada_l, Decimal("902.25564"), places=4)
        self.assertEqual(balance.avisos, ())


class CierreDescremacionTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="76.999.111-2", nombre="Descremación")
        sucursal = Sucursal.objects.create(empresa=empresa, codigo="DES", nombre="Planta")
        self.sucursal = sucursal
        self.usuario = User.objects.create_user("operador-descremacion")
        mandante = Mandante.objects.create(
            empresa=empresa, nombre="Productos intermedios", codigo_cliente="des"
        )
        self.producto_descremada = Producto.objects.create(
            mandante=mandante, nombre="Leche descremada intermedia",
            familia=Producto.Familia.LIQUIDO, naturaleza=Producto.Naturaleza.INTERMEDIO,
            tipo=Producto.TipoProducto.DESCREMADA, unidad_base=Producto.Unidad.L,
        )
        self.producto_crema = Producto.objects.create(
            mandante=mandante, nombre="Crema intermedia para mantequilla",
            familia=Producto.Familia.CREMA, naturaleza=Producto.Naturaleza.INTERMEDIO,
            categoria=Producto.Categoria.CREMA, unidad_base=Producto.Unidad.KG,
        )
        self.origen = Silo.objects.create(
            sucursal=sucursal, codigo="ENTERA-D", tipo=Silo.Tipo.SILO, capacidad_l=5000
        )
        self.descremada = Silo.objects.create(
            sucursal=sucursal, codigo="DESCREMADA-D", tipo=Silo.Tipo.TK_LD,
            capacidad_l=5000,
        )
        self.crema = Silo.objects.create(
            sucursal=sucursal, codigo="CREMA-D", tipo=Silo.Tipo.TK_CREMA,
            capacidad_l=1000,
        )
        MovimientoSilo.objects.create(
            silo=self.origen, tipo=MovimientoSilo.Tipo.INGRESO, litros=1000,
            fecha_hora=timezone.now() - timedelta(hours=2),
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
        )
        analisis = AnalisisSilo.objects.create(
            silo=self.origen, tomado_en=timezone.now() - timedelta(hours=1),
            grasa=Decimal("4.000"), sng=Decimal("8.700"),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(), estado=AnalisisSilo.Estado.CONFIRMADO,
            analista=self.usuario, visualizado_por=self.usuario,
        )
        equipo = Equipo.objects.create(
            sucursal=sucursal, codigo="DES-1", nombre="Descremadora 1",
            tipo=Equipo.Tipo.DESCREMADORA,
        )
        proceso = Proceso.objects.create(codigo="descremar", nombre="Descremación")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="des", nombre="Descremar",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=1,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-DES-1", etapa=etapa, sucursal=sucursal,
            equipo=equipo, responsable=self.usuario,
        )
        self.ejecucion = ejecucion
        self.corrida = CorridaDescremacion.objects.create(
            ejecucion=ejecucion, silo_entera=self.origen, analisis_entrada=analisis,
            litros_entrada=1000, grasa_entrada=Decimal("4.000"),
            sng_entrada=Decimal("8.700"), silo_descremada=self.descremada,
            estanque_crema=self.crema,
            producto_descremada=self.producto_descremada,
            producto_crema=self.producto_crema,
            litros_descremada_plan=Decimal("900"),
            litros_crema_plan=Decimal("90"),
            fuente_plan={"metodo": "prueba"},
            plan_confirmado_por=self.usuario,
            plan_confirmado_en=timezone.now(),
        )

    def test_alta_guiada_crea_ejecucion_y_corrida_en_una_operacion(self):
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=self.sucursal.empresa,
            sucursal=self.sucursal, rol=Rol.PRODUCCION,
            area=PerfilUsuario.Area.CONDENSACION,
        )
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        Especificacion.objects.create(
            producto=self.producto_descremada,
            tipo_analisis=Especificacion.TipoAnalisis.SILO,
            version=1, vigente_desde=timezone.localdate(),
            rangos={"mg": {"min": 0, "max": 0.2}},
        )
        Especificacion.objects.create(
            producto=self.producto_crema,
            tipo_analisis=Especificacion.TipoAnalisis.SILO,
            version=1, vigente_desde=timezone.localdate(),
            rangos={"mg": {"min": 35, "max": 45}},
        )
        proceso_descremada = Proceso.objects.create(
            codigo="descremada-est", nombre="Descremada a estandarizacion"
        )
        EtapaProceso.objects.create(
            proceso=proceso_descremada, codigo="est", nombre="Estandarizar",
            tipo=EtapaProceso.Tipo.ESTANDARIZACION, orden=1,
        )
        ruta_descremada = RutaProducto.objects.create(
            sucursal=self.sucursal, producto=self.producto_descremada,
            proceso=proceso_descremada,
        )
        proceso_crema = Proceso.objects.create(
            codigo="crema-mant", nombre="Crema a mantequilla"
        )
        EtapaProceso.objects.create(
            proceso=proceso_crema, codigo="mant", nombre="Mantequilla",
            tipo=EtapaProceso.Tipo.MANTEQUILLA, orden=1,
        )
        ruta_crema = RutaProducto.objects.create(
            sucursal=self.sucursal, producto=self.producto_crema,
            proceso=proceso_crema,
        )

        respuesta = cliente.post(
            "/api/procesos/descremaciones/crear-guiada/",
            {
                "codigo": "EJ-DES-GUIADA",
                "etapa": self.ejecucion.etapa_id,
                "equipo": self.ejecucion.equipo_id,
                "silo_entera": self.origen.pk,
                "analisis_entrada": self.corrida.analisis_entrada_id,
                "litros_entrada": "500",
                "silo_descremada": self.descremada.pk,
                "estanque_crema": self.crema.pk,
                "producto_descremada": self.producto_descremada.pk,
                "producto_crema": self.producto_crema.pk,
                "litros_descremada_plan": "450",
                "litros_crema_plan": "45",
                "plan_confirmado": True,
                "ruta_descremada": ruta_descremada.pk,
                "ruta_crema": ruta_crema.pk,
                "destino_descremada": "estandarizacion",
                "destino_crema": "siguiente_proceso",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        guiada = CorridaDescremacion.objects.get(pk=respuesta.data["id"])
        self.assertEqual(guiada.ejecucion.codigo, "EJ-DES-GUIADA")
        self.assertEqual(guiada.ejecucion.responsable, self.usuario)
        self.assertEqual(guiada.grasa_entrada, self.corrida.analisis_entrada.grasa)
        self.assertEqual(guiada.sng_entrada, self.corrida.analisis_entrada.sng)
        self.assertEqual(guiada.ruta_descremada, ruta_descremada)
        self.assertEqual(guiada.ruta_crema, ruta_crema)
        self.assertEqual(guiada.plan_confirmado_por, self.usuario)
        self.assertEqual(guiada.fuente_plan["metodo"], "balance_materia_grasa")

    def test_sugerencia_usa_especificaciones_y_exige_confirmacion_posterior(self):
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=self.sucursal.empresa,
            sucursal=self.sucursal, rol=Rol.PRODUCCION,
            area=PerfilUsuario.Area.CONDENSACION,
        )
        for producto, minimo, maximo in (
            (self.producto_descremada, 0, 0.2),
            (self.producto_crema, 35, 45),
        ):
            Especificacion.objects.create(
                producto=producto, tipo_analisis=Especificacion.TipoAnalisis.SILO,
                version=1, vigente_desde=timezone.localdate(),
                rangos={"mg": {"min": minimo, "max": maximo}},
            )
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)

        respuesta = cliente.post(
            "/api/procesos/descremaciones/sugerir-balance/",
            {
                "analisis_entrada": self.corrida.analisis_entrada_id,
                "litros_entrada": "1000",
                "producto_descremada": self.producto_descremada.pk,
                "producto_crema": self.producto_crema.pk,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["grasa_descremada_objetivo"], Decimal("0.1"))
        self.assertEqual(respuesta.data["grasa_crema_objetivo"], Decimal("40"))
        self.assertTrue(respuesta.data["requiere_confirmacion_operador"])

    def test_opciones_alta_entrega_solo_maestros_compatibles(self):
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=self.sucursal.empresa,
            sucursal=self.sucursal, rol=Rol.PRODUCCION,
            area=PerfilUsuario.Area.CONDENSACION,
        )
        Equipo.objects.create(
            sucursal=self.sucursal, codigo="EQ-NO-DES",
            nombre="Equipo no compatible", tipo=Equipo.Tipo.EVAPORADOR,
        )
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)

        respuesta = cliente.get("/api/procesos/descremaciones/opciones-alta/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(
            [item["id"] for item in respuesta.data["equipos"]],
            [self.ejecucion.equipo_id],
        )
        self.assertEqual(
            [item["id"] for item in respuesta.data["productos_descremada"]],
            [self.producto_descremada.pk],
        )
        self.assertEqual(
            [item["id"] for item in respuesta.data["silos_descremada"]],
            [self.descremada.pk],
        )
        self.assertEqual(respuesta.data["bloqueos"], [])

    def test_opciones_alta_informa_especificaciones_silo_vigentes(self):
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=self.sucursal.empresa,
            sucursal=self.sucursal, rol=Rol.PRODUCCION,
            area=PerfilUsuario.Area.CONDENSACION,
        )
        Especificacion.objects.create(
            producto=self.producto_descremada,
            tipo_analisis=Especificacion.TipoAnalisis.SILO,
            version=1,
            vigente_desde=timezone.localdate(),
            rangos={"mg": {"min": 0, "max": 0.2}},
        )
        Especificacion.objects.create(
            producto=self.producto_crema,
            tipo_analisis=Especificacion.TipoAnalisis.SILO,
            version=1,
            vigente_desde=timezone.localdate() - timedelta(days=10),
            vigente_hasta=timezone.localdate() - timedelta(days=1),
            rangos={"mg": {"min": 35, "max": 45}},
        )
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)

        respuesta = cliente.get("/api/procesos/descremaciones/opciones-alta/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertTrue(
            respuesta.data["productos_descremada"][0][
                "tiene_especificacion_silo_vigente"
            ]
        )
        self.assertFalse(
            respuesta.data["productos_crema"][0][
                "tiene_especificacion_silo_vigente"
            ]
        )

    def test_ruta_de_otra_rama_no_puede_identificar_la_salida(self):
        proceso = Proceso.objects.create(codigo="ruta-ajena", nombre="Ruta ajena")
        EtapaProceso.objects.create(
            proceso=proceso, codigo="est-ajena", nombre="Estandarizar",
            tipo=EtapaProceso.Tipo.ESTANDARIZACION, orden=1,
        )
        ruta_de_crema = RutaProducto.objects.create(
            sucursal=self.sucursal, producto=self.producto_crema, proceso=proceso,
        )
        self.corrida.ruta_descremada = ruta_de_crema
        self.corrida.destino_descremada = CorridaDescremacion.DestinoRama.ESTANDARIZACION

        with self.assertRaisesMessage(
            ValidationError, "La ruta seleccionada no pertenece al producto de esta salida."
        ):
            self.corrida.full_clean()

    def test_sugerencia_rechaza_producto_terminado_en_polvo(self):
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=self.sucursal.empresa,
            sucursal=self.sucursal, rol=Rol.PRODUCCION,
            area=PerfilUsuario.Area.CONDENSACION,
        )
        polvo = Producto.objects.create(
            mandante=self.producto_descremada.mandante,
            nombre="Leche descremada en polvo 25 kg",
            familia=Producto.Familia.POLVO,
            naturaleza=Producto.Naturaleza.TERMINADO,
            tipo=Producto.TipoProducto.DESCREMADA,
            unidad_base=Producto.Unidad.KG,
        )
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)

        respuesta = cliente.post(
            "/api/procesos/descremaciones/sugerir-balance/",
            {
                "analisis_entrada": self.corrida.analisis_entrada_id,
                "litros_entrada": "1000",
                "producto_descremada": polvo.pk,
                "producto_crema": self.producto_crema.pk,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertIn("producto_descremada", respuesta.data)

    def test_inicio_reserva_origen_y_capacidad_y_cierre_consume_reservas(self):
        iniciar_descremacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        self.assertEqual(
            ReservaSiloProceso.objects.filter(
                ejecucion=self.ejecucion, estado=ReservaSiloProceso.Estado.ACTIVA,
            ).count(),
            3,
        )

        cerrar_descremacion(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            litros_descremada=900, grasa_descremada="0.1",
            litros_crema=90, grasa_crema="40",
        )

        reservas = ReservaSiloProceso.objects.filter(ejecucion=self.ejecucion)
        self.assertFalse(reservas.filter(estado=ReservaSiloProceso.Estado.ACTIVA).exists())
        self.assertEqual(
            set(reservas.values_list("estado", flat=True)),
            {ReservaSiloProceso.Estado.CONSUMIDA},
        )

    def test_cancelar_libera_las_reservas_de_tk(self):
        iniciar_descremacion(corrida_id=self.corrida.pk, usuario=self.usuario)

        transicionar_ejecucion(
            ejecucion_id=self.ejecucion.pk,
            estado_nuevo=EjecucionProceso.Estado.CANCELADA,
            usuario=self.usuario,
            motivo="Operación suspendida",
        )

        self.assertFalse(ReservaSiloProceso.objects.filter(
            ejecucion=self.ejecucion, estado=ReservaSiloProceso.Estado.ACTIVA,
        ).exists())
        self.assertEqual(
            set(ReservaSiloProceso.objects.filter(
                ejecucion=self.ejecucion
            ).values_list("estado", flat=True)),
            {ReservaSiloProceso.Estado.LIBERADA},
        )

    def test_no_inicia_si_el_plan_supera_capacidad_del_tk(self):
        self.crema.capacidad_l = Decimal("50")
        self.crema.save(update_fields=["capacidad_l"])

        with self.assertRaisesMessage(ValidationError, "no tiene capacidad"):
            iniciar_descremacion(corrida_id=self.corrida.pk, usuario=self.usuario)

        self.assertFalse(ReservaSiloProceso.objects.filter(
            ejecucion=self.ejecucion
        ).exists())
        self.assertFalse(self.ejecucion.entradas.exists())

    def test_un_tk_con_reserva_activa_no_se_asigna_a_otra_corrida(self):
        self.corrida.litros_entrada = Decimal("500")
        self.corrida.litros_descremada_plan = Decimal("450")
        self.corrida.litros_crema_plan = Decimal("45")
        self.corrida.save(update_fields=[
            "litros_entrada", "litros_descremada_plan", "litros_crema_plan",
        ])
        iniciar_descremacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        segundo_equipo = Equipo.objects.create(
            sucursal=self.sucursal, codigo="DES-2", nombre="Descremadora 2",
            tipo=Equipo.Tipo.DESCREMADORA,
        )
        segunda_ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-DES-2", etapa=self.ejecucion.etapa,
            sucursal=self.sucursal, equipo=segundo_equipo,
            responsable=self.usuario,
        )
        segunda = CorridaDescremacion.objects.create(
            ejecucion=segunda_ejecucion, silo_entera=self.origen,
            analisis_entrada=self.corrida.analisis_entrada,
            litros_entrada=Decimal("100"), grasa_entrada=Decimal("4"),
            sng_entrada=Decimal("8.7"), silo_descremada=self.descremada,
            estanque_crema=self.crema,
            producto_descremada=self.producto_descremada,
            producto_crema=self.producto_crema,
            litros_descremada_plan=Decimal("90"),
            litros_crema_plan=Decimal("9"),
            fuente_plan={"metodo": "prueba"},
            plan_confirmado_por=self.usuario,
            plan_confirmado_en=timezone.now(),
        )

        with self.assertRaisesMessage(ValidationError, "ya está reservado"):
            iniciar_descremacion(corrida_id=segunda.pk, usuario=self.usuario)

        self.assertFalse(ReservaSiloProceso.objects.filter(
            ejecucion=segunda_ejecucion
        ).exists())

    def test_cierre_genera_dos_saldos_y_hereda_fifo_en_una_operacion(self):
        iniciar_descremacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        resultado = cerrar_descremacion(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            litros_descremada=900, grasa_descremada=Decimal("0.1"),
            litros_crema=90, grasa_crema=Decimal("40"),
            controles={"ph_salida": "6.7"},
        )

        movimientos = MovimientoSilo.objects.filter(operacion_id=self.corrida.operacion_id)
        self.assertEqual(movimientos.count(), 3)
        self.assertEqual(resultado.estado, CorridaDescremacion.Estado.CERRADA)
        self.assertEqual(resultado.ejecucion.salidas.count(), 3)
        merma = resultado.ejecucion.salidas.get(
            naturaleza=SalidaProceso.Naturaleza.MERMA
        )
        self.assertEqual(merma.cantidad, Decimal("10"))
        self.assertEqual(
            sum(m.atribuciones_recepcion.count() for m in movimientos.filter(tipo="ingreso")),
            2,
        )
        self.assertTrue(resultado.controles["avisos_balance"])

    def test_continuacion_usa_la_primera_etapa_de_la_ruta_de_la_rama(self):
        proceso_secado = Proceso.objects.create(codigo="rama-sec", nombre="Rama secado")
        etapa_secado = EtapaProceso.objects.create(
            proceso=proceso_secado, codigo="secar-rama", nombre="Secar rama",
            tipo=EtapaProceso.Tipo.SECADO, orden=1,
        )
        ruta = RutaProducto.objects.create(
            sucursal=self.sucursal, producto=self.producto_descremada,
            proceso=proceso_secado,
        )
        torre = Equipo.objects.create(
            sucursal=self.sucursal, codigo="TORRE-RAMA", nombre="Torre rama",
            tipo=Equipo.Tipo.TORRE,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=self.ejecucion, lote=None, silo=self.descremada,
            producto=self.producto_descremada, ruta_producto=ruta,
            destino=SalidaProceso.Destino.SIGUIENTE_PROCESO,
            cantidad=Decimal("300"), unidad="L",
        )
        LiberacionProceso.objects.create(
            salida=salida, analisis_silo=self.corrida.analisis_entrada,
            estado=LiberacionProceso.Estado.LIBERADO,
            decidida_por=self.usuario, decidida_en=timezone.now(),
        )
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=self.sucursal.empresa,
            sucursal=self.sucursal, rol=Rol.PRODUCCION,
            area=PerfilUsuario.Area.CONDENSACION,
        )
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        disponibles = cliente.get("/api/procesos/salidas/disponibles/")
        self.assertEqual(disponibles.status_code, 200, disponibles.data)
        material = next(item for item in disponibles.data if item["id"] == salida.pk)
        self.assertEqual(material["etapas_siguientes"][0]["id"], etapa_secado.pk)
        self.assertEqual(
            material["acciones_permitidas"],
            [{"codigo": "continuar_secado", "etiqueta": "Continuar a Secado"}],
        )

        ejecucion = preparar_continuacion(
            salida_id=salida.pk, etapa_id=etapa_secado.pk,
            equipo_id=torre.pk, cantidad="100", usuario=self.usuario,
        )

        self.assertEqual(ejecucion.etapa, etapa_secado)
        self.assertEqual(ejecucion.ruta_producto, ruta)
        self.assertEqual(ejecucion.estado, EjecucionProceso.Estado.PREPARACION)

    def test_disponibles_puede_cargarse_solo_para_un_silo(self):
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=self.sucursal.empresa,
            sucursal=self.sucursal, rol=Rol.PRODUCCION,
            area=PerfilUsuario.Area.CONDENSACION,
        )
        salida_descremada = SalidaProceso.objects.create(
            ejecucion=self.ejecucion, silo=self.descremada,
            producto=self.producto_descremada,
            cantidad=Decimal("300"), unidad="L",
        )
        salida_crema = SalidaProceso.objects.create(
            ejecucion=self.ejecucion, silo=self.crema,
            producto=self.producto_crema,
            cantidad=Decimal("50"), unidad="L",
        )
        for salida in (salida_descremada, salida_crema):
            LiberacionProceso.objects.create(
                salida=salida,
                analisis_silo=self.corrida.analisis_entrada,
                estado=LiberacionProceso.Estado.LIBERADO,
                decidida_por=self.usuario,
                decidida_en=timezone.now(),
            )
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)

        respuesta = cliente.get(
            "/api/procesos/salidas/disponibles/",
            {"silo": self.descremada.pk},
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(
            [item["id"] for item in respuesta.data],
            [salida_descremada.pk],
        )

    def test_calidad_decide_descremada_y_crema_por_separado(self):
        Especificacion.objects.create(
            producto=self.producto_descremada, version=1,
            vigente_desde=timezone.localdate() - timedelta(days=1),
            rangos={"mg": {"min": 0, "max": 0.2, "obligatorio": True}},
        )
        Especificacion.objects.create(
            producto=self.producto_crema, version=1,
            vigente_desde=timezone.localdate() - timedelta(days=1),
            rangos={"mg": {"min": 35, "max": 45, "obligatorio": True}},
        )
        self.ejecucion.etapa.requiere_calidad = True
        self.ejecucion.etapa.save(update_fields=["requiere_calidad"])
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=self.sucursal.empresa, sucursal=self.sucursal,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.CONDENSACION,
        )
        etapa_siguiente = EtapaProceso.objects.create(
            proceso=self.ejecucion.etapa.proceso, codigo="continuar",
            nombre="Secado", tipo=EtapaProceso.Tipo.SECADO, orden=2,
        )
        torre = Equipo.objects.create(
            sucursal=self.sucursal, codigo="TORRE-D", nombre="Torre de secado",
            tipo=Equipo.Tipo.TORRE,
        )
        ejecucion_siguiente = EjecucionProceso.objects.create(
            codigo="EJ-DES-SIG", etapa=etapa_siguiente, sucursal=self.sucursal,
            responsable=self.usuario,
        )
        iniciar_descremacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        cerrar_descremacion(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            litros_descremada=900, grasa_descremada="0.1",
            litros_crema=90, grasa_crema="40",
        )
        self.ejecucion.refresh_from_db()
        self.descremada.refresh_from_db()
        self.crema.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.PENDIENTE_CONTROL)
        self.assertEqual(self.descremada.estado, Silo.Estado.BLOQUEADO_CALIDAD)
        self.assertEqual(self.crema.estado, Silo.Estado.BLOQUEADO_CALIDAD)

        analisis = {}
        for silo, grasa, sng in (
            (self.descremada, "0.10", "8.70"),
            (self.crema, "40.00", "5.00"),
        ):
            analisis[silo.pk] = AnalisisSilo.objects.create(
                silo=silo, tomado_en=timezone.now(), grasa=grasa, sng=sng,
                densidad=Decimal("1020") if silo == self.crema else Decimal("1032"),
                inhibidores_resultado="negativo", metodo="snap",
                hora_lectura=timezone.localtime().time(),
                estado=AnalisisSilo.Estado.CONFIRMADO,
                analista=self.usuario, visualizado_por=self.usuario,
            )
        calidad = User.objects.create_user("calidad-descremacion")
        PerfilUsuario.objects.create(
            usuario=calidad, empresa=self.sucursal.empresa, sucursal=self.sucursal,
            rol=Rol.CALIDAD, area=PerfilUsuario.Area.CALIDAD,
        )
        cliente = APIClient()
        cliente.force_authenticate(calidad)
        salidas = {salida.silo_id: salida for salida in self.ejecucion.salidas.all()}
        produccion = APIClient()
        produccion.force_authenticate(self.usuario)
        bloqueada = produccion.post(
            "/api/procesos/entradas/",
            {
                "ejecucion": ejecucion_siguiente.pk,
                "silo": self.descremada.pk,
                "salida_origen": salidas[self.descremada.pk].pk,
                "cantidad": "400",
                "unidad": "L",
            },
            format="json",
        )
        self.assertEqual(bloqueada.status_code, 400)
        cola = cliente.get(
            "/api/calidad/expedientes/", {"incluir_procesos": "1"}
        )
        self.assertEqual(cola.status_code, 200, cola.data)
        self.assertEqual(
            {item["producto_nombre"] for item in cola.data["procesos"]},
            {"Leche descremada", "Crema"},
        )

        primera = cliente.post(
            f"/api/calidad/resultados-proceso/{salidas[self.descremada.pk].pk}/liberar/",
            {"analisis_id": analisis[self.descremada.pk].pk}, format="json",
        )
        self.assertEqual(primera.status_code, 200, primera.data)
        self.ejecucion.refresh_from_db()
        self.crema.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.PENDIENTE_CONTROL)
        self.assertEqual(self.crema.estado, Silo.Estado.BLOQUEADO_CALIDAD)
        entrada = produccion.post(
            "/api/procesos/entradas/",
            {
                "ejecucion": ejecucion_siguiente.pk,
                "silo": self.descremada.pk,
                "salida_origen": salidas[self.descremada.pk].pk,
                "cantidad": "400",
                "unidad": "L",
            },
            format="json",
        )
        self.assertEqual(entrada.status_code, 201, entrada.data)

        segunda = cliente.post(
            f"/api/calidad/resultados-proceso/{salidas[self.crema.pk].pk}/liberar/",
            {"analisis_id": analisis[self.crema.pk].pk}, format="json",
        )
        self.assertEqual(segunda.status_code, 200, segunda.data)
        lote_crema = salidas[self.crema.pk].lote
        lote_crema.refresh_from_db()
        self.assertEqual(lote_crema.estado, lote_crema.Estado.PRODUCIDO)
        self.assertEqual(lote_crema.kg_producidos, Decimal("91.80"))
        lote_descremada = salidas[self.descremada.pk].lote
        lote_descremada.refresh_from_db()
        self.assertEqual(lote_descremada.estado, lote_descremada.Estado.PRODUCIDO)
        self.assertEqual(lote_descremada.kg_producidos, Decimal("928.80"))
        self.ejecucion.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.CERRADA)
        disponibles = produccion.get("/api/procesos/salidas/disponibles/")
        self.assertEqual(disponibles.status_code, 200, disponibles.data)
        descremada = next(
            item for item in disponibles.data if item["id"] == salidas[self.descremada.pk].pk
        )
        self.assertEqual(descremada["cantidad_disponible"], Decimal("500"))
        self.assertEqual(descremada["lote_codigo"], lote_descremada.codigo_lote)
        self.assertEqual(descremada["producto_nombre"], "Leche descremada intermedia")
        self.assertEqual(descremada["estado_material"], "liberado")
        self.assertEqual(descremada["densidad_kg_m3"], Decimal("1032.000"))
        self.assertEqual(descremada["cantidad_consumida_kg"], Decimal("412.800"))
        self.assertEqual(descremada["cantidad_disponible_kg"], Decimal("516.000"))
        self.assertEqual(
            descremada["etapas_siguientes"][0]["equipos"][0]["id"], torre.pk
        )
        continuacion = produccion.post(
            f"/api/procesos/salidas/{salidas[self.descremada.pk].pk}/preparar-continuacion/",
            {"etapa": etapa_siguiente.pk, "equipo": torre.pk, "cantidad": "200"},
            format="json",
        )
        self.assertEqual(continuacion.status_code, 201, continuacion.data)
        self.assertEqual(
            continuacion.data["estado"], EjecucionProceso.Estado.PREPARACION
        )
        self.assertEqual(
            continuacion.data["entradas"][0]["salida_origen"],
            salidas[self.descremada.pk].pk,
        )
        listado = produccion.get("/api/procesos/descremaciones/")
        self.assertEqual(listado.status_code, 200, listado.data)
        corrida = listado.data["results"][0]
        self.assertEqual(corrida["producto_descremada_nombre"], "Leche descremada intermedia")
        self.assertEqual(corrida["producto_crema_nombre"], "Crema intermedia para mantequilla")
        self.assertIn("iniciada_por_nombre", corrida)
