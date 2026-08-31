"""
Pruebas de la API de producción.

Verifican lo que el frontend va a consumir: que el resultado de calidad llega
calculado, que el resumen informa su cobertura y que un listado no dispara una
consulta por lote.
"""

from datetime import date
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from estandarizacion.models import ValeEstandarizacion
from maestros.models import Especificacion, Mandante, Producto, Silo
from recepcion.models import MovimientoSilo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal
from usuarios.tests_helpers import credencial_sesion

from .models import Analisis, Lote
from .serializers import LoteSerializer
from .views import LoteViewSet


class BaseAPI(TestCase):
    def setUp(self):
        # La API exige identificarse y tener el rol que corresponde. Quién
        # puede escribir qué se prueba en usuarios/tests_permisos.py; aquí se
        # prueba el camino autorizado, con el rol que registra lotes.
        self.empresa = Empresa.objects.create(rut="API-PROD", nombre="API Producción")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, codigo="PLANTA", nombre="Planta pruebas"
        )
        usuario = User.objects.create_user(username="pruebas", password="x")
        PerfilUsuario.objects.create(
            usuario=usuario,
            rol=Rol.PRODUCCION,
            area=PerfilUsuario.Area.SECADO,
            empresa=self.empresa,
            sucursal=self.sucursal,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {credencial_sesion(usuario)}"
        )

        self.nestle = Mandante.objects.create(empresa=self.empresa, nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.nestle,
        )
        Especificacion.objects.create(
            producto=self.producto,
            version=1,
            vigente_desde=date(2026, 1, 1),
            rangos={
                "humedad": {"min": 2.0, "max": 4.0, "obligatorio": True},
                "mg": {"min": 26.0, "max": 28.0, "obligatorio": True},
            },
        )

    def _lote(self, codigo="CCAA6140N", **extra):
        datos = {
            "sucursal": self.sucursal,
            "codigo_lote": codigo,
            "producto": self.producto,
            "fecha": date(2026, 7, 20),
            "kg_producidos": 10000,
        }
        datos.update(extra)
        return Lote.objects.create(**datos)


class TransicionesDeEstadoTests(BaseAPI):
    """
    `Lote.TRANSICIONES` estaba declarado desde el primer día y no lo comprobaba
    nadie: por la API se podía saltar de `en_proceso` a `cerrado` sin pasar por
    `producido`, o devolver a producción un lote anulado.

    Importa porque el estado del lote decide si llega a Calidad, y el histórico
    se audita: un lote anulado que revive es un registro que dice algo falso
    sobre lo que pasó en planta.
    """

    def _patch(self, lote, estado):
        return self.cliente.patch(
            f"/api/produccion/lotes/{lote.id}/", {"estado": estado}, format="json"
        )

    def test_el_camino_normal_se_permite(self):
        lote = self._lote(estado=Lote.Estado.EN_PROCESO)

        self.assertEqual(self._patch(lote, "producido").status_code, 200)

        lote.refresh_from_db()
        self.assertEqual(lote.estado, Lote.Estado.PRODUCIDO)

        self.assertEqual(self._patch(lote, "cerrado").status_code, 200)

    def test_no_se_salta_un_estado_intermedio(self):
        lote = self._lote(estado=Lote.Estado.EN_PROCESO)

        respuesta = self._patch(lote, "cerrado")
        lote.refresh_from_db()

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(lote.estado, Lote.Estado.EN_PROCESO)

    def test_un_lote_cerrado_no_vuelve_a_produccion(self):
        lote = self._lote(estado=Lote.Estado.CERRADO)

        respuesta = self._patch(lote, "en_proceso")
        lote.refresh_from_db()

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(lote.estado, Lote.Estado.CERRADO)

    def test_un_lote_anulado_no_revive(self):
        lote = self._lote(estado=Lote.Estado.ANULADO)

        respuesta = self._patch(lote, "producido")
        lote.refresh_from_db()

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(lote.estado, Lote.Estado.ANULADO)

    def test_el_rechazo_dice_a_donde_si_se_puede_ir(self):
        """Un 400 que solo dice «no» obliga a adivinar el estado correcto."""
        lote = self._lote(estado=Lote.Estado.EN_PROCESO)

        mensaje = str(self._patch(lote, "cerrado").json())

        self.assertIn("producido", mensaje)
        self.assertIn("anulado", mensaje)

    def test_al_cambiar_el_estado_devuelve_el_lote_entero(self):
        """
        La respuesta de un PATCH sobre un lote trae sus análisis, igual que el
        detalle. Devolver menos dejaba la ficha de Producción a medias al
        cerrar un lote: la pantalla se quedaba sin `analisis` y reventaba.
        """
        lote = self._lote(estado=Lote.Estado.EN_PROCESO)
        Analisis.objects.create(
            lote=lote, fecha=date(2026, 7, 20), valores={"humedad": 3.0, "mg": 27.0}
        )

        datos = self._patch(lote, "producido").json()

        self.assertIn("analisis", datos)
        self.assertIn("pallets_resumen", datos)
        self.assertEqual(datos["pallets_resumen"]["total"], 0)
        self.assertEqual(len(datos["analisis"]), 1)
        self.assertEqual(datos["estado"], "producido")

    def test_guardar_sin_cambiar_el_estado_no_molesta(self):
        """
        Editar un lote no debe tropezar con la máquina de estados: el
        formulario reenvía el estado actual junto con lo demás.
        """
        lote = self._lote(estado=Lote.Estado.PRODUCIDO)

        respuesta = self.cliente.patch(
            f"/api/produccion/lotes/{lote.id}/",
            {"estado": "producido", "bultos": 42},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        lote.refresh_from_db()
        self.assertEqual(lote.bultos, 42)


class EdicionDeLoteTests(BaseAPI):
    """
    Editar un lote se permite, con dos guardas: no después de cerrarlo, y no
    mientras Calidad lo tenga firmado.
    """

    def _patch(self, lote, **campos):
        return self.cliente.patch(
            f"/api/produccion/lotes/{lote.id}/", campos, format="json"
        )

    def _liberar(self, lote):
        """Deja el lote con una liberación firmada, como quedaría tras firmar."""
        from calidad.models import Liberacion

        firmante = User.objects.create_user(
            username=f"calidad-{lote.id}", password="x", first_name="M.", last_name="Rivas"
        )
        PerfilUsuario.objects.create(
            usuario=firmante,
            rol=Rol.CALIDAD,
            area=PerfilUsuario.Area.CALIDAD,
            empresa=self.empresa,
            sucursal=self.sucursal,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )

        return Liberacion.objects.create(
            lote=lote,
            estado=Liberacion.Estado.LIBERADO,
            autorizada_por=firmante,
            autorizada_en=timezone.now(),
        )

    def test_se_editan_los_datos_de_un_lote_en_proceso(self):
        lote = self._lote(estado=Lote.Estado.EN_PROCESO)

        respuesta = self._patch(lote, kg_producidos="11500.00", bultos=230, turno="B")
        lote.refresh_from_db()

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(str(lote.kg_producidos), "11500.00")
        self.assertEqual(lote.bultos, 230)
        self.assertEqual(lote.turno, "B")

    def test_tambien_se_edita_un_lote_producido(self):
        """Producido no es final: todavía se corrige lo que se tecleó mal."""
        lote = self._lote(estado=Lote.Estado.PRODUCIDO)

        self.assertEqual(self._patch(lote, bultos=99).status_code, 200)

    def test_un_lote_cerrado_no_se_edita(self):
        lote = self._lote(estado=Lote.Estado.CERRADO)

        respuesta = self._patch(lote, kg_producidos="1.00")
        lote.refresh_from_db()

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("histórico", str(respuesta.json()))
        self.assertNotEqual(str(lote.kg_producidos), "1.00")

    def test_un_lote_anulado_tampoco(self):
        lote = self._lote(estado=Lote.Estado.ANULADO)

        self.assertEqual(self._patch(lote, bultos=5).status_code, 400)

    def test_no_se_cambian_los_kilos_de_un_lote_liberado(self):
        """
        Es la guarda que importa: la firma de Calidad respalda unos kilos
        concretos, y Despachos descuenta de ahí.
        """
        lote = self._lote(estado=Lote.Estado.PRODUCIDO)
        self._liberar(lote)

        respuesta = self._patch(lote, kg_producidos="99999.00")
        lote.refresh_from_db()

        self.assertEqual(respuesta.status_code, 400)
        self.assertNotEqual(str(lote.kg_producidos), "99999.00")

    def test_el_rechazo_dice_como_desbloquearlo(self):
        lote = self._lote(estado=Lote.Estado.PRODUCIDO)
        self._liberar(lote)

        mensaje = str(self._patch(lote, bultos=7).json())

        self.assertIn("revisar/", mensaje)

    def test_la_observacion_si_se_anota_en_un_lote_liberado(self):
        """Anotar no cambia lo que se produjo, así que no toca la firma."""
        lote = self._lote(estado=Lote.Estado.PRODUCIDO)
        self._liberar(lote)

        respuesta = self._patch(lote, observacion="Revisar el peso con bodega.")
        lote.refresh_from_db()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("bodega", lote.observacion)

    def test_la_ficha_avisa_de_la_liberacion_antes_de_editar(self):
        """
        La pantalla necesita saberlo por adelantado. Si no, ofrece «Editar»,
        alguien llena el formulario y descubre el rechazo al guardar.
        """
        lote = self._lote(estado=Lote.Estado.PRODUCIDO)
        self._liberar(lote)

        datos = self.cliente.get(f"/api/produccion/lotes/{lote.id}/").json()

        self.assertTrue(datos["liberacion"]["liberado"])
        self.assertEqual(datos["liberacion"]["autorizada_por_nombre"], "M. Rivas")

    def test_un_lote_sin_expediente_lo_dice_con_null(self):
        lote = self._lote(estado=Lote.Estado.PRODUCIDO)

        datos = self.cliente.get(f"/api/produccion/lotes/{lote.id}/").json()

        self.assertIsNone(datos["liberacion"])

    def test_guardar_los_mismos_valores_no_molesta(self):
        """Reenviar el formulario sin tocar nada no debe dar error."""
        lote = self._lote(estado=Lote.Estado.CERRADO)

        respuesta = self._patch(lote, kg_producidos=str(lote.kg_producidos))

        self.assertEqual(respuesta.status_code, 200)


class LotesAPITests(BaseAPI):
    def test_calidad_puede_registrar_el_analisis_del_lote(self):
        lote = self._lote()
        usuario = User.objects.create_user(username="calidad-analisis", password="x")
        PerfilUsuario.objects.create(
            usuario=usuario,
            rol=Rol.CALIDAD,
            area=PerfilUsuario.Area.CALIDAD,
            empresa=self.empresa,
            sucursal=self.sucursal,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {credencial_sesion(usuario)}")

        respuesta = cliente.post(
            "/api/produccion/analisis/",
            {
                "lote": lote.pk,
                "fecha": "2026-07-20",
                "muestra": "M-CAL-01",
                "valores": {"humedad": 3.0, "mg": 27.0},
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertTrue(Analisis.objects.filter(lote=lote, muestra="M-CAL-01").exists())

    def test_calidad_recibe_los_parametros_que_faltan_en_un_analisis(self):
        lote = self._lote()

        respuesta = self.cliente.post(
            "/api/produccion/analisis/",
            {"lote": lote.pk, "fecha": "2026-07-20", "valores": {"humedad": 3.0}},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("mg", str(respuesta.data["valores"]))

    def test_un_lote_no_admite_mas_de_dos_analisis(self):
        lote = self._lote()
        for numero in range(2):
            Analisis.objects.create(
                lote=lote, fecha=lote.fecha, muestra=f"M-{numero + 1}",
                valores={"humedad": 3.0, "mg": 27.0},
            )

        respuesta = self.cliente.post(
            "/api/produccion/analisis/",
            {
                "lote": lote.pk, "fecha": "2026-07-20", "muestra": "M-3",
                "valores": {"humedad": 3.0, "mg": 27.0},
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("máximo de 2", str(respuesta.data["lote"]))

    def test_el_listado_trae_el_resultado_de_calidad_calculado(self):
        lote = self._lote()
        Analisis.objects.create(
            lote=lote, fecha=date(2026, 7, 20), valores={"humedad": 3.0, "mg": 27.0}
        )

        respuesta = self.cliente.get("/api/produccion/lotes/")

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()["results"][0]
        self.assertEqual(datos["calidad"]["resultado"], "conforme")
        self.assertEqual(datos["calidad"]["etiqueta"], "Conforme")
        self.assertEqual(datos["calidad"]["evaluados"], 1)

    def test_un_lote_fuera_de_rango_informa_la_desviacion(self):
        lote = self._lote()
        Analisis.objects.create(
            lote=lote,
            fecha=date(2026, 7, 20),
            muestra="M-01",
            valores={"humedad": 9.0, "mg": 27.0},
        )

        datos = self.cliente.get("/api/produccion/lotes/").json()["results"][0]

        self.assertEqual(datos["calidad"]["resultado"], "no_conforme")
        desviacion = datos["calidad"]["desviaciones"][0]
        self.assertEqual(desviacion["parametro"], "humedad")
        self.assertEqual(desviacion["desvio"], "alto")
        self.assertEqual(desviacion["muestra"], "M-01")

    def test_la_ficha_de_un_lote_incluye_sus_analisis(self):
        lote = self._lote()
        Analisis.objects.create(
            lote=lote, fecha=date(2026, 7, 20), valores={"humedad": 3.0, "mg": 27.0}
        )

        datos = self.cliente.get(f"/api/produccion/lotes/{lote.id}/").json()

        self.assertEqual(len(datos["analisis"]), 1)

    def test_se_puede_crear_un_lote(self):
        respuesta = self.cliente.post(
            "/api/produccion/lotes/",
            {
                "codigo_lote": "CCAA6142N",
                "producto": self.producto.id,
                "fecha": "2026-07-22",
                "kg_producidos": "8000.00",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(Lote.objects.count(), 1)

    def test_rechaza_un_analisis_con_parametros_inventados(self):
        lote = self._lote()

        respuesta = self.cliente.post(
            "/api/produccion/analisis/",
            {"lote": lote.id, "fecha": "2026-07-20", "valores": {"inventado": 1}},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("valores", respuesta.json())

    def test_filtra_por_producto(self):
        otro = Producto.objects.create(
            nombre="Crema", familia=Producto.Familia.CREMA, mandante=self.nestle
        )
        self._lote()
        self._lote(codigo="CR-01", producto=otro)

        datos = self.cliente.get(
            f"/api/produccion/lotes/?producto={otro.id}"
        ).json()

        self.assertEqual(datos["count"], 1)
        self.assertEqual(datos["results"][0]["codigo_lote"], "CR-01")

    def test_filtra_por_resultado_de_calidad(self):
        """
        El veredicto no está en la base: se calcula. El filtro tiene que
        funcionar igual, y seguir paginando.
        """
        bueno = self._lote(codigo="L-OK")
        Analisis.objects.create(
            lote=bueno, fecha=date(2026, 7, 20), valores={"humedad": 3.0, "mg": 27.0}
        )
        malo = self._lote(codigo="L-MAL")
        Analisis.objects.create(
            lote=malo, fecha=date(2026, 7, 20), valores={"humedad": 9.0, "mg": 27.0}
        )
        self._lote(codigo="L-SIN")

        for resultado, esperado in [
            ("conforme", ["L-OK"]),
            ("no_conforme", ["L-MAL"]),
            ("sin_analisis", ["L-SIN"]),
        ]:
            datos = self.cliente.get(
                f"/api/produccion/lotes/?calidad={resultado}"
            ).json()

            self.assertEqual(
                [l["codigo_lote"] for l in datos["results"]], esperado, resultado
            )

    def test_el_filtro_de_calidad_se_combina_con_los_demas(self):
        crema = Producto.objects.create(
            nombre="Crema", familia=Producto.Familia.CREMA, mandante=self.nestle
        )
        bueno = self._lote(codigo="L-OK")
        Analisis.objects.create(
            lote=bueno, fecha=date(2026, 7, 20), valores={"humedad": 3.0, "mg": 27.0}
        )
        self._lote(codigo="CR-01", producto=crema)

        datos = self.cliente.get(
            f"/api/produccion/lotes/?calidad=conforme&producto={crema.id}"
        ).json()

        self.assertEqual(datos["count"], 0)

    def test_busca_por_codigo_de_lote(self):
        self._lote(codigo="CCAA6140N")
        self._lote(codigo="CCAA6141N")

        datos = self.cliente.get("/api/produccion/lotes/?buscar=6141").json()

        self.assertEqual(datos["count"], 1)

    def test_no_se_puede_borrar_un_lote(self):
        lote = self._lote()

        respuesta = self.cliente.delete(f"/api/produccion/lotes/{lote.id}/")

        self.assertEqual(respuesta.status_code, 405)
        self.assertEqual(Lote.objects.count(), 1)
        self.assertIn("anulado", respuesta.json()["detail"])

    def test_anular_exige_motivo_y_conserva_el_lote(self):
        lote = self._lote(estado=Lote.Estado.EN_PROCESO)

        sin_motivo = self.cliente.patch(
            f"/api/produccion/lotes/{lote.id}/", {"estado": "anulado"}, format="json"
        )
        self.assertEqual(sin_motivo.status_code, 400)

        respuesta = self.cliente.patch(
            f"/api/produccion/lotes/{lote.id}/",
            {"estado": "anulado", "motivo_anulacion": "Orden cancelada por planificación."},
            format="json",
        )
        lote.refresh_from_db()

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(lote.estado, Lote.Estado.ANULADO)
        self.assertIn("Orden cancelada", lote.observacion)

    def test_el_listado_no_dispara_una_consulta_por_lote(self):
        """
        Con prefetch, agregar lotes no debe agregar consultas. Sin él, esto
        crecería con cada lote y el panel se volvería lento con datos reales.
        """
        silo = Silo.objects.create(
            sucursal=self.sucursal,
            codigo="S-PERF-LOTES",
            tipo=Silo.Tipo.SILO,
            capacidad_l=50000,
        )
        vale = ValeEstandarizacion.objects.create(
            codigo="V-PERF-LOTES",
            fecha=date(2026, 7, 20),
            producto=self.producto,
            silo_destino=silo,
        )
        for i in range(5):
            lote = self._lote(codigo=f"L-{i}", vale=vale)
            Analisis.objects.create(
                lote=lote, fecha=date(2026, 7, 20), valores={"humedad": 3.0, "mg": 27.0}
            )
            MovimientoSilo.objects.create(
                silo=silo,
                tipo=MovimientoSilo.Tipo.SALIDA,
                litros=1000 + i,
                fecha_hora=timezone.now(),
                origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
                origen_id=lote.pk,
            )

        # 1 valida el token, 1 cuenta para paginar, 1 trae los lotes, 1 trae
        # todos sus análisis de una vez y 1 las especificaciones. Ninguna
        # depende del número de lotes.
        with self.assertNumQueries(5):
            respuesta = self.cliente.get("/api/produccion/lotes/")

        self.assertEqual(
            sorted(fila["litros_procesados"] for fila in respuesta.json()["results"]),
            [1000.0, 1001.0, 1002.0, 1003.0, 1004.0],
        )

    def test_un_patch_no_reutiliza_litros_anotados_antes_de_guardar(self):
        silos = [
            Silo.objects.create(
                sucursal=self.sucursal,
                codigo=f"S-PATCH-{numero}",
                tipo=Silo.Tipo.SILO,
                capacidad_l=50000,
            )
            for numero in (1, 2)
        ]
        vales = [
            ValeEstandarizacion.objects.create(
                codigo=f"V-PATCH-{numero}",
                fecha=date(2026, 7, 20),
                producto=self.producto,
                silo_destino=silo,
            )
            for numero, silo in enumerate(silos, 1)
        ]
        lote = self._lote(vale=vales[0])
        for silo, litros in zip(silos, (100, 200)):
            MovimientoSilo.objects.create(
                silo=silo,
                tipo=MovimientoSilo.Tipo.SALIDA,
                litros=litros,
                fecha_hora=timezone.now(),
                origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
                origen_id=lote.pk,
            )

        instancia = LoteViewSet.queryset.get(pk=lote.pk)
        serializador_lote = LoteSerializer(instancia)
        self.assertEqual(
            serializador_lote.get_litros_procesados(instancia), 100.0
        )

        class SerializerGuardado:
            def __init__(self, objeto):
                self.instance = objeto

            def save(self):
                self.instance.vale = vales[1]
                self.instance.save(update_fields=["vale"])

        serializer = SerializerGuardado(instancia)
        vista = LoteViewSet()
        vista.request = SimpleNamespace(data={})
        vista.perform_update(serializer)

        self.assertFalse(hasattr(instancia, "litros_procesados_anotados"))
        self.assertEqual(
            serializador_lote.get_litros_procesados(instancia), 200.0
        )


class ResumenAPITests(BaseAPI):
    def test_el_resumen_informa_su_cobertura(self):
        """
        Un 100 % de cumplimiento sobre 1 lote de 3 no es una buena noticia:
        el panel tiene que poder decirlo.
        """
        conforme = self._lote(codigo="L-1")
        Analisis.objects.create(
            lote=conforme, fecha=date(2026, 7, 20), valores={"humedad": 3.0, "mg": 27.0}
        )
        self._lote(codigo="L-2")
        self._lote(codigo="L-3")

        datos = self.cliente.get("/api/produccion/resumen/").json()

        self.assertEqual(datos["lotes"], 3)
        self.assertEqual(datos["kg_producidos"], 30000.0)
        self.assertEqual(datos["calidad"]["conforme"], 1)
        self.assertEqual(datos["calidad"]["sin_analisis"], 2)
        self.assertEqual(datos["calidad"]["evaluados"], 1)
        self.assertEqual(datos["calidad"]["cumplimiento"], 100.0)
        self.assertAlmostEqual(datos["calidad"]["cobertura"], 33.3)

    def test_el_resumen_agrupa_kilos_por_producto_y_mandante(self):
        crema = Producto.objects.create(
            nombre="Crema", familia=Producto.Familia.CREMA, mandante=self.nestle
        )
        self._lote(codigo="L-1", kg_producidos=10000)
        self._lote(codigo="L-2", producto=crema, kg_producidos=4000)

        datos = self.cliente.get("/api/produccion/resumen/").json()

        self.assertEqual(datos["kg_por_producto"][0]["kg"], 10000.0)
        self.assertEqual(len(datos["kg_por_producto"]), 2)
        self.assertEqual(datos["kg_por_mandante"][0]["nombre"], "Nestlé")
        self.assertEqual(datos["kg_por_mandante"][0]["kg"], 14000.0)

    def test_los_lotes_anulados_no_entran_al_resumen(self):
        self._lote(codigo="L-1")
        self._lote(codigo="L-2", estado=Lote.Estado.ANULADO)

        datos = self.cliente.get("/api/produccion/resumen/").json()

        self.assertEqual(datos["lotes"], 1)
        self.assertEqual(datos["kg_producidos"], 10000.0)

    def test_sin_lotes_no_inventa_porcentajes(self):
        datos = self.cliente.get("/api/produccion/resumen/").json()

        self.assertEqual(datos["lotes"], 0)
        self.assertIsNone(datos["calidad"]["cobertura"])
        self.assertIsNone(datos["calidad"]["cumplimiento"])

    def test_acota_por_periodo(self):
        self._lote(codigo="L-1", fecha=date(2026, 7, 1))
        self._lote(codigo="L-2", fecha=date(2026, 8, 1))

        datos = self.cliente.get(
            "/api/produccion/resumen/?desde=2026-07-15"
        ).json()

        self.assertEqual(datos["lotes"], 1)
