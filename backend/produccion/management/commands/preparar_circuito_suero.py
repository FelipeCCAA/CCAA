"""Prepara datos aislados para recorrer por pantalla el circuito de Suero.

No define parámetros oficiales de planta. Los maestros creados llevan el
sufijo E2E y las especificaciones declaran expresamente su carácter simulado.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from inventario.models import Bodega, Insumo, LoteInventario, Ubicacion
from inventario.servicios import registrar_entrada
from maestros.models import (
    DocumentoLiberacion,
    Equipo,
    Especificacion,
    FormatoEnvasado,
    Mandante,
    Producto,
    Receta,
    RecetaComponente,
)
from procesos.models import EtapaProceso, Proceso, RutaProducto
from produccion.models import OrdenProduccion
from usuarios.models import PerfilUsuario, Sucursal


class Command(BaseCommand):
    help = "Prepara materia prima, ruta y envase E2E para Secado de suero."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar", action="store_true",
            help="Escribe los datos E2E. Sin esta opción simula y revierte.",
        )

    def handle(self, *args, **opciones):
        with transaction.atomic():
            resumen = self._preparar()
            if not opciones["aplicar"]:
                transaction.set_rollback(True)
        for linea in resumen:
            self.stdout.write(linea)
        mensaje = "Circuito visual de Suero preparado."
        if opciones["aplicar"]:
            self.stdout.write(self.style.SUCCESS(mensaje))
        else:
            self.stdout.write(self.style.WARNING(f"Simulación: {mensaje} Usa --aplicar."))

    def _preparar(self):
        planta = Sucursal.objects.filter(activa=True).select_related("empresa").order_by("id").first()
        if planta is None:
            raise CommandError("No existe una planta activa.")
        usuario = User.objects.filter(
            username="e2e_inventario", perfil__sucursal=planta,
            perfil__area=PerfilUsuario.Area.BODEGA,
        ).first()
        if usuario is None:
            raise CommandError("Ejecuta primero manage.py crear_usuarios_flujo_e2e.")

        sufijo = timezone.now().strftime("%Y%m%d%H%M%S%f")
        empresa = planta.empresa
        mandante, _ = Mandante.objects.get_or_create(
            empresa=empresa, codigo_cliente="E2E-SUERO",
            defaults={"nombre": "Mandante E2E Suero"},
        )
        producto, _ = Producto.objects.get_or_create(
            mandante=mandante, nombre="Suero en polvo E2E",
            defaults={
                "familia": Producto.Familia.POLVO,
                "categoria": Producto.Categoria.SUERO,
                "naturaleza": Producto.Naturaleza.TERMINADO,
                "formato": Producto.Formato.BIG_BAG,
                "unidad_base": Producto.Unidad.KG,
            },
        )
        Especificacion.objects.get_or_create(
            producto=producto, version=1,
            defaults={
                "vigente_desde": date.today(),
                "rangos": {"humedad": {"min": 0, "max": 10, "obligatorio": True}},
                "fuente": "Rango simulado exclusivo del circuito E2E; no operacional.",
            },
        )

        insumo, _ = Insumo.objects.get_or_create(
            empresa=empresa, codigo="SUE-EXT-E2E",
            defaults={
                "nombre": "Suero externo E2E", "categoria": Insumo.Categoria.MATERIA_PRIMA,
                "area": PerfilUsuario.Area.SECADO, "unidad": Insumo.Unidad.KG,
                "requiere_calidad": True, "requiere_lote": True,
            },
        )
        bodega_mp, _ = Bodega.objects.get_or_create(
            sucursal=planta, codigo="BMP-SUE-E2E",
            defaults={"nombre": "Materia prima Suero E2E", "area": PerfilUsuario.Area.BODEGA},
        )
        ubicacion_mp, _ = Ubicacion.objects.get_or_create(
            bodega=bodega_mp, codigo="SUE-DISP-E2E",
            defaults={"tipo": Ubicacion.Tipo.DISPONIBLE, "descripcion": "Suero E2E aprobado"},
        )
        lote_externo = LoteInventario.objects.create(
            sucursal=planta, insumo=insumo, codigo=f"SUERO-EXTERNO-E2E-{sufijo}",
            estado_calidad=LoteInventario.EstadoCalidad.APROBADO,
        )
        registrar_entrada(
            lote=lote_externo, ubicacion=ubicacion_mp, cantidad=Decimal("1000"),
            usuario=usuario, documento_tipo="produccion.PrepararCircuitoSuero",
            documento_id=lote_externo.pk,
        )

        torre, _ = Equipo.objects.get_or_create(
            sucursal=planta, codigo="TOR-SUERO-E2E",
            defaults={"nombre": "Torre Suero E2E", "tipo": Equipo.Tipo.TORRE},
        )
        envasadora, _ = Equipo.objects.get_or_create(
            sucursal=planta, codigo="ENV-SUERO-E2E",
            defaults={"nombre": "Envasadora Big Bag E2E", "tipo": Equipo.Tipo.ENVASADORA},
        )
        proceso, _ = Proceso.objects.get_or_create(
            codigo="ruta-suero-e2e", defaults={"nombre": "Ruta Suero E2E"}
        )
        EtapaProceso.objects.get_or_create(
            proceso=proceso, codigo="secado-suero-e2e",
            defaults={
                "nombre": "Secado Suero E2E", "tipo": EtapaProceso.Tipo.SECADO,
                "orden": 1, "requiere_calidad": True,
            },
        )
        EtapaProceso.objects.get_or_create(
            proceso=proceso, codigo="envase-suero-e2e",
            defaults={
                "nombre": "Envasado Suero E2E", "tipo": EtapaProceso.Tipo.ENVASADO,
                "orden": 2,
            },
        )
        RutaProducto.objects.update_or_create(
            sucursal=planta, producto=producto, proceso=proceso,
            defaults={
                "insumo_origen": insumo, "destino_final": RutaProducto.DestinoFinal.ENVASADO,
                "destino": "Secado → Calidad → Big Bag → Calidad → Inventario",
                "observaciones": "Ruta simulada exclusiva del circuito E2E.", "activa": True,
            },
        )
        orden = OrdenProduccion.objects.create(
            sucursal=planta, codigo=f"OP-SUERO-E2E-{sufijo}", producto=producto,
            cantidad_planificada=Decimal("700"), unidad="kg",
            estado=OrdenProduccion.Estado.PROGRAMADA, creada_por=usuario,
        )

        formato, _ = FormatoEnvasado.objects.get_or_create(
            producto=producto, codigo="BIG-BAG-700-E2E",
            defaults={
                "nombre": "Big Bag 700 kg E2E", "kg_neto": Decimal("700"),
                "unidades_maximas_pallet": 1,
                "tipo_unidad_logistica": FormatoEnvasado.TipoUnidadLogistica.BIG_BAG,
            },
        )
        formato.equipos.add(envasadora)
        envase, _ = Insumo.objects.get_or_create(
            empresa=empresa, codigo="ENV-BB-700-E2E",
            defaults={
                "nombre": "Envase Big Bag 700 kg E2E", "categoria": Insumo.Categoria.EMPAQUE,
                "area": PerfilUsuario.Area.ENVASE, "unidad": Insumo.Unidad.UN,
                "requiere_calidad": False,
            },
        )
        receta, _ = Receta.objects.get_or_create(
            producto=producto, version=1,
            defaults={
                "cantidad_base": Decimal("700"), "vigente_desde": date.today(),
                "fuente": "Receta simulada exclusiva del circuito E2E.",
            },
        )
        RecetaComponente.objects.get_or_create(
            receta=receta, insumo=envase, fase=RecetaComponente.Fase.ENVASADO,
            defaults={"cantidad": Decimal("1"), "unidad": "un"},
        )
        bodega_envase, _ = Bodega.objects.get_or_create(
            sucursal=planta, codigo="BENV-SUE-E2E",
            defaults={"nombre": "Envases Suero E2E", "area": PerfilUsuario.Area.BODEGA},
        )
        ubicacion_envase, _ = Ubicacion.objects.get_or_create(
            bodega=bodega_envase, codigo="ENV-DISP-E2E",
            defaults={"tipo": Ubicacion.Tipo.DISPONIBLE},
        )
        lote_envase = LoteInventario.objects.create(
            sucursal=planta, insumo=envase, codigo=f"BB-E2E-{sufijo}",
            estado_calidad=LoteInventario.EstadoCalidad.NO_REQUIERE,
        )
        registrar_entrada(
            lote=lote_envase, ubicacion=ubicacion_envase, cantidad=Decimal("2"),
            usuario=usuario, documento_tipo="produccion.PrepararCircuitoSuero",
            documento_id=lote_envase.pk,
        )
        if not DocumentoLiberacion.objects.filter(
            empresa=empresa, aplica_a__contains=[Producto.Familia.POLVO], activo=True,
        ).exists():
            DocumentoLiberacion.objects.create(
                empresa=empresa, codigo="LIB-SUERO-E2E", nombre="Liberación Suero E2E",
                aplica_a=[Producto.Familia.POLVO],
                plantilla=[{
                    "clave": "lote", "etiqueta": "Lote", "tipo": "texto",
                    "req": True, "origen": "lote.codigo_lote",
                }],
                fuente="Documento mínimo exclusivo del circuito E2E.",
            )
        return [
            f"Orden: {orden.codigo}", f"Lote externo: {lote_externo.codigo} (1.000 kg)",
            f"Producto: {producto.nombre}", "Formato: Big Bag 700 kg E2E",
        ]
