# CLAUDE.md — CCAA (Gestión Productiva Planta)

Contexto para Claude Code. Lee estos documentos antes de proponer cambios:

- **`DECISIONES.md`** — decisiones de plataforma e infraestructura (PostgreSQL, bloqueo de la firma). Léelo: hay garantías que dependen del motor.
- **`prototipo/MODELO_DATOS.md`** — modelo funcional y decisiones de modelado (veredicto no persistido, especificaciones versionadas, recetas multinivel, checklist por plantilla). Es la referencia de diseño; respétala.
- **`docs/levantamiento-2026-07/LEVANTAMIENTO_PLANTA.md`** — levantamiento de los procesos reales de planta (HACCP/FSSC) y el **delta de modelo** a integrar (10 modelos nuevos, reglas, plan por archivo, mapeo a apps). **Empieza por aquí para la fase de integración.**
- **`docs/levantamiento-2026-07/SKU_PRODUCTOS.md`** — estructura del **SKU de producto** (12 dígitos, 6 segmentos) y el generador/validador para `maestros`. Distinto del código de lote de `produccion`: el SKU identifica un producto (maestro, estable) y el código de lote una corrida (transaccional). Lee también las salvedades de §4 y la nota de este archivo más abajo.
- **`docs/levantamiento-2026-07/BORRADOR_P0.md`** — código de arranque P0 (código de lote, ControlProceso/MonitoreoPPRO, siembra del Dossier). Ya aplicado; queda como referencia de lo que se pidió.

## Arquitectura

- **Backend:** Django REST + **PostgreSQL**. Apps: `maestros`, `recepcion`, `produccion`, `calidad`, `inocuidad`, `planificacion`, `auditoria`, `usuarios`. Cada app separa:
  - `models.py` — esquema (usa **JSONField** para formularios dinámicos: `plantilla`, `valores`, `rangos`, `controles`).
  - `dominio.py` — reglas puras y testeables (sin ORM/DOM). Toda regla nueva se cubre en `tests_dominio.py`.
  - `views.py` — API; el camino de la **firma de liberación** usa `select_for_update` (no romper, ver `DECISIONES.md` §001).
  - `serializers.py`, `urls.py`, `admin.py`.
- **Frontend:** `frontend/src` (TypeScript): `pages/`, `components/`, `services/` (uno por módulo), `layouts/`.
- **`prototipo/`** — versión HTML/JS previa, archivada. Referencia histórica del modelo; no es el código vivo.

## Decisiones vigentes

- **PostgreSQL** es el motor (no SQLite en producción): protege el bloqueo de fila en la firma. Detalle en `DECISIONES.md` §001.
- Formularios dinámicos en **JSONField**; catálogos simples como `TextChoices`/`CHECK`; detalle repetitivo (lecturas horarias, etapas, muestras) como **modelo hijo con FK**.
- El veredicto de calidad y el avance del checklist **no se persisten**: se recalculan.
- Las decisiones (`puede_liberar` / `puede_despachar`) devuelven motivos de bloqueo, no un booleano.
- Español en UI, datos y comentarios. Fechas ISO `YYYY-MM-DD`. `codigo_lote` como string.
- El diseño manda: extender el modelo, no reescribirlo.
- **Dónde va cada registro:** `produccion` guarda **cómo se produjo** (lote, análisis, control de proceso — el PCC 1 vive ahí como un límite dentro del control). `inocuidad` guarda lo que **solo existe para vigilar un peligro**: PPRO, PCC de detector de metales, y más adelante limpieza CIP/COP, no conformidades y calibraciones. Mover modelos entre apps después obliga a renombrar tablas a mano, así que la separación se decidió con dos modelos y no con seis.
- **Código de lote** (vigente desde 2026-07-31): `CCAA` + último dígito del año + día juliano (3) + **SKU del producto** + `-` + correlativo del día (2) — p. ej. `CCAA6212010102010201-01`. El correlativo va **siempre**, desde `-01`: dos formas conviviendo obligan a conocer la excepción al leer, ordenar y buscar. Reemplaza al esquema del POE.009.02, donde el sufijo codificaba la torre (E1→1, E2→2) y el uso nacional (`N`); eso ahora vive dentro del SKU, que es donde se mantiene una sola vez.
- `codigo_lote_valido` **avisa, no restringe**: el histórico de planta trae códigos que no siguen el patrón —empezando por todos los del POE anterior— y hay que poder registrarlos. No conectarlo al `clean()` de `Lote`.
- **`Producto.codigo` guarda el SKU** y es parte del código de lote. Un producto sin él no frena nada: `codigo-sugerido/` devuelve `codigo: null` con un motivo que dice qué falta y dónde, y el operador escribe el código a mano. Se carga desde el admin, y conviene componerlo con `generar_sku` en vez de teclearlo.
- **SKU de producto** (`maestros/dominio.py` + `catalogos_sku.py`): 12 dígitos en 6 segmentos, compuestos **solo desde catálogos**. Un valor fuera de catálogo falla en vez de improvisar — un SKU con un segmento inventado se ve igual de válido que uno correcto y termina impreso en un saco. El orden de los segmentos se dedujo de los datos, no de los encabezados de la planilla, que están desalineados; `tests_dominio_sku.py` recompone los 24 productos reales del archivo y es lo que fija ese orden. `sku_valido` comprueba además la regla naturaleza↔cliente, para que el validador no apruebe lo que el generador se niega a componer.
- **Auditoría** (`auditoria`): se captura por señales, no desde las vistas, para cubrir todo lo que escribe en la base —API, admin, scripts, shell— y no solo los caminos instrumentados. Los dos lados del diff se leen **de la base** en `pre_save`/`post_save`: comparar la base contra el objeto en memoria marca como cambiados campos que solo cambiaron de tipo. Todos los cambios tienen la **misma forma** `{campo: [antes, después]}`, también las altas —con `None` delante—: dos formas obligan a cada consumidor a distinguirlas y el que no lo haga revienta. Es **de solo lectura en las tres capas** (viewset, admin y servicio del frontend): un registro que se puede editar no prueba nada.
- **Máquinas** (`maestros.Equipo`): `consume_leche` es una **regla del balance**, no una etiqueta. Un mismo código de producción se programa en el evaporador y en la línea que lo recibe; si ambos restaran, la semana contaría la misma leche dos veces. Solo los evaporadores.
- Los **catálogos de opciones** se sirven desde el backend (`/api/maestros/catalogos/`, `/api/planificacion/catalogos/`) y no se escriben en el frontend: una copia ofrece tarde o temprano un valor que el backend rechaza.

## Trampas conocidas

- El catálogo de `DocumentoLiberacion` se siembra por **migración de datos**, así que también aparece en la base de **pruebas**. Cualquier prueba que arme su propio checklist debe limpiarlo primero (`DocumentoLiberacion.objects.all().delete()` en `setUp`), o medirá el avance contra documentos que no creó.
- El camino de la firma usa `select_for_update`; en SQLite eso **no hace nada** y la garantía desaparece en silencio. De ahí el check `calidad.E001`.
- `frontend/tsconfig.json` es de tipo **solución** (`files: []` + referencias), así que `npx tsc --noEmit` a secas **no comprueba nada** y sale con 0. Usa `npx tsc -b` (es lo que corre `npm run build`).
- El runner de pruebas **migra la base de pruebas solo**, así que una migración generada y no aplicada deja la suite entera en verde y revienta en el navegador con un `IntegrityError`. Después de `makemigrations`, correr `migrate`.
- Las **migraciones de datos siembran también la base de pruebas** (documentos de liberación, equipos). Un `create()` en `setUp` choca con la unicidad: usar `update_or_create`.
- En una pantalla que carga varias fuentes con `Promise.all`, **un endpoint caído las vacía todas**. Los datos auxiliares —catálogos de desplegables— van aparte y degradan solos.
- Dentro de `transaction.atomic()`, **salir con `return` confirma la transacción**: solo una excepción revierte. Un `return Response(...)` de validación a mitad de un lote de escrituras deja media operación guardada.

## Tarea de integración en curso

Integrar el delta del levantamiento (`LEVANTAMIENTO_PLANTA.md` §2–§5) siguiendo el backlog
`docs/levantamiento-2026-07/Backlog_Mejoras_App_CCAA.md`.

**P0 aplicado** (2026-07-30): campo `area` en `DocumentoLiberacion`, siembra de los registros
del Dossier, `generar_codigo_lote` con sus pruebas, `ControlProceso`+`ControlProcesoLectura` con
el PCC 1, y la app `inocuidad` con `MonitoreoPPRO`+`PproLectura`.

**Ciclo de vida del lote** (cambiado el 2026-07-31): un lote **se abre al empezar la corrida**,
con su leche asignada y **sin kilos** — `kg_producidos` es nulable. Los kilos se declaran al
pasar a `producido`, que es cuando se saben; la regla vive en
`produccion.dominio.puede_declarar_producido`, no en el esquema, para que un lote histórico se
pueda cargar completo de una vez. La leche asignada **avisa pero no bloquea** ese paso: exigirla
detendría la producción del día por un dato completable, y endurecerlo es decisión de Calidad
sobre esa misma función. El código se propone con `codigo-sugerido/` y queda editable, por la
misma razón que `codigo_lote_valido` avisa y no restringe.

**Codificador de SKU** (2026-07-31): completo. Dominio puro en `maestros/catalogos_sku.py` +
`maestros/dominio.py`, y el maestro en `Producto` (`naturaleza_comercial`, `categoria`, `tipo`,
`formato`, `mercado`, `variante`) más `Mandante.codigo_cliente`.

**El SKU se deriva, no se teclea.** `Producto.save()` lo recalcula desde los atributos cada vez;
en el admin el campo es de solo lectura y al lado va «Cómo se lee el SKU», que lo descompone de
vuelta. Dejarlo escribible invitaría a teclear un código que contradiga los atributos del mismo
producto — que es exactamente el defecto que trae el archivo de origen (§4.2). Un producto sin los
atributos cargados conserva el código que tenga: el histórico está lleno de códigos a mano.

**Dónde se crea un producto:** pantalla **Maestros** (`/maestros`), pestaña Productos — o el admin
de Django. El mandante necesita su `codigo_cliente` cargado o sus productos no generan SKU.

**Maestros** cubre seis pestañas: productos, mandantes, máquinas, silos, camiones y códigos de
producción. Los tres últimos comparten `FormularioMaestro`, un formulario descrito por datos; los
tres primeros tienen el suyo porque muestran reglas propias (el SKU derivado, el cliente que
aporta el mandante, la advertencia del balance). Faltan **especificaciones**, **documentos de
liberación** y **recetas**: sus formularios son plantillas JSON y quien decide sobre ellos es
Calidad, así que siguen en el admin.

**Auditoría** vive en `/auditoria`, visible para todos los roles.

**Inocuidad aplicada** (2026-07-31): las dos reglas de bloqueo están y funcionan de punta a punta.
Una lectura fuera del límite del **PCC 1** de uperización, o un **PPRO** con lecturas No-OK sin
acción correctiva, impiden liberar el lote — y **no admiten concesión**: una concesión asume un
riesgo conocido y medido sobre la calidad, y aquí lo que falló es la barrera que hace seguro el
producto. El mecanismo no es una rama aparte: sus motivos entran en `bloqueos` y eso ya anula las
dos vías; si alguien los saca de esa lista, tiene que reponer la exclusión a mano.

Los límites del PCC viven **en cada `ControlProceso`** y no en un maestro: cambian por equipo —VEB
80,0 °C / 14.175 kg·h; Scheffers 2 81,2 °C / 17.100— y un control de mayo se audita contra el
límite que regía en mayo. Las claves que el PCC vigila dentro de `valores` (`t_dsi`,
`flujo_entrada`) se sirven en `/api/produccion/catalogos-inocuidad/` para que la pantalla las
rotule igual que el dominio las evalúa: si divergieran, el PCC dejaría de vigilar en silencio.

La captura está en el **panel de inocuidad de la ficha del lote**.

**Documentos que cumple el propio dato** (2026-07-31). Once de los diecinueve registros del
Dossier son datos que la aplicación ya captura, y pedir además una casilla es doble digitación —
peor aún: la casilla puede decir «cumplido» sobre un PCC 1 incumplido.
`DocumentoLiberacion.evidencia` declara qué registro lo cumple, y
`calidad.dominio.documentos_con_evidencia` lo resuelve.

**Solo cinco están atados**, y es deliberado: un documento cumplido *de más* deja salir producto.
Los seis restantes dependen del equipo donde se registró, y `MonitoreoPPRO.equipo` todavía es
texto libre — un monitoreo de cuerpos extraños daría por cumplidos los tres checklists
(evaporadores, E1-E2, Rovema) cuando solo se hizo uno. Para habilitarlos hace falta que ese campo
referencie el maestro de equipos (el mismo cambio que se hizo con `BloquePlan`), y que el maestro
tenga las Rovemas y las torres E1/E2.

| Documento | Lo cumple |
|---|---|
| `CCAA.REC.FORM.005` Trazabilidad | la asignación de silos del lote |
| `CCAA.Cond.FORM.010` PCC 1 | un `ControlProceso` en VEB, SCH2 o SCH3 |
| `CCAA.Sec.FORM.025` Pulverización | un `ControlProceso` en E1 o E2 |
| `CCAA.Sec.FORM.001` Fisicoquímico | un `Analisis` del lote |
| `CCAA.ENV.FORM.001` Detector de metales | un `MonitoreoPPRO` de ese tipo |

El expediente **distingue** el cumplimiento por dato del visto manual: no es lo mismo «hay control
de proceso» que «alguien lo marcó».

**El checklist tiene 21 documentos, no 19.** El Dossier lista el checklist de cuerpos extraños
como un solo registro (`Cond.FORM.005/014/016`), pero en planta son tres formatos con **piezas
distintas**: el Scheffers 2 tiene pulmones y coil, el Scheffers 3 tapas por efecto, y el VEB
cuatro efectos. Una plantilla única pediría el estado de piezas que ese evaporador no tiene, y el
checklist se marcaría igual sin decir qué se revisó.

**Plantillas cargadas** (desde `Documentos Planta/`, no inventadas): los cuatro checklists de
cuerpos extraños —Scheffers 2, Scheffers 3, VEB y Rovemas 3-4—. `maestros.tests` exige que solo
tengan plantilla los documentos declarados en `PLANTILLAS_DE_UN_FORMATO_REAL` junto a su formato
de origen: agregar una obliga a decir de dónde salió.

Dos documentos **no deberían llevar plantilla nunca**: el PPRO E1-E2 (`Sec.FORM.022`) son lecturas
horarias OK/No-OK de tres tipos que `MonitoreoPPRO` ya modela, y la dosificación de lecitina son
lecturas horarias, o sea `ControlProcesoLectura`. Darles formulario sería volver a teclear lo que
el modelo captura.

**Ojo con el tipo `lista`**: está en el contrato de la plantilla pero `FormularioDinamico` no lo
dibuja — cae al campo de texto por defecto, sin avisar. Hay una prueba que impide usarlo hasta que
se implemente.

**Los registros que no son por lote viven en el equipo y su período** (2026-07-31). En el catálogo
de planta **solo 12 de 204 documentos son por lote**; el resto son aseos por ciclo, monitoreos por
turno y programas. `DocumentoLiberacion.frecuencia` decide dónde vive el dato, y `RegistroEquipo`
—hermano de `RegistroCalidad`, mismo contrato de plantilla— cuelga del equipo y su fecha. El
checklist del lote lo **consume**: un aseo semanal se llena una vez y cubre todos los lotes de esa
semana.

La ventana se deduce de la frecuencia y **no se guarda**: un `vigente_hasta` almacenado se
desincroniza al corregir la fecha del registro, y un lote quedaría cubierto por un aseo que ya no
lo alcanza. La excepción es `segun_programa`, sin período deducible: ahí el registro declara su
vigencia y sin ella **no cubre nada**.

La captura vive en **`/registros`**, organizada por equipo y fecha — quien asea una torre no
piensa en lotes. Los campos los dibuja `components/CampoDePlantilla`, el mismo componente que el
expediente: un solo renderizador para un solo contrato.

**Las frecuencias se cargan solo cuando el formato las declara.** El catálogo del levantamiento
tiene una columna de frecuencia que **no coincide** con los formularios: clasifica los checklists
de cuerpos extraños como «Según programa» mientras el formato dice «Al inicio del ciclo de
producción». Manda el formato. El resto se queda en `por_lote`, que además es el valor seguro:
pasarse de frecuencia solo molesta, quedarse corto deja que un registro cubra lotes que nunca
revisó.

La pantalla cubre productos, mandantes y silos (estos últimos de solo lectura: su ocupación es un
saldo del libro de movimientos, y un formulario invitaría a «corregirlo» escribiéndolo). Las
**especificaciones** y el **catálogo de documentos** siguen en el admin: sus formularios son JSON
y quien decide sobre ellos es Calidad, no Administración.

Los catálogos de los desplegables se sirven en `/api/maestros/catalogos-sku/` en vez de escribirse
en el frontend, y el SKU **no se previsualiza en el cliente**: reproducir el generador allí crea
una segunda implementación que puede diferir de la que manda, justo en el dato que se imprime en
el saco. Lo que sí se anticipa es qué falta para poder componerlo.

**Salvedades sobre `SKU_PRODUCTOS.md`** (verificadas contra el Excel fuente):

- §4.2 concluye que el generador «corrige automáticamente» las filas mal codificadas. **No las
  corrige.** *Leche Entera Estándar 28% NE* trae la **columna Categoría = "Crema"**, no solo el
  SKU; el generador compone desde atributos, así que de un atributo malo sale el mismo SKU malo.
  Hay que arreglar el dato.
- §4.2 sospecha de *Leche Entera Instantánea 27% CN*: está bien, es Colun (`02`). Sin acción.
- §4.1 atribuye las colisiones a falta de estructura. **Parte es carga inconsistente:** la
  categoría `11` «Leche en Polvo c/Lec» ya existe y uno de los tres productos c/LdS la usa; los
  otros dos van como `02`. Antes de agregar un 7.º segmento, ver cuántas colisiones desaparecen
  al aplicar la `11` donde corresponde.
- §4.3 dice 17 productos sin validar; en la hoja son **16**.
- §7 da `Receta` por «pendiente de portar del prototipo»: **ya está** (`maestros/recetas.py`, con
  explosión multinivel y pruebas). Lo que sigue vigente de §7 es que las hojas de recetas del
  mismo Excel son la BOM por 100 kg y pueden sembrarla.

**Resuelto (2026-07-31): el código de lote lleva el SKU completo de 12 dígitos**, o sea 23
caracteres —`CCAA6212010102010201-01`—. Se planteó la alternativa de un código corto por producto
(el Excel trae `Cód. CeGe` 101–123 y `Cód. Patricio R.` 5001–7004, que darían `CCAA6197101-01`) y
se descartó a favor de que el código cargue toda la información del producto. Si en planta el
largo resulta impracticable al imprimirlo o transcribirlo, el cambio es de una línea en
`generar_codigo_lote` — pero invalida los códigos ya emitidos.

**SKU cargados** (2026-07-31), compuestos con `generar_sku` y no a mano:

| Producto | Mandante | SKU |
|---|---|---|
| Crema | CCAA | `020004010101` |
| Leche entera en polvo | Nestlé | `010102010201` |

El segundo **no** es el del archivo (`010104010201`): ese codifica Categoría = Crema y es la fila
mal codificada de §4.2. Se cargó el correcto. Si aparecen más productos, componerlos igual y no
copiarlos crudos del Excel.

**Decisiones abiertas antes de tocar el modelo:**

1. El 7.º segmento de variante para unicidad (`SKU_PRODUCTOS.md` §4.1), después de aplicar lo de
   la categoría `11`.
2. Validar con negocio los 16 productos marcados «¿definido correctamente? = False».

**Lo siguiente, en este orden:**

1. La `plantilla` de los documentos que siguen siendo manuales, contra su **formato real**. Los
   archivos están en `Documentos Planta/` (ignorada por git: 1,8 GB y no todo es de producción).
   Inventarlas es el error que hay que evitar: una plantilla inventada se completa igual y da el
   documento por cumplido.
2. Habilitar la evidencia de los seis documentos que hoy no se pueden atar — ver abajo.
3. Las tres pestañas que faltan en Maestros: especificaciones, documentos de liberación y recetas.
4. Cargar el maestro de productos completo (hoy hay 3 de los 23 del Excel) y resolver las
   decisiones abiertas del SKU.

**Pendiente con Calidad:** los 19 se sembraron con `aplica_a = ["polvo"]`. Cuáles exigen además
crema o mantequilla sigue abierto (`MODELO_DATOS.md` §8.3) y se responde editando el catálogo,
no migrando.
