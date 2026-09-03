from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from maestros.models import Equipo, Especificacion, Mandante, Producto
from planificacion.models import CapacidadProceso
from procesos.models import Proceso, RutaProducto
from usuarios.models import Sucursal


FUENTE = (
    "Referencia provisional de ingeniería: GEA CleanSkimmer 100 (hasta 15.000 L/h) "
    "y Tetra Pak Dairy Processing Handbook, separación 0,04-0,07% MG. Validar CCAA."
)


class Command(BaseCommand):
    help = "Prepara maestros provisionales y trazables para operar Descremado."

    def add_arguments(self, parser):
        parser.add_argument("--sucursal", type=int)
        parser.add_argument("--aplicar", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        sucursales = Sucursal.objects.filter(activa=True).select_related("empresa")
        if options["sucursal"]:
            sucursales = sucursales.filter(pk=options["sucursal"])
        if sucursales.count() != 1:
            raise CommandError("Indica --sucursal cuando no exista una única planta activa.")
        sucursal = sucursales.get()
        if not options["aplicar"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Vista previa para {sucursal.nombre}: DES-01 15.000 L/h, "
                    "leche descremada líquida y especificaciones provisionales. "
                    "Usa --aplicar para guardar."
                )
            )
            transaction.set_rollback(True)
            return

        mandante = Mandante.objects.filter(
            empresa=sucursal.empresa, codigo_cliente=Mandante.Cliente.NO_DEFINIDO,
        ).first()
        if mandante is None:
            mandante = Mandante.objects.create(
                empresa=sucursal.empresa,
                nombre="CCAA",
                codigo_cliente=Mandante.Cliente.NO_DEFINIDO,
            )

        equipo, _ = Equipo.objects.get_or_create(
            sucursal=sucursal,
            codigo="des-01",
            defaults={
                "nombre": "Descremadora DES-01 · referencia 15.000 L/h",
                "sigla": "D1",
                "tipo": Equipo.Tipo.DESCREMADORA,
                "consume_leche": False,
                "consume_materiales": False,
                "orden": 25,
                "activo": True,
            },
        )
        CapacidadProceso.objects.get_or_create(
            equipo=equipo,
            vigente_desde=date(2026, 1, 1),
            defaults={
                "capacidad_hora": Decimal("15000"),
                "unidad": "L/h",
                "observacion": FUENTE[:250],
            },
        )

        descremada, _ = Producto.objects.get_or_create(
            mandante=mandante,
            nombre="Leche descremada líquida intermedia CCAA",
            defaults={
                "naturaleza_comercial": Producto.NaturalezaComercial.PRODUCTO_PROPIO,
                "categoria": Producto.Categoria.LECHE_FLUIDA,
                "tipo": Producto.TipoProducto.DESCREMADA,
                "formato": Producto.Formato.GRANEL,
                "mercado": Producto.Mercado.LOCAL,
                "familia": Producto.Familia.LIQUIDO,
                "naturaleza": Producto.Naturaleza.INTERMEDIO,
                "unidad_base": Producto.Unidad.L,
            },
        )
        proceso_polvo = Proceso.objects.filter(codigo="ruta-polvo", activo=True).first()
        if proceso_polvo is None:
            raise CommandError("Falta el proceso activo ruta-polvo; no se inventó una ruta paralela.")
        proceso_mantequilla = Proceso.objects.filter(
            codigo="ruta-mantequilla", activo=True,
        ).first()
        RutaProducto.objects.get_or_create(
            sucursal=sucursal, producto=descremada, proceso=proceso_polvo,
            defaults={
                "prioridad": 1,
                "destino_final": RutaProducto.DestinoFinal.ENVASADO,
                "destino": "Estandarización → Evaporación → Secado → Envasado",
                "observaciones": "Ruta provisional para validar por Producción y Calidad.",
                "activa": True,
            },
        )
        Especificacion.objects.get_or_create(
            producto=descremada,
            tipo_analisis=Especificacion.TipoAnalisis.SILO,
            version=1,
            defaults={
                "vigente_desde": date(2026, 1, 1),
                "rangos": {
                    "mg": {"min": 0.04, "max": 0.07, "obligatorio": True},
                    "sng": {"min": 8.6, "max": 9.2, "obligatorio": True},
                    "ph": {"min": 6.5, "max": 6.8, "obligatorio": True},
                },
                "fuente": FUENTE[:250],
            },
        )

        cremas = Producto.objects.filter(
            mandante__empresa=sucursal.empresa,
            familia=Producto.Familia.CREMA,
            naturaleza=Producto.Naturaleza.INTERMEDIO,
            activo=True,
        )
        for crema in cremas:
            if proceso_mantequilla is not None:
                RutaProducto.objects.get_or_create(
                    sucursal=sucursal,
                    producto=crema,
                    proceso=proceso_mantequilla,
                    defaults={
                        "prioridad": 2,
                        "destino_final": RutaProducto.DestinoFinal.ENVASADO,
                        "destino": "Mantequilla → Calidad → Envasado",
                        "observaciones": (
                            "Alternativa provisional para crema liberada; "
                            "validar por Producción y Calidad antes de publicar."
                        ),
                        "activa": True,
                    },
                )
            Especificacion.objects.get_or_create(
                producto=crema,
                tipo_analisis=Especificacion.TipoAnalisis.SILO,
                version=1,
                defaults={
                    "vigente_desde": date(2026, 1, 1),
                    "rangos": {
                        "mg": {"min": 40.0, "max": 44.0, "obligatorio": True},
                        "ph": {"min": 6.4, "max": 6.8, "obligatorio": True},
                    },
                    "fuente": (
                        "Objetivo local nominal 42% según nombre del producto; "
                        "referencia Tetra Pak 35-40%. Banda provisional, validar CCAA."
                    ),
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Descremado preparado en {sucursal.nombre}: DES-01, {descremada.nombre}, "
            f"rutas y {cremas.count() + 1} especificaciones de silo."
        ))
