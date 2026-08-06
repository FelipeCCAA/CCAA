# Plan de implementación de módulos CCAA

Este documento cruza la especificación funcional de los módulos 01–20 con el
modelo que ya existe. Su regla principal es **extender responsabilidades
existentes y no crear una aplicación Django por cada formulario o Excel**.

## Arquitectura objetivo aplicada al repositorio

- `usuarios`: administración, alcance, autenticación y permisos.
- `maestros`: catálogos, equipos, silos, productos, especificaciones y recetas.
- `planificacion`: semana, programa, balance y futuras órdenes/reservas.
- `recepcion`: llegada por módulo, muestra, decisión, silo y descarga.
- `calidad` + `inocuidad`: resultados, liberaciones, PCC y PPRO.
- `procesos`: motor común para fabricación, descremación, condensación, secado,
  envase y mantequilla; las diferencias deben vivir en etapas y formularios
  versionados, no en tablas copiadas.
- `produccion`: lotes, controles y cantidades producidas.
- `inventario`: materiales, bodega, compras, cuarentena, reservas y MRP.
- `mantenimiento`: equipos, planes, fallas, órdenes y repuestos.
- `auditoria`: eventos inmutables y consultas transversales.

Aplicaciones nuevas solo cuando exista una identidad y ciclo propio que no
quepa limpiamente en lo anterior: `recoleccion`, `saneamiento` y `despachos`.

## Cobertura y brechas

| Módulo | Cobertura actual | Decisión |
|---|---|---|
| 01 Administración | Alta | Extender permisos por acción/área y sesiones; no reemplazar usuarios actuales. |
| 02 Maestros | Alta | Agregar predios, conductores, módulos de transporte, áreas y líneas cuando los flujos los necesiten. |
| 03 Planificación | Media | Mantener semana/Gantt/balance; agregar Orden de Producción, ruta, versión y reservas. |
| 04 Recolección | Ausente | Crear módulo propio con ruta, parada, control de origen, muestra, carga por módulo, voucher e idempotencia. |
| 05 Recepción | Alta | Flujo ya alineado; falta enlace formal con carga de Recolección, diferencias e incidentes. |
| 06 Calidad | Media/alta | Generalizar muestra y resultado para que sirvan a cualquier etapa y conservar especificación aplicada. |
| 07 Silos | Media | El libro de movimientos es oficial; agregar estados operativos, bloqueos, transferencias y reservas. |
| 08 Fabricación | Media | Configurar etapas en `procesos`; agregar balance RC y transferencias reales. |
| 09 Condensación | Media | Usar ejecución/controles existentes; completar precondensado, destino y detenciones. |
| 10 Secado | Media | Usar ejecución/controles; completar inspección, polvo, rework y descarte. |
| 11 Envase | Baja | Crear etapas configurables y entidades estables LoteEnvasado/Pallet. |
| 12 Mantequilla | Baja | Configurar ruta en `procesos`; crear solo lote y registros específicos indispensables. |
| 13 Inventario | Alta | Consolidar UI, FEFO, calidad y vínculos de consumos con órdenes. |
| 14 Aseos/CIP | Baja | Crear `saneamiento`; su liberación debe cambiar el estado operativo de equipos/silos. |
| 15 Mantenimiento | Media/alta | Conectar disponibilidad/calibración con planificación y Calidad. |
| 16 Rework/NC | Parcial | Unificar NC de materiales y producto; agregar lote de rework y disposición trazable. |
| 17 Dossier | Media | Extender liberación existente con requisitos por ruta y evidencia congelada. |
| 18 Despachos | Ausente | Crear módulo propio y descontar silo/inventario en transacción única. |
| 19 Trazabilidad | Parcial | Construir consultas sobre movimientos, lotes y eventos; no duplicar registros. |
| 20 Reportes/Auditoría | Media | Conservar auditoría inmutable; agregar notificaciones y trabajos en segundo plano después del núcleo. |

## Orden de entrega

Estado actual: se completaron Recolección y su enlace formal con Recepción.
Las fases siguientes permanecen planificadas y deben entregarse de forma
incremental, con migraciones y pruebas por cada corte.

### Fase 1 — Cadena de leche fresca

1. Recolección y cargas por módulo.
2. Enlace carga esperada → recepción → muestra → decisión.
3. Estados, bloqueos, transferencias y reservas de silos.
4. Diferencias de litros/kilos e incidentes.
5. Consulta de trazabilidad proveedor → carga → silo.

### Fase 2 — Plan ejecutable

1. Orden de Producción derivada de la semana.
2. Ruta productiva versionada.
3. Reserva de equipo, silo y material.
4. Validación de mantenimiento, CIP, calidad y stock.
5. Liberación, reprogramación y cancelación auditadas.

### Fase 3 — Transformación

Configurar en `procesos` las rutas de descremación, estandarización,
condensación, secado, envase y mantequilla. Cada ejecución debe identificar
orden, lote, equipo, entradas, salidas, controles y eventos.

### Fase 4 — Cierre de cadena

Saneamiento, no conformidades/rework, dossier, pallets, bodega, despachos y
trazabilidad hacia cliente.

### Fase 5 — Operación escalable

Redis, Celery/Beat, Sentry, almacenamiento de adjuntos y reportes pesados se
incorporan cuando el flujo transaccional esté estable. No deben ser requisito
para registrar movimientos críticos.

## Reglas obligatorias de implementación

1. PostgreSQL es la fuente oficial; los saldos se derivan de movimientos.
2. Movimientos y cambios de estado críticos usan `transaction.atomic()` y
   bloqueo de filas.
3. No se eliminan registros con historia: se inactivan o anulan con motivo.
4. Calidad, liberaciones y reaperturas registran actor y fecha.
5. Las operaciones sincronizables usan UUID/idempotencia.
6. Los formularios largos admiten borrador; los registros cerrados no se
   editan sin reapertura autorizada.
7. Las reglas se prueban en backend; React guía, pero no decide seguridad.
8. Toda entidad nueva debe aportar claves para trazabilidad hacia atrás y
   hacia adelante.

## Siguiente incremento concreto

Crear `recoleccion` con rutas, paradas, controles en origen, muestras y cargas
por módulo. Después añadir una referencia opcional desde `Recepcion` a la carga
esperada, validando que vehículo, módulo, procedencia y cantidad sean
consistentes sin impedir recepciones manuales autorizadas.
