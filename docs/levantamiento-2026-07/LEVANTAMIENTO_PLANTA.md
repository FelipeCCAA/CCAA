# Levantamiento de procesos de planta → integración al backend

> Documento de contexto para Claude Code. Resume el levantamiento de la carpeta
> `Documentos Planta` (Sistema de Aseguramiento de Calidad, HACCP / FSSC 22000) y define
> **qué modelos y reglas agregar** al backend Django actual.
> Léelo junto con `prototipo/MODELO_DATOS.md` (decisiones de modelado) y `DECISIONES.md` (plataforma).
> **Fecha:** 2026-07-30.

---

## 0. Cómo usar este documento

1. El backend es **Django REST + PostgreSQL** (ver `DECISIONES.md` §001). Cada app tiene
   `models.py` (esquema), `dominio.py` (reglas puras, testeables), `views.py` (API + firma con
   `select_for_update`), `serializers.py`, `urls.py`, `admin.py` y `tests_dominio.py`.
2. **No reescribir el diseño**: extenderlo. Este doc define el *qué* y el *por qué*; los campos
   exactos se declaran en el `models.py` de cada app.
3. Todo lo que sigue proviene de **formatos reales en uso** (`CCAA.<Área>.<Tipo>.<n>.<v>`).
   Catálogo completo: `docs/levantamiento-2026-07/Catalogo_Formatos_Procesos_CCAA.xlsx`.
   Mapa visual (flujo + Dossier + modelo): `Modelo_Datos_Flujo_CCAA.html`.
   Plan priorizado: `Backlog_Mejoras_App_CCAA.md` (donde dice «esquema.js / dominio.js», léase
   «`models.py` / `dominio.py` de la app correspondiente»).

## 1. Estado actual del backend (13 modelos ya implementados)

| App | Modelos existentes |
|---|---|
| `maestros` | Mandante, Producto, Silo, Vehiculo, Especificacion *(rangos JSON, versionada)*, DocumentoLiberacion *(aplica_a, plantilla, orden, fuente — JSON)* |
| `recepcion` | Recepcion *(controles JSON, estado, motivo)*, MovimientoSilo |
| `produccion` | Lote *(codigo_lote, op, linea, turno, estado)*, Analisis *(valores JSON, especificacion FK)* |
| `calidad` | RegistroCalidad *(valores JSON, documento FK)*, Liberacion *(concesion, motivo_concesion)* |
| `usuarios` | PerfilUsuario *(rol, area, turno)* |

Ya resuelto y **coherente con el levantamiento**: JSONField para formularios dinámicos (`plantilla`/`valores`), especificaciones versionadas, Liberacion con concesión, y el bloqueo de fila en la firma. La regla central del sistema ya está protegida a nivel de plataforma.

Pendiente de portar del prototipo (si aún no está): `Receta` (multinivel), y la capa de **planificación** (`CodigoProduccion`, `SemanaPlan`, `BloquePlan`, `BalanceDia`, `AsignacionTurno`).

## 2. Delta del modelo — modelos nuevos (del levantamiento)

Nacen de formatos reales. Ubicación de app propuesta (a confirmar). La estructura repetitiva
(lecturas horarias, etapas, muestras) → **modelo hijo** con FK; los formularios dinámicos → **JSONField**.

| Modelo nuevo | App sugerida | Origen (formato) | Hijo (FK) | Regla |
|---|---|---|---|---|
| `Equipo` | maestros | límites críticos hoy dispersos en cada formato | — | fuente única de límites PCC |
| `Proveedor` | maestros | evaluación de proveedores / MP | — | — |
| `ControlProceso` | produccion | CCAA.Cond.FORM.* , CCAA.Sec.FORM.002/025/026 | `ControlProcesoLectura` (horaria) | **PCC1 uperización** viola límite → bloquea liberación |
| `MonitoreoPPRO` | inocuidad* / produccion | CCAA.Sec.FORM.022/007 , CCAA.ENV.FORM.001/003 | `PproLectura` (horaria OK/No-OK) | **PCC detector metales**; No-OK sin acción → bloquea |
| `RegistroLimpiezaCIP` | inocuidad* / produccion | CCAA.Cond.FORM.001 , CCAA.Rec.FORM.013/015 , CCAA.Sec.FORM.020 | `CipEtapa` | equipo apto para producir |
| `ControlPesoNeto` | produccion | CCAA.ENV.FORM.004 , CCAA.MAN.FORM.005 | `PesoNetoMuestra` | requisito de liberación (hermeticidad) |
| `ConsumoMaterialEnvase` | produccion | CCAA.Sec.FORM.011 | — | balance de materiales |
| `NoConformidad` | calidad | CCAA.Calidad.FORM.025/026/027/029 | — | enlaza `Liberacion.concesion` |
| `CalibracionInstrumento` | calidad | CCAA.Calidad.FORM.004/007/009/020/033/047 | `CalibracionLectura` | fuera de calibración → advierte análisis dependientes |
| `EvaluacionMateriaPrima` | recepcion | CCAA.Calidad.FORM.024 | `EvaluacionMpParametro` | entra a trazabilidad |

\* **Opción de diseño:** crear una app nueva `inocuidad` para PPRO / PCC / CIP / cuerpos extraños
mantiene la separación FSSC limpia; alternativamente viven en `produccion`. Decidir con el usuario.

Ampliaciones a modelos existentes:
- `Lote`: **autogenerar `codigo_lote`** (§4) + FK a `Equipo` y campo `turno` (ya existe).
- `DocumentoLiberacion`: agregar `area` (Recepción/Condensación/Secado/Envase); ya tiene `orden`,
  `fuente`, `plantilla`, `aplica_a`. **Sembrar los 19 registros del Dossier** (`CCAA.Calidad.FORM.023`).
- `Analisis.valores` (JSON): ampliar al formato Egron real (peso específico, solubilidad, tamiz,
  separación F.C., sensorial IN/OUT, acidez inicio/medio/fin, N° bolsa, muestra microbiológica).
- `CertificadoAnalisis`: **derivado** de `Analisis` + `Liberacion` (endpoint/serializer imprimible), no modelo nuevo.

## 3. El Dossier de Liberación (regla central) — tarea P0

`CCAA.Calidad.FORM.023` = los **19 registros** obligatorios, en orden de flujo
(Recepción → Condensación → Secado → Envase), que un lote necesita completos, firmados y
conformes para despacharse. La lista con códigos y modelo destino está en
`Modelo_Datos_Flujo_CCAA.html` (pestaña «Dossier») y en la hoja homónima del Excel.
Se siembra en `maestros.DocumentoLiberacion` (fixture o data migration) usando `area`, `orden`,
`aplica_a` y `plantilla`. El motor de checklist (`RegistroCalidad` + `calidad/dominio.py`) ya existe.

## 4. Reglas de dominio nuevas (en `dominio.py`, con `tests_dominio.py`)

- **Codificación de lote** (`CCAA.Calidad.POE.009.02`), en `produccion/dominio.py`:
  `CCAA + <año><día juliano> + sufijo`. Sufijo: `N` nacional · `1` Egron 1 · `2` Egron 2 ·
  sin sufijo = crema · `A` = segunda producción del mismo día. Autogenerar y validar desde
  fecha + línea + destino; clave natural `codigo_lote + producto + fecha`.
- **Bloqueo por PCC1**: una `ControlProcesoLectura` que viola el límite crítico de uperización
  marca el lote y bloquea `puede_liberar()` (en `calidad/dominio.py`).
- **Bloqueo por PPRO / detector de metales**: un No-OK en `MonitoreoPPRO` sin acción correctiva
  bloquea la liberación.
- Mantener el patrón existente: las decisiones devuelven motivos de bloqueo, no un booleano; el
  veredicto de calidad y el avance del checklist **no se persisten**, se recalculan
  (`prototipo/MODELO_DATOS.md` §2.2 / §2.6).
- Al tocar el camino de la firma, respetar el bloqueo de filas descrito en `DECISIONES.md` §001
  (no agregar `select_related` a la consulta que hace `select_for_update`).

## 5. Plan de integración por archivo (por cada modelo nuevo)

1. `<app>/models.py` — el modelo + su hijo (FK) si tiene detalle repetitivo; JSON solo para lo dinámico.
2. `<app>/dominio.py` — reglas puras (§4); cubrir en `<app>/tests_dominio.py`.
3. `python manage.py makemigrations <app>` → `migrate` (PostgreSQL).
4. `<app>/serializers.py`, `<app>/urls.py`, `<app>/admin.py` — exponer el modelo.
5. `frontend/src/services/<app>.service.ts` + `frontend/src/pages/…` — captura (formularios por `plantilla`).
6. Sembrar catálogos: los 19 documentos del Dossier y `Equipo` con límites por PCC (data migration/fixture).

## 6. Preguntas abiertas (confirmar con Calidad y Producción)

1. Especificaciones oficiales por producto **y mandante** (Nestlé vs. CCAA pueden diferir).
2. ¿Análisis por lote o por despacho? El modelo admite N por lote y agrega por el peor caso.
3. Límites de control de recepción (acidez, pH, crioscopía) — hoy referenciales.
4. ¿Está poblada la columna `OP`? Si lo está, puede ser la clave natural del lote (`Lote.op` ya existe).
5. Confirmar abastecimiento: ¿el secado Colun se abastece de leche de P. Unión?
6. ¿App nueva `inocuidad` o los PPRO/CIP viven en `produccion`? (ver §2).

## 7. Entregables del levantamiento (en `docs/levantamiento-2026-07/`)

- `Modelo_Datos_Flujo_CCAA.html` — flujo de proceso + Dossier + modelo de datos (interactivo).
- `Catalogo_Formatos_Procesos_CCAA.xlsx` — 204 documentos codificados, clasificados.
- `Backlog_Mejoras_App_CCAA.md` — 17 mejoras priorizadas (P0/P1/P2).

> Nota: estos tres se generaron mirando el prototipo; el **modelo y el flujo son
> agnósticos de plataforma** y siguen siendo válidos. Las referencias a `esquema.js`/`dominio.js`
> corresponden ahora a `models.py`/`dominio.py` de cada app Django.
