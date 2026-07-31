"""
La API de los registros por equipo, y su efecto en el checklist del lote.

La costura que importa: un aseo registrado **una vez** para el equipo tiene
que aparecer cumplido en todos los lotes de su período, sin que nadie lo
vuelva a teclear. Y no debe aparecer en los de fuera.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import DocumentoLiberacion, Equipo, Mandante, Producto
from produccion.models import Lote
from usuarios.models import PerfilUsuario, Rol

from .models import RegistroEquipo


class BasePeriodicos(TestCase):
    def setUp(self):
        # El catálogo se siembra por migración y también existe en la base de
        # pruebas (CLAUDE.md, «Trampas conocidas»).
        DocumentoLiberacion.objects.all().delete()

        self.mandante = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )
        # Los equipos también se siembran por migración.
        self.equipo, _ = Equipo.objects.update_or_create(
            codigo="veb",
            defaults={"nombre": "Evaporador VEB", "tipo": Equipo.Tipo.EVAPORADOR},
        )

        self.aseo = DocumentoLiberacion.objects.create(
            codigo="ASEO-SEM",
            nombre="Aseo semanal del evaporador",
            aplica_a=["polvo"],
            orden=1,
            frecuencia=DocumentoLiberacion.Frecuencia.SEMANAL,
        )

        self.produccion = self._cliente(Rol.PRODUCCION)
        self.calidad = self._cliente(Rol.CALIDAD)

    def _cliente(self, rol):
        usuario = User.objects.create_user(f"u-{rol}", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=rol)
        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )
        return cliente

    def _lote(self, dia, codigo):
        return Lote.objects.create(
            codigo_lote=codigo,
            producto=self.producto,
            fecha=dia,
            kg_producidos=1000,
            estado=Lote.Estado.PRODUCIDO,
        )

    def _registrar(self, dia, estado="completado", **extra):
        datos = {
            "documento": self.aseo.id,
            "equipo": self.equipo.id,
            "fecha": dia.isoformat(),
            "estado": estado,
        }
        datos.update(extra)

        return self.produccion.post(
            "/api/calidad/registros-equipo/", datos, format="json"
        )

    def _avance(self, lote):
        datos = self.calidad.get(f"/api/calidad/expedientes/{lote.id}/").json()

        return datos["decision"]["avance"]


class UnRegistroCubreVariosLotesTests(BasePeriodicos):

    def test_el_aseo_del_lunes_cubre_los_lotes_de_la_semana(self):
        """
        Es todo el punto: se llena una vez y cubre la semana. Antes había que
        teclearlo en cada lote, o dejar los demás sin poder liberarse aunque
        la máquina sí se aseó.
        """
        lunes = self._lote(date(2026, 7, 27), "L-LUN")
        viernes = self._lote(date(2026, 7, 31), "L-VIE")

        self.assertEqual(self._registrar(date(2026, 7, 27)).status_code, 201)

        for lote in (lunes, viernes):
            with self.subTest(lote=lote.codigo_lote):
                self.assertEqual(self._avance(lote)["completados"], 1)

    def test_no_cubre_los_de_la_semana_siguiente(self):
        siguiente = self._lote(date(2026, 8, 3), "L-SIG")

        self._registrar(date(2026, 7, 27))

        self.assertEqual(self._avance(siguiente)["completados"], 0)

    def test_un_borrador_no_cubre(self):
        lote = self._lote(date(2026, 7, 31), "L-1")

        self._registrar(date(2026, 7, 27), estado="borrador")

        self.assertEqual(self._avance(lote)["completados"], 0)

    def test_el_expediente_dice_cual_lo_cubre(self):
        """Sin eso, quien audita no puede llegar al papel."""
        lote = self._lote(date(2026, 7, 31), "L-1")
        self._registrar(date(2026, 7, 27))

        detalle = self._avance(lote)["detalle"][0]

        self.assertIsNotNone(detalle["cubierto_por"])
        self.assertEqual(detalle["cubierto_por"]["fecha"], "2026-07-27")


class ApiTests(BasePeriodicos):

    def test_se_lista_por_equipo_y_fecha(self):
        self._registrar(date(2026, 7, 27))

        datos = self.produccion.get(
            "/api/calidad/registros-equipo/",
            {"equipo": self.equipo.id, "desde": "2026-07-01"},
        ).json()

        self.assertEqual(datos["count"], 1)

    def test_no_se_repite_el_mismo_periodo(self):
        """
        Dos capturas del mismo aseo convivirían y el checklist tomaría
        cualquiera de las dos.
        """
        self._registrar(date(2026, 7, 27))

        self.assertEqual(self._registrar(date(2026, 7, 27)).status_code, 400)

    def test_quien_completa_lo_pone_el_servidor(self):
        """Un registro que dice haber sido completado por otro no prueba nada."""
        respuesta = self._registrar(date(2026, 7, 27))

        registro = RegistroEquipo.objects.get(pk=respuesta.data["id"])

        self.assertEqual(registro.completado_por.username, "u-produccion")
        self.assertIsNotNone(registro.completado_en)

    def test_un_borrador_no_lleva_firma(self):
        respuesta = self._registrar(date(2026, 7, 27), estado="borrador")

        registro = RegistroEquipo.objects.get(pk=respuesta.data["id"])

        self.assertIsNone(registro.completado_por)

    def test_segun_programa_exige_su_vigencia(self):
        """
        Sin ella no cubriría nada, y el usuario no entendería por qué su
        registro no aparece en ningún lote.
        """
        self.aseo.frecuencia = DocumentoLiberacion.Frecuencia.SEGUN_PROGRAMA
        self.aseo.save()

        respuesta = self._registrar(date(2026, 7, 27))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("vigente_hasta", respuesta.data)

    def test_con_vigencia_declarada_se_acepta(self):
        self.aseo.frecuencia = DocumentoLiberacion.Frecuencia.SEGUN_PROGRAMA
        self.aseo.save()

        respuesta = self._registrar(date(2026, 7, 27), vigente_hasta="2026-12-31")

        self.assertEqual(respuesta.status_code, 201)

    def test_solo_lista_los_documentos_periodicos(self):
        DocumentoLiberacion.objects.create(
            codigo="POR-LOTE", nombre="Uno por lote", aplica_a=["polvo"], orden=2
        )

        datos = self.produccion.get("/api/calidad/documentos-periodicos/").json()

        self.assertEqual([d["codigo"] for d in datos], ["ASEO-SEM"])

    def test_la_frecuencia_se_cambia_desde_el_catalogo(self):
        """
        Es un dato configurable y no una constante del código: cambiarla mueve
        el formulario entre el expediente del lote y los registros de planta,
        sin desplegar nada. Lo escribe Calidad, que es quien responde por el
        checklist.
        """
        por_lote = DocumentoLiberacion.objects.create(
            codigo="MOVIBLE", nombre="Cambia de sitio", aplica_a=["polvo"], orden=9
        )

        respuesta = self.calidad.patch(
            f"/api/maestros/documentos/{por_lote.id}/",
            {"frecuencia": "semanal"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)

        # Y desde ese momento aparece entre los periódicos.
        codigos = [
            d["codigo"]
            for d in self.produccion.get("/api/calidad/documentos-periodicos/").json()
        ]
        self.assertIn("MOVIBLE", codigos)

    def test_produccion_no_cambia_el_checklist(self):
        """
        El catálogo lo escribe Calidad. Que Producción pudiera bajar la
        frecuencia de un documento le dejaría reducir lo que se le exige.
        """
        documento = DocumentoLiberacion.objects.create(
            codigo="OTRO", nombre="Otro", aplica_a=["polvo"], orden=8
        )

        respuesta = self.produccion.patch(
            f"/api/maestros/documentos/{documento.id}/",
            {"frecuencia": "semanal"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403)

    def test_calidad_tambien_registra(self):
        """Quien está en la máquina llena el aseo; Calidad revisa y corrige."""
        respuesta = self.calidad.post(
            "/api/calidad/registros-equipo/",
            {
                "documento": self.aseo.id,
                "equipo": self.equipo.id,
                "fecha": "2026-07-27",
                "estado": "completado",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201)
