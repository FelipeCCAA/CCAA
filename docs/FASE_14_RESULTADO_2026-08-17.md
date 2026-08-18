# Fase 14 · Auditoría completa

## Resultado

Se reutilizó el registro transversal por señales, que ya captura altas, cambios y bajas desde API, admin y procesos internos con actor, IP, origen y diff antes/después.

- Se incorporaron las rutas de tenant de pallet y despacho para atribuir correctamente empresa y planta.
- `RegistroAuditoria` quedó protegido contra edición y borrado a nivel de modelo, además de su API estrictamente de solo lectura.
- Los nuevos movimientos, existencias, autorizaciones y estados de despacho pertenecen a las aplicaciones auditadas.
- El listado permanece paginado y filtrable por usuario, modelo, acción, objeto y período.

No se duplicó auditoría dentro de cada vista: las señales cubren servicios, admin, shell y tareas, evitando huecos entre caminos de escritura.
