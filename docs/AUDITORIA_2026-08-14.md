# Auditoría técnica — CCAA

**Alcance:** rama `feature-inocuidadAseos`, commit `bb99ba5`. Despliegue objetivo
Ubuntu, 4 vCPU / 8 GB. Mismos parámetros que la auditoría de Codex, para poder
contrastarlas.

**Método:** lectura del código y **medición sobre la instalación**. Cada nota va
con la evidencia que la sostiene. Donde no pude medir, lo digo.

---

## 1. Resultado, contrastado con Codex

| Área | Codex | Esta | Δ | Por qué difiere |
|---|---|---|---|---|
| Aislamiento empresa/sucursal | 9.0 | **9.0** | = | Coincidimos |
| Configuración Django/HTTPS | 8.5 | **8.5** | = | Coincidimos |
| Autenticación y sesiones | 7.2 | **7.0** | −0.2 | El token vive en `localStorage` y no rota |
| Autorización de API | 8.5 | **8.5** | = | Coincidimos |
| Protección contra abuso/DoS | 5.0 | **5.5** | +0.5 | El login **sí** está defendido; el resto de la API no tiene ningún límite |
| Auditoría y trazabilidad | 7.0 | **6.0** | −1.0 | **Dos apps quedan sin auditar**, y una es la que decide el producto |
| Archivos adjuntos | 5.5 | **5.0** | −0.5 | `MEDIA_ROOT` está vacío: los archivos caen en el directorio del proceso |
| Dependencias / supply chain | 5.5 | **5.5** | = | Coincidimos |
| Rendimiento con pocos datos | 7.2 | **7.5** | +0.3 | Los `select_related` están bastante puestos |
| Rendimiento con muchos datos | 4.3 | **4.5** | +0.2 | Coincidimos en el fondo: nunca se ha medido con volumen |
| Observabilidad / recuperación | 4.5 | **3.5** | −1.0 | `LOGGING` está **literalmente vacío** |
| **Preparación para producción** | 5.8 | **5.5** | −0.3 | No liberaría: sin logs ni alarmas, un fallo se descubre por llamada telefónica |
| **Seguridad general** | 7.3 | **7.2** | −0.1 | Base sólida, coincidimos |
| **Rendimiento general** | 5.1 | **5.2** | +0.1 | Coincidimos |

**Coincido con el diagnóstico de fondo de Codex**: no hay vulnerabilidad crítica
confirmada —ni RCE, ni inyección SQL, ni acceso cruzado entre empresas— y lo que
falta es endurecimiento y operación, no arquitectura.

Donde discrepo es en el **detalle accionable**: cinco defectos concretos que la
tabla no refleja, y que son justamente los que se pueden arreglar mañana.

---

## 2. Lo que la tabla de Codex no refleja

### 🔴 A. `estandarizacion` y `recoleccion` no se auditan

`auditoria.registro.APPS_AUDITADAS` es una **lista blanca**. Medido:

```
auditadas:    calidad, inocuidad, inventario, maestros, mantenimiento,
              planificacion, procesos, produccion, recepcion, usuarios
SIN AUDITAR:  estandarizacion, recoleccion
```

`estandarizacion` es donde vive el **vale de RC**, la decisión que determina qué
producto sale. Si alguien corrige una grasa medida o cambia un volumen, **no
queda registro de quién ni cuándo**. Es exactamente el papel que pide una
auditoría FSSC, y es el que falta.

Y el mecanismo es silencioso: una app nueva no se audita y nada avisa.

**Coste:** dos líneas y una prueba que recorra `INSTALLED_APPS` y falle si alguna
app de negocio queda fuera — para que el próximo módulo no repita el olvido.

### 🔴 B. Solo el login tiene límite de peticiones

```
DEFAULT_THROTTLE_RATES:  login_ip, login_usuario, password_reset_*
DEFAULT_THROTTLE_CLASSES: no existe
```

El acceso está bien defendido —límite por IP y por cuenta, con `NUM_PROXIES`
correcto, registro de intentos y herramienta de desbloqueo—. Pero **el resto de
la API no tiene ningún límite**: una cuenta válida puede martillear cualquier
endpoint hasta tumbar los dos workers de Gunicorn.

Es el hueco más grande de la nota de DoS, y también el más barato de cerrar.

**Coste:** cuatro líneas de configuración.

### 🟠 C. `LOGGING = {}` — no hay registro de nada

Está vacío. Django cae a su comportamiento por omisión: los errores salen por
`stderr` y los recoge Docker con rotación. En la práctica eso significa que un
error 500 en producción deja **un stack trace suelto**, sin identificador de
petición, sin usuario, sin correlación — y nadie se entera hasta que alguien
llama por teléfono.

No hay Sentry, ni métricas, ni alarma sobre las ejecuciones de MRP que quedan en
`pendiente`.

**Coste:** un `LOGGING` estructurado son treinta líneas. Sentry, media hora.

### 🟠 D. `MEDIA_ROOT` está vacío

```
MEDIA_ROOT = ''    MEDIA_URL = '/'
upload_to = "abastecimiento/%Y/%m/"
```

Los adjuntos se escriben **relativos al directorio de trabajo del proceso**, que
dentro del contenedor no es un volumen. Al reconstruir la imagen, los archivos
subidos desaparecen.

La comprobación de contenido sí está bien hecha —lee la cabecera, rechaza HTML y
SVG por ejecutables, y no se fía de la extensión— pero se guarda en el sitio
equivocado.

**Coste:** una variable y un volumen en `compose.yml`.

### 🟡 E. La tabla de auditoría crece sin límite

No hay política de purga. Es además la tabla con más escrituras del sistema: el
registro cuesta **dos consultas por cada escritura** de las diez apps
auditadas. Con volumen de planta, es la primera candidata a dominar el tamaño de
la base y a ralentizar los backups.

**Coste:** un comando de purga con retención configurable, más el índice que ya
tiene.

---

## 3. Plan de acción

Ordenado por **puntos de nota por hora de trabajo**, no por gravedad.

### Fase 1 — Una tarde (sube ~1.5 puntos globales)

| # | Acción | Área | Efecto |
|---|---|---|---|
| 1 | `DEFAULT_THROTTLE_CLASSES` con tasas por usuario y anónimo | DoS | 5.5 → **7.0** |
| 2 | Añadir `estandarizacion` y `recoleccion` a `APPS_AUDITADAS` + prueba que recorra `INSTALLED_APPS` | Auditoría | 6.0 → **7.5** |
| 3 | `MEDIA_ROOT` explícito + volumen en compose | Adjuntos | 5.0 → **6.5** |
| 4 | `pip-audit` como paso de CI + Dependabot | Dependencias | 5.5 → **7.0** |
| 5 | Traer el arreglo de la prueba obsoleta desde `seguridad` | — | Deja la suite verde |

Los cinco son configuración o líneas sueltas. Ninguno toca reglas de negocio.

### Fase 2 — Dos o tres días (sube ~1 punto)

| # | Acción | Área | Efecto |
|---|---|---|---|
| 6 | `LOGGING` estructurado con identificador de petición y usuario | Observabilidad | 3.5 → **5.5** |
| 7 | Sentry o equivalente, con alarma de error rate | Observabilidad | → **7.0** |
| 8 | Comando de purga de auditoría con retención | Auditoría / Rendimiento | → **8.0** |
| 9 | Backup automatizado en cron **con restauración ensayada** | Recuperación | Un backup que nunca se restauró no es un backup |
| 10 | Rotación de token al renovar sesión, y sacarlo de `localStorage` a cookie `httpOnly` | Autenticación | 7.0 → **8.0** |

### Fase 3 — Una semana (la nota que más pesa)

| # | Acción | Área | Efecto |
|---|---|---|---|
| 11 | **Prueba de carga con volumen real**: 2 años de lotes, recepciones y auditoría | Rendimiento | 4.5 → medible |
| 12 | Índices guiados por esa prueba, no por intuición | Rendimiento | → **6.5** |
| 13 | PgBouncer + Redis para caché y throttling | Rendimiento / DoS | → **7.5** |
| 14 | Pentest externo | Seguridad | Lo que ninguna auditoría estática puede dar |

**El punto 11 es el que desbloquea los demás.** Hoy nadie sabe dónde se rompe:
la base de desarrollo tiene 6 recepciones y 1 lote. Poner índices antes de medir
es adivinar, y los índices que sobran también cuestan.

---

## 4. Lo que esta auditoría **no** puede decir

Por honestidad, y porque marca el límite de lo que ambas auditorías valen:

- **No se ejecutó un escaneo de CVE** sobre las dependencias. 12 de 15 están
  fijadas con versión exacta, pero no sé si alguna tiene un aviso abierto.
- **No hubo prueba de carga.** La nota de «rendimiento con muchos datos» es una
  lectura del código, no una medición.
- **No hubo pentest.** Ninguna auditoría estática puede afirmar que algo sea
  impenetrable, y esta tampoco.
- **No se auditó el frontend** más allá de la sesión: no revisé XSS en los
  formularios dinámicos, que es donde el sistema pinta JSON del servidor.

---

## 5. Lo que está genuinamente bien, y conviene no perder

Ambas auditorías coinciden en que la base es sólida. Vale la pena nombrar por qué:

- **El aislamiento entre empresas está probado, no supuesto.** Hay una prueba que
  recorre los 59 endpoints de escritura publicados y falla si alguno resuelve el
  tenant por su cuenta — más una comprobación estática que mira el código, porque
  la de comportamiento no alcanza a las acciones a medida.
- **La configuración de producción se valida al arrancar.** `validar_entorno_endurecido`
  impide levantar `production` con `DEBUG`, sin HTTPS o sin HSTS. No es un aviso
  en un README: el proceso no arranca.
- **La firma de liberación toma bloqueo de fila**, y hay un check que falla si el
  motor no lo soporta — porque en SQLite ese bloqueo no hace nada, en silencio.
- **Las reglas de inocuidad no admiten concesión.** Un PCC fuera de límite o un
  PPRO sin acción correctiva bloquean la liberación por una vía que no se puede
  saltar desde la interfaz.
- **985 pruebas**, muchas verificadas por mutación: se rompe la regla a propósito
  y se comprueba que alguna prueba lo detecta.

Eso es lo que separa «funciona» de «se puede sostener», y es la parte cara de
construir. Lo que falta —límites, logs, backups, medición— es trabajo conocido y
acotado.
