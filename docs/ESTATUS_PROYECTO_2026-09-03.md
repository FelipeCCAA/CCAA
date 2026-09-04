# Estatus del proyecto · rama `DevelopMain`

**Fecha:** 2026-09-03 · **Commit:** `ce09c91` · **Base de comparación:** `main` (`508867d`, 2026-08-17).

Cada afirmación de este documento se sostiene en algo que se ejecutó o se leyó en el
código de esta rama, y dice dónde. Donde no se pudo medir, lo dice.

Es la foto de situación vigente. `docs/FLUJO_DEL_SISTEMA.md` (verificado el 2026-08-27) y
`docs/AUDITORIA_2026-08-14.md` siguen siendo válidos en su detalle, pero han quedado atrás
en varios puntos — abajo se marca cuáles.

---

## 1. Dónde está la rama

| | |
|---|---|
| Commits sobre `main` | **133**, del 2026-08-14 al 2026-09-03 |
| Commits de `main` que faltan aquí | **0** — `DevelopMain` contiene `main` entero; técnicamente el merge sería avance rápido, pero ver §4.0 |
| Sincronía con `origin/DevelopMain` | **al día** (`0 0` en `rev-list --left-right --count`) |
| Backend | 237 archivos, +25.249 / −1.639 |
| Frontend (`src`, `tests`, `e2e`) | 138 archivos, +11.950 / −1.645 |
| Documentación | 41 archivos, +41.085 |
| `graphify-out/` | 380 archivos, +420.139 líneas — generados, y `.gitignore` dice que no se versionan (§6) |

`main` lleva 17 días sin recibir nada. Todo el trabajo de tres semanas —descremación,
mantequilla, secado, rutas de producto, permisos por etapa, inventario— vive solo en esta
rama.

---

## 2. Lo que se verificó ejecutando

| Control | Resultado |
|---|---|
| `manage.py makemigrations --check --dry-run` | **Sin cambios pendientes.** No hay migración generada y no aplicada |
| `npx tsc -b` (frontend) | **Limpio**, código de salida 0 |
| `node --test tests/*.test.ts` | **21 de 21 en verde** |
| `manage.py test` (backend, PostgreSQL, `DJANGO_ENV=test`) | 🔴 **1.320 pruebas, 48 fallos + 43 errores, 5 omitidas** (664 s) |

El backend está en rojo. Es lo más importante de esta foto y tiene su ficha en §4.0.

**Aviso vivo en cada arranque:** `usuarios.W001` — dos perfiles con área fuera del
catálogo (`admin` → «Sistemas», `jsepulveda` → «Gestion TI»). No es cosmético: los avisos
por área se reparten con `PerfilUsuario.area`, así que esos perfiles no reciben ninguna
notificación de planta ni obtienen los permisos del área. Es el hueco 4 de
`FLUJO_DEL_SISTEMA.md`, todavía abierto y todavía siendo un problema de **dato**, no de
código.

**Nota de operación:** `manage.py test --parallel` se cae en este equipo con
`TypeError: cannot pickle 'traceback' object`, y al caerse deja bases `test_ccaa_N`
huérfanas que hacen fallar el siguiente arranque con «la base está siendo utilizada por
otros usuarios». Correr en serie, con `--noinput`.

---

## 3. Lo que se cerró desde la foto del 2026-08-27

Cuatro de los seis huecos que `FLUJO_DEL_SISTEMA.md` da por abiertos ya no lo están. Ese
documento necesita una pasada (§6).

- **🔴 Hueco 1 — «un silo en aseo puede recibir leche»: cerrado.**
  `recepcion.dominio.motivos_silo_no_disponible` (línea 698) consulta el `ciclo_cip`, y se
  **aplica**, no solo se muestra: `descargar` responde 409 con los motivos, y
  `estandarizacion/servicios.py:68` más cuatro puntos de `procesos/servicios.py` (863,
  1074, 1140, 1254) lo exigen antes de consumir un silo.

- **🟠 Hueco 3 — «la descremación no está modelada»: cerrado.**
  Existe `procesos.CorridaDescremacion` (`models.py:290`) con su servicio completo
  —`crear_corrida_descremacion`, `iniciar_descremacion`, `cerrar_descremacion`—, sus
  pruebas (`tests_descremacion.py`) y sus pantallas (`FormularioDescremacion.tsx`,
  `CierreDescremacion.tsx`). El TK de descremada ya no se carga con un ajuste manual.

- **🟠 Hueco 2 — «cinco de siete etapas no registran ejecución»: en gran parte cerrado.**
  Además de estandarización y secado, hoy tienen corrida propia condensación
  (`CorridaCondensacion`), descremación y mantequilla (`CorridaMantequilla`). Quedan
  recepción y envasado.

- **🟡 Hueco 6 — «la sesión caducada no manda al login»: cerrado.**
  `frontend/src/services/api.ts:80` redirige a `/#/login`, que es la ruta real del
  `HashRouter`.

- **Auditoría de `estandarizacion`: cerrada.** El hallazgo A de `AUDITORIA_2026-08-14.md`
  señalaba dos apps de negocio fuera de la lista blanca. `estandarizacion` ya está en
  `auditoria.registro.APPS_AUDITADAS` (línea 32) — o sea que el vale de RC, la decisión
  que determina qué producto sale, ya deja rastro de quién lo tocó.

También creció la plataforma: la rama trae **seis apps que `CLAUDE.md` todavía no
menciona** (`recoleccion`, `estandarizacion`, `inventario`, `observabilidad`, `procesos`,
`mantenimiento`), 84 rutas registradas, 108 acciones `@action`, 156 migraciones y 116
archivos de pruebas con del orden de 1.300 casos.

---

## 4. Lo que sigue abierto

Ordenado por lo que costaría que se materializara, no por esfuerzo. Todo verificado hoy
contra el código de esta rama.

### 🔴 0. La suite de pruebas del backend está en rojo, y CI no lo ve

**91 de 1.320 pruebas fallan** (48 fallos, 43 errores). Se reproducen **aisladamente** —
`manage.py test produccion.tests_apertura.ConsumoDeInventarioTests` falla 4 de 5 por sí
sola—, así que no es contaminación entre pruebas ni un problema de este equipo.

Reparto por app:

| App | Fallos + errores |
|---|---|
| `estandarizacion` | 26 |
| `produccion` | 24 |
| `recepcion` | 12 |
| `usuarios` | 11 |
| `mantenimiento` | 8 |
| `procesos` | 6 |
| `auditoria` · `maestros` · `inventario` | 2 · 1 · 1 |

Es exactamente donde aterrizó el trabajo de las últimas tres semanas.

**Por qué nadie se enteró:** `.github/workflows/ci.yml` se dispara con `push` a `main` y
con `pull_request`. `DevelopMain` recibió 133 commits sin pasar por ninguno de los dos, y
`main` no se toca desde el 2026-08-17. La rama donde se trabaja es la única sin control de
integración.

**Qué se ve en las trazas** (sin haber hecho el diagnóstico, que es tarea aparte):

- En `estandarizacion` el grupo más grande falla en el montaje, no en lo que mide:
  `servicios.transferir` corta con «El silo no tiene un análisis confirmado vigente» —la
  regla que entró el 2026-08-19—, y las pruebas construyen su vale sin ese análisis.
- En `mantenimiento` varias esperan 400 y reciben **404**, que huele a un cambio de alcance
  o de permisos, no a la validación que la prueba apunta.
- En `produccion`, `test_sin_stock_el_lote_igual_se_declara_y_avisa` espera 200 y recibe
  **400**. Eso **contradice una decisión escrita** —«declarar el lote producido descuenta
  su material, y no bloquea»—, así que aquí hay que decidir cuál de los dos lados tiene
  razón antes de tocar nada: si manda la prueba, hay una regresión en producción; si manda
  el código, la decisión cambió sin que el documento se enterara.

Mientras esto siga así, **ninguna de las garantías que la suite protege está siendo
verificada**, incluidas las que este mismo documento cita como resueltas.

### 🔴 1. Un despacho a granel no descuenta el silo

`inventario.servicios.ejecutar_despacho` (línea 199) valida la liberación de Calidad y el
destino de cada `SalidaProceso`, cambia el estado a `DESPACHADO` y termina. **No crea
ningún `MovimientoSilo` de salida.** El saldo del silo sigue mostrando el producto que ya
salió de la planta, y ese mismo volumen puede volver a consumirse en Producción.

Es el hallazgo crítico de `docs/auditorias/auditoria-cuatro-flujos-productivos.md`
(2026-09-03) y sigue tal cual. Rompe la garantía central del modelo —«la ocupación del
silo es un saldo del libro, nunca un campo»— justo en el punto donde el libro debería
cerrarse.

### 🔴 2. El flujo de crema para despacho no se puede completar

`SalidaProceso.destinos_permitidos()` no admite `despacho_directo` para una salida de
descremado, y en la base no hay ninguna ruta activa para los dos productos de crema (16
rutas activas: polvo, precondensado y mantequilla). La crema se produce, se analiza y se
libera — y ahí se detiene.

### 🟠 3. La pantalla ofrece lo que el backend va a rechazar

Dos casos del patrón que ya está descrito en `CLAUDE.md`, ambos vigentes:

- **Silos bloqueados por Calidad como destino del concentrado.** `procesos/views.py:196`
  filtra `Silo.objects.filter(activo=True)` y **no mira `estado`**: escribe «Bloqueado por
  Calidad» en la etiqueta de la opción pero la deja elegible. El rechazo llega al cerrar la
  corrida, con el evaporador ya trabajado.
- **Máquinas ocupadas por lotes anulados.** Anular un lote no cierra su `EjecucionProceso`:
  nada en `produccion/serializers.py` ni en `produccion/views.py` toca la ejecución cuando
  el estado pasa a `anulado`, y `ESTADOS_QUE_OCUPAN_EQUIPO` la sigue contando. Tres
  corridas abandonadas dejan la planta sin evaporadores, y el único síntoma es «Máquina
  ocupada por otra corrida» sobre una máquina que nadie usa.

### 🟠 4. Envasado está fijo en 25 kg

`frontend/src/pages/Produccion/FormularioEnvase.tsx` fija formato 25 kg, máximo 20 sacos y
total 500 kg. Sirve para leche en polvo; la mantequilla se envasa en cajas de 20 kg, así
que su flujo **no puede terminarse desde la interfaz**. El formato tiene que venir del
backend y validarse contra el producto.

### 🟠 5. Crema y precondensado están clasificados como producto terminado

La carga inicial (`maestros/management/commands/cargar_productos.py`) los deja como
`terminado`, y la bandeja de Envasado lista todos los lotes terminados. Resultado: el
operador ve crema y precondensado en una bandeja donde el POST los va a rechazar. La
posibilidad de despachar debería decidirla la ruta y la liberación, no la clasificación del
maestro.

### 🟠 6. `RutaProducto.destino` es texto libre

El servicio decide el comportamiento buscando las palabras «despacho» o «inventario».
Cambiar la redacción del maestro cambia la regla operacional, en silencio. Debe pasar a un
valor estructurado (`siguiente_proceso` · `envasado` · `despacho_directo` · `inventario`).

### 🟡 7. Dos puertas de Calidad sin separar

Al cerrar Secado o Mantequilla el lote entra a la bandeja de liberación comercial aunque
todavía no exista ningún envase ni pallet. La liberación comercial debería exigir el cierre
de Envasado cuando el formato lo pida; si no, los pallets creados después quedan pendientes
otra vez.

### 🟡 8. La API no tiene límite de tráfico salvo el login

`DEFAULT_THROTTLE_RATES` (`config/settings.py:366`) solo define `login_ip` (60/hora) y
`login_usuario` (15/hora). El resto de la API no tiene ningún límite. Hallazgo de
`AUDITORIA_2026-08-14.md`, sin cambios.

### 🟡 9. `MEDIA_ROOT` sigue sin definirse

No aparece en `config/`. `inventario/models.py:739` tiene un `FileField` con
`upload_to="abastecimiento/%Y/%m/"`, así que los adjuntos caen en el directorio de trabajo
del proceso. Hallazgo de `AUDITORIA_2026-08-14.md`, sin cambios.

### 🟡 10. `recoleccion` sigue sin auditarse

`auditoria.registro.APPS_AUDITADAS` incorporó `estandarizacion` pero no `recoleccion`. El
mecanismo sigue siendo silencioso: una app que no está en la lista blanca no se audita y
nada avisa. Falta la prueba que recorra `INSTALLED_APPS` y falle si una app de negocio
queda fuera — que es lo que impediría que el próximo módulo repita el olvido.

### 🟡 11. La trazabilidad no llega del saco al camión

`MovimientoSilo` guarda el vínculo (`origen_tipo` + `origen_id`) pero
`procesos/servicios.py::genealogia_lote` no lo expone. Cruzar un lote con sus recepciones
sigue siendo trabajo a mano — que es justo lo que se pide en un retiro de producto.

---

## 5. Lo que espera una decisión, no código

No son deudas técnicas: el mecanismo está construido y falta la respuesta.

| Decisión | Quién responde | Dónde se aplica |
|---|---|---|
| Cuatro pares de productos comparten SKU: ¿duplicados del archivo o productos distintos? | Negocio | `Producto.variante` ya lo admite; el SKU pasaría a 14 dígitos |
| 16 productos marcados «¿definido correctamente? = False» | Negocio | Maestro de productos |
| `Sec.FORM.024`: ¿checklist de inicio + lecturas horarias, o un `MonitoreoPPRO` con más tipos? | Calidad | `DocumentoLiberacion` |
| ¿Un análisis de silo vencido **impide** crear el vale, o solo avisa? | Calidad | `recepcion.AnalisisSilo` |
| ¿`ControlInhibidores` positivo debe bloquear el cierre por sí mismo? | Calidad | `recepcion.dominio.bloqueos_de_cierre` |
| Cuáles de los 19 documentos del Dossier aplican a crema y mantequilla | Calidad | Se edita el catálogo, no se migra |

---

## 6. Documentación que ya no describe el terreno

Un mapa desactualizado es peor que no tener mapa, porque se sigue. Estos tres tienen
afirmaciones que hoy son falsas:

- **`CLAUDE.md` § Arquitectura** lista 8 apps (`maestros`, `recepcion`, `produccion`,
  `calidad`, `inocuidad`, `planificacion`, `auditoria`, `usuarios`). En `INSTALLED_APPS`
  hay **14**: faltan `recoleccion`, `estandarizacion`, `inventario`, `observabilidad`,
  `procesos` y `mantenimiento`. `procesos` es hoy el corazón del flujo productivo y no
  aparece.
- **`docs/FLUJO_DEL_SISTEMA.md`** da por abiertos los huecos 1, 3 y 6, que están cerrados
  (§3), y el 2 solo parcialmente vigente. Su propio encabezado pide cambiar cuando cambien
  las reglas.
- **`docs/AUDITORIA_2026-08-14.md`** sigue contando `estandarizacion` entre las apps sin
  auditar. Ya lo está.

Además, **`graphify-out/` está versionado pese a estar en `.gitignore`** (línea 30, con el
comentario «No se versiona»): 380 archivos, 39 MB, 420.139 líneas de salida generada que
son el 83 % del diff contra `main`. Entraron antes de la regla de ignorado. Un
`git rm -r --cached graphify-out/` los saca del índice sin borrarlos del disco.

---

## 7. Lo siguiente, en este orden

1. **Poner la suite en verde** (§4.0), grupo por grupo, decidiendo en cada uno si manda la
   prueba o el código. Va primero porque es lo que dice si todo lo demás de esta lista se
   arregló de verdad.
2. **Disparar CI también en `DevelopMain`** (`push` a la rama, no solo a `main`). Un solo
   renglón en `ci.yml`, y es lo que impide que esto se repita.
3. **Cerrar el despacho a granel** (§4.1). Es el único hallazgo que deja el saldo de un
   silo mintiendo, y ese saldo alimenta la decisión de qué se produce mañana.
4. **Deshabilitar en las pantallas lo que el backend va a rechazar** (§4.3): silos
   bloqueados y máquinas ocupadas por lotes anulados. Barato, y cada caso hoy cuesta una
   corrida.
5. **Formato de envase desde el backend** (§4.4) — sin esto la mantequilla no termina.
6. **Ruta y destino de despacho para crema** (§4.2), junto con `RutaProducto.destino`
   estructurado (§4.6): es la misma pieza mirada desde dos lados.
7. **Reclasificar crema y precondensado a intermedio** (§4.5).
8. **Poner al día `CLAUDE.md` y `FLUJO_DEL_SISTEMA.md`** (§6) y sacar `graphify-out/` del
   índice.
9. **Asignar áreas reales a los perfiles** (`usuarios.W001`): es un dato, y desbloquea
   todas las notificaciones de planta.
10. **`recoleccion` en `APPS_AUDITADAS`, con la prueba que recorre `INSTALLED_APPS`**
    (§4.10) — sin la prueba, se vuelve a olvidar.

**No merge a `main` hasta el punto 1.** Hoy sería un avance rápido de 133 commits con la
suite en rojo.

Nada de esto exige resolver antes lo de §5: el sistema parte en blanco, así que una
decisión de modelado que resulte mal todavía se corrige sin migración ni reimpresión.
