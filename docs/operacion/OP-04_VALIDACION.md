# OP-04 — Secado y FIFO

## Alcance autorizado

Implementación en `codex/op-04-secado-fifo`, desde OP-03 `5fd3d89`. El usuario validó las seis reglas y autorizó código, pruebas y PR para revisión. Sin producción, despliegue, merge, inventario real ni contratación. No se utiliza Supabase. Se conserva el esquema existente: no se añade migración ni se hace backfill.

| Regla aprobada | Implementación |
|---|---|
| Origen real y cantidad efectivamente consumida | `crear_secado_desde_inventario` registra entrada y consumo del lote; `cerrar_secado` contrasta entradas con el libro físico. Rechaza entradas sin evidencia o con un mismo silo duplicado. |
| Unidades explícitas | Inventario externo en kg. Los orígenes de silo conservan L; cerrar requiere kg medidos y referencia del registro. No convierte litros ni inventa densidad, rendimiento o tolerancia. |
| FIFO decidido por servidor | Inventario: primer lote compatible utilizable con saldo libre, ordenado por recepción/lote/existencia. Leche entera del vale: silo compatible con capa física más antigua, Calidad/CIP/retención/reservas revalidados. La sugerencia del cliente no autoriza el retiro. |
| Excepción con evidencia | Elegir otro origen exige motivo y registra recomendado/utilizado, actor y fecha. No habilita material rechazado, reservado o insuficiente. |
| Consumo atómico e idempotente | UUID estable por solicitud; bloqueo de operación y filas, comparación de carga y recuperación del resultado. Error revierte lote, consumo, cierre y eventos de esa transacción. |
| Cierre trazable | Conserva alimentación, polvo, finos y merma; exige firma vigente para salida intermedia y mantiene el circuito de Calidad del producto. No inventa consumos históricos. |

## Contrato y archivos

- `backend/procesos/servicios.py`: inicio externo, cierre, evidencia de consumo, retiro físico de continuación, recuperación por UUID y bloqueos compatibles con OP-03.
- `backend/procesos/serializers.py`: UUID obligatorio, referencia kg, metadatos del servidor protegidos y lista de orígenes de alimentación.
- `backend/procesos/views.py`: opciones FIFO utilizables e inicio nuevo 201 / recuperación exacta 200.
- `backend/estandarizacion/servicios.py`: decisión FIFO al ejecutar el vale; evento de confirmación o excepción.
- `backend/calidad/vigencia.py`: corrección de `AnalisisSilo` comparte el bloqueo del silo con los retiros; evita modificar Calidad entre comprobación y confirmación física.
- `frontend/src/pages/Secado/{InicioSecadoExterno,CierreSecado}.tsx`, `frontend/src/services/{secado.service,secado-operacion}.ts`: origen/unidad, motivo, referencia y recuperación de respuesta incierta con misma clave/carga.
- Pruebas nuevas: `backend/procesos/tests_op04_secado.py`, `backend/estandarizacion/tests_op04_fifo.py`, `frontend/tests/op04-secado.test.ts`, `frontend/op04-ui/`. Fixtures heredados de Secado/suero incorporan origen físico y UUID exigidos, sin debilitar verificaciones.

Tablas existentes: `CorridaSecado`, `EjecucionProceso`, `EntradaProceso`, `SalidaProceso`, `EventoProceso`, `ReservaSiloProceso`, `Lote`, `OrdenProduccion`, `LoteInventario`, `Existencia`, `MovimientoInventario`, `Silo`, `MovimientoSilo`, `AnalisisSilo` y liberaciones/firma de Calidad. Sin tabla nueva ni alteración de estructura.

`POST /api/procesos/secados/iniciar-desde-inventario/` añade `operacion_id` UUID y `excepcion_fifo_motivo` opcional. `POST /api/procesos/secados/{id}/cerrar/` añade `operacion_id` y `referencia_medicion_kg` cuando el origen está en L. Una clave reutilizada con distinta carga se rechaza. `_op04` en controles es evidencia reservada del servidor. Repetir una operación confirmada recupera su resultado, sin volver a producir ni consumir; no equivale a una nueva autorización de uso.

FIFO externo se decide en una consulta SQL de candidatos durante la confirmación. El elegido y su stock/Calidad se bloquean; no se impone orden global de commit a reposiciones concurrentes. El evento conserva ganador y saldo libre del snapshot, con `fifo_evaluado_en` como inicio de evaluación inmediatamente anterior a esa consulta. Bloquear todos los lotes fue descartado por invertir el orden de `registrar_entrada` y provocar interbloqueos. En leche se bloquean los silos candidatos en orden común; no se añade FIFO nuevo para todos los componentes de mezcla ni reparto automático entre varios orígenes.

## Evidencias

Antes del cambio se reprodujeron seis fallos: cuatro casos Secado (cierre sin origen, litros sin referencia kg, salto FIFO y reintento rechazado) y dos FIFO del vale (sugerencia omitida o falsificada). Las salidas se conservan localmente en `../op00-runtime/op04-baseline-{secado,fifo}.log`.

Las pruebas de base de datos se ejecutan exclusivamente mediante el harness OP-00: PostgreSQL 17 local, `127.0.0.1:55439`, rol `op00_test`, directorio `../op00-runtime/pgdata`; valida identidad antes de Django y rechaza `.env`. Datos sintéticos y bases desechables. Las pruebas concurrentes usan conexiones independientes y observan bloqueos reales en `pg_blocking_pids`; las pruebas de navegador usan API simulada y bloquean servicios externos.

**Validación en curso:** el cierre de evidencia, CI, commits y PR se incorporará al terminar las comprobaciones. No considerar este estado una aprobación global.

## Límites operacionales y reversión

La referencia de kg es una declaración identificada por operador; no integra ni certifica una báscula o documento externo. Los finos/merma quedan registrados en el balance, sin crear destinos de inventario no definidos. Preparación Protomalt y genealogía histórica sin respaldo siguen pendientes; no se activan rutas ni se reconstruyen consumos automáticamente. Los registros ambiguos fallan de forma conservadora y necesitan revisión humana.

Los contratos nuevos requieren actualizar conjuntamente interfaz y backend en un futuro despliegue autorizado. Aquí sólo se prepara la rama. Los reintentos se conservan mientras el formulario siga abierto; al recargar o cerrar la sesión debe consultarse el historial antes de iniciar otra operación. No se certifica carga de 70 usuarios, UAT de planta, respaldo/restauración ni ausencia de cualquier fallo ajeno a este alcance.

Para revertir la propuesta no fusionada basta no integrarla. Si posteriormente se autoriza desplegarla, conservar eventos/controles y movimientos confirmados: revertir código no significa borrar consumos ni historia. Sin migración nueva para revertir.

## Continuidad

OP-05 (Mantequilla) tiene dependencia OP-03 satisfecha en rama. Próxima actividad permitida: diagnóstico acotado y propuesta de reglas sobre consumo de crema, cierre, merma y liberaciones. Su implementación requiere autorización específica; no se inicia aquí. Mazada y tolerancias industriales siguen sujetas a definición de planta.

## EXPLICADOR — OP-04

1. **Problema:** Secado podía cerrar sin demostrar de dónde salió la alimentación y algunos reintentos/saltos FIFO no quedaban controlados.
2. **Causa:** inicio, cierre y recomendación no compartían un contrato verificable de origen, unidad y operación única.
3. **Ejemplo:** si se pierde la respuesta al alimentar la torre, repetir no debe descontar otra vez; declarar 600 kg tampoco demuestra por sí solo un retiro del silo.
4. **Solución:** enlazar origen y retiro, conservar unidades y recuperar la misma operación; las excepciones FIFO llevan motivo.
5. **Trabajo real:** backend, interfaz y pruebas coordinadas por PM; revisión independiente; sin nueva estructura de base de datos.
6. **Pruebas:** resultados verificables se registran en la sección de evidencias al terminar, distinguiendo PostgreSQL real de pantallas con API simulada.
7. **Estado:** EN IMPLEMENTACIÓN. La entrega de rama no habilita producción; revisión y despliegue son pasos separados.
