"""
Pruebas de la API de liberación.

Verifican lo que el frontend va a consumir y, sobre todo, lo que la API no
debe dejar hacer: firmar por una vía que se salte la regla, o estampar una
firma con datos que vengan del navegador.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from inventario.models import Bodega, ExistenciaProductoTerminado, Ubicacion
from maestros.models import DocumentoLiberacion, Equipo, Especificacion, Mandante, Producto
from produccion.models import Analisis, Lote, PalletProducto, RegistroEnvase
from usuarios.models import PerfilUsuario, Rol

from .models import Liberacion, RegistroCalidad


class BaseAPI(TestCase):
    def setUp(self):
        # El catálogo del Dossier se siembra por migración y también está en la
        # base de pruebas. Aquí se arma un checklist propio de dos documentos,
        # así que hay que partir de cero.
        DocumentoLiberacion.objects.all().delete()

        self.usuario = self._usuario("calidad1", Rol.CALIDAD, nombre="M.", apellido="Rivas")
        self.cliente = self._cliente(self.usuario)

        self.mandante = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )
        Especificacion.objects.create(
            producto=self.producto,
            version=1,
            vigente_desde=date(2026, 1, 1),
            rangos={"mg": {"min": 26.0, "max": 30.0, "obligatorio": True}},
        )

        self.ficha = DocumentoLiberacion.objects.create(
            nombre="Ficha técnica",
            aplica_a=["polvo"],
            orden=1,
            plantilla=[
                {"clave": "lote", "etiqueta": "Lote", "tipo": "texto", "req": True,
                 "origen": "lote.codigo_lote"},
                {"clave": "mg", "etiqueta": "Materia grasa", "tipo": "decimal",
                 "req": True, "parametro": "mg"},
            ],
        )
        self.micro = DocumentoLiberacion.objects.create(
            nombre="Liberación microbiológica", aplica_a=["polvo"], orden=2
        )

        self.lote = Lote.objects.create(
            codigo_lote="CCAA6140N",
            producto=self.producto,
            fecha=date(2026, 7, 20),
            kg_producidos=12500,
            estado=Lote.Estado.PRODUCIDO,
        )

    # -- ayudantes ---------------------------------------------------------

    def _usuario(self, username, rol, nombre="", apellido=""):
        usuario = User.objects.create_user(
            username=username, password="x", first_name=nombre, last_name=apellido
        )
        PerfilUsuario.objects.create(usuario=usuario, rol=rol)
        return usuario

    def _cliente(self, usuario):
        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )
        return cliente

    def _analisis(self, mg=28.0):
        return Analisis.objects.create(
            lote=self.lote, fecha=date(2026, 7, 20), valores={"mg": mg}
        )

    def _checklist_completo(self):
        RegistroCalidad.objects.create(
            lote=self.lote,
            documento=self.ficha,
            estado=RegistroCalidad.Estado.COMPLETADO,
            valores={"lote": "CCAA6140N", "mg": 28.0},
        )
        RegistroCalidad.objects.create(
            lote=self.lote,
            documento=self.micro,
            estado=RegistroCalidad.Estado.COMPLETADO,
        )

    def _expediente(self):
        return self.cliente.get(f"/api/calidad/expedientes/{self.lote.id}/").json()


class ExpedienteTests(BaseAPI):
    def test_el_expediente_trae_los_documentos_exigibles_con_su_plantilla(self):
        """La pantalla dibuja el formulario desde esto: sin plantilla no hay qué dibujar."""
        datos = self._expediente()
        detalle = datos["decision"]["avance"]["detalle"]

        self.assertEqual(len(detalle), 2)
        self.assertEqual(len(detalle[0]["documento"]["plantilla"]), 2)
        self.assertEqual(detalle[0]["documento"]["nombre"], "Ficha técnica")

    def test_el_expediente_explica_por_que_no_se_puede_liberar(self):
        """Un botón apagado sin motivo obliga a llamar por teléfono a alguien."""
        datos = self._expediente()

        self.assertFalse(datos["decision"]["permitido"])
        self.assertTrue(datos["decision"]["bloqueos"])

    def test_el_expediente_trae_el_prellenado(self):
        datos = self._expediente()

        self.assertEqual(
            datos["prellenado"][str(self.ficha.id)], {"lote": "CCAA6140N"}
        )

    def test_el_expediente_avisa_si_el_formulario_discrepa_del_analisis(self):
        self._analisis(mg=28.0)
        RegistroCalidad.objects.create(
            lote=self.lote,
            documento=self.ficha,
            estado=RegistroCalidad.Estado.COMPLETADO,
            valores={"lote": "CCAA6140N", "mg": 22.0},
        )

        datos = self._expediente()
        discrepancias = datos["discrepancias"][str(self.ficha.id)]

        self.assertTrue(any(d["tipo"] == "discrepa_del_analisis" for d in discrepancias))

    def test_el_listado_no_muestra_lotes_en_proceso(self):
        """Un lote que aún se está produciendo no es materia de Calidad."""
        Lote.objects.create(
            codigo_lote="EN-CURSO",
            producto=self.producto,
            fecha=date(2026, 7, 22),
            kg_producidos=100,
            estado=Lote.Estado.EN_PROCESO,
        )

        datos = self.cliente.get("/api/calidad/expedientes/").json()
        codigos = [f["lote"]["codigo_lote"] for f in datos["resultados"]]

        self.assertIn("CCAA6140N", codigos)
        self.assertNotIn("EN-CURSO", codigos)

    def test_el_listado_omite_lotes_historicos_sin_producto(self):
        """Un registro incompleto no puede tumbar la pantalla de Calidad."""
        Lote.objects.create(
            codigo_lote="SIN-PRODUCTO",
            fecha=date(2026, 7, 22),
            kg_producidos=100,
            estado=Lote.Estado.CERRADO,
        )

        respuesta = self.cliente.get("/api/calidad/expedientes/")

        self.assertEqual(respuesta.status_code, 200)
        codigos = [fila["lote"]["codigo_lote"] for fila in respuesta.json()["resultados"]]
        self.assertIn("CCAA6140N", codigos)
        self.assertNotIn("SIN-PRODUCTO", codigos)

    def test_el_listado_trae_el_avance_de_cada_lote(self):
        self._checklist_completo()

        fila = self.cliente.get("/api/calidad/expedientes/").json()["resultados"][0]

        self.assertEqual(fila["avance"], {"completados": 2, "total": 2, "pct": 100, "completo": True})

    def test_el_listado_no_dispara_una_consulta_por_lote(self):
        """
        Con ~954 lotes en el histórico, una consulta por lote haría la pantalla
        inusable. Los maestros se cargan una vez y se comparten.

        Se mide que el número NO crezca con la cantidad de lotes, en vez de
        fijar una cifra: el numero exacto cambia con cualquier `select_related`
        que se agregue, y una prueba que se rompe por eso enseña a subirle el
        número en vez de a mirar por qué subió.
        """

        def consultas_con(cantidad_de_lotes):
            Lote.objects.exclude(id=self.lote.id).delete()
            for i in range(cantidad_de_lotes - 1):
                Lote.objects.create(
                    codigo_lote=f"L{i}",
                    producto=self.producto,
                    fecha=date(2026, 7, 20),
                    kg_producidos=100,
                    estado=Lote.Estado.PRODUCIDO,
                )

            with CaptureQueriesContext(connection) as consultas:
                self.cliente.get("/api/calidad/expedientes/")

            return len(consultas)

        pocas = consultas_con(2)
        muchas = consultas_con(20)

        self.assertEqual(
            pocas,
            muchas,
            f"con 2 lotes hizo {pocas} consultas y con 20 hizo {muchas}: crece por lote",
        )


class FirmaTests(BaseAPI):
    def test_no_se_libera_un_lote_con_el_checklist_incompleto(self):
        self._analisis()

        respuesta = self.cliente.post(f"/api/calidad/expedientes/{self.lote.id}/liberar/")

        self.assertEqual(respuesta.status_code, 409)
        self.assertTrue(respuesta.json()["bloqueos"])
        self.assertFalse(Liberacion.objects.exists())

    def test_se_libera_un_lote_conforme_con_el_checklist_completo(self):
        self._analisis()
        self._checklist_completo()

        respuesta = self.cliente.post(f"/api/calidad/expedientes/{self.lote.id}/liberar/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], "liberado")
        self.assertTrue(respuesta.json()["liberado"])

    def test_liberar_cambia_estado_sin_duplicar_stock_fisico(self):
        equipo = Equipo.objects.create(
            sucursal=self.lote.sucursal, codigo="ENV-CAL", nombre="Envase Calidad",
            tipo=Equipo.Tipo.ENVASADORA,
        )
        envase = RegistroEnvase.objects.create(
            lote=self.lote, equipo=equipo, formato_kg=25, unidades=4,
            kg_envasados=100, operador=self.usuario,
            inicio=timezone.now() - timedelta(hours=1), termino=timezone.now(),
        )
        pallet = PalletProducto.objects.create(
            envase=envase, codigo="PAL-CAL-STOCK", unidades=4,
            kg_neto=Decimal("100"),
        )
        bodega = Bodega.objects.create(
            sucursal=self.lote.sucursal, codigo="BPT-CAL", nombre="Producto terminado",
        )
        ubicacion = Ubicacion.objects.create(
            bodega=bodega, codigo="PT-CUAR-CAL", tipo=Ubicacion.Tipo.CUARENTENA,
        )
        ExistenciaProductoTerminado.objects.create(pallet=pallet, ubicacion=ubicacion)
        self._analisis()
        self._checklist_completo()

        respuesta = self.cliente.post(f"/api/calidad/expedientes/{self.lote.id}/liberar/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(ExistenciaProductoTerminado.objects.count(), 1)
        pallet.refresh_from_db()
        self.assertEqual(pallet.estado, PalletProducto.Estado.LIBERADO)

    def test_la_firma_la_estampa_el_servidor(self):
        """Quién firmó y cuándo no se aceptan del navegador: son la auditoría."""
        self._analisis()
        self._checklist_completo()

        datos = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.id}/liberar/",
            {"autorizada_por": 999, "autorizada_en": "2020-01-01T00:00:00Z"},
            format="json",
        ).json()

        liberacion = Liberacion.objects.get()

        self.assertEqual(liberacion.autorizada_por, self.usuario)
        self.assertEqual(datos["autorizada_por_nombre"], "M. Rivas")
        self.assertGreater(liberacion.autorizada_en.year, 2020)

    def test_un_lote_no_conforme_no_se_libera_por_la_via_normal(self):
        self._analisis(mg=35.0)
        self._checklist_completo()

        respuesta = self.cliente.post(f"/api/calidad/expedientes/{self.lote.id}/liberar/")

        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("no conforme", " ".join(respuesta.json()["bloqueos"]))


class ConcesionAPITests(BaseAPI):
    def setUp(self):
        super().setUp()
        self._analisis(mg=35.0)
        self._checklist_completo()

    def test_la_concesion_exige_motivo(self):
        respuesta = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.id}/conceder/",
            {"motivo": "ok"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Liberacion.objects.exists())

    def test_la_concesion_sin_motivo_alguno_tampoco_pasa(self):
        respuesta = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.id}/conceder/", {}, format="json"
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_con_motivo_escrito_se_concede_y_queda_la_marca(self):
        respuesta = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.id}/conceder/",
            {"motivo": "Aceptado por el mandante según correo del 21-05."},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)

        liberacion = Liberacion.objects.get()
        self.assertEqual(liberacion.estado, Liberacion.Estado.CONCESION)
        self.assertTrue(liberacion.concesion, "la marca es permanente")
        self.assertIn("mandante", liberacion.motivo_concesion)
        self.assertTrue(liberacion.liberado)

    def test_no_se_concede_un_lote_sin_analisis(self):
        """No se concede una excepción sobre algo que nunca se midió."""
        Analisis.objects.all().delete()

        respuesta = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.id}/conceder/",
            {"motivo": "Aceptado por el mandante según correo del 21-05."},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 409)

    def test_no_se_concede_con_el_checklist_incompleto(self):
        RegistroCalidad.objects.filter(documento=self.micro).delete()

        respuesta = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.id}/conceder/",
            {"motivo": "Aceptado por el mandante según correo del 21-05."},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 409)


class NoHayPuertaDeAtrasTests(BaseAPI):
    """
    La regla que justifica el sistema no se puede saltar por otra ruta.

    Existen porque se pudo: un `PATCH` a `/liberaciones/<id>/` con
    `estado: liberado` dejaba el lote despachable sin checklist, sin
    autorizador y sin fecha. El ViewSet lo advertía en su docstring en vez de
    impedirlo.
    """

    def _expediente_pendiente(self):
        """Un expediente sin checklist, que la vía correcta rechaza."""
        return Liberacion.objects.create(lote=self.lote)

    def test_no_se_firma_escribiendo_el_estado(self):
        liberacion = self._expediente_pendiente()

        respuesta = self.cliente.patch(
            f"/api/calidad/liberaciones/{liberacion.id}/",
            {"estado": "liberado"},
            format="json",
        )

        liberacion.refresh_from_db()

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("estado", respuesta.json())
        self.assertEqual(liberacion.estado, Liberacion.Estado.PENDIENTE)
        self.assertFalse(liberacion.liberado)

    def test_no_se_concede_escribiendo_el_estado(self):
        """Lo más grave: concesión sin motivo y sin la marca permanente."""
        liberacion = self._expediente_pendiente()

        respuesta = self.cliente.patch(
            f"/api/calidad/liberaciones/{liberacion.id}/",
            {"estado": "liberado_concesion", "motivo_concesion": ""},
            format="json",
        )

        liberacion.refresh_from_db()

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(liberacion.liberado)
        self.assertFalse(liberacion.concesion)

    def test_no_se_falsifica_el_autorizador(self):
        liberacion = self._expediente_pendiente()
        otro = self._usuario("otro", Rol.CALIDAD)

        respuesta = self.cliente.patch(
            f"/api/calidad/liberaciones/{liberacion.id}/",
            {"autorizada_por": otro.id, "autorizada_en": "2020-01-01T00:00:00Z"},
            format="json",
        )

        liberacion.refresh_from_db()

        self.assertEqual(respuesta.status_code, 400)
        self.assertIsNone(liberacion.autorizada_por)

    def test_el_rechazo_dice_por_donde_se_hace(self):
        """
        Un 400 que no dice la alternativa deja a quien integra buscando a
        ciegas, y el atajo se vuelve a intentar por otro lado.
        """
        liberacion = self._expediente_pendiente()

        respuesta = self.cliente.patch(
            f"/api/calidad/liberaciones/{liberacion.id}/",
            {"estado": "liberado"},
            format="json",
        )

        self.assertIn("liberar/", str(respuesta.json()))

    def test_anotar_la_observacion_si_se_permite(self):
        """Cerrar la puerta no es tapiar la ventana: el expediente se anota."""
        liberacion = self._expediente_pendiente()

        respuesta = self.cliente.patch(
            f"/api/calidad/liberaciones/{liberacion.id}/",
            {"observacion": "Pendiente del informe microbiológico."},
            format="json",
        )

        liberacion.refresh_from_db()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("microbiológico", liberacion.observacion)


class VolverARevisionTests(BaseAPI):
    """
    Retirar una liberación firmada es una transición legítima, y antes solo se
    podía haciendo justamente lo que ahora está prohibido.
    """

    def test_una_liberacion_firmada_puede_volver_a_revision(self):
        self._analisis()
        self._checklist_completo()
        self.cliente.post(f"/api/calidad/expedientes/{self.lote.id}/liberar/")

        respuesta = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.id}/revisar/"
        )

        liberacion = Liberacion.objects.get(lote=self.lote)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(liberacion.estado, Liberacion.Estado.EN_REVISION)
        self.assertFalse(liberacion.liberado)

    def test_al_volver_a_revision_se_retira_la_firma(self):
        """Dejarla puesta diría que alguien autorizó algo que ya no lo está."""
        self._analisis()
        self._checklist_completo()
        self.cliente.post(f"/api/calidad/expedientes/{self.lote.id}/liberar/")

        self.cliente.post(f"/api/calidad/expedientes/{self.lote.id}/revisar/")

        liberacion = Liberacion.objects.get(lote=self.lote)

        self.assertIsNone(liberacion.autorizada_por)
        self.assertIsNone(liberacion.autorizada_en)
        self.assertFalse(liberacion.concesion)
        self.assertEqual(liberacion.motivo_concesion, "")

    def test_produccion_no_retira_liberaciones(self):
        cliente = self._cliente(self._usuario("prod9", Rol.PRODUCCION))

        respuesta = cliente.post(f"/api/calidad/expedientes/{self.lote.id}/revisar/")

        self.assertEqual(respuesta.status_code, 403)


class RegistroAPITests(BaseAPI):
    def test_no_se_da_por_completado_un_formulario_al_que_le_faltan_campos(self):
        respuesta = self.cliente.post(
            "/api/calidad/registros/",
            {
                "lote": self.lote.id,
                "documento": self.ficha.id,
                "estado": "completado",
                "valores": {"lote": "CCAA6140N"},
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Materia grasa", str(respuesta.json()))

    def test_un_borrador_si_se_guarda_a_medias(self):
        """Un formulario de planta se llena por partes; exigirlo entero lo devuelve al papel."""
        respuesta = self.cliente.post(
            "/api/calidad/registros/",
            {
                "lote": self.lote.id,
                "documento": self.ficha.id,
                "estado": "borrador",
                "valores": {"lote": "CCAA6140N"},
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201)
        self.assertFalse(respuesta.json()["completo"])
        self.assertEqual(respuesta.json()["faltantes"], ["Materia grasa"])

    def test_al_completar_queda_registrado_quien_y_cuando(self):
        respuesta = self.cliente.post(
            "/api/calidad/registros/",
            {
                "lote": self.lote.id,
                "documento": self.ficha.id,
                "estado": "completado",
                "valores": {"lote": "CCAA6140N", "mg": 28.0},
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201)

        registro = RegistroCalidad.objects.get()
        self.assertEqual(registro.completado_por, self.usuario)
        self.assertIsNotNone(registro.completado_en)

    def test_al_volver_a_borrador_se_limpia_la_firma(self):
        """Si dejó de estar completado, decir que alguien lo completó sería falso."""
        creado = self.cliente.post(
            "/api/calidad/registros/",
            {
                "lote": self.lote.id,
                "documento": self.ficha.id,
                "estado": "completado",
                "valores": {"lote": "CCAA6140N", "mg": 28.0},
            },
            format="json",
        ).json()

        self.cliente.patch(
            f"/api/calidad/registros/{creado['id']}/",
            {"estado": "borrador"},
            format="json",
        )

        registro = RegistroCalidad.objects.get()
        self.assertIsNone(registro.completado_por)
        self.assertIsNone(registro.completado_en)

    def test_un_formulario_observado_debe_decir_que_se_observo(self):
        respuesta = self.cliente.post(
            "/api/calidad/registros/",
            {
                "lote": self.lote.id,
                "documento": self.micro.id,
                "estado": "observado",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("observacion", respuesta.json())


class PermisosDeLiberacionTests(BaseAPI):
    """Quién puede firmar. Es la regla que justifica el módulo."""

    def setUp(self):
        super().setUp()
        self._analisis()
        self._checklist_completo()

    def test_produccion_no_firma_liberaciones(self):
        cliente = self._cliente(self._usuario("prod1", Rol.PRODUCCION))

        respuesta = cliente.post(f"/api/calidad/expedientes/{self.lote.id}/liberar/")

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Liberacion.objects.exists())

    def test_produccion_tampoco_completa_formularios(self):
        cliente = self._cliente(self._usuario("prod2", Rol.PRODUCCION))

        respuesta = cliente.post(
            "/api/calidad/registros/",
            {"lote": self.lote.id, "documento": self.micro.id, "estado": "completado"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403)

    def test_administracion_si_puede_firmar(self):
        cliente = self._cliente(self._usuario("admin1", Rol.ADMIN))

        respuesta = cliente.post(f"/api/calidad/expedientes/{self.lote.id}/liberar/")

        self.assertEqual(respuesta.status_code, 200)

    def test_calidad_administra_el_catalogo_de_documentos(self):
        """
        El módulo promete que Calidad cambia un campo y el formulario cambia
        sin desplegar. Si hiciera falta un administrador, la promesa es vacía.
        """
        respuesta = self.cliente.post(
            "/api/maestros/documentos/",
            {"nombre": "Nuevo control", "aplica_a": ["polvo"], "plantilla": []},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201)

    def test_produccion_no_toca_el_catalogo_de_documentos(self):
        cliente = self._cliente(self._usuario("prod3", Rol.PRODUCCION))

        respuesta = cliente.post(
            "/api/maestros/documentos/",
            {"nombre": "X", "aplica_a": ["polvo"], "plantilla": []},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403)

    def test_la_api_rechaza_una_plantilla_mal_escrita(self):
        respuesta = self.cliente.post(
            "/api/maestros/documentos/",
            {
                "nombre": "Malo",
                "aplica_a": ["polvo"],
                "plantilla": [{"clave": "x", "etiqueta": "X", "tipo": "textito"}],
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("textito", str(respuesta.json()))
