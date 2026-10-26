# Continuidad de producción con Calidad pendiente

## Contrato autorizado — 26-10-2026

El usuario validó para la futura operación real: avanzar producción con análisis o firmas pendientes, avisar y registrar al responsable; conservar bloqueos por resultados adversos/inocuidad y exigir liberación final de Calidad. Esta entrega prepara código en una rama y pruebas ficticias. No autoriza activar el cambio en producción, desplegar ni fusionar con DevelopMain.

La política `CCAA_CALIDAD_INTERMEDIA_AVISO` nace **false**. Sólo la configuración del servidor puede habilitarla. La interfaz consulta `GET /api/calidad/politica-continuidad/`; un cliente no puede encenderla mediante un POST o un campo del formulario.

## Comportamiento y límites

| Situación | Producción intermedia con política activa | Producto terminado / despacho |
|---|---|---|
| Falta firma o revisión de muestra | Aviso, identidad del operador y pendiente trazable | Retenido hasta resolver antecedentes y firmar |
| Falta muestra representativa de materia prima | Puede avanzar sólo donde no se necesita una medición para calcular; conserva deuda del material original | Una muestra de otro llenado no salda la deuda |
| Falta MG/SNG, densidad o referencia real de masa necesaria | Se conserva el requisito físico/técnico | No se inventan conversiones ni resultados |
| Vale ejecutado, RC medido conforme y litros conciliados | Acción operacional «Continuar con Calidad pendiente»; vale sigue muestreado | No se convierte en liberado ni crea firma |
| Resultado adverso, rechazo de Calidad, PCC/PPRO incumplidos | Bloqueo | Bloqueo |
| Equipo ocupado, CIP, silo fuera de servicio, saldo insuficiente, ruta incompatible | Bloqueo | Bloqueo |
| Polvo o mantequilla pendientes, con masa y embalajes válidos | Puede envasar en cuarentena | Ingreso como liberado y despacho conservan la guarda estricta |

Recepción inicial del camión conserva su compuerta de inocuidad. La política no crea productos, especificaciones industriales, tolerancias, densidades ni autorizaciones de reproceso. No habilita una etapa que aún no terminó físicamente.

Un remuestreo conforme no constituye por sí mismo la disposición de un resultado adverso conocido del mismo material. Las muestras se acotan al ciclo físico del silo; un llenado posterior tampoco debe bloquear o liberar retrospectivamente el anterior.

## Diseño y archivos principales

- `backend/calidad/continuidad.py`: política, clasificación de firma pendiente frente a rechazo, evaluación de resultados conocidos, avisos y eventos auditados, seguimiento de deuda de muestra.
- `backend/calidad/vigencia.py`: conserva las funciones estrictas finales y exige resolver las deudas de las entradas originales antes de firmar.
- `backend/recepcion/{dominio,servicios}.py`: excepción sólo para consumo productivo, nunca para despacho; CIP y estados duros permanecen.
- `backend/estandarizacion/{origenes,servicios,views,serializers}.py`: cierre operacional de vale conforme sin liberación ficticia, permisos existentes, catálogo y auditabilidad.
- `backend/procesos/{models,servicios,views,serializers}.py` y `backend/produccion/{dominio,servicios,views}.py`: Descremado, Evaporación, Secado, Mantequilla y Envase conservan origen, rutas, masa, litros, retiro único y cuarentena.
- `frontend/src/components/Calidad/`, servicios y formularios operacionales: aviso global, estado real de cada material y acción de continuidad autorizada por servidor.
- `backend/maestros/migrations/0039_silo_pendiente_calidad.py`: migración aditiva de opciones del estado; no mueve inventario ni convierte registros existentes.

Tablas involucradas: `Silo`, `AnalisisSilo`, `MovimientoSilo`, `ValeEstandarizacion`, `EjecucionProceso`, `EntradaProceso`, `SalidaProceso`, `EventoProceso`, `LiberacionProceso`, `Liberacion`, `Lote`, controles PCC/PPRO y registros de envasado/pallets existentes. La escritura de movimientos y evento de continuidad ocurre dentro de la misma transacción de la operación física. Los reintentos reutilizan la clave estable del evento.

El pendiente se conserva por la genealogía explícita `EntradaProceso.salida_origen`, incluso si el silo original queda vacío y se reutiliza. Para materia prima sin salida productora, se guarda la muestra utilizada o la ventana exacta entre ingreso y retiro correlacionado. No se acepta una muestra de otro llenado. El evento no contiene una firma de Calidad inventada.

## Compatibilidad, activación y reversión

1. Revisar y aprobar el PR y sus pruebas. Esta entrega no realiza despliegues.
2. En un entorno aislado, aplicar la migración aditiva, habilitar explícitamente la política y verificar el aviso del servidor/interfaz. La configuración estricta sigue siendo el valor por omisión.
3. Los antiguos `bloqueado_calidad` **no se reclasifican automáticamente**: no se puede inferir si eran una espera administrativa o un bloqueo real. Calidad debe revisar esos casos mediante acciones autorizadas.
4. Nuevas esperas administrativas utilizan `pendiente_calidad`. Si se consume completamente el contenido, se libera el contenedor vacío; el pendiente sigue unido al material y sus descendientes.
5. Para volver al régimen estricto, apagar la política conservando este código y sus guardas de deuda. Antes de volver a una versión de código anterior o revertir la migración, resolver o clasificar los estados nuevos y las deudas existentes; una reversión ciega perdería esas guardas. No se incluye un borrado o saneamiento automático.

No requiere contrataciones ni nuevos servicios. Reutiliza Django/React/PostgreSQL y la auditoría existentes. Las muestras reales y las decisiones industriales pendientes deben ser aportadas por las áreas responsables.

## Evidencias y aceptación

Las pruebas se ejecutan sobre OP00 local desechable (127.0.0.1:55439, rol `op00_test`), con verificación del directorio/base antes de cada corrida. El ensayo por pantalla OPFLOW es independiente. No se consultó Supabase ni sus logs.

La evidencia definitiva y los cortes intermedios se registran en `evidencias/calidad-continuidad/summary.json`. No sumar pruebas de cortes solapados ni considerar aprobada una corrida sin resumen completo. Chrome con API simulada verifica interfaz y permisos visibles; no equivale a un circuito completo de planta ni a una prueba de carga.

Criterios: política apagada conserva modo estricto; cliente no puede activar política; productor terminado y composición/balance válidos; continuidad deja autor y pendiente sin firma falsa; reintento no duplica retiro/evento; fallo tardío revierte ambos; adversos y CIP bloquean; deuda antigua sigue al material; Envase mantiene cuarentena; despacho requiere liberación final vigente. Las pruebas de carga OP09 y reservas propuestas del vale siguen siendo tareas separadas.

## EXPLICADOR

1. **Problema:** una firma pendiente detenía la siguiente etapa aunque la operación anterior ya había terminado.
2. **Causa:** las compuertas usaban la liberación de Calidad también como condición para continuar la producción intermedia.
3. **Ejemplo:** un precondensado terminado puede pasar a Secado con aviso; el polvo resultante sigue pendiente y sus pallets quedan en cuarentena.
4. **Solución:** separar avance físico de liberación comercial y mantener el pendiente ligado al material original.
5. **Trabajo:** coordinador backend, un apoyo frontend y un QA independiente; cambio acotado y migración aditiva, sin producción.
6. **Pruebas:** política, permisos, trazabilidad, reintento, reversión, resultados adversos, circuitos, interfaz y regresiones. Los resultados finales están en el manifiesto de evidencias.
7. **Estado:** entrega en verificación y revisión; activar en planta, completar UAT y resolver pendientes industriales son hitos separados.
