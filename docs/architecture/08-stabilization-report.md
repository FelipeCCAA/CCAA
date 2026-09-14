# Estabilización integral desde cero — 2026-09-14

## Resultado

CCAA fue reiniciado sobre la base local de desarrollo `ccaa`, se conservaron
los maestros necesarios y se recorrieron desde datos operacionales vacíos los
circuitos de polvo, precondensado, descremado/mantequilla y suero/Big Bag.

> **Regla arquitectónica:** “CCAA no utiliza Empresa ni Sucursal como
> dimensiones funcionales, de permisos, aislamiento o navegación.”

Los campos históricos siguen presentes únicamente cuando el esquema persistido
los exige. No seleccionan trabajo, no autorizan acciones y no filtran bandejas,
notificaciones ni navegación.

## Reset y estado QA reproducible

Comandos, únicamente en desarrollo/QA:

```powershell
cd backend
.venv\Scripts\python.exe manage.py reset_datos_operacionales --confirmar-base ccaa --aplicar
.venv\Scripts\python.exe manage.py preparar_estado_qa
```

El reset imprime entorno, motor, host, puerto, base, conteo por modelo y total;
aborta en entornos endurecidos, contra hosts no locales o si la confirmación no
coincide. Usa una transacción y `TRUNCATE ... RESTART IDENTITY` sobre 87 tablas
operacionales explícitas, sin `CASCADE`. No toca migraciones ni esquema.

Estado QA base comprobado:

| Conservado | Cantidad |
|---|---:|
| perfiles con áreas/roles | 13 |
| productos | 24 |
| rutas productivas | 22 |
| procesos / etapas | 6 / 18 |
| equipos / silos-TK | 12 / 14 |
| especificaciones | 29 |
| insumos / bodegas / ubicaciones | 12 / 8 / 15 |
| registros operacionales | 0 |

## Bugs encontrados y corregidos

| Área / endpoint | Problema | Causa raíz | Corrección y regresión | Estado |
|---|---|---|---|---|
| Calidad `POST resultados-proceso/{id}/rechazar/` | `500` al rechazar con el equipo ya ocupado | el rechazo intentaba volver la ejecución a un estado que adquiría físicamente el equipo | rechazo bloquea material, cierra la decisión pendiente, libera el equipo y no reinicia la ejecución; prueba exacta en `calidad/tests_rechazo_resultado.py` | corregido |
| API operacional | `django.core.ValidationError` esperables podían escapar como `500` | no existía traducción central consistente | handler DRF entrega `code`, `message`, `details`; equipo ocupado es `409 EQUIPO_OCUPADO` y transición inválida `400 TRANSICION_NO_PERMITIDA` | corregido |
| Procesos `POST ejecuciones/{id}/transicionar/` | la UI ofrecía continuar desde `pendiente_control` y backend respondía `400` | divergencia entre matriz backend y acciones visibles | desde control pendiente solo se cierra o bloquea; un reproceso crea ejecución trazable nueva; frontend consume el contrato | corregido |
| Producción | borrar un movimiento provisional podía producir error protegido | existía una atribución de recepción dependiente | se elimina primero la atribución provisional dentro de la operación controlada | corregido |
| Mantenimiento | endpoints devolvían `404` aun con implementación presente | el include de URLs faltaba en la configuración raíz | se registró `/api/mantenimiento/` | corregido |
| Permisos | lecturas necesarias de Recepción, especificaciones e Inventario daban `403` | matriz de lectura incompleta | lectura por área, rol, permiso y responsabilidad real; escritura continúa restringida | corregido |
| Notificaciones | aislamiento heredado por Empresa/Sucursal | lógica histórica de tenancy | entrega por áreas principales/adicionales y relación real del trabajo | corregido |
| Tests de reset | el reset contaminaba la base compartida y las fixtures auditadas fallaban | `TRUNCATE` fuera del rollback esperado y señales durante `raw=True` | reset cubierto en `TestCase`; auditoría ignora carga raw; constraints verificadas | corregido |
| E2E Polvo | Envasado esperaba una sección antigua para material pendiente | la UX actual oculta correctamente material no liberado | prueba actualizada para verificar mensaje de ausencia y lote no seleccionable | corregido |
| E2E Descremado | `409` al iniciar 1.000 L desde un silo vacío | prueba dependía de saldo residual histórico | el circuito ahora se valida después de una Recepción real; saldo y genealogía nacen desde cero | corregido |
| E2E firma de silo | botón siguiente podía quedar desactualizado tras la segunda firma externa | la pestaña del primer firmante conservaba estado anterior | recarga y reselección explícita en el helper E2E | corregido |
| Cierre residual Empresa/Sucursal | planificación, rutas, expediente de Calidad, alertas y disponibilidad de envases aún consultaban claves históricas | sobrevivían filtros funcionales directos fuera del adaptador de compatibilidad ya neutralizado | los cálculos usan fechas, producto, proceso, ubicaciones físicas, permisos y relaciones reales; 4 regresiones nuevas cubren los puntos críticos | corregido |

## Matriz operacional de estados y equipo

| Estado real | Acción válida principal | Equipo |
|---|---|---|
| `borrador` | preparar | se adquiere al entrar a preparación |
| `preparacion` | iniciar / cancelar | permanece ocupado / se libera al cancelar |
| `ejecucion` | pausar / cerrar proceso | ocupado durante ejecución |
| `pausada` | reanudar / cancelar | reserva coherente con la ejecución |
| `pendiente_control` | decisión de Calidad | no se readquiere; queda disponible al cerrar etapa física |
| `bloqueada` | disposición o reproceso nuevo | no se readquiere automáticamente |
| `cerrada` / `cancelada` | ninguna transición productiva | libre |

La exclusión usa la identidad física de `Equipo`, bloqueo de fila y una
restricción única condicionada. Dos solicitudes sobre la misma máquina dejan un
solo ganador; la otra obtiene `409`, nunca `500`.

## Inventario de endpoints activos

El resolver Django registra **345 nombres lógicos API** (sin duplicar variantes
de formato):

| Módulo | Endpoints lógicos | Responsabilidad / permiso dominante |
|---|---:|---|
| inventario | 95 | Bodega, Inventario, Compras, Calidad y Despacho |
| procesos | 50 | Producción por tipo de etapa; Calidad en decisiones |
| recepción | 36 | Recepción y Calidad; consultas relacionadas para Producción |
| producción | 31 | Producción, Secado y Envasado |
| planificación | 28 | Planificación y Administración |
| maestros | 21 | lectura operacional; escritura administrativa autorizada |
| calidad | 19 | Calidad; consulta relacionada por responsables |
| estandarización | 19 | Estandarización y continuidad productiva |
| usuarios | 13 | sesión propia y administración de trabajadores |
| recolección | 11 | Recolección / Recepción |
| mantenimiento | 11 | Mantenimiento y lecturas operacionales |
| inocuidad | 5 | Inocuidad y responsables de controles |
| auditoría | 4 | Administración autorizada |
| salud | 2 | disponibilidad técnica |

Endpoints críticos usados realmente por React y comprobados durante los E2E:

| Método / ruta | Pantalla | Resultado esperado / error observable |
|---|---|---|
| `POST recepcion/recepciones/*` | Recepción | borrador → muestra → decisión → silo → descarga; 400 regla, 403 permiso |
| `POST recepcion/analisis-silo/*` | Silos / Calidad | borrador, confirmación y segunda firma; 409 conflicto de estado |
| `POST estandarizacion/vales/*` | Estandarización | cálculo, confirmación y cierre trazable; 400 datos/balance |
| `GET procesos/planta-ahora/` | Planta Ahora | agregado por estados y relaciones reales; 403 sin permiso |
| `GET/POST procesos/condensaciones/*` | Evaporación | alta, inicio y cierre; 409 equipo/saldo |
| `GET/POST procesos/secados/*` | Secado | alimentación interna/externa y balance; 409 equipo/stock |
| `GET/POST procesos/descremaciones/*` | Descremado | sugerencia, reserva, inicio y dos salidas; 409 saldo/equipo |
| `GET/POST procesos/mantequillas/*` | Mantequilla | alta, inicio y balance completo; 409 material/equipo |
| `POST procesos/ejecuciones/{id}/transicionar/` | Mi Producción | transición permitida; 400 transición, 409 equipo |
| `GET/POST calidad/resultados-proceso/*` | Calidad | liberar/rechazar/bloquear; 400 decisión, 403 permiso |
| `GET/POST calidad/expedientes/*` | Expediente | registros, liberación y envío; 409 expediente incompleto |
| `GET/POST produccion/envases/*` | Envasado | solo material liberado y unidades completas; 400 saldo/formato |
| `GET inventario/estado-operacional/` | Inventario | existencias físicas y disponibles sin doble conteo |
| `POST inventario/despachos/*` | Despacho | crear, autorizar y ejecutar; 400 saldo, 403 permiso, 409 estado |
| `GET procesos/genealogia/*` | Trazabilidad | padres, hijos, cantidades, equipo, usuario, calidad y destino |

No se eliminó ningún endpoint antiguo: la petición exigía evidencia de desuso y
la estabilización priorizó los contratos consumidos por el frontend. Los no
consumidos quedan como `LEGACY NECESARIO / POR CLASIFICAR`, no como obsoletos.

## E2E desde cero

| Circuito / compuerta | Resultado |
|---|---|
| Polvo: Recepción → Vale → Estandarización → Evaporación → Secado → Calidad → Envasado → Inventario | PASS |
| Mantequilla: Recepción → Descremado → Crema → Mantequilla → Calidad → Envasado → Inventario | PASS |
| Precondensado: leche estandarizada → Evaporación → Calidad → despacho directo | PASS |
| Suero / Big Bag: entrada externa liberada → Secado → Calidad → Big Bag → Inventario | PASS |
| rechazo y bloqueo de Calidad | PASS |
| Inventario y Despacho | PASS |
| concurrencia de equipo | PASS |
| permisos por puesto/área | PASS |
| trazabilidad y genealogía | PASS |

## Rendimiento observado

- Se conservó la deduplicación/caché corta de GET ya existente.
- No se agregó ningún refetch global ni nueva cascada de requests.
- El expediente de Calidad crece aproximadamente de 33 KB a 41 KB al completar
  sus 19 registros. La pantalla utiliza la plantilla, estados y registros para
  habilitar la liberación; no se recortó el payload sin evidencia segura.
- En esta estabilización no se atribuye una reducción adicional de requests,
  N+1 o payload: las mejoras realizadas fueron de integridad y contrato.

## Calidad técnica final

| Verificación | Resultado |
|---|---|
| backend Django | 1.417 correctas, 5 omitidas, 0 fallos |
| frontend unitario | 41/41 correctas |
| E2E productivos | Polvo, Precondensado, Descremado, Mantequilla y Suero/Big Bag PASS |
| Ruff completo | sin hallazgos |
| ESLint completo | sin hallazgos |
| TypeScript + build Vite | correcto |
| `manage.py check` | sin hallazgos |
| `makemigrations --check --dry-run` | sin cambios |
| `migrate --noinput` | esquema al día |
| reset final + estado QA | operación `0`, maestros disponibles |

## Repetición de circuitos

Después de reset y `preparar_estado_qa`, aplicar solo el preparado requerido:

```powershell
.venv\Scripts\python.exe manage.py preparar_circuito_polvo --aplicar
.venv\Scripts\python.exe manage.py preparar_circuito_precondensado --aplicar
.venv\Scripts\python.exe manage.py preparar_circuito_descremado --aplicar
.venv\Scripts\python.exe manage.py preparar_circuito_mantequilla --aplicar
.venv\Scripts\python.exe manage.py preparar_circuito_suero --aplicar
```

Los preparados usan claves históricas solo para persistir modelos legados; no
aceptan Empresa/Sucursal como filtro o dimensión de la prueba.

## Cierre residual de la regla arquitectónica

La revisión posterior a los E2E encontró y eliminó los últimos usos directos
que todavía podían alterar un resultado funcional:

- el contraste semanal ya no recorta recepciones, movimientos, lotes, códigos
  ni stock de seguridad por la sucursal histórica de la semana;
- las rutas y etapas se resuelven por producto, proceso, prioridad y estado
  activo, no por sucursal;
- el expediente de Calidad considera los documentos aplicables por familia y
  evidencia, independientemente de la empresa histórica del catálogo;
- las alertas suman el stock operacional total del insumo y Envasado usa la
  disponibilidad física total del material;
- Recepción permite vincular el vehículo real sin comparar su antigua clave de
  sucursal.

Las firmas que aún reciben `sucursal`, los campos persistidos y los nombres
legados de mixins se conservan solamente para no romper esquema, migraciones o
llamadores antiguos. No deciden permisos, aislamiento, navegación ni lógica de
negocio.

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de
> permisos, aislamiento o navegación.”
