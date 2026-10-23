# OP-09 — nueva ejecución de carga, 2026-10-23

**RESULTADO PARCIAL: CARGA NO APROBADA.** Se ejecutó el protocolo autorizado
hasta su guarda de recursos. No se reinició, acortó ni redondeó el escalón para
declararlo aprobado. No hay autorización de uso productivo derivada de esto.

Rama `codex/op09-carga-revalidacion`, base de aplicación
`58444474facb420bbfbe24d19b05ddb06f6bea57` (corrección H09-01 incluida).
Únicamente cambios de QA, fixtures ficticios y documentación; backend/frontend
de aplicación intactos. Un apoyo QA; PM/ejecución/AVANCE/EXPLICADOR por coordinador.
Sin producción, despliegues, contratación, datos reales ni consultas Supabase.

## Contrato y entorno

Usuario validó seis reglas y autorizó ejecutar: entorno aislado; registro de cada
intento; calentamiento cinco minutos; 10/25/50/70 usuarios diez minutos por nivel,
sin avanzar tras fallo; integridad por operación y ubicación; sostenida treinta
minutos en mayor nivel aprobado; prueba de entrada de turno sin cambiar cuotas.
Esperas de 1–3 segundos por usuario, una petición en vuelo por usuario. Cuatro
áreas: Recepción escribe borradores, Bodega traslada una unidad ficticia entre
ubicaciones particulares; Calidad y Producción consultan. No son 70 cierres
industriales simultáneos ni un circuito industrial completo bajo carga.

Clúster PostgreSQL17 **nuevo**, `../op09r-runtime/pgdata`, usuario `op09r_test`,
única base `op09r_carga`, loopback55469. Identidad de directorio/rol/dirección/
puerto/catálogo validada antes de operaciones. Respaldo **ficticio** OP09
20261022T133548Z restaurado tras comprobar SHA256; archivos privados ficticios
copiados. Fuente, respaldo y resultados OP09/H09 anteriores preservados. Setenta
cuentas nuevas `op09r_carga_`, 18 lotes de 10.000 unidades y 36 ubicaciones.
API exclusiva loopback8229; ninguna modificación a la vista local5209.

Se comprobó Docker Desktop ya instalado; no quedó disponible el motor Linux.
No se descargaron imágenes ni instalaron dependencias, ni se cambió configuración
de Docker. Por ello este ensayo es **diagnóstico local con Django de desarrollo
en Windows**, no prueba de capacidad en servidor representativo. La equivalencia
con servidor productivo sigue pendiente. Se comunicó esa limitación antes de
iniciar carga. Correo en memoria, tareas eager, sin broker/workers.

Guardas mantenidas: RAM del host>85% (muestra cada cinco segundos), CPU>80% en dos
muestras de treinta segundos, conexiones>80, errores>=1% tras cien solicitudes,
cualquier escritura incierta/fallida, repetición diferente o diferencia de saldo.
Aprobar exige duración completa, lecturas p95<1s, escrituras p95<2s, errores<1%,
integridad y ninguna parada. No se cerraron aplicaciones ajenas ni se redujeron
guardas para forzar resultados. La RAM medida es del equipo compartido; **no se
demostró que CCAA fuera la causa de su aumento**.

## Resultados medidos

| Prueba | Duración real / prevista | Solicitudes | Errores | p95 lectura / escritura | Veredicto |
| --- | --- | ---: | ---: | --- | --- |
| Calentamiento, 10 usuarios | 302,535 / 300s, incluye drenaje | 1.406 | 0 | 0,275 / 0,373s | Aprobado |
| Escalón, 10 usuarios | **597,512 / 600s** | 2.831 | 0 | 0,269 / 0,372s | **Incompleto**, RAM86% |
| 25 / 50 / 70 | No ejecutados | — | — | — | No escalar tras guarda |
| Sostenida treinta minutos | No ejecutada | — | — | — | Ningún escalón nuevo aprobado |
| Entrada de turno, 70 previstos | **4 accesos ejecutados** | 4 login, todos200 | 0 en esos cuatro | No se evaluó carga70 | **Incompleta**, guarda RAM>85% |

La muestra que disparó STOP fue a597,336s; la duración total597,512s incorpora
finalización de peticiones en vuelo. Faltaron aproximadamente2,5s: **no se
declaran diez minutos aprobados**. Calentamiento+escalón suman4.237 solicitudes;
el diario incluye además23 peticiones de preparación autorizada, total4.260.
La salida del generador fue exit1, según corresponde al protocolo incompleto.

En entrada de turno se cerraron primero las70 sesiones sintéticas de la carga.
La memoria había bajado a82%, por lo que se inició la prueba independiente;
una nueva subida>85% detuvo tras cuatro accesos. Sus cuatro identidades fueron
verificadas y sus cuatro sesiones se cerraron. Llegadas secuenciales separadas1s
desde una IP: **no benchmark simultáneo**. No se cambió cuota ni se limpió caché.
No se alcanzó70 ni se observó429 en este corte: **no demuestra ni descarta el
problema de cuota compartida** documentado anteriormente.

## Integridad y trazabilidad verificadas

Diario exclusivo append-only:8.557 eventos,4.260 intenciones y4.260 resultados;
secuencia contigua, intención persistida antes de enviar HTTP, método/payload
ficticio/UUID, estado/tiempo/clase de excepción/ID sin secretos. No hubo errores
HTTP ni escrituras inciertas en este ensayo; el procedimiento de recuperación
por UUID no necesitó activarse. **No se declara probada aquí una recuperación
real por respuesta perdida**, aunque el protocolo esté preparado.

- **304 UUID originales =304 movimientos nuevos**, cantidades, origen/destino,
  lote, documento, usuario e ID confirmado concordantes; cero UUID desconocidos
  o nulos y cero diferencias. Se comprobaron63 reenvíos con mismo ID, sin nuevo
  efecto. No sumar reenvíos como movimientos independientes.
- **36 ubicaciones de18 lotes** cuadran con baseline+movimientos, sin negativos
  ni reservas inesperadas; estado inicial preservado. Snapshot PostgreSQL de
  lectura repetible evita comparar libro y saldos en instantes distintos.
- TrasSTOP no se emitió ninguna intención nueva. Se esperó la terminación de
  peticiones y se conciliaron todas las intenciones, no sólo respuestas exitosas.
- Revisor independiente recalculó conteos/p95 desde diario y cotejó IDs y
  conciliación sin ejecutar HTTP ni acceder nuevamente a la base.

## Cambios QA y comprobaciones

`qa/op09r/manage_isolated.py`: entorno dedicado, limpieza de variables y guardas.
`seed.py`: cuentas/materiales/sesiones ficticias con namespace nuevo; preparación
rechaza repetición. `load.py`: diario previo a envío, guardas para cualquier
escritura, conciliación exacta y conservación de resultados fallidos.
`login_turn.py`: acceso válido por IP común, cierre de sesiones y cuotas intactas.
`test_recorder.py`: pruebas de registro concurrente, evidencia previa, no
sobrescritura, parada ante PATCH incierto y descuadre por ubicación aunque el
total del lote cuadre. README e informe explican límites y reproducción.

Las cinco comprobaciones iniciales del registrador pasaron, Ruff aprobado.
Se conservaron copias exactas de los scripts ejecutados con SHA256. Después del
ensayo se fortaleció el veredicto de login para exigir todas las identidades y
cierres, con regresión para HTTP200 sin token: no cambia el resultado fallido
real y **no se reejecutó el ensayo para sustituirlo**. El resultado final de las
comprobaciones QA está en las evidencias versionadas.

Preparación: un primer shell usó ruta relativa errónea y falló antes de escribir;
se corrigió al cwd de Django y se prepararon los70 ficticios. Ruff inicial
detectó importaciones de QA y se corrigieron antes del ensayo. No fueron errores
de aplicación ni se ocultaron como comprobaciones aprobadas. No se repitieron
suites generales backend/frontend: no hubo cambios de aplicación.

Al cierre se comprobó **cero sesiones nuevas abiertas**, se detuvieron únicamente
la API8229 y el nuevo PG55469; `postmaster.pid` ausente. Base ficticia/evidencias
conservadas. No se detuvieron servicios antiguos ni aplicaciones ajenas.

## Hallazgos y continuidad

| Prioridad | Estado | Evidencia y siguiente paso |
| --- | --- | --- |
| P1 H09-03 | Pendiente, reproducida limitación del host | RAM86% interrumpió10 y la guarda>85% interrumpió login. Disponer de recursos libres en entorno existente y servidor Linux representativo antes de repetir. No contratar ni cambiar el equipo automáticamente |
| P1 H09-02 | Pendiente, causa anterior no resuelta | Las tres respuestas inciertas a25 del primer OP09 no se reprodujeron ni descartaron: este corte no llegó a25. No atribuirlas a CCAA/red/Django sin nueva evidencia |
| P2 ingreso de turno | Incompleto | Sólo4/70 correctos; no certifica cuota ni70 accesos. Repetir con recursos disponibles sin desactivar protección |
| P2 instrumentación | Mejorada y probada en QA | UUID/intención previa, excepciones, ID y conciliación exacta ya disponibles; errores originales conservados |
| Entorno representativo | No disponible en este ensayo | Django Windows no certifica capacidad productiva; no afirmar «máximo10 usuarios» |

H09-01 firmas conserva su validación anterior; esta carga no modifica ese cierre.
Respaldo/restauración OP09 conserva evidencia local anterior y no se repitió.
No existe autorización para cambiar cuotas, reglas industriales, infraestructura
real, código productivo, fusionar ni desplegar. Próxima decisión: identificar un
entorno existente sin costo con recursos disponibles, o acordar cuándo liberar
el equipo; **no es necesario cambiar reglas de negocio para superar una guarda
del host**. No seguir repitiendo sobre este corte ni bajar el85%.

## AVANCE y EXPLICADOR

**AVANCE:** ejecución terminada por guarda, integridad aprobada, carga y entrada
de turno incompletas. Una revisión independiente; evidencias y trabajo QA en rama.

1. **PROBLEMA DETECTADO:** no se logró completar el tiempo ni los niveles de carga.
2. **CAUSA TÉCNICA:** memoria agregada del equipo excedió85%; servidor Linux no
   disponible. No se probó que la aplicación causara el consumo.
3. **EJEMPLO REAL DE OPERACIÓN:** usuarios ficticios operaron sin errores, pero el
   computador obligó a detener antes de completar diez minutos.
4. **SOLUCIÓN RECOMENDADA:** usar recursos libres existentes y servidor de pruebas
   representativo; mantener guardas y validar antes de cambiar políticas.
5. **TRABAJO REALIZADO POR LOS AGENTES:** coordinador preparó aislamiento y ejecutó;
   un QA preparó/revisó instrumentación y comprobó evidencias; sólo QA/docs.
6. **PRUEBAS Y RESULTADOS:** calentamiento aprobado,10 incompleto por RAM,304
   operaciones exactas,4/70 accesos;25/50/70/sostenida no ejecutados.
7. **ESTADO FINAL:** **BLOQUEADO PARA COMPLETAR VALIDACIÓN DE CARGA** por entorno;
   no aprobación global OP09 ni certificación de planta.
