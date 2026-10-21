# OP-05 — Mantequilla: origen, consumo y recuperación

**Estado: COMPLETADA EN LA RAMA.** Código/pruebas `85b5ad1b8d8134fe1bf97d722ae2ca0fe7b396ff`, CI global aprobada y PR #12 borrador. El cierre posterior actualiza tres documentos y dos valores de fixtures Chrome (unidad del segundo origen y tipo de equipo), sin cambiar código de funcionamiento ni pruebas backend; esos fixtures finales pasaron Chrome 5/5. Su CI adicional no se declara aprobada anticipadamente. Rama `codex/op-05-mantequilla` desde OP-04 `f00e39a`. El usuario validó las seis reglas y autorizó implementación, pruebas aisladas y PR. No autoriza producción, despliegue, merge ni inventario real. No se conecta Supabase ni se cambia de infraestructura.

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

Tras adaptar genealogía, sus dos regresiones pasaron 2/2 en 0,726 s (`op05-genealogia-focal.log`), sobre PostgreSQL real local. No constituye aprobación de toda OP-05. La evidencia final y PR se registran abajo; este resultado focal aislado no se extrapoló a toda OP-05.

Entorno: harness OP-00 comprueba directorio `../op00-runtime/pgdata`, rol `op00_test`, dirección `127.0.0.1:55439` y base desechable antes de Django; rechaza `.env` y limpia variables heredadas. Un coordinador serializa los tests de BD. Chrome usa API simulada y no accede a servicios externos. Las bases de pruebas no contienen datos reales.

## Riesgos y continuidad

Corridas históricas sin origen demostrable requieren revisión humana; no se autorreparan ni se consumen por inferencia. La mazada requiere definición de planta antes de habilitar nuevos registros; no se la transforma automáticamente en merma. No se cambian rendimientos, formatos de caja, tolerancias ni reglas de liberación ajenas a OP-05.

Antes de cualquier despliegue futuro autorizado debe revisarse si existen corridas abiertas sin `salida_crema` y resolver su evidencia operacional: el contrato nuevo bloquea iniciar/cerrar sin ese respaldo. No se afirma compatibilidad automática con corridas históricas abiertas. Esta entrega no modifica esas corridas.

Reversión: la propuesta no fusionada se puede descartar sin afectar producción. Si se integrase en el futuro, conservar FK/evidencias y movimientos confirmados; revertir código no autoriza borrar historia ni hacer migraciones destructivas.

Pendientes externos a la entrega: UAT con operadores, carga de 70 usuarios y restauración de backup. No se certifican con pruebas unitarias o de escritorio. OP-06 queda para diagnóstico y propuesta de reglas; implementar requiere su autorización específica.

## EXPLICADOR — OP-05

1. **Problema:** podía iniciarse mantequilla sin demostrar el retiro de crema o con una aprobación sin firma vigente; perder una respuesta dejaba el resultado incierto.
2. **Causa:** la corrida no identificaba explícitamente la salida física y no había contrato de recuperación por petición.
3. **Ejemplo:** un TK con saldo total no demuestra que esos litros pertenezcan al lote elegido; un reintento debe recuperar el retiro original.
4. **Solución:** ligar salida/lote/TK, verificar Calidad y saldos, registrar unidades y una sola operación.
5. **Trabajo:** backend e interfaz con revisión independiente; genealogía y consultas integradas por PM. Sólo tres subagentes necesarios.
6. **Pruebas:** CI global 1.719 backend (1.714 aprobadas, cinco omitidas), frontend 103/103; focal final limpia 34/34 y Chrome con API simulada 5/5. Sin UAT de planta.
7. **Estado:** VALIDADO MEDIANTE PRUEBAS EN LA RAMA; revisión humana/UAT pendientes, sin producción ni despliegue.


## Checkpoint previo a CI

Primera focal conjunta: 23 pruebas en 7,061 s, 22 aprobadas y un fallo por comparar texto decimal 1010.00 con 1010. Se corrigió únicamente el test para comparar el valor Decimal.

Primera integración amplia (Procesos y Despacho OP-01): 207 pruebas en 124,592 s, 203 aprobadas y cuatro errores en fixtures TransactionTestCase por firmar fuera de una transacción. Los fixtures quedaron corregidos para confirmar la firma antes de abrir la conexión competidora; esa corrida ya había importado la versión anterior. No se declara aprobada. La focal final limpia y la CI global del commit de implementación aprobaron después, según la evidencia siguiente.

Frontend final: 103/103 en 3,349 s; lint, TypeScript/build aprobados. Aviso preexistente FormularioMaestro de import dinámico, sin cambiarlo. Chrome final 5/5 en 18,6 s con API simulada (op05-ui-validado.log). El primer ensayo tuvo dos botones con nombre igual y una expectativa de texto que no coincidía con el párrafo combinado; se corrigieron los localizadores. La revisión encontró además una etiqueta de kg presentada como L y se corrigió con aserción de ambas unidades.

Django check, Ruff y makemigrations --check --dry-run aprobados; el esquema coincide con la migración 0024. Revisión independiente de los últimos tres hallazgos por lectura sin bloqueantes pendientes. No ejecutó DB.

Archivos principales: procesos/servicios.py (Mantequilla, genealogía y orden de continuación/Secado), modelos/migración 0024, serializers/views y consultas de disponibilidad; inventario/servicios.py sólo orden de bloqueos al validar Despacho; fixtures de Mantequilla y cinco módulos de pruebas OP-05. Frontend: tres pantallas de Procesos, DTO/métodos Mantequilla, helper de petición recuperable, tests y harness Chrome. No cambia dependencias ni despliegues.

## Validación final y entrega

Código/pruebas: `85b5ad1b8d8134fe1bf97d722ae2ca0fe7b396ff`. [PR #12 borrador](https://github.com/FelipeCCAA/CCAA/pull/12), sobre OP-04 #11; [manifiesto de 24 archivos](https://github.com/FelipeCCAA/CCAA/pull/12/files). No fusionado ni desplegado.

**Focal final limpia 34/34 en 24,774 s, exit 0** (`op05-focal-final.log`): 23 pruebas nuevas y once heredadas de Mantequilla. Incluye dos carreras PostgreSQL (misma clave y dos corridas disputando el último saldo), tres comprobaciones entre conexiones del orden de bloqueos, seis casos de genealogía/consulta/guardas físicas y doce casos de alimentación, aprobación, conversión, balance, recuperación y rollback. Fuente con densidad 1.010 kg/m³: 200 kg requieren 198,02 L; no se supone 1 kg = 1 L. La renovación a otra densidad conserva el cálculo de inicio y registra la aprobación actual por separado.

El clúster local exacto quedó detenido mediante `pg_ctl -D`, exit 0 y sin `postmaster.pid`. Ninguna base real recibió migraciones o datos. DevelopMain sigue en `d34df44ca30c402e9da34dc7b75f7652c2751fef` al verificar GitHub tras publicar el PR.

**CI final SUCCESS:** [39647306726](https://github.com/FelipeCCAA/CCAA/actions/runs/39647306726) en `85b5ad1b8d8134fe1bf97d722ae2ca0fe7b396ff`. [Backend](https://github.com/FelipeCCAA/CCAA/actions/runs/39647306726/job/119386156128): `Ran 1719 tests in 393.864s`, `OK (skipped=5)`: **1.714 aprobadas, cinco omitidas preexistentes, cero fallos/errores**. Incluye los 23 casos nuevos, once heredados adaptados y regresiones globales. Ruff, Django checks, dry-run y migraciones en PostgreSQL 17 efímero aprobados. [Frontend](https://github.com/FelipeCCAA/CCAA/actions/runs/39647306726/job/119386156759): **103/103**, lint, tipos y build aprobados. [Configuración](https://github.com/FelipeCCAA/CCAA/actions/runs/39647306726/job/119386156849): aprobada.

Chrome final tras precisar los fixtures: **5/5 en 15,6 s**, `op05-ui-contrato-final.log`. Ambos orígenes simulados están en L y el equipo es tipo línea; el saldo se muestra en kg. El código de servidor/interfaz y las pruebas backend permanecen iguales al commit con CI aprobada. El cierre documental/fixtures tiene CI separada, no aprobada por anticipado.

Reproducción en PostgreSQL sintético y configuración CI:

```text
python manage.py test procesos.tests_op05_mantequilla procesos.tests_op05_genealogia procesos.tests_op05_guardas procesos.tests_op05_bloqueos procesos.tests_op05_concurrencia procesos.tests_mantequilla --noinput --verbosity 1
python manage.py test --verbosity 1
```

En frontend: `npm test`, `npm run lint`, `npm run build`; navegador Chrome local: `npx playwright test --config op05-ui/playwright.config.ts`. Este último levanta localhost:5196 y simula todas las APIs. No es un E2E con BD ni UAT.

## Recorridos DESK de operadores

Se reutilizaron los agentes necesarios para cubrir perspectivas de operación, sin afirmar participación de operadores humanos.

- **Recepción (coordinador):** crema identifica lote, salida, TK y análisis firmado. Un antecedente sin evidencia o con firma retirada no se vuelve utilizable por tener saldo físico; no se completa historia por inferencia. La firma posterior no cambia retroactivamente la conversión que produjo el retiro.
- **Almacenamiento/Producción (backend):** 200 kg con densidad 1.010 kg/m³ retiran 198,02 L una vez. CIP, firma inválida o reserva ajena impiden retirar. Clasificar 195 kg mantequilla + 3 kg merma + 2 kg reproceso es un ejemplo sintético de balance exacto, no rendimiento/tolerancia de planta. El reproceso sigue esperando Calidad.
- **Inventario/Despacho (frontend):** saldo de selección en kg, unidad física L separada; respuesta perdida se recupera con la misma clave. Cierre envía a Calidad y no ofrece mazada. Las cajas y disponibilidad final conservan sus liberaciones existentes. No se certifica con este DESK todo el circuito industrial.

## AVANCE

Tres subagentes: backend/revisión `gpt-6-sol high`, frontend `gpt-6-luna medium`; coordinación, integración, evidencia y explicación por el agente principal. OP-06 es la siguiente por dependencia, sólo para diagnóstico/propuesta hasta nueva autorización. Las decisiones posteriores son revisión humana de PR/dependencias y UAT; cualquier producción, despliegue o implementación de OP-06 necesita autorización aparte.


**Cierre AVANCE:** seis reglas efectivamente implementadas y probadas en rama; commit de implementación `85b5ad1`, PR #12 borrador sobre #11, código sin merge/despliegue. Archivos y pruebas arriba; backlog y progreso actualizados. Riesgos pendientes: evidencia de corridas históricas abiertas, UAT y capacidad/backup no certificados. Próxima OP-06 para diagnóstico/reglas. Ninguna contratación ni credencial nueva fue necesaria.
