"""Regresiones de consultas para listados de inventario."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from usuarios.models import PerfilUsuario

from .models import (
    Bodega,
    DetalleSolicitudMaterial,
    Existencia,
    Insumo,
    InsumoProveedor,
    LiberacionExcepcionalMaterial,
    LoteInventario,
    Proveedor,
    SolicitudMaterial,
    Ubicacion,
)
from .serializers import (
    InsumoSerializer,
    LiberacionExcepcionalSerializer,
    SolicitudMaterialSerializer,
)
from .views import (
    InsumoViewSet,
    LiberacionExcepcionalViewSet,
    SolicitudMaterialViewSet,
)


class RendimientoListadoInsumosTests(TestCase):
    def test_existencias_y_eoq_no_agregan_consultas_por_insumo(self):
        bodega = Bodega.objects.create(codigo="B-PERF", nombre="Bodega rendimiento")
        ubicacion = Ubicacion.objects.create(
            bodega=bodega, codigo="DISP-PERF", tipo=Ubicacion.Tipo.DISPONIBLE
        )
        ids = []
        for numero in range(3):
            insumo = Insumo.objects.create(
                codigo=f"PERF-{numero}",
                nombre=f"Material {numero}",
                area=PerfilUsuario.Area.BODEGA,
                unidad=Insumo.Unidad.KG,
                demanda_anual=1000,
                costo_por_pedido=10,
                costo_mantencion_unitario=2,
            )
            proveedor = Proveedor.objects.create(
                rut=f"99.999.99{numero}-{numero}", nombre=f"Proveedor {numero}"
            )
            InsumoProveedor.objects.create(
                insumo=insumo, proveedor=proveedor, principal=True
            )
            for lote_numero in range(2):
                lote = LoteInventario.objects.create(
                    insumo=insumo,
                    codigo=f"L-{numero}-{lote_numero}",
                    estado_calidad=LoteInventario.EstadoCalidad.NO_REQUIERE,
                )
                Existencia.objects.create(
                    lote=lote, ubicacion=ubicacion, cantidad_fisica=10
                )
            ids.append(insumo.id)

        consulta = InsumoViewSet.queryset.filter(pk__in=ids).order_by("pk")

        # Insumos, lotes, existencias+ubicación y proveedores principales.
        # La cifra no crece al agregar filas ni posiciones de stock.
        with self.assertNumQueries(4):
            datos = InsumoSerializer(consulta, many=True).data

        self.assertEqual(len(datos), 3)
        self.assertEqual(datos[0]["stock_fisico"], Decimal("20.000"))
        self.assertEqual(datos[0]["stock_disponible"], Decimal("20.000"))


class RendimientoLiberacionesExcepcionalesTests(TestCase):
    def test_saldo_no_agrega_dos_consultas_por_concesion(self):
        solicitante = User.objects.create_user("solicitante-perf")
        calidad = User.objects.create_user("calidad-perf")
        insumo = Insumo.objects.create(
            codigo="CONC-PERF",
            nombre="Material concesionado",
            area=PerfilUsuario.Area.BODEGA,
            unidad=Insumo.Unidad.KG,
        )
        lote = LoteInventario.objects.create(
            insumo=insumo,
            codigo="CONC-LOTE-PERF",
            estado_calidad=LoteInventario.EstadoCalidad.BLOQUEADO,
        )
        ids = [
            LiberacionExcepcionalMaterial.objects.create(
                lote=lote,
                cantidad=100,
                uso_especifico=f"Uso {numero}",
                justificacion="Autorización de prueba de rendimiento",
                solicitante=solicitante,
                aprobada_calidad_por=calidad,
                vence_en=timezone.now() + timedelta(days=1),
            ).id
            for numero in range(3)
        ]
        consulta = LiberacionExcepcionalViewSet.queryset.filter(pk__in=ids)

        # La suma del libro viaja anotada en la misma consulta; ``saldo`` la
        # reutiliza y no vuelve a agregar por cada fila.
        with self.assertNumQueries(1):
            datos = LiberacionExcepcionalSerializer(consulta, many=True).data

        self.assertEqual(len(datos), 3)
        self.assertTrue(all(
            Decimal(fila["cantidad_usada"]) == Decimal("0") for fila in datos
        ))
        self.assertTrue(all(Decimal(fila["saldo"]) == Decimal("100") for fila in datos))


class RendimientoSolicitudesMaterialTests(TestCase):
    def test_detalles_no_consultan_el_insumo_por_cada_linea(self):
        solicitante = User.objects.create_user("solicitante-mrq-perf")
        insumos = [
            Insumo.objects.create(
                codigo=f"MRQ-PERF-{numero}",
                nombre=f"Material MRQ {numero}",
                area=PerfilUsuario.Area.BODEGA,
                unidad=Insumo.Unidad.KG,
            )
            for numero in range(2)
        ]
        ids = []
        for numero in range(3):
            solicitud = SolicitudMaterial.objects.create(
                numero=f"MRQ-PERF-{numero}",
                area=PerfilUsuario.Area.SECADO,
                solicitante=solicitante,
                fecha_requerida=timezone.localdate(),
            )
            DetalleSolicitudMaterial.objects.bulk_create(
                [
                    DetalleSolicitudMaterial(
                        solicitud=solicitud,
                        insumo=insumo,
                        cantidad_solicitada=10,
                    )
                    for insumo in insumos
                ]
            )
            ids.append(solicitud.id)

        consulta = SolicitudMaterialViewSet.queryset.filter(pk__in=ids)

        # Solicitudes y todos sus detalles+insumo: el número no crece con las
        # seis líneas anidadas.
        with self.assertNumQueries(2):
            datos = SolicitudMaterialSerializer(consulta, many=True).data

        self.assertEqual(sum(len(fila["detalles"]) for fila in datos), 6)
        self.assertTrue(all(
            detalle["insumo_nombre"].startswith("Material MRQ")
            for fila in datos
            for detalle in fila["detalles"]
        ))
