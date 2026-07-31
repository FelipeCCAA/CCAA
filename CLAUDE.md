# CLAUDE.md — CCAA (Gestión Productiva Planta)

Contexto para Claude Code. Lee estos documentos antes de proponer cambios:

- **`DECISIONES.md`** — decisiones de plataforma e infraestructura (PostgreSQL, bloqueo de la firma). Léelo: hay garantías que dependen del motor.
- **`prototipo/MODELO_DATOS.md`** — modelo funcional y decisiones de modelado (veredicto no persistido, especificaciones versionadas, recetas multinivel, checklist por plantilla). Es la referencia de diseño; respétala.
- **`docs/levantamiento-2026-07/LEVANTAMIENTO_PLANTA.md`** — levantamiento de los procesos reales de planta (HACCP/FSSC) y el **delta de modelo** a integrar (10 modelos nuevos, reglas, plan por archivo, mapeo a apps). **Empieza por aquí para la fase de integración.**

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
- `codigo_lote_valido` (POE.009.02) **avisa, no restringe**: el histórico de planta trae códigos que no siguen el patrón y hay que poder registrarlos. No conectarlo al `clean()` de `Lote`.

## Trampas conocidas

- El catálogo de `DocumentoLiberacion` se siembra por **migración de datos**, así que también aparece en la base de **pruebas**. Cualquier prueba que arme su propio checklist debe limpiarlo primero (`DocumentoLiberacion.objects.all().delete()` en `setUp`), o medirá el avance contra documentos que no creó.
- El camino de la firma usa `select_for_update`; en SQLite eso **no hace nada** y la garantía desaparece en silencio. De ahí el check `calidad.E001`.

## Tarea de integración en curso

Integrar el delta del levantamiento (`LEVANTAMIENTO_PLANTA.md` §2–§5) siguiendo el backlog
`docs/levantamiento-2026-07/Backlog_Mejoras_App_CCAA.md`.

**P0 aplicado** (2026-07-30): campo `area` en `DocumentoLiberacion`, siembra de los 19 registros
del Dossier, `generar_codigo_lote` con sus pruebas, `ControlProceso`+`ControlProcesoLectura` con
el PCC 1, y la app `inocuidad` con `MonitoreoPPRO`+`PproLectura`.

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
