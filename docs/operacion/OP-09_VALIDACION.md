# OP-09 — Circuitos, carga y recuperación

**VERIFICACIÓN CON BLOQUEANTES; CIERRE EN PREPARACIÓN.** Usuario aprobó las seis reglas y escalones 10/25/50/70 usuarios virtuales; 10 minutos por escalón, 30 minutos en el mayor estable. Calentamiento de cinco minutos. Sin producción, despliegue, correos reales ni Supabase/logs. Sólo un apoyo QA reutilizado (`op08_revision`, gpt-6-sol high), coordinación/AVANCE/EXPLICADOR por agente principal. Rama `codex/op-09-circuito-carga-respaldos`, desde OP-08 `a564861e00ef836e16d6e59e584de312e31c8812`. Implementación de QA `6773958`; ningún cambio en código de aplicación. No certificar listo para planta.

## Entorno y alcance

PostgreSQL 17 nuevo en `../op09-runtime/pgdata`, rol `op09_test`, loopback 55449; base `op09_circuito`, restauración nueva `op09_restaurada`. API 127.0.0.1:8209, web 127.0.0.1:5209, API restaurada 8219. `qa/op09/manage_isolated.py` valida identidad y catálogo, rechaza `.env` de aplicación y limpia variables heredadas. Correo en memoria, Celery eager, sin worker/beat ni broker. Maestros/cuentas/recepciones/stock exclusivamente ficticios. Volumen privado local dedicado, sin datos de planta. Docker no disponible: se usa servidor Django de desarrollo. La medición no certifica capacidad de un servidor de producción.

Las sesiones de carga son una fixture explícita de 70 personas **ya autenticadas**, con hashes de sesión reales y permisos de cada área. La API valida sus credenciales/permisos normalmente. No se cambian límites de login; ráfaga de acceso se ensaya por separado. Cada usuario hace una petición a la vez y espera 1–3 s: 70 usuarios virtuales activos no equivalen a 70 solicitudes simultáneas en vuelo. Mezcla observada y RPS deben acompañar cada resultado. Escrituras de carga: borradores propios de Recepción y traslados reversibles de lotes particulares de Bodega, con repetición exacta del UUID; Calidad y Producción consultan. No equivale a 70 cierres industriales simultáneos.

## Evidencias ya obtenidas

Resultados crudos, trazas y capturas fuera del repositorio: `../op09-runtime/`.

- Maestros iniciales ausentes en base nueva: preparación polvo rechazó producto inexistente. Fixture explícita `seed_masters.py`, conservando la única organización de test. Dos fallos de fixture previos (segunda planta activa y supuesto código OP09 de sucursal) revirtieron íntegramente; corregidos sin producción.
- Polvo: recepción → vale liberado, 2/2 en 24,8 s incluyendo sesión; evaporación, 2/2 en 50,1 s. Continuación bloqueada, según hallazgo abajo. Cortes reanudados sobre el mismo lote, no pruebas completas independientes.
- Precondensado: recepción/vale 2/2 en 1,1 min tras reanudar un timeout de montaje del módulo; evaporación 2/2 en 18,8 s; liberación y despacho físico desde silo 1/1 en 36,5 s (paso operativo 15,0 s). Handoff `OP09-PRE-335212`, 1.500 L de precondensado, destino Silo 5. Capturas previas conservadas.
- Descremado: separación y liberación de ambas salidas aprobada (23,8 s); primer escenario comercial directo falló por catálogo sintético incompleto. Se vinculó la ruta existente `ruta-crema-despacho` (migración 0018) a productos ficticios creados después de migrar y cliente ficticio, sin inventar ruta industrial. Reejecución comercial `descremado-directo-2.log`: 3/3 incluyendo sesión, despacho directo y visibilidad de bifurcación. Crema física `INT-DES-1-CR`, ID 4, TkC2, 62,86 L.
- Mantequilla: producción real desde esa crema, 2/2 con sesión en 49,9 s; lote `MANT-E2E-74988730`, ID 6, 31 kg. Continuación principal: caja de 20 kg + remanente de 11 kg, disposición de Calidad y traslado a Bodega aprobados. Suite de continuación: 3 aprobadas incluyendo sesión y una auxiliar fallida, no 4/4. Esa auxiliar intentó reabrir sólo Calidad sobre un lote ya liberado, ausente correctamente de pendientes; fallo de preparación/orden del test, sin demostrar defecto operacional. No se oculta ni se fuerza verde.
- Suero externo: primera ejecución esperaba etiqueta retirada «Liberado», actual «Disponible»; corregido sólo selector E2E. Reejecución 2/2 incluyendo sesión, 2,7 min: entrada externa ficticia 1.000 kg, consumo 800 kg, BigBag 700 kg e Inventario. No se atribuye recepción de leche a un material externo.
- Evidencia privada subida y descargada por API: adjunto 1, CSV ficticio 68 bytes, SHA256 `186f0a2cbb31663d6278ac2ca2e336e0bebddde657349ec0b923287228239627`; respuesta privada no-store. Primer envío rechazó falta del campo tipo en fixture; segundo válido, sin cambiar la API.
- Preparación de carga: nueve lecturas permitidas por cuatro áreas, un borrador con texto confirmado y dos traslados repetidos (4 POST) sin duplicar ID. 18 lotes de 10.000 unidades cada uno, saldo total conservado y no negativos. Esto es preflight, no carga aprobada.

## Hallazgo H09-01 — P1, bloqueo operativo en polvo multietapa

En lote `CCAA-EVA-188552` (ID 1), asignar el secador invalida la aprobación de la salida anterior por cambio de `lote.equipo_id`; el cierre se rechazó 400 hasta nueva revisión de Calidad, ejecutada realmente por la interfaz. Al cerrar Secado se modifican `lote.kg_producidos` y estado; otra vez invalidan la aprobación de Evaporación. Liberar el polvo nuevo no rehabilita esa aprobación anterior.

La bandeja ofrece el material y habilita crear pallet, pero `POST /api/produccion/envases/` devuelve 400: «Evaporación está pendiente de aprobación de Calidad antes de Envasado». **No se creó el pallet, no se quitó la guarda ni se añadieron más firmas para forzar un resultado verde.**

Trazabilidad técnica: `calidad/vigencia.py` CAMPOS de Lote/evidencia_salida/invalidar_por_cambio; `procesos/servicios.py` preparar_continuacion y cerrar_secado (cambia equipo, peso y estado); `produccion/servicios.py` bloqueo_calidad_para_envasado revisa todas las salidas principales; `produccion/views.py` materiales_habilitados revisa sólo la salida final. UI y confirmación no usan el mismo criterio.

Evidencia: `continuacion-polvo-2.log` (firma inválida), `continuacion-polvo-4.log` (Envasado 400), carpetas `evidence-polvo-fallo2` y `evidence-polvo-fallo4`. `continuacion-polvo-1` omitía ticket obligatorio de kg medidos (fixture obsoleta OP-04); `-3` tenía selector ambiguo entre dos etapas, corregido sólo en E2E. Ninguno se declara aprobado.

Decisión pendiente: delimitar evidencia de la salida intermedia frente a cambios normales de etapas posteriores, o diseñar revalidación visible antes de ofrecer Envasado; alinear bandeja y POST. Requiere validación del usuario antes de modificar negocio/código productivo. No se certifica el circuito polvo completo.

## Concurrencia y recuperación por UUID — aprobadas en el alcance ensayado

`http-races.json/log`: dos POST HTTP retenidos sobre la misma fila; PostgreSQL observó realmente dos conexiones bloqueadas. Al liberar, 201 y 409, un solo retiro de 7.500 sobre 10.000, compensado mediante API. En otra operación se descartó deliberadamente la respuesta después de demostrar el primer commit: reenvío con mismo UUID devuelve 200 e ID 41, sin segundo efecto. Saldo final 10.000. No es sólo un mock o dos funciones llamadas secuencialmente.

`carreras-regresion.log`: **77/77** en 76,994 s sobre PostgreSQL real y base de test desechable: vigencia/firmas, concurrencia de Calidad y Despacho, reservas/recepción/inventario/procesos y 19 casos de Envasado. Ninguna omitida. Base de test destruida al terminar. Lint y tipos frontend, Ruff de QA y diff-check aprobados. No sumar cortes solapados como pruebas únicas ni extrapolar cobertura exhaustiva.

## Carga — H09-02, P1 de validación pendiente

| Etapa | Tiempo real | Solicitudes | Errores | p95 lectura / escritura | Resultado |
| --- | ---: | ---: | ---: | --- | --- |
| Calentamiento 10 | 301,297 s | 1.384 | 0 | 0,334 / 0,435 s | Aprobado |
| 10 usuarios | 603,159 s | 2.759 | 0 | 0,325 / 0,425 s | Aprobado, 4,574 req/s |
| 25 usuarios | 244,726 de 600 s | 2.598 | 7 | 0,552 / 0,817 s | Abortado por escrituras inciertas |
| 50 / 70 | No ejecutado | — | — | — | No escalar tras la guarda |
| Sostenida independiente 10 | En ejecución, 1.800 s previstos | — | — | — | No anticipar aprobación |

Evidencia original `load-summary.json` y `load-users-25.json` conservada sin sobrescribir. Siete fallos de transporte sin respuesta HTTP (status sintético 0), cuatro GET y tres POST de traslado de cuentas 22/14/18. Aunque 7/2.598 <1% y p95 cumplía, una escritura incierta exige parar inmediatamente; el tiempo previsto no se completó. Al primer corte había 449 movimientos frente a 448 UUID de respuestas exitosas; tras drenar API quedaron **451 movimientos, 451 UUID distintos, cero nulos**, compatibles con los tres POST tardíos. El servidor registra respuestas 200/201 y tres `Broken pipe`, sin 500/traceback observado. No se demostró causa definitiva entre aplicación, servidor de desarrollo, red local o carga compartida del host. RAM alcanzó 82%, CPU de muestra 60,67%; no se atribuye saturación a partir de esas cifras ni se certifica «máximo 10 usuarios».

`load-reconciliation.json`: 18 lotes de 10.000, todas las ubicaciones coinciden con entradas/salidas del libro, cero reservas y no negativos. No se borró ni corrigió stock. **Limitación de observabilidad del generador**: los fallos no persistieron UUID original, clase de excepción ni duración; los éxitos iniciales se guardaron como cantidad, no conjunto completo. Por eso la atribución exacta de los tres POST es inferida, no probada por clave cliente. Referencias: `qa/op09/load.py` call/worker/finally. Prioridad P2 para mejorar futuras evidencias, conservando ésta.

La guarda impide reejecutar el protocolo original sobre movimientos previos. Tras conciliación y revisión independiente se inició `soak_after_abort.py`, prueba **nueva** a 10 durante 30 minutos, mismo trabajo/guardas/umbrales, login HTTP normal sin cambiar cuotas. Usa baseline de 451 UUID, guarda nuevas claves y compara diferencia exacta con BD; archivos `load-post-abort-soak-*`, sin reemplazar el fallo a 25. No transforma OP-09 en aprobada globalmente.

Ráfaga de acceso normal pendiente al acabar la sostenida; no cambiar throttle ni limpiar caché para forzar resultado.

## Respaldo coherente y restauración — aprobados localmente

Todos los escritores propios detenidos: API fuente 8209 parada, sin worker/beat/otros clientes PG; frontend no escribe sin API. Corte `freeze-source.json`, UTC `2026-10-22T13:35:45.6654428Z`. Clúster dedicado verificado antes de ejecutar; destino nuevo y vacío, sin sobrescribir recursos previos.

Backup `backup-20261022T133548Z`: `pg_dump` custom + copia privada de archivos. Fuente antes/después idéntica. Restauración `op09_restaurada` + directorio privado nuevo: **130 tablas** comparadas con conteo y hash de todas las filas, todas iguales. Adjunto exacto ID 1 subido antes por API, 68 bytes, hash arriba, enlace BD→archivo comprobado; no sólo una carpeta vacía. Dump 814.076 bytes, SHA256 `9dca4d28f6dccf9b10084f576ba2c1b5815fa356c67b96327f8ab4b3db025b41`.

Backup 1,5642 s; restauración 2,5677 s; restauración+verificación 3,0451 s. API restaurada 8219: login/identidad autorizada, descarga privada con hash exacto, traslado nuevo 201 y repetición 200, saldo conservado y fuente sin cambios. Prueba HTTP 1,2989 s; desde congelación hasta final funcional **89,3186 s incluyendo coordinación manual**. API restaurada detenida después; fuente reiniciada para vista local y carga.

Evidencia `backup-summary.json`, `backup-restore.log`, manifiesto timestamp y `restore-smoke.json/log`. Son datos pequeños y ficticios: **no equivalen a RTO/RPO productivos**, no implementan programación, cifrado, retención ni copia fuera del equipo. Cero divergencia sólo en el corte congelado. Próxima decisión de infraestructura: definir recuperación real y ensayar dataset/tamaño representativos en entorno equivalente, con autorización propia.

## Matriz de las seis reglas autorizadas

| Regla | Evidencia y resultado | Límite |
| --- | --- | --- |
| Aislamiento y datos ficticios | PG/rol/puertos/catálogo dedicados, `.env` rechazado; aprobado | No producción ni Supabase |
| Circuitos reales por familia | UI→API→PG, precondensado/descremado/mantequilla/suero principales logrados | Polvo bloqueado H09-01; auxiliar de mantequilla fallida |
| Carreras, reintento y permisos | HTTP 201/409, pérdida de respuesta dirigida, 77/77 backend | No prueba exhaustiva de todo rol/ruta |
| Carga escalonada y sostenida | 10 aprobado; 25 abortado, datos conciliados | 50/70 no ejecutado; sostenida separada en curso |
| Respaldo completo y recuperación | 130 tablas + adjunto, igualdad y operación real restaurada | Dataset pequeño, no SLA productivo |
| Evidencias y decisiones | Rama, expediente, crudos conservados; QA independiente | PR/CI final en preparación; no modificar reglas para ocultar fallos |

## Cambios, reproducción y entrega

Sólo `qa/op09/*`, `frontend/op09-ui/*`, cuatro archivos E2E de familias y documentación. Cambios E2E: ticket obligatorio de kg; revisión legítima de Calidad antes del cierre; selectores precisos de etapa; origen físico de mantequilla y balance ficticio sin mazada retirada; etiqueta actual Disponible de suero. Ninguna tolerancia, modelo, migración, servicio o regla de planta modificados.

Reproducción: `qa/op09/manage_isolated.py` y README `frontend/op09-ui/README.md`; ambiente existente necesario, no ejecutar fixtures sobre producción. `load.py` y backup rechazan repetir sobre datos/destinos existentes. Dependencias locales ya instaladas en OP-00 y PostgreSQL 17; no contratar servicios. CI general se registra por SHA en el PR, no sustituye los circuitos locales ni reproduce esta carga Windows.

Vista entregada en navegador del chat: `http://127.0.0.1:5209`, captura `../op09-runtime/pantalla-local.png`. Cuenta de demostración ficticia separada para no cerrar sesiones E2E. Fuente 8209, Vite 5209 y PG 55449 quedan accesibles sólo en loopback para la revisión local; restaurada 8219 detenida. No publicar esta vista como producción.

**Siguiente tarea propuesta, sin implementar:** corregir H09-01 con decisión del usuario sobre firmas por etapa y habilitación coherente; después repetir polvo completo y diagnosticar pérdidas de respuesta en servidor de pruebas equivalente al futuro entorno real. Mejorar trazado de UUID del generador antes de nueva carga. No se autoriza merge/despliegue ni se declara CCAA listo para uso industrial.

Los números de Mantequilla adaptados en el E2E (36 kg entrada, 31 kg mantequilla, 5 kg merma) son datos ficticios para probar el balance informático y el remanente. No son una receta ni una validación del rendimiento físico o del balance de materia grasa de planta.
