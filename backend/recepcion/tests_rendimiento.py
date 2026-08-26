"""Regresiones de consultas para análisis de silo."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from maestros.models import Silo

from .models import AnalisisSilo, MovimientoSilo
from .serializers import AnalisisSiloSerializer
from .views import AnalisisSiloViewSet


class RendimientoAnalisisSiloTests(TestCase):
    def test_vigencia_y_motivo_no_consultan_dos_veces_por_analisis(self):
        silo = Silo.objects.create(
            codigo="S-AN-PERF", tipo=Silo.Tipo.SILO, capacidad_l=10000
        )
        ahora = timezone.now()
        ids = [
            AnalisisSilo.objects.create(
                silo=silo,
                tomado_en=ahora - timedelta(hours=numero + 1),
                estado=AnalisisSilo.Estado.CONFIRMADO,
            ).id
            for numero in range(3)
        ]
        MovimientoSilo.objects.create(
            silo=silo,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=100,
            fecha_hora=ahora,
        )
        consulta = AnalisisSiloViewSet.queryset.filter(pk__in=ids)

        # Los dos resúmenes correlacionados viajan en la consulta principal;
        # vigente y motivo reutilizan el mismo resultado en el serializer.
        with self.assertNumQueries(1):
            datos = AnalisisSiloSerializer(consulta, many=True).data

        self.assertTrue(all(not fila["vigente"] for fila in datos))
        self.assertTrue(all("Entraron 100.00 L" in fila["motivo_vigencia"] for fila in datos))

    def test_un_patch_no_reutiliza_la_vigencia_anotada_antes_de_guardar(self):
        silo = Silo.objects.create(
            codigo="S-AN-PATCH", tipo=Silo.Tipo.SILO, capacidad_l=10000
        )
        ahora = timezone.now()
        analisis = AnalisisSilo.objects.create(
            silo=silo,
            tomado_en=ahora - timedelta(hours=1),
            estado=AnalisisSilo.Estado.CONFIRMADO,
        )
        MovimientoSilo.objects.create(
            silo=silo,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=100,
            fecha_hora=ahora,
        )
        instancia = AnalisisSiloViewSet.queryset.get(pk=analisis.pk)
        self.assertFalse(instancia.vigente)

        serializer = AnalisisSiloSerializer(
            instancia,
            data={"tomado_en": ahora + timedelta(minutes=1)},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        AnalisisSiloViewSet().perform_update(serializer)

        self.assertFalse(hasattr(instancia, "ingresos_posteriores_cantidad"))
        self.assertTrue(serializer.data["vigente"])
