# Problemas arquitectónicos priorizados

| ID | Severidad | Problema | Impacto | Evidencia |
|---|---|---|---|---|
| ARCH-001 | CRITICAL | Bulk create/update omite signals de auditoría | decisiones/movimientos sin rastro | `backend/auditoria/registro.py:125-196`; usos en Calidad/Procesos/Estandarización |
| ARCH-002 | HIGH | Bandeja operativa no filtra por etapa autorizada | operador ve trabajo ajeno y recibe 403 | `backend/procesos/views.py:1070-1113` |
| ARCH-003 | HIGH | `/procesos` mezcla operación, configuración y genealogía | tarea inmediata queda enterrada | `frontend/src/pages/Procesos/Procesos.tsx:194-349` |
| ARCH-004 | HIGH | Balance de Mantequilla puede quedar sin explicar | pérdida de trazabilidad de masa | `backend/procesos/models.py:651-656` |
| ARCH-005 | MEDIUM | Dashboard global usa 7–8 GET y página para conteos | contador parcial/carga innecesaria | `frontend/src/pages/Dashboard/Dashboard.tsx:77-110` |
| ARCH-006 | MEDIUM | Dependencia circular procesos-inventario | alto costo de cambio | `backend/procesos/servicios.py:915-928`; `backend/inventario/servicios.py:165-170` |
| ARCH-007 | MEDIUM | MRP sin idempotencia fuerte ante redelivery | resultados duplicados/parciales | `backend/inventario/tareas.py:26-56` |
| ARCH-008 | MEDIUM | Mantenimiento implementado pero API no montada | módulo inaccesible | `backend/mantenimiento/urls.py:1-15`; `backend/config/urls.py:23-56` |

## Clasificación

ARCH-001 está confirmado y se aborda en el Bloque 1. ARCH-004 y reglas de Protomalt/coproducto requieren validación de planta antes de cambiar comportamiento. Los demás pueden implementarse incrementalmente sin reescritura.

