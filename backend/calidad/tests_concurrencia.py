"""
Pruebas del bloqueo que protege la firma de una liberación.

Son las que justifican la migración a PostgreSQL (ver DECISIONES.md). Dos
niveles:

- El check de arranque corre en cualquier motor y comprueba que la degradación
  se avise en vez de pasar en silencio.
- La carrera real solo se puede reproducir donde el bloqueo existe, así que se
  salta en los motores que no lo soportan. Que se salte NO significa que la
  garantía esté; significa que ahí no la hay.
"""

import threading
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import OperationalError, connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import DocumentoLiberacion, Especificacion, Mandante, Producto
from produccion.models import Analisis, Lote
from usuarios.models import PerfilUsuario, Rol

from .checks import motor_soporta_bloqueo
from .models import RegistroCalidad
from .views import _contexto_del_lote


class CheckDelMotorTests(TestCase):
    """
    `select_for_update()` en un motor que no lo soporta no falla: se compila a
    nada. El código queda idéntico y la garantía desaparece. Este check es lo
    que convierte ese silencio en un mensaje.
    """

    def test_en_un_motor_con_bloqueo_no_dice_nada(self):
        if not connection.features.has_select_for_update:
            self.skipTest("este motor no soporta bloqueo de filas")

        self.assertEqual(motor_soporta_bloqueo(None), [])

    def test_en_un_motor_sin_bloqueo_avisa(self):
        if connection.features.has_select_for_update:
            self.skipTest("este motor sí soporta bloqueo de filas")

        problemas = motor_soporta_bloqueo(None)

        self.assertEqual(len(problemas), 1)
        self.assertIn("select_for_update", problemas[0].msg)

    def test_un_motor_sin_bloqueo_que_nadie_pidio_impide_arrancar(self):
        """Un motor sin bloqueo siempre impide arrancar."""
        if connection.features.has_select_for_update:
            self.skipTest("este motor sí soporta bloqueo de filas")

        problemas = motor_soporta_bloqueo(None)

        self.assertEqual(problemas[0].id, "calidad.E001")
        self.assertEqual(problemas[0].level, 40)  # ERROR

    def test_pedir_sqlite_no_degrada_el_error_a_aviso(self):
        if connection.features.has_select_for_update:
            self.skipTest("este motor sí soporta bloqueo de filas")

        problemas = motor_soporta_bloqueo(None)

        self.assertEqual(problemas[0].id, "calidad.E001")
        self.assertEqual(problemas[0].level, 40)  # ERROR

    def test_en_desarrollo_tambien_es_error(self):
        if connection.features.has_select_for_update:
            self.skipTest("este motor sí soporta bloqueo de filas")

        problemas = motor_soporta_bloqueo(None)

        self.assertEqual(problemas[0].id, "calidad.E001")
        self.assertEqual(problemas[0].level, 40)  # ERROR

    def test_el_mensaje_explica_que_se_pierde(self):
        """Un aviso que no dice la consecuencia se ignora."""
        if connection.features.has_select_for_update:
            self.skipTest("este motor sí soporta bloqueo de filas")

        pista = motor_soporta_bloqueo(None)[0].hint

        self.assertIn("checklist", pista)
        self.assertIn("DECISIONES.md", pista)


class BloqueoAlFirmarTests(TransactionTestCase):
    """
    Que el bloqueo exista de verdad.

    Se comprueba el bloqueo, no la carrera. Lanzar los dos hilos y ver qué pasa
    no sirve: sin bloqueo, la carrera se gana o se pierde por milisegundos, así
    que la prueba pasaría casi siempre y no delataría nada. Se comprobó
    quitando el `select_for_update()`: la versión que medía la carrera pasaba
    igual, tres veces de tres.

    Lo que sí es determinista: mientras la firma tiene los formularios
    bloqueados, otro no puede tocarlos. Se mantiene el bloqueo abierto y se
    intenta borrar desde otra conexión con un `lock_timeout` corto. Si el
    borrado pasa, el bloqueo no está.

    Necesita `TransactionTestCase` y no `TestCase`: el segundo envuelve cada
    prueba en una transacción que nunca se confirma, así que un segundo hilo no
    vería nada de lo que la prueba creó.
    """

    def setUp(self):
        # Igual que en las demás pruebas de calidad: el catálogo sembrado por
        # migración se limpia para armar aquí el checklist que se quiere medir.
        DocumentoLiberacion.objects.all().delete()

        usuario = User.objects.create_user("mrivas", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=Rol.CALIDAD)

        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )

        mandante = Mandante.objects.create(nombre="Nestlé")
        producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=mandante,
        )
        Especificacion.objects.create(
            producto=producto,
            version=1,
            vigente_desde=date(2026, 1, 1),
            rangos={"mg": {"min": 26.0, "max": 30.0, "obligatorio": True}},
        )

        self.lote = Lote.objects.create(
            codigo_lote="CCAA6140N",
            producto=producto,
            fecha=date(2026, 7, 20),
            kg_producidos=12500,
            estado=Lote.Estado.PRODUCIDO,
        )
        Analisis.objects.create(
            lote=self.lote, fecha=date(2026, 7, 20), valores={"mg": 28.0}
        )

        self.documentos = [
            DocumentoLiberacion.objects.create(
                nombre=f"Documento {i}", aplica_a=["polvo"], orden=i
            )
            for i in (1, 2)
        ]

        for documento in self.documentos:
            RegistroCalidad.objects.create(
                lote=self.lote,
                documento=documento,
                estado=RegistroCalidad.Estado.COMPLETADO,
            )

    def _intentar_borrar_desde_otra_conexion(self, resultado):
        """
        Intenta borrar los formularios del lote con un `lock_timeout` corto.

        Deja en `resultado` qué pasó: "bloqueado" si el motor lo hizo esperar
        —lo correcto mientras la firma está decidiendo— o "borro" si pudo.
        """
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '1500ms'")

                RegistroCalidad.objects.filter(lote=self.lote).delete()

            resultado.append("borro")

        except OperationalError:
            resultado.append("bloqueado")

        except Exception as error:  # pragma: no cover - solo para diagnosticar
            resultado.append(f"error inesperado: {error!r}")

        finally:
            connections.close_all()

    def test_mientras_la_firma_decide_nadie_toca_los_formularios(self):
        if not connection.features.has_select_for_update:
            self.skipTest(
                "este motor no bloquea filas: la protección NO existe aquí"
            )

        resultado = []

        with transaction.atomic():
            # Lo mismo que hace el camino de la firma antes de decidir.
            _contexto_del_lote(self.lote, bloquear=True)

            hilo = threading.Thread(
                target=self._intentar_borrar_desde_otra_conexion, args=(resultado,)
            )
            hilo.start()
            hilo.join(timeout=20)

        self.assertEqual(
            resultado,
            ["bloqueado"],
            "los formularios que la firma leyó no quedaron bloqueados: otro "
            "usuario puede desmarcar un documento y dejar la liberación "
            "firmada contra un checklist incompleto",
        )

    def test_el_camino_de_la_firma_pide_el_bloqueo(self):
        """
        Las otras comprueban que el bloqueo funciona; esta, que la firma lo
        pide. Sin ella, alguien podría quitar `bloquear=True` de la vista y
        todo seguiría en verde.

        Corre en cualquier motor: comprueba la llamada, no el efecto.
        """
        from calidad import views

        pedidos = []
        original = views._contexto_del_lote

        def espia(lote, bloquear=False):
            pedidos.append(bloquear)
            return original(lote, bloquear=bloquear)

        with patch.object(views, "_contexto_del_lote", espia):
            self.cliente.post(f"/api/calidad/expedientes/{self.lote.id}/liberar/")

        self.assertEqual(
            pedidos, [True], "la firma leyó el expediente sin bloquear las filas"
        )

    def test_sin_bloquear_las_filas_quedan_libres(self):
        """
        La contraparte, que es la que le da valor a la prueba de arriba: por el
        camino de solo lectura las filas NO se bloquean. Si esta fallara,
        la anterior estaría pasando por cualquier otro motivo.
        """
        if not connection.features.has_select_for_update:
            self.skipTest("este motor no bloquea filas")

        resultado = []

        with transaction.atomic():
            _contexto_del_lote(self.lote, bloquear=False)

            hilo = threading.Thread(
                target=self._intentar_borrar_desde_otra_conexion, args=(resultado,)
            )
            hilo.start()
            hilo.join(timeout=20)

        self.assertEqual(resultado, ["borro"])
