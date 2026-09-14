"""Reinicia datos transaccionales sin tocar la configuración maestra."""

from __future__ import annotations

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


ENTORNOS_PERMITIDOS = {"development", "dev", "qa", "test", "testing"}
MARCAS_PRODUCCION = {"prod", "production", "produccion"}

# Fuente única del alcance del reset. Todo lo que se genera operando la planta
# pertenece aquí; catálogos, usuarios, permisos, áreas, equipos, productos,
# rutas, especificaciones y ubicaciones se conservan.
MODELOS_OPERACIONALES = (
    "usuarios.IntentoAcceso",
    "usuarios.SesionUsuario",
    "usuarios.EventoSeguridad",
    "auditoria.RegistroAuditoria",
    "recepcion.Recepcion",
    "recepcion.ModuloRecepcion",
    "recepcion.CorreccionRecepcion",
    "recepcion.AlertaCalidadSilo",
    "recepcion.MovimientoSilo",
    "recepcion.AtribucionRecepcion",
    "recepcion.ControlInhibidores",
    "recepcion.BusquedaProveedor",
    "recepcion.AnalisisSilo",
    "recepcion.DespachoLeche",
    "recoleccion.RutaRecoleccion",
    "recoleccion.ParadaRuta",
    "recoleccion.Recoleccion",
    "recoleccion.CargaModulo",
    "estandarizacion.ValeEstandarizacion",
    "estandarizacion.CorreccionValeEstandarizacion",
    "produccion.OrdenProduccion",
    "produccion.Lote",
    "produccion.CorreccionLote",
    "produccion.Analisis",
    "produccion.ControlProceso",
    "produccion.ControlProcesoLectura",
    "produccion.RegistroEnvase",
    "produccion.PalletProducto",
    "procesos.CorridaCondensacion",
    "procesos.CorridaSecado",
    "procesos.CorridaDescremacion",
    "procesos.ReservaSiloProceso",
    "procesos.CorridaMantequilla",
    "procesos.EjecucionProceso",
    "procesos.EntradaProceso",
    "procesos.SalidaProceso",
    "procesos.EventoProceso",
    "procesos.AutorizacionReproceso",
    "calidad.RegistroCalidad",
    "calidad.Liberacion",
    "calidad.LiberacionProceso",
    "calidad.RegistroEquipo",
    "inocuidad.MonitoreoPPRO",
    "inocuidad.PproLectura",
    "inventario.ConsumoLoteProduccion",
    "inventario.CicloCIP",
    "inventario.EtapaCIP",
    "inventario.LoteInventario",
    "inventario.Existencia",
    "inventario.MovimientoInventario",
    "inventario.SolicitudCompra",
    "inventario.Aprobacion",
    "inventario.DetalleSolicitudCompra",
    "inventario.OrdenCompra",
    "inventario.DetalleOrdenCompra",
    "inventario.RecepcionCompra",
    "inventario.DetalleRecepcionCompra",
    "inventario.InspeccionMaterial",
    "inventario.NoConformidadMaterial",
    "inventario.LiberacionExcepcionalMaterial",
    "inventario.Adjunto",
    "inventario.SolicitudMaterial",
    "inventario.DetalleSolicitudMaterial",
    "inventario.ReservaInventario",
    "inventario.EntregaProduccion",
    "inventario.DetalleEntregaProduccion",
    "inventario.AjusteInventario",
    "inventario.DevolucionProduccion",
    "inventario.EjecucionMRP",
    "inventario.ResultadoMRP",
    "inventario.Notificacion",
    "inventario.Alerta",
    "inventario.ExistenciaProductoTerminado",
    "inventario.Despacho",
    "inventario.DetalleDespacho",
    "inventario.DetalleDespachoGranel",
    "inventario.MovimientoProductoTerminado",
    "inventario.UnidadRework",
    "inventario.MovimientoRework",
    "planificacion.SemanaPlan",
    "planificacion.BloquePlan",
    "planificacion.BalanceDia",
    "planificacion.MovimientoPlan",
    "planificacion.VersionSemanaPlan",
    "mantenimiento.OrdenTrabajo",
    "mantenimiento.FallaEquipo",
    "mantenimiento.RepuestoUtilizado",
)


def datos_conexion() -> dict[str, str]:
    configuracion = settings.DATABASES["default"]
    return {
        "entorno": str(getattr(settings, "DJANGO_ENV", "")).strip().lower(),
        "motor": str(configuracion.get("ENGINE", "")),
        "host": str(configuracion.get("HOST") or "(local/archivo)"),
        "puerto": str(configuracion.get("PORT") or "(default)"),
        "base": str(configuracion.get("NAME", "")),
    }


def validar_destino(info: dict[str, str]) -> None:
    entorno = info["entorno"]
    texto_destino = " ".join(info.values()).lower()
    if entorno not in ENTORNOS_PERMITIDOS:
        raise CommandError(
            f"RESET ABORTADO: entorno {entorno!r} no está autorizado."
        )
    if entorno not in {"test", "testing"} and any(
        marca in texto_destino for marca in MARCAS_PRODUCCION
    ):
        raise CommandError("RESET ABORTADO: la conexión parece productiva.")
    if info["motor"] != "django.db.backends.postgresql":
        raise CommandError("RESET ABORTADO: el comando exige PostgreSQL.")
    if entorno in {"development", "dev"} and info["host"].lower() not in {
        "localhost",
        "127.0.0.1",
        "::1",
        "(local/archivo)",
    }:
        raise CommandError(
            "RESET ABORTADO: development solo puede limpiarse en un host local."
        )


def modelos_operacionales():
    modelos = []
    faltantes = []
    for etiqueta in MODELOS_OPERACIONALES:
        try:
            modelos.append(apps.get_model(etiqueta))
        except LookupError:
            faltantes.append(etiqueta)
    if faltantes:
        raise CommandError(
            "RESET ABORTADO: modelos declarados inexistentes: " + ", ".join(faltantes)
        )
    return modelos


def tablas_para_reset(modelos):
    seleccionados = set(modelos)
    tablas = {modelo._meta.db_table for modelo in seleccionados}
    bloqueos = []

    for modelo in apps.get_models(include_auto_created=True):
        referencias = {
            campo.remote_field.model
            for campo in modelo._meta.get_fields()
            if getattr(campo, "many_to_one", False)
            or getattr(campo, "one_to_one", False)
        }
        if not (referencias & seleccionados):
            continue
        if modelo._meta.auto_created:
            tablas.add(modelo._meta.db_table)
        elif modelo not in seleccionados:
            bloqueos.append(modelo._meta.label)

    if bloqueos:
        raise CommandError(
            "RESET ABORTADO: tablas no operacionales dependen de datos a borrar: "
            + ", ".join(sorted(set(bloqueos)))
        )
    return sorted(tablas)


class Command(BaseCommand):
    help = "Borra datos operacionales de desarrollo/QA y conserva maestros."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true")
        parser.add_argument(
            "--confirmar-base",
            default="",
            help="Nombre exacto de la base. Obligatorio junto con --aplicar.",
        )

    def handle(self, *args, **opciones):
        info = datos_conexion()
        self.stdout.write(f"ENTORNO: {info['entorno']}")
        self.stdout.write(f"MOTOR:   {info['motor']}")
        self.stdout.write(f"HOST:    {info['host']}:{info['puerto']}")
        self.stdout.write(f"BASE:    {info['base']}")
        validar_destino(info)

        modelos = modelos_operacionales()
        tablas = tablas_para_reset(modelos)
        conteos = [(modelo._meta.label, modelo.objects.count()) for modelo in modelos]
        total = sum(cantidad for _, cantidad in conteos)
        for etiqueta, cantidad in conteos:
            if cantidad:
                self.stdout.write(f"  {etiqueta:<48}{cantidad:>8}")
        self.stdout.write(f"TOTAL OPERACIONAL: {total}")
        self.stdout.write(f"TABLAS INCLUIDAS:  {len(tablas)}")

        if not opciones["aplicar"]:
            self.stdout.write(self.style.WARNING("VISTA PREVIA: no se borró ningún dato."))
            self.stdout.write(
                f"Para aplicar: --aplicar --confirmar-base {info['base']}"
            )
            return
        if opciones["confirmar_base"] != info["base"]:
            raise CommandError(
                "RESET ABORTADO: --confirmar-base debe coincidir exactamente con la base."
            )

        tablas_sql = ", ".join(connection.ops.quote_name(tabla) for tabla in tablas)
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {tablas_sql} RESTART IDENTITY")
        cache.clear()
        self.stdout.write(self.style.SUCCESS(f"RESET COMPLETO: {total} registros borrados."))
