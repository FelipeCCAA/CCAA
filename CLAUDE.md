# CLAUDE.md — CCAA (Gestión Productiva Planta)

Contexto para Claude Code. Lee estos documentos antes de proponer cambios:

- **`DECISIONES.md`** — decisiones de plataforma e infraestructura (PostgreSQL, bloqueo de la firma). Léelo: hay garantías que dependen del motor.
- **`prototipo/MODELO_DATOS.md`** — modelo funcional y decisiones de modelado (veredicto no persistido, especificaciones versionadas, recetas multinivel, checklist por plantilla). Es la referencia de diseño; respétala.
- **`docs/levantamiento-2026-07/LEVANTAMIENTO_PLANTA.md`** — levantamiento de los procesos reales de planta (HACCP/FSSC) y el **delta de modelo** a integrar (10 modelos nuevos, reglas, plan por archivo, mapeo a apps). **Empieza por aquí para la fase de integración.**
- **`docs/levantamiento-2026-07/SKU_PRODUCTOS.md`** — estructura del **SKU de producto** (12 dígitos, 6 segmentos) y el generador/validador para `maestros`. Distinto del código de lote de `produccion`: el SKU identifica un producto (maestro, estable) y el código de lote una corrida (transaccional). Lee también las salvedades de §4 y la nota de este archivo más abajo.
- **`docs/levantamiento-2026-07/BORRADOR_P0.md`** — código de arranque P0 (código de lote, ControlProceso/MonitoreoPPRO, siembra del Dossier). Ya aplicado; queda como referencia de lo que se pidió.

## Arquitectura

- **Backend:** Django REST + **PostgreSQL**. Apps: `maestros`, `recepcion`, `produccion`, `calidad`, `inocuidad`, `usuarios`. Cada app separa:
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
- **Código de lote** (vigente desde 2026-07-31): `CCAA` + último dígito del año + día juliano (3) + **SKU del producto** + `-` + correlativo del día (2) — p. ej. `CCAA6197LEP25-01`. El correlativo va **siempre**, desde `-01`: dos formas conviviendo obligan a conocer la excepción al leer, ordenar y buscar. Reemplaza al esquema del POE.009.02, donde el sufijo codificaba la torre (E1→1, E2→2) y el uso nacional (`N`); eso ahora vive dentro del SKU, que es donde se mantiene una sola vez.
- `codigo_lote_valido` **avisa, no restringe**: el histórico de planta trae códigos que no siguen el patrón —empezando por todos los del POE anterior— y hay que poder registrarlos. No conectarlo al `clean()` de `Lote`.
- **`Producto.codigo` está vacío en la base**, y es parte del código de lote: hasta que se cargue desde el admin, `codigo-sugerido/` devuelve `codigo: null` con su motivo y el operador escribe el código a mano.
- **SKU de producto** (`maestros/dominio.py` + `catalogos_sku.py`): 12 dígitos en 6 segmentos, compuestos **solo desde catálogos**. Un valor fuera de catálogo falla en vez de improvisar — un SKU con un segmento inventado se ve igual de válido que uno correcto y termina impreso en un saco. El orden de los segmentos se dedujo de los datos, no de los encabezados de la planilla, que están desalineados; `tests_dominio_sku.py` recompone los 24 productos reales del archivo y es lo que fija ese orden. `sku_valido` comprueba además la regla naturaleza↔cliente, para que el validador no apruebe lo que el generador se niega a componer.

## Trampas conocidas

- El catálogo de `DocumentoLiberacion` se siembra por **migración de datos**, así que también aparece en la base de **pruebas**. Cualquier prueba que arme su propio checklist debe limpiarlo primero (`DocumentoLiberacion.objects.all().delete()` en `setUp`), o medirá el avance contra documentos que no creó.
- El camino de la firma usa `select_for_update`; en SQLite eso **no hace nada** y la garantía desaparece en silencio. De ahí el check `calidad.E001`.
- `frontend/tsconfig.json` es de tipo **solución** (`files: []` + referencias), así que `npx tsc --noEmit` a secas **no comprueba nada** y sale con 0. Usa `npx tsc -b` (es lo que corre `npm run build`).
- El runner de pruebas **migra la base de pruebas solo**, así que una migración generada y no aplicada deja la suite entera en verde y revienta en el navegador con un `IntegrityError`. Después de `makemigrations`, correr `migrate`.
- Dentro de `transaction.atomic()`, **salir con `return` confirma la transacción**: solo una excepción revierte. Un `return Response(...)` de validación a mitad de un lote de escrituras deja media operación guardada.

## Tarea de integración en curso

Integrar el delta del levantamiento (`LEVANTAMIENTO_PLANTA.md` §2–§5) siguiendo el backlog
`docs/levantamiento-2026-07/Backlog_Mejoras_App_CCAA.md`.

**P0 aplicado** (2026-07-30): campo `area` en `DocumentoLiberacion`, siembra de los 19 registros
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

**Codificador de SKU** (2026-07-31): hecho el dominio puro —`maestros/catalogos_sku.py`,
`maestros/dominio.py`, `tests_dominio_sku.py`—. **El modelo no se tocó**: los campos de `Producto`
(`naturaleza_comercial`, `categoria`, `tipo`, `formato`, `mercado`, `sku`, `variante`) y el
`codigo_cliente` de `Mandante` dependen de decisiones abiertas, abajo.

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

**Decisiones abiertas antes de tocar el modelo:**

1. **El código de lote embebe el SKU, y el SKU real son 12 dígitos.** El formato se decidió con un
   mnemónico corto de ejemplo (`CCAA6197LEP25-01`, 16 caracteres); con el SKU real queda
   `CCAA6197010103010101-01` — **23 caracteres, 20 dígitos corridos**, para imprimir en un saco y
   transcribir a mano. El archivo ya trae dos códigos cortos por producto (`Cód. CeGe` 101–123,
   `Cód. Patricio R.` 5001–7004) que darían `CCAA6197101-01`. **Se resuelve antes de cargar SKU.**
2. El 7.º segmento de variante para unicidad (`SKU_PRODUCTOS.md` §4.1), después de aplicar el
   punto anterior sobre la categoría `11`.
3. Validar con negocio los 16 productos marcados «¿definido correctamente? = False».

**Lo siguiente, en este orden:**

1. Las dos **reglas de bloqueo** en `calidad/dominio.py`, con pruebas de regresión: una lectura de
   `ControlProceso` fuera del límite del PCC 1, o un `MonitoreoPPRO` con lecturas No-OK y sin
   acción correctiva, deben impedir liberar el lote. El dato ya está listo y probado
   (`MonitoreoPPRO.resuelto`).
2. Serializers, urls, admin y pantallas de captura de los modelos nuevos.
3. La `plantilla` de cada uno de los 19 documentos, contra su formato real. Hoy van como
   atestación, y eso es deliberado: una plantilla inventada se completa igual y da el documento
   por cumplido.

**Pendiente con Calidad:** los 19 se sembraron con `aplica_a = ["polvo"]`. Cuáles exigen además
crema o mantequilla sigue abierto (`MODELO_DATOS.md` §8.3) y se responde editando el catálogo,
no migrando.
