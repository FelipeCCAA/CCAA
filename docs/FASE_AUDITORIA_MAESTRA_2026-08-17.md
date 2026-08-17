# Auditoría incremental del prompt maestro — 17-08-2026

## 1. Qué se encontró

CCAA ya es un monolito modular Django/DRF + React/TypeScript sobre PostgreSQL.
No corresponde reescribirlo. Existen módulos operativos para usuarios,
planificación, recolección, recepción, estandarización, producción, procesos,
calidad, inocuidad, inventario, mantenimiento y auditoría. También existen
tenancy por empresa/sucursal, paginación, bloqueos transaccionales, Celery para
MRP, caché compartida y una genealogía configurable con entradas y salidas.

Clasificación consolidada:

| Fase del prompt | Estado comprobado | Observación principal |
|---|---|---|
| Usuarios, áreas, roles y alcance | Ya existe, requiere evolución | Tenancy y jefaturas por área están protegidos; falta una matriz granular uniforme por acción/recurso. |
| Planificación semanal | Ya existe, requiere evolución | Programa, balance, publicación, cierre y contraste real existen; faltan todos los estados y operaciones de copia/cancelación solicitados. |
| Orden/lote central | Existe parcialmente | `Lote` es central y se enlaza con vale/ejecución; la OP sigue siendo texto y no una entidad de orden completa. |
| Recepción, silos y movimientos | Ya existe y está bien encaminado | Calidad previa a descarga, saldos por movimientos y controles de capacidad están implementados. |
| Estandarización y balance | Ya existe y está bien encaminado | El vale conserva orígenes, destino y consumo real. |
| Producción, líneas, equipos y ruteo | Existe parcialmente | Equipos y procesos configurables existen; faltan reservas explícitas y un panel por área con todas las precondiciones consolidadas. |
| Condensación, secado y envase | Existe parcialmente | Se representan mediante procesos/etapas y controles; faltan experiencias especializadas completas. |
| Mantequilla | Existe parcialmente | Producto/receta/coproducto permiten modelarla, pero no existe un flujo operacional especializado de punta a punta. |
| Calidad transversal | Ya existe, requiere evolución | Recepción, controles, dossier, liberación y concesión existen; falta generalizar puertas configurables a todo movimiento/despacho. |
| Inventario y despacho | Existe parcialmente | Inventario, FEFO, cuarentena y movimientos existen. No hay módulo completo de despacho comercial/intermedio. |
| Dossier y trazabilidad | Ya existe y está bien encaminado | Expediente y genealogía hacia atrás/adelante existen; faltan pallet/cliente/despacho para cerrar la cadena comercial. |
| Auditoría | Ya existe, requiere evolución | Señales capturan antes/después, actor, IP y tenant; el motivo debe formalizarse en todas las acciones extraordinarias. |
| Rendimiento, seguridad e infraestructura | Ya existe, requiere evolución | PostgreSQL obligatorio, Nginx/Gunicorn, throttling, caché y Celery existen; faltan mediciones de carga, observabilidad y validación Docker real. |
| Integración y concurrencia | Ya existe, requiere evolución | Hay una suite amplia y pruebas PostgreSQL; deben crecer junto con despacho, reservas y nuevas transiciones. |

## 2. Problema corregido en esta iteración

La API y la tabla de Producción todavía permitían borrar físicamente un lote.
Esto contradecía la trazabilidad append-only del prompt: al eliminar el lote se
eliminaban también análisis relacionados y se cortaba la reconstrucción
histórica.

## 3. Arquitectura aplicada

- El lote conserva sus estados terminales y usa `ANULADO` como corrección.
- `DELETE /api/produccion/lotes/{id}/` queda rechazado con HTTP 405.
- La transición a `ANULADO` exige `motivo_anulacion` en backend.
- El motivo se incorpora a la observación con marca `[ANULACIÓN]`; el sistema
  de auditoría existente registra en una misma modificación el cambio de
  estado y de observación, junto con usuario, IP y tenant.
- React guía la operación y exige el motivo, pero Django mantiene la autoridad.

## 4. Archivos modificados

- `backend/produccion/views.py`
- `backend/produccion/serializers.py`
- `backend/produccion/tests_api.py`
- `backend/produccion/tests_apertura.py`
- `frontend/src/services/produccion.service.ts`
- `frontend/src/pages/Produccion/Produccion.tsx`
- `frontend/src/pages/Produccion/DetalleLote.tsx`

Se conservan además los cambios anteriores del panel operacional en Dashboard,
Navbar y estilos globales.

## 5. Modelos y migraciones

No cambió ningún modelo ni se necesita migración. Se reutilizaron el estado
`Lote.Estado.ANULADO`, `observacion` y la auditoría existente.

## 6. Endpoints

- `DELETE /api/produccion/lotes/{id}/`: ahora responde 405 y explica que se
  debe anular.
- `PATCH /api/produccion/lotes/{id}/` con `estado=anulado`: requiere
  `motivo_anulacion` no vacío.

## 7. Componentes React

- La tabla de Producción ya no ofrece el icono de eliminación.
- El detalle del lote muestra confirmación irreversible y textarea de motivo.
- El servicio API dejó de exponer `borrarLote`.

## 8. Permisos

No se agregaron permisos. La anulación mantiene `EscribeProduccion` y el scope
por sucursal existentes. El rechazo de DELETE aplica incluso a usuarios con
permiso de escritura; la corrección es una regla del dominio, no de interfaz.

## 9. Riesgos

- `observacion` reúne notas generales y el motivo. En una fase futura conviene
  modelar eventos de transición con `motivo`, `actor` y fecha como entidad
  explícita, sin perder compatibilidad con el historial actual.
- Integraciones antiguas que usen DELETE recibirán 405 y deberán migrar a la
  transición auditada.

## 10. Tests creados o actualizados

- Rechazo de eliminación física y conservación del lote.
- Rechazo de anulación sin motivo.
- Anulación válida sin exigir kilos, con persistencia del motivo.
- Se actualizaron fixtures antiguos de Producción al tenancy obligatorio.

## 11. Resultado de validaciones

| Control | Resultado |
|---|---|
| Suite API de Producción, 34 pruebas PostgreSQL | OK |
| `manage.py check` | OK |
| `makemigrations --check --dry-run` | sin cambios |
| Ruff Producción | OK |
| ESLint frontend | OK |
| TypeScript (`tsc -b`) | OK |

## 12. Pendientes priorizados

1. Convertir la OP de texto a entidad operacional vinculada con planificación.
2. Completar estados/copia/cancelación de semanas con motivo auditado.
3. Formalizar permisos granulares por acción y recurso.
4. Implementar reservas de materia prima y claves idempotentes uniformes.
5. Completar Mantequilla y despacho de productos intermedios/terminados.
6. Incorporar pallet, cliente y despacho a la genealogía y al dossier.
7. Medir consultas y carga antes de añadir índices o caché adicionales.
