from django.core.management.base import BaseCommand
from django.db import transaction

from inventario.models import Bodega, Insumo, Ubicacion
from usuarios.models import Empresa, Sucursal


class Command(BaseCommand):
    help = "Crea el catálogo y ubicaciones iniciales para embalaje y producto terminado."

    def add_arguments(self, parser):
        parser.add_argument("--empresa", type=int, required=True)
        parser.add_argument("--aplicar", action="store_true")

    def handle(self, *args, **options):
        empresa = Empresa.objects.filter(pk=options["empresa"]).first()
        if empresa is None:
            self.stderr.write("La empresa indicada no existe.")
            return
        sucursal = Sucursal.objects.filter(empresa=empresa, activa=True).order_by("id").first()
        if sucursal is None:
            self.stderr.write("La empresa no tiene una sucursal activa.")
            return
        if not options["aplicar"]:
            self.stdout.write("Vista previa: use --aplicar para crear catálogo y ubicaciones.")
            return

        materiales = [
            ("EMB-BOL-25", "Bolsa para leche en polvo 25 kg", "empaque", "envase", "un", True, True),
            ("EMB-ETQ-25", "Etiqueta leche en polvo 25 kg", "empaque", "envase", "un", True, False),
            ("EMB-FILM", "Film stretch para pallet", "empaque", "bodega", "un", False, False),
            ("EMB-PALLET", "Pallet madera industrial", "empaque", "bodega", "un", False, False),
        ]
        with transaction.atomic():
            bodega, _ = Bodega.objects.get_or_create(
                sucursal=sucursal, codigo="BEM", defaults={"nombre": "Bodega de embalaje", "area": "bodega"}
            )
            bodega_producto, _ = Bodega.objects.get_or_create(
                sucursal=sucursal, codigo="BPT",
                defaults={"nombre": "Bodega de producto terminado", "area": "bodega"},
            )
            for codigo, nombre, categoria, area, unidad, calidad, certificado in materiales:
                Insumo.objects.get_or_create(
                    empresa=empresa, codigo=codigo,
                    defaults={
                        "nombre": nombre, "categoria": categoria, "area": area,
                        "unidad": unidad, "requiere_lote": True,
                        "requiere_calidad": calidad, "requiere_certificado": certificado,
                        "stock_minimo": 100, "stock_seguridad": 100,
                    },
                )
            for codigo, tipo, descripcion in [
                ("EMB-DISP", "disponible", "Material liberado para producción"),
                ("EMB-CUAR", "cuarentena", "Material pendiente de decisión de Calidad"),
                ("EMB-RECH", "rechazado", "Material rechazado o bloqueado"),
            ]:
                Ubicacion.objects.get_or_create(
                    bodega=bodega, codigo=codigo, defaults={"tipo": tipo, "descripcion": descripcion}
                )
            for codigo, tipo, descripcion in [
                ("PT-CUAR", "cuarentena", "Producto terminado pendiente de Calidad"),
                ("PT-DISP", "disponible", "Producto terminado liberado"),
            ]:
                Ubicacion.objects.get_or_create(
                    bodega=bodega_producto, codigo=codigo,
                    defaults={"tipo": tipo, "descripcion": descripcion},
                )
        self.stdout.write(self.style.SUCCESS("Catálogo de embalaje y ubicaciones operativas configurados."))
