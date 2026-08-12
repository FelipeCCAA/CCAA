"""
Quién trabaja en cada área, respondido una sola vez.

En CCAA la misma persona opera en más de un área —«operario» es un comodín que
no dice dónde—, así que el área no es un dato único por persona y el rol no
sirve para deducirla.

Lo que se fija aquí:

1. Las **áreas adicionales** cuentan igual que la principal.
2. El **rol solo cuenta cuando nombra un área**; `operario` no aporta nada.
3. Las dos consultas del flujo de recepción —a quién ofrecer como responsable y
   a quién avisar— dan **la misma respuesta**, que es lo que no ocurría.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from .areas import areas_fuera_de_catalogo, perfiles_del_area, usuarios_del_area
from .checks import areas_dentro_del_catalogo
from .models import AreaDePerfil, Empresa, PerfilUsuario, Rol, Sucursal


class BaseAreas(TestCase):

    def setUp(self):
        self.empresa = Empresa.objects.create(rut="76.121.121-1", nombre="CCAA")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="P", nombre="Planta"
        )

    def _perfil(self, username, *, area="", rol=Rol.OPERARIO, extras=()):
        usuario = User.objects.create_user(username=username, password="x")
        perfil = PerfilUsuario.objects.create(
            usuario=usuario,
            area=area,
            rol=rol,
            empresa=self.empresa,
            sucursal=self.planta,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )

        for extra in extras:
            AreaDePerfil.objects.create(perfil=perfil, area=extra)

        return usuario

    def _nombres(self, area):
        return sorted(
            usuarios_del_area(area, empresa_id=self.empresa.pk).values_list(
                "username", flat=True
            )
        )


class QuienEsDeUnAreaTests(BaseAreas):

    def test_el_area_principal_cuenta(self):
        self._perfil("ana", area=PerfilUsuario.Area.RECEPCION)

        self.assertEqual(self._nombres(PerfilUsuario.Area.RECEPCION), ["ana"])

    def test_las_areas_adicionales_cuentan_igual(self):
        """
        El caso que motivó todo esto: el mismo operario está en Recepción por la
        mañana y en Secado por la tarde. Con un solo campo, la mitad de su
        trabajo era invisible.
        """
        self._perfil(
            "beto",
            area=PerfilUsuario.Area.RECEPCION,
            extras=[PerfilUsuario.Area.SECADO],
        )

        self.assertEqual(self._nombres(PerfilUsuario.Area.RECEPCION), ["beto"])
        self.assertEqual(self._nombres(PerfilUsuario.Area.SECADO), ["beto"])

    def test_quien_esta_en_varias_areas_aparece_una_sola_vez(self):
        """
        Sin `distinct`, el JOIN lo duplica y recibiría un aviso por cada área.

        Hacen falta **dos** adicionales para que se note: el `OR` con el área
        principal se cumple en todas las filas que produce el JOIN, así que con
        una sola adicional sale una fila y el defecto no aparece. La primera
        versión de esta prueba usaba una y decía proteger algo que no protegía —
        quitar el `distinct` la dejaba en verde.
        """
        self._perfil(
            "cata",
            area=PerfilUsuario.Area.RECEPCION,
            extras=[PerfilUsuario.Area.SECADO, PerfilUsuario.Area.ENVASE],
        )

        self.assertEqual(
            usuarios_del_area(
                PerfilUsuario.Area.RECEPCION, empresa_id=self.empresa.pk
            ).count(),
            1,
        )
        self.assertEqual(
            perfiles_del_area(
                PerfilUsuario.Area.RECEPCION, empresa_id=self.empresa.pk
            ).count(),
            1,
        )

    def test_el_rol_operario_no_dice_donde_trabaja(self):
        """
        Es un comodín: la misma etiqueta la lleva quien está en Recepción y
        quien está en Envase. Tratarlo como un área repartiría los avisos de
        Recepción a toda la planta.
        """
        self._perfil("dario", area="", rol=Rol.OPERARIO)

        self.assertEqual(self._nombres(PerfilUsuario.Area.RECEPCION), [])

    def test_un_rol_que_si_nombra_un_area_sirve_de_respaldo(self):
        """
        Los perfiles antiguos se cargaron sin área. Sin este respaldo, el
        desplegable de responsables se habría quedado vacío de golpe el día que
        esto se unificó.
        """
        self._perfil("eva", area="", rol=Rol.RECEPCION)

        self.assertEqual(self._nombres(PerfilUsuario.Area.RECEPCION), ["eva"])

    def test_no_se_cuela_quien_es_de_otra_empresa(self):
        otra = Empresa.objects.create(rut="77.131.131-1", nombre="Otra")
        ajena = Sucursal.objects.create(empresa=otra, codigo="X", nombre="Ajena")
        usuario = User.objects.create_user(username="ajeno", password="x")
        PerfilUsuario.objects.create(
            usuario=usuario,
            area=PerfilUsuario.Area.RECEPCION,
            empresa=otra,
            sucursal=ajena,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )

        self.assertEqual(self._nombres(PerfilUsuario.Area.RECEPCION), [])

    def test_un_inactivo_no_cuenta(self):
        usuario = self._perfil("fran", area=PerfilUsuario.Area.RECEPCION)
        usuario.is_active = False
        usuario.save(update_fields=["is_active"])

        self.assertEqual(self._nombres(PerfilUsuario.Area.RECEPCION), [])

    def test_las_dos_consultas_del_flujo_dan_lo_mismo(self):
        """
        La razón de existir de este módulo. Antes, `beto` aparecía en el
        desplegable de responsables y **no recibía ningún aviso**, porque cada
        consulta preguntaba a su manera.
        """
        self._perfil("gabo", area="", rol=Rol.RECEPCION)
        self._perfil("hugo", extras=[PerfilUsuario.Area.RECEPCION])

        responsables = set(
            usuarios_del_area(
                PerfilUsuario.Area.RECEPCION, empresa_id=self.empresa.pk
            ).values_list("id", flat=True)
        )
        avisados = set(
            perfiles_del_area(
                PerfilUsuario.Area.RECEPCION, empresa_id=self.empresa.pk
            ).values_list("usuario_id", flat=True)
        )

        self.assertEqual(responsables, avisados)
        self.assertEqual(len(responsables), 2)


class AreaFueraDeCatalogoTests(BaseAreas):

    def test_se_detecta_y_se_avisa(self):
        """
        `choices` no valida en la base. Un área inventada no la encuentra
        ninguna consulta y no da error: la persona deja de existir para el
        sistema, en silencio.
        """
        self._perfil("ivan", area="Gestion TI")

        self.assertEqual(
            list(areas_fuera_de_catalogo().values_list("area", flat=True)),
            ["Gestion TI"],
        )

        avisos = areas_dentro_del_catalogo(None)
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0].id, "usuarios.W001")
        self.assertIn("ivan", avisos[0].msg)

    def test_un_area_valida_no_dispara_el_aviso(self):
        self._perfil("julia", area=PerfilUsuario.Area.CALIDAD)

        self.assertEqual(areas_dentro_del_catalogo(None), [])

    def test_el_area_vacia_tampoco(self):
        """No es un error, es un perfil que todavía no la tiene cargada."""
        self._perfil("kira", area="")

        self.assertEqual(areas_dentro_del_catalogo(None), [])


class AreaAdicionalTests(BaseAreas):

    def test_no_se_repite_el_area_principal(self):
        from django.core.exceptions import ValidationError

        usuario = self._perfil("lena", area=PerfilUsuario.Area.RECEPCION)
        duplicada = AreaDePerfil(
            perfil=usuario.perfil, area=PerfilUsuario.Area.RECEPCION
        )

        with self.assertRaises(ValidationError):
            duplicada.full_clean()

    def test_no_se_repite_la_misma_area_adicional(self):
        from django.db import IntegrityError

        usuario = self._perfil("mora", area=PerfilUsuario.Area.RECEPCION)
        AreaDePerfil.objects.create(perfil=usuario.perfil, area=PerfilUsuario.Area.SECADO)

        with self.assertRaises(IntegrityError):
            AreaDePerfil.objects.create(
                perfil=usuario.perfil, area=PerfilUsuario.Area.SECADO
            )
