# Detalles de los puestos de Evaporación y Secado — plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Cerrar los pendientes que dejaron las revisiones de los puestos de Evaporación y Secado (PR #2), recuperar la limpieza de la base de desarrollo y dejar la cadena E2E en 4/4.

**Architecture:** Cambios acotados sobre código existente; ninguna regla nueva sin una sola implementación. Rama `feature-detalles-secado`, nacida de `feature-puesto-evaporacion` (4ed91f1).

**Tech Stack:** Django 6 + DRF + PostgreSQL; React 19 + TypeScript; `node --test`; Playwright.

## Global Constraints

- Una regla, una implementación: el saldo de una salida es `procesos.servicios.disponible_de_salida`; quién abre lote desde un vale es `produccion.servicios.abre_desde_vale`.
- Trampa de `CLAUDE.md`: un `return` dentro de `transaction.atomic()` confirma; los errores se lanzan.
- Español en código, mensajes y UI. Archivos en LF. Commits convencionales en español, sin líneas de atribución, archivos agregados por nombre; nunca `frontend/e2e/.auth/estado.json`.
- Pruebas backend: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test <etiquetas> --noinput`, en serie, nunca `--parallel`. Frontend: `npx tsc -b --pretty false`, `npx eslint .`, `npm test`.
- Si el clasificador de permisos bloquea un comando, no se rodea con otra herramienta: se informa.

---

### Task 1: Saldo, destino, cancelación externa, orden de candados y limpieza de la base

**Archivos:** `backend/procesos/servicios.py`, `backend/procesos/views.py` (`SalidaProcesoViewSet.disponibles`), `backend/procesos/consultas_planta.py`, `backend/usuarios/management/commands/limpiar_transaccional.py`, pruebas en `backend/procesos/tests_puesto_secado.py`, `backend/procesos/tests_*.py` correspondientes y `backend/usuarios/tests_limpiar_transaccional.py` (nuevo).

1. **Un saldo.** `SalidaProcesoViewSet.disponibles` y `consultas_planta.contar_materiales_listos` restan hoy todos los `usos_como_origen`, también los de una preparación cancelada (`PREPARACION_CANCELADA`). Ambos deben descontar los usos con la misma regla que `disponible_de_salida`. Si `disponibles` además resta movimientos físicos de silo, mantener esa parte pero tomar los usos de la misma función o del mismo `Q`; documentar en un comentario por qué difieren, si difieren. Prueba: preparar → cancelar → la salida vuelve a aparecer en `salidas/disponibles/` y cuenta en «materiales listos».
2. **Destino libre tras cancelar.** `definir_destino_salida` usa `usos_como_origen.exists()`; debe ignorar los usos de preparaciones canceladas (mismo `Q`). Prueba: salida cuya única toma se canceló puede cambiar de destino; una con toma vigente no.
3. **Orden de vuelta al cancelar una alimentación externa.** Al deshacer una preparación externa (`_deshacer_preparacion_secado`), si la orden quedó `EN_PROCESO` solo por esa ejecución (no hay otra ejecución no terminal ni lote producido de esa orden), vuelve a `PROGRAMADA`. Corregir también el texto `[ANULACIÓN] … {motivo} La materia prima…` para que el motivo termine en punto. Pruebas para ambos casos (vuelve y no vuelve).
4. **Mismo orden de candados.** Cancelar desde `ejecuciones/{id}/transicionar/` bloquea la ejecución y después borra la corrida; `iniciar_secado` bloquea corrida y después ejecución. Hacer que el camino genérico, cuando la ejecución es de Secado en preparación, tome primero el candado de la `CorridaSecado` (si existe) y luego el de la ejecución, igual que `iniciar_secado` y `cancelar_preparacion_secado`. Comentario que explique el porqué. Prueba que fije el orden (por ejemplo, que el camino genérico llama a la misma función de cancelación del puesto) si es razonable; si no, justificarlo.
5. **`limpiar_transaccional` al día.** Su lista `MODELOS` no conoce los modelos transaccionales nuevos (p. ej. `procesos.LiberacionProceso`, `CorridaSecado`, `CorridaCondensacion`, `CorridaDescremacion`, `CorridaMantequilla`, `ReservaSiloProceso`, `recepcion.AnalisisSilo`, inventario de producto terminado, despachos, pallets, consumos, existencias creadas por producción…) y choca con claves `PROTECT`. Rehacerlo para que:
   - borre todo lo transaccional y conserve los maestros (productos, mandantes, silos, equipos, vehículos, catálogo de documentos, especificaciones, recetas, insumos, ubicaciones, personas y perfiles), según el docstring;
   - el orden de borrado no dependa de una lista escrita a mano que envejece: preferir derivarlo (p. ej. declarar qué apps/modelos son **maestros** y borrar el resto de las apps de negocio en orden topológico de dependencias, o reintentar por pasadas hasta que no quede nada borrable), o, si se mantiene lista explícita, una prueba que falle cuando aparezca un modelo de negocio que no esté ni en «maestros» ni en «transaccionales»;
   - siga siendo una sola transacción y sin `--aplicar` solo cuente;
   - no corra en entornos endurecidos (`config.seguridad.ENTORNOS_ENDURECIDOS`), igual que `crear_usuario_e2e`.
   Pruebas en `backend/usuarios/tests_limpiar_transaccional.py`: con un circuito mínimo sembrado (lote, vale, ejecución, corrida, liberación, movimiento de silo), `--aplicar` deja en cero los transaccionales y conserva los maestros; sin `--aplicar` no borra; en entorno endurecido falla.

### Task 2: Evaporación — cancelar una corrida preparada, caso 3 y accesibilidad de los puestos

**Archivos:** `backend/procesos/servicios.py`, `backend/procesos/views.py` (`CorridaCondensacionViewSet`), `backend/produccion/servicios.py` / `views.py` (anular lote), `frontend/src/pages/Evaporacion/*`, `frontend/src/pages/Secado/TarjetaTorre.tsx`, `frontend/src/services/*`, `CLAUDE.md`, pruebas.

1. **Cancelar una corrida de evaporación preparada** (simétrico a Secado): `POST procesos/condensaciones/{id}/cancelar-preparacion/` con motivo obligatorio, permiso de la etapa Condensación, solo desde `borrador`/preparación (sin iniciar), con `select_for_update`. Libera el evaporador, la reserva de destino y **anula el lote** que se abrió con ella, devolviendo la leche al silo de origen con un movimiento de **entrada compensatoria** al mismo silo (no se borra el movimiento original: la trazabilidad queda). Si devolver la leche no es posible (el silo de origen ya no tiene capacidad), rechazar con motivo claro. Frontend: acción secundaria «Cancelar preparación» en la tarjeta *Preparada* del puesto de Evaporación (solo quien opera), motivo obligatorio y `ConfirmarAccion`; recarga el puesto. Pruebas: cancela → evaporador `disponible`, lote `anulado`, saldo del silo de origen repuesto, reserva liberada; ya iniciada → 400; sin permiso → 403.
2. **Caso 3 de `CLAUDE.md`: anular un lote cierra su ejecución.** Anular un lote cuya `EjecucionProceso` está en un estado no terminal la pasa a `cancelada` con el motivo de la anulación (vía `transicionar_ejecucion`), liberando el equipo. Si la ejecución ya inició y tiene leche consumida, la anulación sigue el camino existente (no se inventa una devolución). Prueba: anular → el evaporador o la torre queda libre en su puesto. Actualizar el caso 3 de `CLAUDE.md` a resuelto.
3. **Accesibilidad:** en ambos puestos, el botón de inicio deshabilitado lleva `aria-describedby` al motivo visible; el enlace «dónde se resuelve» solo se muestra si el usuario puede entrar a ese módulo (como hace Evaporación con silos).
4. **Pines de la regla duplicada:** una prueba que fije que `TIPOS_QUE_ABREN_DESDE_VALE` del frontend coincide con el conjunto que acepta `abre_desde_vale` (p. ej. el backend expone la lista en `opciones-inicio` o en un catálogo, y el frontend deja de duplicarla; preferir servirla).
5. **Decisión registrada (2026-10-07):** desde un vale solo abren lote evaporadores, envasadoras y líneas. `carga` (despacho a granel / transferencia), `descremadora` (descremación guiada) y `otro` (mantequilla guiada) tienen su propio flujo y no abren desde un vale. Escribirlo en `CLAUDE.md`, junto a la viñeta de Secado.

### Task 3: Aceptación (controlador)

- `limpiar_transaccional --aplicar` sobre la base local de desarrollo; `preparar_circuito_polvo --aplicar` y `preparar_circuito_suero --aplicar`; cadena `circuito → evaporacion → flujo-polvo` 4/4; `flujo-suero` 2/2; accesibilidad sin reglas nuevas; suite completa del backend.
