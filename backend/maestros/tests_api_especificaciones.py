"""
Pruebas de la API de especificaciones de calidad.

Lo que protegen son dos cosas que la pantalla de Maestros da por ciertas:

1. **Quién escribe.** Los rangos deciden qué producto sale como conforme, así
   que los escribe Calidad. Administración los lee.
2. **Cuál versión está vigente la dice el backend**, con la misma función que
   usa el veredicto del lote. Una lista que marque «vigente» a una versión
   distinta de la que audita el lote miente justo donde importa.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from usuarios.models import PerfilUsuario, Rol

from .models import Especificacion, Mandante, Producto


class BaseApiEspecificaciones(TestCase):

    def setUp(self):
        mandante = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=mandante,
        )
        self.calidad = self._cliente(Rol.CALIDAD)

    def _cliente(self, rol):
        usuario = User.objects.create_user(username=f"u-{rol}", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=rol)

        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )
        return cliente

    def _crear(self, **extra):
        datos = {
            "producto": self.producto,
            "version": 1,
            "vigente_desde": date(2026, 1, 1),
            "rangos": {"humedad": {"min": 2.5, "max": 4.0, "obligatorio": True}},
        }
        datos.update(extra)
        return Especificacion.objects.create(**datos)

    def _cuerpo(self, **extra):
        datos = {
            "producto": self.producto.id,
            "version": 1,
            "vigente_desde": "2026-01-01",
            "rangos": {"humedad": {"min": 2.5, "max": 4.0, "obligatorio": True}},
            "fuente": "Ficha técnica Nestlé",
        }
        datos.update(extra)
        return datos


class PermisosEspecificacionTests(BaseApiEspecificaciones):

    def test_calidad_escribe(self):
        respuesta = self.calidad.post(
            "/api/maestros/especificaciones/", self._cuerpo(), format="json"
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def test_administracion_tambien(self):
        """
        `EscribeCalidad` incluye a Administración, como el resto del sistema:
        un administrador no se queda encerrado fuera de su propia instalación.
        """
        respuesta = self._cliente(Rol.ADMIN).post(
            "/api/maestros/especificaciones/", self._cuerpo(), format="json"
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def test_produccion_no_escribe_pero_lee(self):
        """
        Que Producción pudiera mover los rangos le dejaría cambiar el veredicto
        de su propio lote sin volver a medirlo.
        """
        produccion = self._cliente(Rol.PRODUCCION)

        self.assertEqual(
            produccion.post(
                "/api/maestros/especificaciones/", self._cuerpo(), format="json"
            ).status_code,
            403,
        )
        self.assertEqual(
            produccion.get("/api/maestros/especificaciones/").status_code, 200
        )

    def test_los_rangos_invalidos_se_rechazan_por_la_api(self):
        """El `clean()` del modelo también protege el camino de la API."""
        respuesta = self.calidad.post(
            "/api/maestros/especificaciones/",
            self._cuerpo(rangos={"inventado": {"min": 1, "max": 2}}),
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("rangos", str(respuesta.data))


class VigenciaTests(BaseApiEspecificaciones):

    def _por_version(self, respuesta):
        return {e["version"]: e for e in respuesta.data["results"]}

    def test_marca_vigente_la_version_que_manda_hoy(self):
        """
        Dos versiones abiertas a la vez: gana la de vigencia más reciente. Es
        la misma regla que audita el lote, y por eso se resuelve en el backend.
        """
        self._crear(version=1, vigente_desde=date(2026, 1, 1))
        self._crear(version=2, vigente_desde=timezone.localdate())

        versiones = self._por_version(
            self.calidad.get("/api/maestros/especificaciones/")
        )

        self.assertFalse(versiones[1]["es_vigente"])
        self.assertTrue(versiones[2]["es_vigente"])

    def test_una_version_futura_todavia_no_manda(self):
        self._crear(version=1, vigente_desde=date(2026, 1, 1))
        self._crear(
            version=2, vigente_desde=timezone.localdate() + timedelta(days=30)
        )

        versiones = self._por_version(
            self.calidad.get("/api/maestros/especificaciones/")
        )

        self.assertTrue(versiones[1]["es_vigente"])
        self.assertFalse(versiones[2]["es_vigente"])

    def test_una_version_cerrada_deja_de_mandar(self):
        """
        Cerrada y sin reemplazo, el producto queda **sin especificación
        vigente** — que es exactamente lo que la pantalla tiene que avisar,
        porque un lote de hoy no se podría liberar.
        """
        self._crear(
            version=1,
            vigente_desde=date(2026, 1, 1),
            vigente_hasta=timezone.localdate() - timedelta(days=1),
        )

        versiones = self._por_version(
            self.calidad.get("/api/maestros/especificaciones/")
        )

        self.assertFalse(versiones[1]["es_vigente"])

    def test_una_version_partida_por_la_paginacion_no_se_declara_vigente(self):
        """
        La vigencia se calcula sobre **todas** las versiones del producto, no
        sobre las que la página trae.

        Es la trampa concreta: lo natural es resolverlo recorriendo la página
        que se está serializando, y funciona —hasta que un producto queda con
        sus versiones a caballo entre dos páginas. Ahí la vieja aparece sola en
        la página siguiente y, sin sus hermanas a la vista, parece la que
        manda. El listado de Maestros la mostraría como vigente mientras el
        lote se audita contra la otra.

        El relleno pone la v2 al final de la primera página y deja la v1 sola
        al principio de la segunda. Los nombres empiezan con «AAA» porque el
        orden del modelo es por nombre de producto.
        """
        mandante = self.producto.mandante
        relleno = Producto.objects.bulk_create([
            Producto(
                nombre=f"AAA {n:02d}",
                familia=Producto.Familia.OTRO,
                mandante=mandante,
            )
            for n in range(1, 50)
        ])
        Especificacion.objects.bulk_create([
            Especificacion(
                producto=p, version=1, vigente_desde=date(2026, 1, 1),
                rangos={"humedad": {"min": 2.0, "max": 5.0}},
            )
            for p in relleno
        ])

        self._crear(version=1, vigente_desde=date(2026, 1, 1))
        self._crear(version=2, vigente_desde=timezone.localdate())

        segunda = self.calidad.get(
            "/api/maestros/especificaciones/", {"page": 2}
        ).data["results"]

        # Que el reparto sea el previsto es parte de lo que se comprueba: si
        # cambiara la paginación o el orden, la prueba dejaría de morder y
        # tiene que decirlo en vez de pasar por casualidad.
        self.assertEqual(len(segunda), 1)
        self.assertEqual(segunda[0]["producto"], self.producto.id)
        self.assertEqual(segunda[0]["version"], 1)
        self.assertFalse(segunda[0]["es_vigente"])

    def test_los_parametros_se_sirven_desde_el_backend(self):
        """
        El formulario dibuja una fila por parámetro con estas claves. Copiarlas
        al frontend dejaría ofrecer una que `clean()` rechaza —o peor, omitir
        una que Calidad necesita— sin que nadie lo note.
        """
        respuesta = self.calidad.get("/api/maestros/parametros/")

        claves = {p["clave"] for p in respuesta.data}

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("humedad", claves)
        self.assertIn("mg", claves)
