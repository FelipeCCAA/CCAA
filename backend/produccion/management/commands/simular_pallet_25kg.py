from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from inventario.models import Bodega, Insumo, LoteInventario, Ubicacion
from inventario.servicios import consumir_receta_produccion, registrar_entrada
from maestros.models import Equipo, Producto, Receta, RecetaComponente
from produccion.models import Lote, RegistroEnvase
from produccion.servicios import registrar_envasado
from usuarios.models import PerfilUsuario, Sucursal


class Command(BaseCommand):
    help = "Crea materiales y simula un pallet de 20 sacos de leche en polvo de 25 kg."

    @transaction.atomic
    def handle(self, *args, **options):
        codigo_lote = "SIM-LP25-500-20260828"
        existente = RegistroEnvase.objects.filter(lote__codigo_lote=codigo_lote).first()
        if existente:
            pallet = existente.pallets.first()
            self.stdout.write(self.style.WARNING(
                f"La simulación ya existe: {pallet.codigo}, {pallet.unidades} sacos, {pallet.kg_neto} kg."
            ))
            return

        sucursal = Sucursal.objects.order_by("id").first()
        usuario = get_user_model().objects.filter(is_superuser=True).order_by("id").first()
        producto = (
            Producto.objects.filter(nombre__icontains="entera en polvo").filter(nombre__icontains="25kg").first()
            or Producto.objects.filter(nombre__icontains="leche en polvo").first()
        )
        equipo = Equipo.objects.filter(
            sucursal=sucursal, activo=True, tipo=Equipo.Tipo.ENVASADORA,
        ).order_by("id").first()
        if not all((sucursal, usuario, producto, equipo)):
            raise CommandError("Falta planta, usuario, producto de leche en polvo o envasadora.")

        bolsa, _ = Insumo.objects.get_or_create(
            empresa=sucursal.empresa, codigo="ENV-SACO-25KG",
            defaults={
                "nombre": "Saco multicapa para leche en polvo 25 kg",
                "descripcion": "Envase primario grado alimentario para formato 25 kg",
                "categoria": Insumo.Categoria.EMPAQUE, "area": PerfilUsuario.Area.ENVASE,
                "unidad": Insumo.Unidad.UN, "contenido_envase": 1,
                "requiere_calidad": True, "stock_minimo": 100,
            },
        )
        pallet_base, _ = Insumo.objects.get_or_create(
            empresa=sucursal.empresa, codigo="ENV-PALLET-500KG",
            defaults={
                "nombre": "Pallet base para carga máxima 500 kg",
                "descripcion": "Base logística; una unidad por cada pallet terminado",
                "categoria": Insumo.Categoria.EMPAQUE, "area": PerfilUsuario.Area.ENVASE,
                "unidad": Insumo.Unidad.UN, "contenido_envase": 1,
                "requiere_calidad": False, "stock_minimo": 10,
            },
        )
        receta = Receta.objects.create(
            producto=producto,
            version=(producto.recetas.order_by("-version").values_list("version", flat=True).first() or 0) + 1,
            cantidad_base=Decimal("500"), vigente_desde=date(2026, 1, 1),
            fuente="Simulación operacional: 20 sacos de 25 kg por pallet",
        )
        RecetaComponente.objects.create(
            receta=receta, insumo=bolsa, cantidad=Decimal("20"), unidad="un",
            fase=RecetaComponente.Fase.ENVASADO,
        )
        RecetaComponente.objects.create(
            receta=receta, insumo=pallet_base, cantidad=Decimal("1"), unidad="un",
            fase=RecetaComponente.Fase.ENVASADO,
        )

        bodega, _ = Bodega.objects.get_or_create(
            sucursal=sucursal, codigo="B-ENV", defaults={"nombre": "Bodega de envases"},
        )
        ubicacion, _ = Ubicacion.objects.get_or_create(
            bodega=bodega, codigo="ENV-DISP",
            defaults={"tipo": Ubicacion.Tipo.DISPONIBLE, "descripcion": "Envases liberados para Producción"},
        )
        for insumo, cantidad in ((bolsa, Decimal("120")), (pallet_base, Decimal("6"))):
            lote_material = LoteInventario.objects.create(
                sucursal=sucursal, insumo=insumo, codigo=f"SIM-20260828-{insumo.codigo}",
                estado_calidad=(
                    LoteInventario.EstadoCalidad.APROBADO
                    if insumo.requiere_calidad
                    else LoteInventario.EstadoCalidad.NO_REQUIERE
                ),
            )
            registrar_entrada(
                lote=lote_material, ubicacion=ubicacion, cantidad=cantidad,
                usuario=usuario, documento_tipo="produccion.SimulacionPallet", documento_id=insumo.pk,
            )

        lote = Lote.objects.create(
            sucursal=sucursal, codigo_lote=codigo_lote, producto=producto,
            fecha=date(2026, 8, 28), estado=Lote.Estado.PRODUCIDO,
            kg_producidos=Decimal("500"), bultos=20,
            observacion="Simulación completa de pallet 20 × 25 kg",
        )
        consumir_receta_produccion(lote_produccion=lote, usuario=usuario)
        ahora = timezone.now()
        registro = registrar_envasado(
            lote_id=lote.pk, equipo=equipo, formato_kg=Decimal("25"),
            inicio=ahora - timedelta(minutes=10), termino=ahora, usuario=usuario,
            pallets=[{"codigo": "PAL-SIM-25KG-500", "unidades": 20, "kg_neto": "500"}],
            observacion="Pallet de simulación: peso máximo permitido",
        )
        pallet = registro.pallets.get()
        self.stdout.write(self.style.SUCCESS(
            f"Simulación completa: {pallet.codigo} · 20 sacos × 25 kg = {pallet.kg_neto} kg. "
            "Consumió 20 sacos y 1 base; quedó en cuarentena de Calidad."
        ))
