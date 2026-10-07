"""
Borra los movimientos de planta y deja los maestros en pie.

El sistema está en desarrollo y lo que hay son datos de prueba acumulados a
mano. Lo que se borra es **lo que se produce operando**: recepciones, vales,
lotes, ejecuciones y corridas, análisis, liberaciones, existencias, pallets,
despachos, planes. Lo que se conserva es **lo que cuesta volver a cargar**: los
productos, los mandantes, los silos, los equipos, los vehículos, el catálogo de
documentos, las especificaciones, las recetas, los insumos, las ubicaciones,
las personas y sus perfiles —y sus sesiones: limpiar la planta no tiene por qué
cerrarle la sesión a nadie—.

Qué es transaccional lo dice **una sola lista**,
`reset_datos_operacionales.MODELOS_OPERACIONALES`; este comando la comparte en
vez de llevar la suya. Su lista escrita a mano, en orden de borrado, envejeció:
no conocía las corridas, la liberación por proceso ni el inventario de producto
terminado, y chocaba con una clave `PROTECT` en cuanto alguien cerraba un lote.
Ahora el borrado es un único `TRUNCATE` de todas las tablas a la vez, así que
**no hay orden** que mantener, y `tablas_para_reset` aborta si una tabla que se
conserva apunta a una que se borra. `MODELOS_CONSERVADOS` declara el resto, y
`usuarios.tests_limpiar_transaccional` falla cuando aparece un modelo que no
está en ninguna de las dos: cada modelo nuevo obliga a decidir qué es.

Sin `--aplicar` solo cuenta lo que borraría. Es la misma forma que
`cargar_productos`: una orden destructiva que se ejecuta a ciegas es una que
tarde o temprano se ejecuta sobre lo que no era. Nunca corre en un entorno
endurecido (`config.seguridad.ENTORNOS_ENDURECIDOS`).

La auditoría se borra también **a propósito**: es el registro de los cambios que
estamos borrando, y dejarla convertiría el expediente en una lista de
referencias a filas que ya no existen.
"""

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from config.seguridad import ENTORNOS_ENDURECIDOS
from usuarios.management.commands.reset_datos_operacionales import (
    MODELOS_OPERACIONALES,
    tablas_para_reset,
)


# Lo que se conserva. Los de `usuarios` que figuran también en
# `MODELOS_OPERACIONALES` —intentos de acceso, sesiones, eventos de
# seguridad— son de las personas, no de la planta: este comando los deja.
MODELOS_CONSERVADOS = frozenset({
    "maestros.DocumentoLiberacion",
    "maestros.Equipo",
    "maestros.Especificacion",
    "maestros.FormatoEnvasado",
    "maestros.Mandante",
    "maestros.Producto",
    "maestros.Receta",
    "maestros.RecetaComponente",
    "maestros.Silo",
    "maestros.Vehiculo",
    "inventario.Bodega",
    "inventario.ClienteDespacho",
    "inventario.Insumo",
    "inventario.InsumoProveedor",
    "inventario.PlantillaInspeccion",
    "inventario.Proveedor",
    "inventario.Ubicacion",
    "mantenimiento.PlanPreventivo",
    "planificacion.CapacidadProceso",
    "planificacion.CodigoProduccion",
    "planificacion.StockSeguridadPlan",
    "planificacion.TipoActividadPlan",
    "procesos.EtapaProceso",
    "procesos.Proceso",
    "procesos.RutaProducto",
    "usuarios.AreaDePerfil",
    "usuarios.Empresa",
    "usuarios.PerfilUsuario",
    "usuarios.Sucursal",
    "usuarios.EventoSeguridad",
    "usuarios.IntentoAcceso",
    "usuarios.SesionUsuario",
})


def modelos_a_borrar():
    """Los transaccionales de `MODELOS_OPERACIONALES` menos los conservados."""
    modelos = []
    faltantes = []
    for etiqueta in MODELOS_OPERACIONALES:
        if etiqueta in MODELOS_CONSERVADOS:
            continue
        try:
            modelos.append(apps.get_model(etiqueta))
        except LookupError:
            faltantes.append(etiqueta)
    if faltantes:
        raise CommandError(
            "Modelos declarados que no existen: " + ", ".join(faltantes)
        )
    return modelos


class Command(BaseCommand):
    help = "Borra los movimientos de planta y conserva los maestros."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Borra de verdad. Sin esto solo cuenta.",
        )

    def handle(self, *args, **opciones):
        if settings.DJANGO_ENV in ENTORNOS_ENDURECIDOS:
            raise CommandError(
                f"DJANGO_ENV={settings.DJANGO_ENV}: este comando borra la operación "
                "de la planta y solo corre en desarrollo o pruebas."
            )
        aplicar = opciones["aplicar"]
        modelos = modelos_a_borrar()
        # Se calcula también sin `--aplicar`: si una tabla conservada apunta a
        # una que se borra, la vista previa ya lo dice.
        tablas = tablas_para_reset(modelos)

        with transaction.atomic():
            total = 0
            for modelo in sorted(modelos, key=lambda m: m._meta.label):
                cuantos = modelo.objects.count()
                if cuantos:
                    total += cuantos
                    self.stdout.write(f"  {modelo._meta.label:<44}{cuantos}")

            if aplicar:
                nombres = ", ".join(connection.ops.quote_name(tabla) for tabla in tablas)
                with connection.cursor() as cursor:
                    # PostgreSQL no trunca una tabla con verificaciones de
                    # clave diferidas pendientes en la transacción (pasa si
                    # alguien la llama dentro de otra que ya escribió, como
                    # una prueba). Dispararlas antes es inocuo en el uso
                    # normal, donde no hay ninguna.
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                    cursor.execute(f"TRUNCATE TABLE {nombres}")

        verbo = "Borrados" if aplicar else "Se borrarían"
        self.stdout.write(self.style.SUCCESS(f"{verbo} {total} registros."))

        if not aplicar:
            self.stdout.write("Nada se escribió. Repite con --aplicar.")
