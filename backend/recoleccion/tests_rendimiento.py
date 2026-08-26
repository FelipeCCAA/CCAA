"""Regresiones de consultas para el listado de recolecciones."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from maestros.models import Vehiculo

from .models import CargaModulo, ParadaRuta, Recoleccion, RutaRecoleccion
from .serializers import RecoleccionSerializer
from .views import RecoleccionViewSet


class RendimientoListadoRecoleccionTests(TestCase):
    def test_estado_de_cargas_no_consulta_por_cada_carga(self):
        usuario = User.objects.create_user("recoleccion-perf")
        vehiculo = Vehiculo.objects.create(placa="PERF01", numero="P-01")
        ruta = RutaRecoleccion.objects.create(
            codigo="R-PERF",
            fecha=timezone.localdate(),
            vehiculo=vehiculo,
            creada_por=usuario,
        )
        ids = []
        for numero in range(3):
            parada = ParadaRuta.objects.create(
                ruta=ruta,
                orden=numero + 1,
                proveedor=f"Proveedor {numero}",
                predio=f"Predio {numero}",
            )
            recoleccion = Recoleccion.objects.create(
                parada=parada,
                fecha_hora=timezone.now(),
                litros_medidos=Decimal("1000"),
                alcohol=Recoleccion.Alcohol.CONFORME,
                codigo_muestra=f"M-PERF-{numero}",
                operador=usuario,
            )
            for modulo in range(2):
                CargaModulo.objects.create(
                    codigo=f"C-PERF-{numero}-{modulo}",
                    recoleccion=recoleccion,
                    modulo=f"M{modulo + 1}",
                    litros=Decimal("500"),
                )
            ids.append(recoleccion.id)

        consulta = RecoleccionViewSet.queryset.filter(pk__in=ids)

        # Una consulta para recepciones y otra para todas sus cargas. El
        # ``Exists`` que calcula si fueron recibidas viaja en esa segunda SQL.
        with self.assertNumQueries(2):
            datos = RecoleccionSerializer(consulta, many=True).data

        self.assertEqual(sum(len(fila["cargas"]) for fila in datos), 6)
        self.assertFalse(any(
            carga["recepcionada"]
            for fila in datos
            for carga in fila["cargas"]
        ))

