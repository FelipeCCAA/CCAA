# OP-07 — Identificadores, auditoría masiva y exportaciones

**IMPLEMENTADA Y VALIDADA LOCALMENTE EN LA RAMA** `codex/op-07-auditoria-exportaciones`, desde OP-06 `4dd3a9425c57e983e4d9458c44f52fd54070c52e`. Código/pruebas `3ad83f3`. El usuario aprobó las seis reglas y su implementación con pruebas y PR, sin producción/despliegue. Revisión apilada sobre OP-06 #13, no directamente sobre DevelopMain.

## Contrato y archivos

| Regla | Cambio y evidencia |
|---|---|
| Conservar IDs/UUID | Sin renumeración, modelos, migraciones ni backfill. Prueba del UUID exacto del movimiento, modificación de otro campo y reintento sin cambios. El soporte UUID ya existía. |
| Auditar cambios masivos críticos | Helpers conectados a los caminos enumerados abajo; fila, actor/contexto, fecha y pares antes/después. Pruebas con actor API y UUID real. |
| Guardar dato e historia juntos | Tres helpers con `atomic`, actualizaciones bloqueadas por PK ordenada y transacciones envolventes de dominio conservadas. Fallos forzados revierten operación y eventos. |
| Historia sólo lectura/sin secretos | API/admin y exclusiones password/last_login/token_hash conservadas. Pruebas de lectura, permisos, create/update/delete rechazados y contraseña excluida. No se inventa historia faltante. |
| Reportes fieles/texto seguro | Misma lista y filtros/permisos existentes para JSON/CSV/XLSX. CSV neutraliza fórmulas sólo en columnas textuales; XLSX fuerza cadenas literales, conserva ceros iniciales/decimales. No modifica datos almacenados ni cálculos. |
| Nunca truncar silenciosamente | Tope síncrono 1000 recepciones, consulta acotada a 1001 para detectar exceso: 400 `REPORTE_DEMASIADO_GRANDE` sin archivo parcial. UI explica errores JSON/Blob y permite reducir período. |

Archivos operativos conectados a `crear_en_lote_con_auditoria`:

- `backend/produccion/servicios.py`: PalletProducto al envasar.
- `backend/inventario/servicios.py`: ExistenciaProductoTerminado, MovimientoProductoTerminado y detalles de solicitudes/órdenes de compra.
- `backend/inventario/serializers.py`: EtapaCIP y DetalleDespacho.
- `backend/recepcion/servicios.py`: AtribucionRecepcion en FIFO/herencia.
- `backend/recepcion/views.py`: ModuloRecepcion de borradores y reportes.
- `backend/planificacion/views.py`: BalanceDia, BloquePlan y MovimientoPlan al duplicar semana.

`backend/auditoria/registro.py` rechaza `ignore_conflicts/update_conflicts`: no permiten distinguir altas reales. Exige IDs persistidos/únicos existentes, conserva retornos y no registra no-op como cambio. Notificacion/Alerta siguen excluidas de esta instrumentación masiva por ser mensajes derivados; escrituras técnicas de identidad/sesión y migraciones históricas no se amplían. Señales save/delete existentes conservadas. No se certifica SQL directo ni scripts privilegiados que eludan los caminos soportados.

`backend/recepcion/exportaciones.py` contiene protección de texto y tope. Frontend: `ReporteDiario.tsx`, `recepcion.service.ts`, nuevo `error-reporte.ts`; cancela consulta anterior al cambiar período, bloquea exportación durante carga y filtros durante descarga. Dos consultas en momentos diferentes pueden reflejar operaciones nuevas: no se presenta un corte histórico congelado.

## Evidencias ejecutadas

PostgreSQL OP-00 dedicado `../op00-runtime/pgdata`, rol `op00_test`, `127.0.0.1:55439`; harness valida identidad/catálogo/puerto y ausencia de `.env`. Sólo bases y datos sintéticos. Logs en `../op00-runtime/`, fuera del repo.

| Ejecución | Resultado / log |
|---|---|
| Primer baseline exportaciones | 6 casos, cinco errores de fixture por asignar propiedad derivada kg_guia; corregida sólo la preparación, no considerados defectos productivos. `op07-exports-baseline.log`. |
| Baseline válido conjunto | 10 pruebas, 3,023 s; nueve fallos contando subcasos: cuatro helpers, CSV, XLSX y tres formatos sin límite. `op07-baseline.log`. |
| Exportaciones + instructivo | 26/26, 12,905 s. `op07-exports-focal.log`. |
| Auditoría intermedia | 30/30, 3,759 s. `op07-auditoria-focal1.log`; se solapa con integración, no sumar. |
| Integración final | 58/58, cero omitidas, 34,965 s: diez nuevas de auditoría, siete de exportación y 41 regresiones. `op07-integracion-final.log`. |
| Historia/API | 12/12, 10,220 s. `op07-historia-readonly.log`. |
| Frontend | 111/111; lint y TypeScript/build exit 0. `op07-frontend-tests.log`, `op07-frontend-lint.log`, `op07-frontend-build.log`. Cuatro nuevos casos JSON/Blob. Aviso preexistente FormularioMaestro `INEFFECTIVE_DYNAMIC_IMPORT`. |
| Chrome simulado | 2/2, 7,8 s: exceso y recuperación; error Blob CSV/Excel sin descarga. `op07-browser-final.log`. Red externa bloqueada, proxy localhost sin servicio. Primera ejecución restringida interrumpida sin resultados, no declarada aprobada. |
| Estática/esquema | Ruff backend y diff-check aprobados; makemigrations --check --dry-run: No changes detected. |

Carrera nueva: dos conexiones/actores distintos, primera retenida durante auditoría; `pg_blocking_pids` prueba espera real de la segunda. Exige cadena `en_proceso → producido → cerrado` y actor correcto, sin esperar un tiempo fijo para decidir quién gana. Rollback integrado probado tras guardar existencia física y tras copiar Balance antes de fallar Bloque: no quedan filas parciales ni eventos.

### Ensayo del tope

1000 recepciones, cuatro módulos cada una y guías de 60 caracteres. Última corrida integrada con tracemalloc activo:

| Formato | Segundos | Pico asignaciones Python, bytes |
|---|---:|---:|
| JSON | 0,826 | 11.378.720 |
| CSV | 0,774 | 11.735.757 |
| XLSX | 2,289 | 14.605.633 |

Prueba exige filas completas, 1.234.560,00 L y pico Python <64 MiB; agrega recepción 1001 y exige rechazo en tres formatos. Protección conservadora de trabajo síncrono, no límite industrial ni medida de RSS total. No certifica carga/tiempos productivos ni exportaciones simultáneas. Lectura real con csv/openpyxl comprueba permisos (Recepción/anónimo/Aseo), filtros, faltantes, cifras, ceros y ausencia de fórmulas.

## Reproducción, entrega y límites

Con OP-00 aislado iniciado según su expediente, desde raíz del repo:

```text
../op00-runtime/.venv/Scripts/python.exe ../op00-runtime/run_backend.py test auditoria.tests_op07_masivos auditoria.tests_registro recepcion.tests_op07_exportaciones recepcion.tests_api_instructivo --noinput --verbosity 1
../op00-runtime/.venv/Scripts/python.exe ../op00-runtime/run_backend.py test auditoria.tests_api auditoria.tests --noinput --verbosity 1
```

Desde frontend: npm test, npm run lint, npm run build y npx playwright test --config op07-ui/playwright.config.ts. Sin nuevas dependencias. Clúster local detenido, exit 0, sin postmaster.pid; servidor Chrome cerrado.

Código/pruebas `3ad83f3`, documentación en commit posterior. TASK_BACKLOG.md y PROGRESS.md actualizados. Revisión independiente de `3ad83f3` por lectura sin bloqueos concretos; ejecución por coordinador. Resultado general del commit entregado y PR definitivo en sus checks e informe AVANCE, sin anticipar aprobación. [PR por cabecera](https://github.com/FelipeCCAA/CCAA/pulls?q=is%3Apr+head%3Acodex%2Fop-07-auditoria-exportaciones).

Revertir código no borra eventos ya generados; nunca eliminar historia para retroceder. Sin producción, datos reales, nuevas migraciones, infraestructura, merge ni despliegue. No UAT, restauración de backup o carga de 70 usuarios. OP-08: envases/archivos/correo; sólo diagnóstico/preparación hasta autorización específica.

**AVANCE:** seis reglas implementadas y verificadas localmente; rama/expediente preparados para revisión sobre OP-06 #13. Dos apoyos reutilizados, backend y revisión independiente; coordinación cubre integración, QA, PM y explicación.

**EXPLICADOR:** 1) Problema: historia faltante en operaciones masivas y planillas con fórmulas/texto sin control de tamaño. 2) Causa: bulk omite señales, exportación escribía texto directamente. 3) Ejemplo: pallets/movimientos físicos sin sus eventos en Auditoría. 4) Solución: historial por fila en la misma transacción y reporte completo literal o rechazo explicado. 5) Trabajo: código/pruebas/docs en rama, sin producción. 6) Pruebas locales: 58+12 backend, 111 frontend y dos recorridos simulados aprobados; CI separada en PR. 7) Estado: implementada y validada localmente, pendiente de revisión humana, sin despliegue.
