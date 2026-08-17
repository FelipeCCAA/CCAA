# Fases 4 a 7 — resultado de implementación

Fecha: 17 de agosto de 2026.

## Fase 4 — Orden y lote central

- Se encontró un lote productivo funcional, pero la orden seguía siendo texto libre (`op`).
- Se agregó `OrdenProduccion` con planta, semana, producto, cantidad, unidad, línea, equipo, destino, responsable y estados controlados.
- `Lote.orden` conserva compatibilidad con el texto histórico `op` y valida planta/producto.
- API: `/api/produccion/ordenes/`; las órdenes no admiten DELETE físico.
- Migración: `produccion/0008_ordenproduccion_lote_orden_and_more.py`.
- Pruebas: `produccion/tests_orden.py`.

## Fase 5 — Recepción, silos y movimientos

- La descarga ya era transaccional y la ocupación se derivaba correctamente del libro mayor.
- Se cerró la escritura arbitraria del libro mayor: movimientos confirmados son inmutables y solo se corrigen mediante ajuste/reversa.
- Se agregó transferencia atómica con bloqueo de silos, validación de saldo/capacidad y `operacion_id` idempotente.
- Los movimientos registran contraparte, lote, producto, equipo y usuario.
- Los silos incorporan estados operacionales, producto declarado, temperatura y última limpieza; el volumen sigue derivándose únicamente de movimientos.
- API: `POST /api/recepcion/movimientos/transferir/` y `POST /api/recepcion/movimientos/ajustar/`.
- Migraciones: `maestros/0028_...` y `recepcion/0010_...`.
- Pruebas: `recepcion/tests_movimientos_operacionales.py` y suite completa de Recepción.

## Fase 6 — Estandarización y balance

- Se reutilizó el servicio transaccional existente y el modelo de entradas/salidas por unidad.
- Estandarización ahora rechaza consumo desde silos bloqueados por Calidad, pendientes/en CIP o fuera de servicio.
- Sus movimientos llevan usuario y una clave determinista de operación.
- El balance impide que las salidas excedan las entradas cuando las unidades son comparables; las mermas exigen motivo.
- Pruebas: suites `estandarizacion` y `procesos`.

## Fase 7 — Producción, equipos y ruteo

- Se reutilizaron `Proceso`, `EtapaProceso`, `EjecucionProceso`, entradas, salidas y eventos inmutables.
- El inicio ya exige entrada, equipo habilitado, aseo/CIP conforme y responsable; el cierre exige salida o merma.
- Se agregó `RutaProducto`, que asigna producto + planta a procesos versionados y sus etapas sin reglas rígidas en React.
- API: `/api/procesos/rutas-producto/`.
- Frontend: la pantalla Procesos muestra rutas y etapas configuradas; la pantalla Silos muestra estado, producto y temperatura.
- Migración: `procesos/0005_rutaproducto.py`.
- Pruebas: `procesos/tests_rutas.py`.

## Validación consolidada

- Django `check`: correcto.
- `makemigrations --check --dry-run`: sin cambios pendientes.
- Ruff: correcto.
- 142 pruebas integradas de fases 2–7: correctas.
- ESLint y TypeScript: correctos.
- El empaquetado Vite quedó bloqueado por el binario local corrupto/no cargable de `@tailwindcss/oxide-win32-x64-msvc` y un `spawn EPERM`; no es un error de TypeScript ni de lint del código modificado.

## Pendientes deliberados

- Continuar fases 8–13: condensación/precondensado, secado/envase, mantequilla, calidad transversal, inventario/despacho y dossier.
- Completar fases 14–16: auditoría integral, seguridad/rendimiento y batería de integración global.
