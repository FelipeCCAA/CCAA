# Arquitectura objetivo incremental

```mermaid
flowchart LR
  U[Persona] --> A[Sesión + capacidades]
  A --> M[Shell contextual Mi área]
  M --> B[Bandeja por área]
  B --> O[Operación explícita]
  O --> S[Servicio de dominio]
  S --> T[(Transacción + locks)]
  T --> AU[Auditoría completa]
  T --> H[Handoff siguiente área]
  H --> B
```

## Principios

- Mantener monolito modular y URLs compatibles.
- Backend autoriza; frontend orienta y oculta lo imposible.
- Resumen primero, detalle bajo demanda.
- Trabajo organizado por área/estado; histórico separado y paginado.
- Transiciones explícitas, auditables e idempotentes.
- `EntradaProceso`/`SalidaProceso`/lote/ruta siguen siendo el eje de genealogía.
- Estados físicos, productivos y de Calidad permanecen separados.

## Transición

AS-IS estable → cerrar integridad/auditoría → contrato “Mi área” → shell jerárquico → handoffs/timeline → panel global agregado → optimización medida. No se introduce microservicios, Kafka ni una segunda fuente de verdad.

