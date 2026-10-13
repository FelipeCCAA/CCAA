import importlib
import io
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal

from django.apps import apps
from django.test import TestCase

from procesos.models import CorridaMantequilla, EjecucionProceso, EtapaProceso, Proceso
from procesos.servicios import tipos_equipo_para_etapa
from produccion.models import Lote, OrdenProduccion
from produccion.servicios import abre_desde_vale
from usuarios.models import Empresa, Sucursal

from .models import Equipo, FormatoEnvasado, Mandante, Producto

# El nombre del módulo empieza con un dígito: solo se importa así.
reclasificacion = importlib.import_module("maestros.migrations.0040_reclasificar_mantequeras")


class ReclasificarMantequerasTests(TestCase):
    """
    `0040` ya corrió al construir la base de pruebas. Aquí se vuelve a llamar
    con el registro de modelos vivo sobre equipos propios, para fijar qué
    reclasifica, qué deja como está, qué anuncia y qué deshace.
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(rut="MTQ-1", nombre="Empresa mantequeras")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="MTQ", nombre="Planta mantequeras"
        )
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Mandante mantequeras", codigo_cliente="mtq"
        )
        self.crema = Producto.objects.create(
            mandante=mandante, nombre="Crema MTQ", familia=Producto.Familia.CREMA
        )
        self.mantequilla = Producto.objects.create(
            mandante=mandante, nombre="Mantequilla MTQ",
            categoria=Producto.Categoria.MANTEQUILLA, naturaleza=Producto.Naturaleza.TERMINADO,
        )
        proceso = Proceso.objects.create(codigo="mtq", nombre="Mantequilla MTQ")
        self.etapa_mantequilla = EtapaProceso.objects.create(
            proceso=proceso, codigo="mtq-batir", nombre="Batido",
            tipo=EtapaProceso.Tipo.MANTEQUILLA, orden=1,
        )
        self.etapa_envasado = EtapaProceso.objects.create(
            proceso=proceso, codigo="mtq-envasar", nombre="Envasado",
            tipo=EtapaProceso.Tipo.ENVASADO, orden=2,
        )
        self.orden = OrdenProduccion.objects.create(
            sucursal=self.planta, codigo="OP-MTQ", producto=self.mantequilla,
            cantidad_planificada=100, unidad="kg",
        )

    def equipo(self, codigo, tipo=Equipo.Tipo.LINEA):
        return Equipo.objects.create(sucursal=self.planta, codigo=codigo, nombre=codigo, tipo=tipo)

    def corrida_en(self, equipo, sufijo):
        """Una corrida de mantequilla que usó `equipo`: lo vuelve candidato."""
        ejecucion = EjecucionProceso.objects.create(
            codigo=f"EJ-MTQ-{sufijo}", etapa=self.etapa_mantequilla,
            sucursal=self.planta, equipo=equipo,
        )
        crema = Lote.objects.create(
            sucursal=self.planta, codigo_lote=f"CR-MTQ-{sufijo}", producto=self.crema,
            fecha=date(2026, 10, 1), estado=Lote.Estado.PRODUCIDO, kg_producidos=Decimal("100"),
        )
        salida = Lote.objects.create(
            sucursal=self.planta, codigo_lote=f"MTQ-{sufijo}", producto=self.mantequilla,
            fecha=date(2026, 10, 1),
        )
        return CorridaMantequilla.objects.create(
            ejecucion=ejecucion, orden=self.orden, lote_crema=crema,
            lote_mantequilla=salida, kg_crema=Decimal("50"),
        )

    def formato_con(self, *equipos, codigo="caja-mtq"):
        formato = FormatoEnvasado.objects.create(
            producto=self.mantequilla, codigo=codigo, nombre=f"Caja {codigo}",
            kg_neto=Decimal("20"), unidades_maximas_pallet=25,
        )
        formato.equipos.add(*equipos)
        return formato

    def reclasificar(self):
        salida = io.StringIO()
        with redirect_stdout(salida):
            reclasificacion.reclasificar(apps, None)
        return salida.getvalue()

    def tipo(self, equipo):
        return Equipo.objects.values_list("tipo", flat=True).get(pk=equipo.pk)

    def test_la_linea_sembrada_es_mantequera_y_conserva_sigla_y_mrp(self):
        # Lo dejó así `0040` al construir la base: la siembra de `0010` no
        # tiene ejecuciones de otra etapa.
        sembradas = Equipo.objects.filter(codigo=reclasificacion.CODIGO_SEMBRADO)
        self.assertTrue(sembradas.exists())
        for equipo in sembradas:
            self.assertEqual(equipo.tipo, Equipo.Tipo.MANTEQUERA)
            self.assertEqual(equipo.sigla, "LM")
            self.assertTrue(equipo.consume_materiales)

    def test_una_linea_usada_solo_por_mantequilla_pasa_a_mantequera_y_sale_de_los_formatos(self):
        linea = self.equipo("mtq-solo")
        envasadora = self.equipo("mtq-envasadora", Equipo.Tipo.ENVASADORA)
        self.corrida_en(linea, "1")
        formato = self.formato_con(linea, envasadora)

        self.reclasificar()

        self.assertEqual(self.tipo(linea), Equipo.Tipo.MANTEQUERA)
        self.assertEqual(list(formato.equipos.values_list("pk", flat=True)), [envasadora.pk])

    def test_una_linea_que_tambien_hizo_otra_etapa_queda_como_esta_y_se_nombra(self):
        linea = self.equipo("mtq-mixta")
        self.corrida_en(linea, "2")
        EjecucionProceso.objects.create(
            codigo="EJ-MTQ-ENV", etapa=self.etapa_envasado, sucursal=self.planta, equipo=linea,
        )
        formato = self.formato_con(linea)

        salida = self.reclasificar()

        self.assertEqual(self.tipo(linea), Equipo.Tipo.LINEA)
        self.assertIn(linea.pk, formato.equipos.values_list("pk", flat=True))
        self.assertIn("mtq-mixta", salida)

    def test_una_linea_ajena_a_la_mantequilla_no_cambia(self):
        linea = self.equipo("mtq-ajena")
        otro = self.equipo("mtq-otro", Equipo.Tipo.OTRO)

        self.reclasificar()

        self.assertEqual(self.tipo(linea), Equipo.Tipo.LINEA)
        self.assertEqual(self.tipo(otro), Equipo.Tipo.OTRO)

    def test_una_envasadora_usada_por_error_no_se_reclasifica(self):
        envasadora = self.equipo("mtq-env-error", Equipo.Tipo.ENVASADORA)
        self.corrida_en(envasadora, "3")

        self.reclasificar()

        self.assertEqual(self.tipo(envasadora), Equipo.Tipo.ENVASADORA)

    def test_un_formato_que_queda_sin_maquinas_se_anuncia(self):
        linea = self.equipo("mtq-unica")
        self.corrida_en(linea, "4")
        formato = self.formato_con(linea)

        salida = self.reclasificar()

        self.assertFalse(formato.equipos.exists())
        self.assertIn(f"«{formato.nombre}» quedó sin máquinas autorizadas", salida)

    def test_reclasificar_dos_veces_no_cambia_nada(self):
        linea = self.equipo("mtq-dos-veces")
        self.corrida_en(linea, "5")

        self.reclasificar()
        segunda = self.reclasificar()

        self.assertEqual(self.tipo(linea), Equipo.Tipo.MANTEQUERA)
        self.assertEqual(segunda, "")

    def test_deshacer_devuelve_las_mantequeras_a_linea(self):
        linea = self.equipo("mtq-deshacer")
        self.corrida_en(linea, "6")
        self.reclasificar()

        reclasificacion.restaurar(apps, None)

        self.assertEqual(self.tipo(linea), Equipo.Tipo.LINEA)
        self.assertFalse(Equipo.objects.filter(tipo=Equipo.Tipo.MANTEQUERA).exists())


class TipoMantequeraTests(TestCase):
    def test_la_etapa_mantequilla_acepta_solo_mantequeras(self):
        self.assertEqual(
            tipos_equipo_para_etapa(EtapaProceso.Tipo.MANTEQUILLA), {Equipo.Tipo.MANTEQUERA},
        )

    def test_el_envasado_no_acepta_una_mantequera(self):
        self.assertNotIn(Equipo.Tipo.MANTEQUERA, tipos_equipo_para_etapa(EtapaProceso.Tipo.ENVASADO))

    def test_una_mantequera_no_abre_lotes_desde_un_vale(self):
        # Cae en el valor por defecto de `tipo_etapa_de_apertura` (Secado), que
        # no abre desde un vale: correcto para una mantequera.
        self.assertFalse(abre_desde_vale(Equipo.Tipo.MANTEQUERA))
