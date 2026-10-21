# OP-05 — Mantequilla: origen, consumo y recuperación

**Estado: EN IMPLEMENTACIÓN.** Rama `codex/op-05-mantequilla` desde OP-04 `f00e39a`. El usuario validó las seis reglas y autorizó implementación, pruebas aisladas y PR. No autoriza producción, despliegue, merge ni inventario real. No se conecta Supabase ni se cambia de infraestructura.

## Reglas y alcance

| Regla validada | Contrato de implementación |
|---|---|
| Origen obligatorio | Elegir expresamente salida y lote de crema, TK y continuidad de ruta a Mantequilla. Sin libro físico verificable se rechaza; no se inventa origen histórico. |
| Calidad vigente | Firma de la salida real comprobada al consumir; mantiene las liberaciones existentes para mantequilla/envasado. Una etiqueta LIBERADO sin evidencia vigente no alcanza. |
| Consumo único y protegido | Cota del lote kg y de la salida L, libro físico del TK, reservas, limpieza y equipo; bloqueos compartidos para evitar dos consumos del mismo saldo. |
| Unidades claras | kg de crema conservados en corrida; L retirados según densidad kg/m³ del análisis firmado e identificado. Factor, referencia y resultado auditados; precisión existente, sin tolerancia industrial nueva. |
| Balance completo | Se conserva clasificación exacta de toda la crema entre mantequilla, merma y reproceso. No completar diferencias automáticamente. Nuevas salidas suero/mazada deshabilitadas; historial intacto. |
| Reintentos seguros | UUID estable por alta/inicio/cierre, carga y actor comparados; operación confirmada recuperable sin repetir efectos. Fallo revierte la transacción completa. |

No se reabre la auditoría general. El balance exacto ya existía y no se presenta como una nueva corrección. El defecto pendiente era acreditar el origen/consumo y la autorización vigente, junto a recuperar respuestas perdidas.

## Contrato técnico y compatibilidad

- `POST /api/procesos/mantequillas/crear-guiada/`: añade `operacion_id` y `salida_crema` explícita; conserva orden, lote_crema, equipo, código y kg. No admite nueva asociación `lote_suero`.
- `POST /api/procesos/mantequillas/{id}/iniciar/`: requiere `operacion_id`; confirma el retiro físico una vez.
- `POST /api/procesos/mantequillas/{id}/cerrar/`: requiere `operacion_id`; conserva `motivo_reproceso` y controles, rechaza `kg_suero` distinto de cero. `_op05` es evidencia del servidor.
- Opciones de crema identifican salida, lote, TK, unidad y kg disponibles; se revalidan al confirmar.
- Migración aditiva `0024_corridamantequilla_salida_crema`: FK nullable a salida real, sin backfill. Históricos conservados sin atribución ficticia. Su aplicación en este trabajo es exclusivamente a bases sintéticas.
- `EntradaProceso` registra silo/salida y L reales; `CorridaMantequilla` conserva kg. La genealogía sigue el lote de la salida en ambas direcciones. Las consultas distinguen una entrada y su retiro como evidencias de un único consumo, evitando contarlo dos veces.

La conversión sólo se admite para crema de TK con densidad real firmada y ruta válida. Una fuente en kg sin libro verificable se bloquea; no se implementan fuentes nuevas. El UUID de alta identifica la corrida/retiro físico existente; los de inicio/cierre quedan en eventos independientes. Actualización conjunta de interfaz/backend y aplicación de migración requerirán un despliegue futuro autorizado, fuera de esta entrega.

## Evidencia inicial

Baseline local: `op05-baseline.log`, 17 pruebas en 4,308 s, seis fallos intencionados y once heredadas aprobadas. Cuatro fallos demuestran inicio sin origen, firma obsoleta aceptada, reintento rechazado y mazada permitida; dos verifican la genealogía requerida al representar el retiro con salida/silo. El módulo inicial importó una clase heredada y el descubridor incluyó sus once pruebas; la importación se corrigió a módulo para no duplicarlas en la entrega.

Tras adaptar genealogía, sus dos regresiones pasaron 2/2 en 0,726 s (`op05-genealogia-focal.log`), sobre PostgreSQL real local. No constituye aprobación de toda OP-05. El resto de resultados, commits y PR se registrará al terminar.

Entorno: harness OP-00 comprueba directorio `../op00-runtime/pgdata`, rol `op00_test`, dirección `127.0.0.1:55439` y base desechable antes de Django; rechaza `.env` y limpia variables heredadas. Un coordinador serializa los tests de BD. Chrome usa API simulada y no accede a servicios externos. Las bases de pruebas no contienen datos reales.

## Riesgos y continuidad

Corridas históricas sin origen demostrable requieren revisión humana; no se autorreparan ni se consumen por inferencia. La mazada requiere definición de planta antes de habilitar nuevos registros; no se la transforma automáticamente en merma. No se cambian rendimientos, formatos de caja, tolerancias ni reglas de liberación ajenas a OP-05.

Reversión: la propuesta no fusionada se puede descartar sin afectar producción. Si se integrase en el futuro, conservar FK/evidencias y movimientos confirmados; revertir código no autoriza borrar historia ni hacer migraciones destructivas.

Pendientes externos a la entrega: UAT con operadores, carga de 70 usuarios y restauración de backup. No se certifican con pruebas unitarias o de escritorio. OP-06 queda para diagnóstico y propuesta de reglas; implementar requiere su autorización específica.

## EXPLICADOR — OP-05

1. **Problema:** podía iniciarse mantequilla sin demostrar el retiro de crema o con una aprobación sin firma vigente; perder una respuesta dejaba el resultado incierto.
2. **Causa:** la corrida no identificaba explícitamente la salida física y no había contrato de recuperación por petición.
3. **Ejemplo:** un TK con saldo total no demuestra que esos litros pertenezcan al lote elegido; un reintento debe recuperar el retiro original.
4. **Solución:** ligar salida/lote/TK, verificar Calidad y saldos, registrar unidades y una sola operación.
5. **Trabajo:** backend e interfaz con revisión independiente; genealogía y consultas integradas por PM. Sólo tres subagentes necesarios.
6. **Pruebas:** baseline reproducido y genealogía focal aprobada; validación integrada pendiente.
7. **Estado:** EN IMPLEMENTACIÓN; no aplicado a producción.


## Checkpoint previo a CI

Primera focal conjunta: 23 pruebas en 7,061 s, 22 aprobadas y un fallo por comparar texto decimal 1010.00 con 1010. Se corrigió únicamente el test para comparar el valor Decimal.

Primera integración amplia (Procesos y Despacho OP-01): 207 pruebas en 124,592 s, 203 aprobadas y cuatro errores en fixtures TransactionTestCase por firmar fuera de una transacción. Los fixtures quedaron corregidos para confirmar la firma antes de abrir la conexión competidora; esa corrida ya había importado la versión anterior. No se declara aprobada. La repetición final y CI incluyen los cambios finales y sus resultados se agregarán al terminar.

Frontend final: 103/103 en 3,349 s; lint, TypeScript/build aprobados. Aviso preexistente FormularioMaestro de import dinámico, sin cambiarlo. Chrome final 5/5 en 18,6 s con API simulada (op05-ui-validado.log). El primer ensayo tuvo dos botones con nombre igual y una expectativa de texto que no coincidía con el párrafo combinado; se corrigieron los localizadores. La revisión encontró además una etiqueta de kg presentada como L y se corrigió con aserción de ambas unidades.

Django check, Ruff y makemigrations --check --dry-run aprobados; el esquema coincide con la migración 0024. Revisión independiente de los últimos tres hallazgos por lectura sin bloqueantes pendientes. No ejecutó DB.

Archivos principales: procesos/servicios.py (Mantequilla, genealogía y orden de continuación/Secado), modelos/migración 0024, serializers/views y consultas de disponibilidad; inventario/servicios.py sólo orden de bloqueos al validar Despacho; fixtures de Mantequilla y cinco módulos de pruebas OP-05. Frontend: tres pantallas de Procesos, DTO/métodos Mantequilla, helper de petición recuperable, tests y harness Chrome. No cambia dependencias ni despliegues.
