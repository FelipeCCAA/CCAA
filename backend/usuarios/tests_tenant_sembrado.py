"""
Una sola organización en pruebas, no dos.

Esta prueba existe por una sesión entera perdida. `manage.py test` sin
`DJANGO_ENV=test` dejaba 20 pruebas en rojo repartidas por cuatro apps, con
mensajes que apuntaban a inocuidad («el equipo no existe») y no tenían nada
que ver con inocuidad.

La causa: la migración `usuarios.0008` siembra la organización inicial mirando
`os.getenv("DJANGO_ENV")`, mientras `_en_pruebas()` mira además `sys.argv`.
Cuando discrepan, la migración siembra la organización *real* del `.env` y los
`default` de tenant creen estar en pruebas. `empresa_predeterminada_pruebas`
intentaba reutilizar la sembrada buscándola por `rut="RUT-LOCAL-DESARROLLO"`
—un literal que ningún camino del código escribe— y, al no encontrarla, creaba
**una segunda**. Los maestros sembrados quedaban en una y los perfiles de
prueba en la otra, así que todo queryset acotado por tenant devolvía vacío.

Por eso la comprobación no es sobre el RUT: es sobre la consecuencia. Un
perfil creado con los valores por omisión tiene que ver los equipos que la
migración sembró. Y tiene que cumplirse **con y sin** `DJANGO_ENV=test`, que
es lo que distinguía a la base local de la de CI.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from maestros.models import Equipo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal
from usuarios.tenancy import (
    empresa_predeterminada_pruebas,
    filtrar_por_scope,
    sucursal_predeterminada_pruebas,
)


class TenantDePruebasEsElSembradoTests(TestCase):
    def test_no_se_crea_una_segunda_organizacion(self):
        empresa = empresa_predeterminada_pruebas()
        sucursal = sucursal_predeterminada_pruebas()

        self.assertIsNotNone(empresa)
        self.assertIsNotNone(sucursal)
        self.assertEqual(sucursal.empresa_id, empresa.pk)
        self.assertEqual(
            Empresa.objects.count(),
            1,
            "Hay más de una empresa: el default creó un tenant en vez de "
            "reutilizar el que sembró usuarios.0008.",
        )

    def test_la_organizacion_por_defecto_es_la_que_siembra_la_migracion(self):
        empresa = empresa_predeterminada_pruebas()

        sembrada = Sucursal.objects.filter(codigo="INTERNA").first()
        self.assertIsNotNone(
            sembrada, "usuarios.0008 siembra la sucursal «INTERNA»; no está."
        )
        self.assertEqual(empresa.pk, sembrada.empresa_id)

    def test_un_perfil_por_defecto_ve_los_equipos_sembrados(self):
        """
        La consecuencia que costó la sesión: con dos organizaciones, esto
        devolvía 0 de 9 y el PCC 1 no se podía registrar desde la API.
        """
        usuario = User.objects.create_user("tenant-sembrado", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=Rol.PRODUCCION)

        visibles = filtrar_por_scope(
            Equipo.objects.all(),
            usuario,
            campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )

        self.assertEqual(Equipo.objects.count(), visibles.count())
        self.assertGreater(
            visibles.count(), 0, "La migración siembra equipos; ninguno es visible."
        )
