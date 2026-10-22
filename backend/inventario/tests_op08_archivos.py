"""OP-08: archivos privados, vinculados a documentos y almacenamiento íntegro."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from usuarios.models import PerfilUsuario
from .models import Adjunto, Insumo, LoteInventario, SolicitudMaterial


class ArchivosOP08Tests(TransactionTestCase):
    def setUp(self):
        self.temporal = TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.config = override_settings(MEDIA_ROOT=self.temporal.name)
        self.config.enable()
        self.addCleanup(self.config.disable)
        self.usuario = User.objects.create_user("op08bodega")
        PerfilUsuario.objects.create(usuario=self.usuario, area="bodega", rol="operario")
        self.api = APIClient()
        self.api.force_authenticate(self.usuario)
        insumo = Insumo.objects.create(codigo="OP08", nombre="Material", area="bodega", unidad="un")
        self.lote = LoteInventario.objects.create(insumo=insumo, codigo="OP08-LOTE")

    def subir(self, **extra):
        datos = {"documento_tipo": "inventario.LoteInventario", "documento_id": self.lote.pk,
                 "tipo": "certificado", "archivo": SimpleUploadedFile("certificado.pdf", b"%PDF-1.7\nprueba", "application/pdf")}
        datos.update(extra)
        return self.api.post("/api/inventario/adjuntos/", datos, format="multipart")

    def test_rechaza_documento_inexistente_y_tipo_desconocido(self):
        for extra in ({"documento_id": 9999999}, {"documento_tipo": "usuarios.User"}):
            with self.subTest(extra=extra):
                self.assertEqual(self.subir(**extra).status_code, 400)
        self.assertFalse(Adjunto.objects.exists())

    def test_descarga_protegida_con_huella_y_sin_url_directa(self):
        respuesta = self.subir()
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["hash_sha256"], hashlib.sha256(b"%PDF-1.7\nprueba").hexdigest())
        ruta = f'/api/inventario/adjuntos/{respuesta.data["id"]}/descargar/'
        descarga = self.api.get(ruta)
        self.assertEqual(descarga.status_code, 200)
        self.assertEqual(b"".join(descarga.streaming_content), b"%PDF-1.7\nprueba")
        self.assertIn("attachment", descarga["Content-Disposition"])
        self.assertEqual(descarga["Cache-Control"], "private, no-store")
        descarga.close()
        self.api.force_authenticate(None)
        self.assertIn(self.api.get(ruta).status_code, (401, 403))

    def test_auditoria_fallida_no_deja_archivo_huerfano(self):
        with patch("auditoria.registro._escribir", side_effect=RuntimeError("fallo simulado")):
            with self.assertRaises(RuntimeError):
                self.subir()
        self.assertFalse(Adjunto.objects.exists())
        self.assertEqual([p for p in Path(self.temporal.name).rglob("*") if p.is_file()], [])

    def test_zip_generico_no_es_excel(self):
        respuesta = self.subir(archivo=SimpleUploadedFile("falso.xlsx", b"PK\x03\x04falso", "application/octet-stream"))
        self.assertEqual(respuesta.status_code, 400)

    def test_archivo_binario_renombrado_csv_no_pasa(self):
        self.assertEqual(self.subir(archivo=SimpleUploadedFile("falso.csv", b"MZ\x00\xffbinary")).status_code, 400)

    def test_cambio_de_permiso_impide_listado_y_descarga(self):
        identificador = self.subir().data["id"]
        otro = User.objects.create_user("op08aseo")
        PerfilUsuario.objects.create(usuario=otro, area="aseo", rol="operario")
        self.api.force_authenticate(otro)
        self.assertEqual(self.api.get(f"/api/inventario/adjuntos/{identificador}/descargar/").status_code, 404)
        self.assertEqual(self.api.get("/api/inventario/adjuntos/").data["count"], 0)
        self.assertEqual(self.subir().status_code, 403)

    def test_guardado_verifica_peso_tamano_y_archivo_alterado_o_faltante(self):
        with override_settings(MAX_UPLOAD_SIZE=8):
            self.assertEqual(self.subir().status_code, 400)
        identificador = self.subir().data["id"]
        adjunto = Adjunto.objects.get(pk=identificador)
        ruta = f"/api/inventario/adjuntos/{identificador}/descargar/"
        with adjunto.archivo.storage.open(adjunto.archivo.name, "wb") as fichero:
            fichero.write(b"contenido alterado")
        self.assertEqual(self.api.get(ruta).status_code, 409)
        adjunto.archivo.storage.delete(adjunto.archivo.name)
        self.assertEqual(self.api.get(ruta).status_code, 404)

    def test_no_se_borra_documento_con_evidencia(self):
        from django.core.exceptions import ValidationError
        self.subir()
        with self.assertRaisesMessage(ValidationError, "adjuntos"):
            self.lote.delete()
        self.assertTrue(LoteInventario.objects.filter(pk=self.lote.pk).exists())
        self.assertEqual(Adjunto.objects.count(), 1)

    def test_area_envase_hereda_acceso_a_su_solicitud_material(self):
        from django.utils import timezone
        usuario = User.objects.create_user("op08envase")
        PerfilUsuario.objects.create(usuario=usuario, area="envase", rol="operario")
        solicitud = SolicitudMaterial.objects.create(numero="OP08-MRQ", area="envase", solicitante=usuario,
                                                    fecha_requerida=timezone.localdate())
        self.api.force_authenticate(usuario)
        respuesta = self.subir(documento_tipo="inventario.SolicitudMaterial", documento_id=solicitud.pk)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        descarga = self.api.get(f'/api/inventario/adjuntos/{respuesta.data["id"]}/descargar/')
        self.assertEqual(descarga.status_code, 200)
        descarga.close()

    def test_fallo_de_almacenamiento_tras_escribir_limpia_el_archivo(self):
        storage = Adjunto._meta.get_field("archivo").storage
        guardar = storage._save

        def fallar_despues(nombre, contenido):
            guardar(nombre, contenido)
            raise OSError("fallo posterior de almacenamiento simulado")

        with patch.object(storage, "_save", side_effect=fallar_despues):
            with self.assertRaises(OSError):
                self.subir()
        self.assertFalse(Adjunto.objects.exists())
        self.assertFalse(any(p.is_file() for p in Path(self.temporal.name).rglob("*")))

    def test_excel_real_pasa_y_webp_riff_falso_no(self):
        from io import BytesIO
        from openpyxl import Workbook
        datos = BytesIO()
        Workbook().save(datos)
        self.assertEqual(self.subir(archivo=SimpleUploadedFile("real.xlsx", datos.getvalue())).status_code, 201)
        self.assertEqual(self.subir(archivo=SimpleUploadedFile("audio.webp", b"RIFF0000WAVEaudio")).status_code, 400)

    def test_subida_y_borrado_concurrentes_conservan_documento_y_archivo(self):
        from queue import Queue
        from threading import Event, Thread
        from time import monotonic
        from django.db import connection, connections
        from .documentos_adjuntos import DocumentoConEvidenciasError

        if connection.vendor != "postgresql":
            self.skipTest("Requiere bloqueo PostgreSQL real")
        guardado = Event()
        liberar = Event()
        resultados = Queue()
        pid_borrado = Queue()
        save_original = Adjunto.save

        def retener(instancia, *args, **kwargs):
            resultado = save_original(instancia, *args, **kwargs)
            guardado.set()
            if not liberar.wait(15):
                raise RuntimeError("No se liberó la subida de prueba")
            return resultado

        def subir():
            try:
                cliente = APIClient()
                cliente.force_authenticate(self.usuario)
                respuesta = cliente.post("/api/inventario/adjuntos/", {
                    "documento_tipo": "inventario.LoteInventario", "documento_id": self.lote.pk,
                    "tipo": "certificado", "archivo": SimpleUploadedFile("prueba.pdf", b"%PDF-1.7\nprueba"),
                }, format="multipart")
                resultados.put(("subida", respuesta.status_code))
            except Exception as error:
                resultados.put(("error", error))
            finally:
                connections.close_all()

        def borrar():
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pid_borrado.put(cursor.fetchone()[0])
                LoteInventario.objects.get(pk=self.lote.pk).delete()
                resultados.put(("borrado", True))
            except DocumentoConEvidenciasError:
                resultados.put(("protegido", True))
            except Exception as error:
                resultados.put(("error", error))
            finally:
                connections.close_all()

        primero, segundo = Thread(target=subir), Thread(target=borrar)
        with patch.object(Adjunto, "save", retener):
            primero.start()
            try:
                self.assertTrue(guardado.wait(10))
                segundo.start()
                pid = pid_borrado.get(timeout=10)
                plazo = monotonic() + 10
                bloqueado = False
                while monotonic() < plazo:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)", [pid])
                        bloqueado = bool(cursor.fetchone()[0])
                    if bloqueado or not segundo.is_alive():
                        break
                    segundo.join(timeout=0.05)
                self.assertTrue(bloqueado)
            finally:
                liberar.set()
                primero.join(timeout=15)
                if segundo.ident is not None:
                    segundo.join(timeout=15)
        self.assertFalse(primero.is_alive() or segundo.is_alive())
        self.assertCountEqual(list(resultados.queue), [("subida", 201), ("protegido", True)])
        self.assertTrue(LoteInventario.objects.filter(pk=self.lote.pk).exists())
        evidencia = Adjunto.objects.get()
        self.assertTrue(evidencia.archivo.storage.exists(evidencia.archivo.name))
