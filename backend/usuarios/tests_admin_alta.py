"""
El admin tiene que poder abrir el formulario de alta de todo lo que registra.

Django pide el `default` de cada campo al construir el modelo vacío que rellena
ese formulario. Mientras los defaults de tenant lanzaban `ImproperlyConfigured`
fuera de pruebas, **22 de los 72 modelos registrados devolvían un error 500 en
«Añadir»** —perfiles de usuario, lotes, recepciones, equipos, silos— con un
mensaje de configuración que no le decía nada a quien lo veía.

Se recorre el registro entero en vez de listar los 22: la lista se quedaría
corta en cuanto alguien registre otro modelo con tenant, que es justo cuando
haría falta.
"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Empresa, PerfilUsuario, Sucursal


# `DJANGO_ENV=development` no es decoración: bajo `test` los defaults de tenant
# devuelven la empresa sembrada y todo abre igual, así que la prueba pasaría
# sin comprobar nada. El defecto solo existe fuera de pruebas —que es donde se
# usa el admin— y aquí es donde hay que reproducirlo.
@override_settings(DJANGO_ENV="development")
class FormularioDeAltaTests(TestCase):

    def setUp(self):
        self.jefe = User.objects.create_superuser(
            username="jefa", email="jefa@ccaa.cl", password="x"
        )
        self.client.force_login(self.jefe)

    def test_todas_las_paginas_de_alta_abren(self):
        fallos = []

        for modelo, opciones in admin.site._registry.items():
            if not opciones.has_add_permission(self._peticion()):
                continue

            etiqueta = f"{modelo._meta.app_label}.{modelo._meta.model_name}"
            url = reverse(f"admin:{modelo._meta.app_label}_{modelo._meta.model_name}_add")
            respuesta = self.client.get(url)

            if respuesta.status_code != 200:
                fallos.append(f"{etiqueta} -> {respuesta.status_code}")

        self.assertEqual(fallos, [], "Páginas «Añadir» que no abren: " + str(fallos))

    def _peticion(self):
        peticion = self.client.request().wsgi_request
        peticion.user = self.jefe
        return peticion


class SinTenantInventadoTests(TestCase):
    """
    Que la página abra no puede costar que el tenant se invente solo: un
    registro guardado contra una planta que nadie eligió es peor que un
    formulario que no abre, porque no se nota.
    """

    def setUp(self):
        self.jefe = User.objects.create_superuser(
            username="jefe", email="jefe@ccaa.cl", password="x"
        )
        self.client.force_login(self.jefe)

    def test_el_perfil_sin_empresa_no_se_guarda(self):
        respuesta = self.client.post(
            reverse("admin:usuarios_perfilusuario_add"),
            {
                "usuario": self.jefe.pk,
                "area": PerfilUsuario.Area.SECADO,
                "nivel": PerfilUsuario.Nivel.TRABAJADOR,
                "alcance": PerfilUsuario.Alcance.SUCURSAL,
                "cargo": "",
                "turno": "",
                # El admin manda el formset del inline de áreas adicionales en cada
                # envío; sin él, el formulario entero es inválido.
                "areas_adicionales-TOTAL_FORMS": "0",
                "areas_adicionales-INITIAL_FORMS": "0",
                "areas_adicionales-MIN_NUM_FORMS": "0",
                "areas_adicionales-MAX_NUM_FORMS": "1000",
            },
        )

        # El admin reexpone el formulario con el error en vez de redirigir.
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(PerfilUsuario.objects.filter(usuario=self.jefe).exists())

    def test_el_admin_guarda_el_perfil_a_nivel_empresa(self):
        empresa = Empresa.objects.create(rut="76.999.999-9", nombre="CCAA")
        planta = Sucursal.objects.create(
            empresa=empresa, codigo="P1", nombre="Planta"
        )

        respuesta = self.client.post(
            reverse("admin:usuarios_perfilusuario_add"),
            {
                "usuario": self.jefe.pk,
                "area": PerfilUsuario.Area.SECADO,
                "nivel": PerfilUsuario.Nivel.TRABAJADOR,
                "empresa": empresa.pk,
                "sucursal": planta.pk,
                "alcance": PerfilUsuario.Alcance.SUCURSAL,
                "cargo": "",
                "turno": "",
                # El admin manda el formset del inline de áreas adicionales en cada
                # envío; sin él, el formulario entero es inválido.
                "areas_adicionales-TOTAL_FORMS": "0",
                "areas_adicionales-INITIAL_FORMS": "0",
                "areas_adicionales-MIN_NUM_FORMS": "0",
                "areas_adicionales-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        perfil = PerfilUsuario.objects.get(usuario=self.jefe)
        self.assertEqual(perfil.empresa_id, empresa.pk)
        self.assertIsNone(perfil.sucursal_id)
        self.assertEqual(perfil.alcance, PerfilUsuario.Alcance.EMPRESA)
