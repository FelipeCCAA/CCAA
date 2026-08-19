# Fase 9 — Secado, envase y pallet

Fecha: 17 de agosto de 2026.

## Hallazgos y arquitectura

- Secado ya estaba integrado al lote maestro: la apertura desde un vale crea la ejecución de torre, registra entrada en litros y el cierre registra salida real en kg.
- Los controles horarios, PCC, CIP/aseo, merma, reproceso y consumo de materiales ya disponían de servicios y pruebas.
- Faltaba representar explícitamente el envase y los pallets sin crear otro lote.

## Implementación

- Se agregó `RegistroEnvase`, vinculado al lote y equipo, con formato, unidades, kg reales, controles, operador, horario e idempotencia.
- Se agregó `PalletProducto`, vinculado al registro y por esa vía al lote maestro, con código único, unidades, peso neto y estado de Calidad/Inventario/Despacho.
- El servicio transaccional impide envasar un lote no producido, usar equipo no habilitado o superar los kg producidos; un reintento no duplica pallets.
- Los pallets físicos no admiten DELETE.
- API: `/api/produccion/envases/` y `/api/produccion/pallets/`.
- Frontend: Producción muestra pallets recientes, unidades, peso y puerta de Calidad.
- Migración: `produccion/0009_registroenvase_palletproducto_and_more.py`.

## Validación

- Pruebas nuevas de envase/pallet: creación, genealogía, límite de kg e idempotencia.
- Regresión integrada de Recepción, Estandarización, Procesos, Producción, Planificación y Permisos: 335/335 correcta.
- Ruff, ESLint y TypeScript: correctos.

## Pendiente siguiente

Fase 10: integrar explícitamente la corriente de crema y fabricación de mantequilla, conservando la genealogía hasta las recepciones originales.
