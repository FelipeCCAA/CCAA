# Fase 10 — Mantequilla

Fecha: 17 de agosto de 2026.

- Se reutilizó la ejecución de descremación existente, que ya genera crema y leche descremada como salidas genealógicas.
- Se agregó `CorridaMantequilla`, vinculada a orden, ejecución, lote de crema, lote de mantequilla y lote opcional de suero.
- El inicio valida orden, equipo/CIP, disponibilidad real del lote de crema y evita doble consumo.
- El cierre registra mantequilla, suero y merma como salidas de la misma ejecución, impide exceder la crema utilizada y deja la corrida pendiente de Calidad.
- API: `/api/procesos/mantequillas/`, acciones `iniciar` y `cerrar`.
- Frontend: Procesos muestra crema utilizada, mantequilla, suero, merma, equipo y estado.
- Migración: `procesos/0007_alter_etapaproceso_tipo_corridamantequilla.py`.
- Pruebas: genealogía crema → mantequilla, coproducto/merma y bloqueo por crema insuficiente.
