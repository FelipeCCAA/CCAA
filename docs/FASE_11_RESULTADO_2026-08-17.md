# Fase 11 — Calidad transversal

Fecha: 17 de agosto de 2026.

- Se conservó el motor existente de expedientes, checklist, análisis, PCC/PPRO, concesiones, firmas y bloqueo concurrente.
- La liberación normal o bajo concesión ahora libera también los pallets del lote.
- Volver un expediente a revisión bloquea sus pallets para evitar que una firma retirada siga habilitando producto físico.
- Se agregó bloqueo explícito con motivo obligatorio: cambia el expediente a rechazado, bloquea pallets y bloquea los silos que contienen ingresos identificados con ese lote.
- API: `POST /api/calidad/expedientes/{lote}/bloquear/`.
- Frontend: el expediente muestra la acción “Bloquear lote” y solicita motivo.
- Pruebas: propagación del bloqueo a lote/pallet/silo y obligatoriedad del motivo.
- Django check, migraciones, Ruff, ESLint y TypeScript: correctos.

Pendiente siguiente: fase 12, inventario de producto terminado y despacho condicionado por liberación de Calidad.
