"""
La inocuidad de punta a punta: se carga por la API y bloquea la liberación.

Las reglas se prueban solas en `tests_inocuidad.py`. Lo que se prueba aquí es
la costura: que lo que un operador registra desde la pantalla llegue a la
decisión de liberar. Sin esta prueba, las dos mitades pueden estar bien y no
tocarse — que es el fallo que no se ve.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import (
    DocumentoLiberacion,
    Equipo,
    Especificacion,
    Mandante,
    Producto,
)
from produccion.models import Analisis, ControlProceso, Lote
from usuarios.models import PerfilUsuario, Rol

from .models import RegistroCalidad


class BaseInocuidadApi(TestCase):
    def setUp(self):
        # El catálogo se siembra por migración y también existe en la base de
        # pruebas (CLAUDE.md, «Trampas conocidas»).
        DocumentoLiberacion.objects.all().delete()

        # Sembrado por migración, igual que el catálogo de documentos.
        self.veb = Equipo.objects.get(codigo="veb")

        mandante = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=mandante,
        )
        self.lote = Lote.objects.create(
            codigo_lote="L-1",
            producto=self.producto,
            fecha=date(2026, 7, 16),
            kg_producidos=1000,
            estado=Lote.Estado.PRODUCIDO,
        )

        Especificacion.objects.create(
            producto=self.producto,
            version=1,
            vigente_desde=date(2026, 1, 1),
            rangos={"humedad": {"min": 2.0, "max": 4.0}},
        )
        Analisis.objects.create(
            lote=self.lote, fecha=date(2026, 7, 16), valores={"humedad": 3.0}
        )

        # Checklist completo: así el único pero posible es la inocuidad.
        documento = DocumentoLiberacion.objects.create(
            codigo="DOC-1", nombre="Formulario único", aplica_a=["polvo"], orden=1
        )
        RegistroCalidad.objects.create(
            lote=self.lote,
            documento=documento,
            estado=RegistroCalidad.Estado.COMPLETADO,
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

    def _expediente(self):
        return self.calidad.get(f"/api/calidad/expedientes/{self.lote.id}/").json()

    def _control(self, temp_min=80.0, caudal_max=14175.0):
        respuesta = self.produccion.post(
            "/api/produccion/controles/",
            {
                "lote": self.lote.id,
                "equipo": self.veb.id,
                "fecha": "2026-07-16",
                "pcc1_temp_min": temp_min,
                "pcc1_caudal_max": caudal_max,
            },
            format="json",
        )
        assert respuesta.status_code == 201, respuesta.data
        return respuesta.data["id"]

    def _lectura(self, control, hora="10:00", **valores):
        return self.produccion.post(
            "/api/produccion/lecturas-control/",
            {"control": control, "hora": hora, "valores": valores},
            format="json",
        )

    def _monitoreo(self, accion=""):
        respuesta = self.produccion.post(
            "/api/inocuidad/monitoreos/",
            {
                "lote": self.lote.id,
                "tipo": "detector_metales",
                "fecha": "2026-07-16",
                "accion_correctiva": accion,
            },
            format="json",
        )
        assert respuesta.status_code == 201, respuesta.data
        return respuesta.data["id"]

    def _lectura_ppro(self, monitoreo, resultado, hora="10:00"):
        return self.produccion.post(
            "/api/inocuidad/lecturas/",
            {"monitoreo": monitoreo, "hora": hora, "resultado": resultado},
            format="json",
        )


class PuntoDePartidaTests(BaseInocuidadApi):

    def test_sin_registros_de_inocuidad_el_lote_se_puede_liberar(self):
        """
        El escenario de control. Si no partiera liberable, las pruebas
        siguientes no demostrarían que lo que bloquea es la inocuidad.
        """
        self.assertTrue(self._expediente()["decision"]["permitido"])


class Pcc1BloqueaTests(BaseInocuidadApi):

    def test_una_lectura_dentro_del_limite_no_bloquea(self):
        control = self._control()
        self.assertEqual(self._lectura(control, t_dsi=82.0).status_code, 201)

        self.assertTrue(self._expediente()["decision"]["permitido"])

    def test_una_lectura_bajo_la_temperatura_minima_bloquea(self):
        """
        La leche pasó sin el tratamiento térmico que la hace inocua. Es el
        caso que justifica todo el PCC.
        """
        control = self._control(temp_min=80.0)
        self._lectura(control, t_dsi=75.4)

        decision = self._expediente()["decision"]

        self.assertFalse(decision["permitido"])
        self.assertTrue(any("PCC 1" in b for b in decision["bloqueos"]))

    def test_una_lectura_sobre_el_caudal_maximo_bloquea(self):
        control = self._control(caudal_max=14175.0)
        self._lectura(control, flujo_entrada=16000)

        self.assertFalse(self._expediente()["decision"]["permitido"])

    def test_el_motivo_dice_el_valor_y_su_limite(self):
        control = self._control(temp_min=80.0)
        self._lectura(control, hora="14:30", t_dsi=75.4)

        motivo = next(
            b for b in self._expediente()["decision"]["bloqueos"] if "PCC 1" in b
        )

        self.assertIn("75.4", motivo)
        self.assertIn("80.0", motivo)

    def test_corregir_la_lectura_desbloquea(self):
        """
        El veredicto se recalcula, no se guarda: una lectura mal tecleada se
        corrige y el lote vuelve a ser liberable sin tocar nada más.
        """
        control = self._control(temp_min=80.0)
        lectura = self._lectura(control, t_dsi=75.4).data["id"]

        self.produccion.patch(
            f"/api/produccion/lecturas-control/{lectura}/",
            {"valores": {"t_dsi": 82.0}},
            format="json",
        )

        self.assertTrue(self._expediente()["decision"]["permitido"])

    def test_el_control_expone_su_veredicto_con_detalle(self):
        control = self._control(temp_min=80.0)
        self._lectura(control, t_dsi=75.4)

        datos = self.produccion.get(f"/api/produccion/controles/{control}/").json()

        self.assertFalse(datos["pcc1"]["cumple"])
        self.assertEqual(len(datos["pcc1"]["incumplimientos"]), 1)
        self.assertIn("descripcion", datos["pcc1"]["incumplimientos"][0])


class PproBloqueaTests(BaseInocuidadApi):

    def test_una_lectura_ok_no_bloquea(self):
        monitoreo = self._monitoreo()
        self.assertEqual(self._lectura_ppro(monitoreo, "ok").status_code, 201)

        self.assertTrue(self._expediente()["decision"]["permitido"])

    def test_un_no_ok_sin_accion_correctiva_bloquea(self):
        monitoreo = self._monitoreo(accion="")
        self._lectura_ppro(monitoreo, "no_ok")

        decision = self._expediente()["decision"]

        self.assertFalse(decision["permitido"])
        self.assertTrue(any("correctiva" in b for b in decision["bloqueos"]))

    def test_escribir_la_accion_correctiva_desbloquea(self):
        """
        Lo que bloquea no es el No-OK —eso pasa y se corrige— sino que nadie
        haya dejado constancia de qué se hizo.
        """
        monitoreo = self._monitoreo(accion="")
        self._lectura_ppro(monitoreo, "no_ok")

        self.produccion.patch(
            f"/api/inocuidad/monitoreos/{monitoreo}/",
            {"accion_correctiva": "Se retiró el producto y se recalibró el detector."},
            format="json",
        )

        self.assertTrue(self._expediente()["decision"]["permitido"])

    def test_el_monitoreo_expone_si_esta_resuelto(self):
        monitoreo = self._monitoreo()
        self._lectura_ppro(monitoreo, "no_ok")

        datos = self.produccion.get(f"/api/inocuidad/monitoreos/{monitoreo}/").json()

        self.assertTrue(datos["tiene_no_ok"])
        self.assertFalse(datos["resuelto"])


class FirmaTests(BaseInocuidadApi):
    """La regla tiene que valer también en el camino que firma, no solo al ver."""

    def _firmar(self):
        return self.calidad.post(
            f"/api/calidad/expedientes/{self.lote.id}/liberar/", {}, format="json"
        )

    def test_sin_problemas_de_inocuidad_se_firma(self):
        self.assertEqual(self._firmar().status_code, 200)

    def test_con_el_pcc1_incumplido_no_se_firma(self):
        control = self._control(temp_min=80.0)
        self._lectura(control, t_dsi=70.0)

        respuesta = self._firmar()

        self.assertEqual(respuesta.status_code, 409)
        self.assertTrue(any("PCC 1" in b for b in respuesta.data["bloqueos"]))

    def test_con_un_ppro_abierto_no_se_firma(self):
        monitoreo = self._monitoreo()
        self._lectura_ppro(monitoreo, "no_ok")

        self.assertEqual(self._firmar().status_code, 409)


class PermisosTests(BaseInocuidadApi):

    def test_calidad_no_carga_lecturas_de_proceso(self):
        """
        Quien está en la línea toma la lectura. Que Calidad pudiera escribirla
        y además firmar contra ella junta las dos manos que el control separa.
        """
        control = ControlProceso.objects.create(
            lote=self.lote, equipo=self.veb, fecha=date(2026, 7, 16)
        )

        respuesta = self.calidad.post(
            "/api/produccion/lecturas-control/",
            {"control": control.id, "hora": "10:00", "valores": {"t_dsi": 82}},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403)

    def test_un_valor_no_numerico_se_rechaza(self):
        control = self._control()

        respuesta = self._lectura(control, t_dsi="ochenta")

        self.assertEqual(respuesta.status_code, 400)
