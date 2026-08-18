# Fase 8 — Condensación y precondensado

Fecha: 17 de agosto de 2026.

## Resultado

- Se reutilizaron el lote maestro, la orden, `EjecucionProceso`, entradas/salidas, equipos y el libro mayor de silos.
- Se agregó `CorridaCondensacion` como especialización vinculada; no se creó un lote paralelo.
- El inicio bloquea corrida y silo, valida orden activa, evaporador habilitado, ausencia de CIP/aseo observado, exclusividad del equipo, estado de Calidad del silo y saldo real.
- El inicio genera el consumo real del silo con usuario, lote, producto, equipo y clave idempotente, y activa orden/ejecución.
- El cierre registra precondensado en el silo destino, controles (flujo, densidad, sólidos, temperatura, vacío y presión), salida de proceso y transición a cierre o puerta de Calidad.
- API: `/api/procesos/condensaciones/`, con acciones `iniciar` y `cerrar`.
- Frontend: Procesos muestra orden, lote, evaporador, origen, destino, volumen y estado de cada corrida.
- Migración: `procesos/0006_corridacondensacion.py`.
- Pruebas nuevas: inicio, consumo real, cierre, balance, saldo insuficiente y bloqueo de Calidad.

## Validación

- 46 pruebas del módulo Procesos: correctas.
- Django check y migraciones pendientes: correctos.
- Ruff, ESLint y TypeScript: correctos.

## Pendiente siguiente

Fase 9: secado y envase con torre, silo de polvo, producción obtenida, merma, reproceso, envasado y pallet.
