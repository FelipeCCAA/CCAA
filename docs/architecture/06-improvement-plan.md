# Plan incremental ejecutable

## Estado actual

Fase **P3 — optimización medida cerrada**. Los bloques 7, `Planta Ahora`, 8,
trazabilidad visual, 9, idempotencia de MRP/destinos, y 10, eliminación medida
de GET auxiliares/N+1 y división de componentes grandes, están cerrados.

La **Fase 9 — QA operacional está cerrada**. Se validaron de extremo a extremo
polvo, mantequilla, precondensado, bloqueo de Calidad, concurrencia y permisos
por puesto. Con el bloque 23 quedan cerradas las nueve fases y no restan bloques
del roadmap aprobado.

## Regla arquitectónica funcional

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de permisos, aislamiento o navegación.”

Los campos y relaciones antiguos pueden permanecer exclusivamente por
compatibilidad de persistencia. Ningún bloque nuevo del roadmap debe usarlos
para seleccionar trabajo, contar operación, autorizar acciones, navegar o
entregar notificaciones. La lógica funcional se apoya en usuario, rol, permisos,
área, responsabilidades, estados y relaciones productivas reales.

## Top mejoras y dependencias

| Prioridad | Bloque | Resultado verificable |
|---|---|---|
| P0 | 1. Auditoría de bulk críticos | cada movimiento/reserva/liberación guarda before/after y actor |
| P0 | 2. Bandeja backend por área | admin ve todo; operador solo etapas propias y acciones autorizadas |
| P1 | 3. “Mi Producción” | pendientes/en curso/bloqueados/Calidad; histórico diferido |
| P1 | 4. Shell jerárquico contextual | navegación por área/proceso sin romper URLs |
| P1 | 5. Balance obligatorio de Mantequilla | 100% de masa clasificada, tras validación de planta |
| P1 | 6. Handoffs explícitos | cierre crea trabajo visible para siguiente área |
| P2 | 7. Panel Planta Ahora agregado | un contrato resumido; conteos globales exactos |
| P2 | 8. Trazabilidad visual | timeline y genealogía cuantificada bajo demanda |
| P2 | 9. Idempotencia MRP/destinos | redelivery y carreras sin duplicados |
| P3 | 10. Optimización medida | eliminar GET auxiliares/N+1 restantes y dividir componentes grandes |

```mermaid
flowchart LR
 B1[P0 Auditoría] --> B2[P0 RBAC bandeja]
 B2 --> B3[P1 Mi Producción]
 B3 --> B4[P1 Shell]
 B2 --> B6[P1 Handoffs]
 B6 --> B7[P2 Panel global]
 B6 --> B8[P2 Trazabilidad]
```

## Bloque 1 — en implementación

Problema: Django no emite señales en `bulk_create`, `bulk_update` ni `QuerySet.update`. Solución: envolturas auditables dentro de la misma transacción y adopción en Calidad, reservas/silos y movimientos de Estandarización. Aceptación: una fila por objeto, `[antes, después]`, actor heredado del request y rollback conjunto. Sin migración ni cambio API.

## Bloque 2 — siguiente prompt Codex

Analiza `EjecucionProcesoViewSet.operativas`, `TIPOS_OPERABLES_POR_AREA` y sus consumidores. Filtra la bandeja por etapa autorizada para usuarios normales, conserva vista global para Administración, entrega acciones realmente autorizadas y agrega tests de Condensación, Secado, Calidad y admin. No cambies las transiciones ni URLs existentes.

## QA por bloque

Ruff, tests Django focales y de regresión, `makemigrations --check`, TypeScript, ESLint, unitarios frontend y E2E del flujo afectado. Los circuitos lácteos completos se ejecutan después de estabilizar cada handoff, no como sustituto de tests de dominio.

## Fase 9 — QA operacional

La fase valida los escenarios ya definidos en el prompt maestro sin introducir
procesos nuevos: leche en polvo hasta Inventario; mantequilla hasta Inventario;
precondensado hasta despacho directo; bloqueo y liberación de Calidad;
exclusión concurrente de equipos; y autorización backend/frontend por área y
permiso. Empresa y Sucursal no son criterios de aceptación ni dimensiones de
aislamiento de estas pruebas.
