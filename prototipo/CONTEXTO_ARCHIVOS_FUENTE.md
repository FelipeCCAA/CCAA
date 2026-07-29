# Contexto de datos — Planta CCAA (leche en polvo y crema)

> Documento de contexto para asistentes de código (Claude Code / Copilot en VS Code).
> Describe **qué es la planta**, **qué contiene cada archivo Excel fuente** y **cómo esa lógica se mapea al prototipo web** (`index.html` + `js/datos.js` + `js/app.js`).
> Úsalo como referencia al extender la app o al construir la carga de datos real.

---

## 1. Qué es la planta

Campos Australes (CCAA) opera una **planta de secado de leche**: produce **leche en polvo** (entera y semidescremada) y **crema**, procesando tanto para **mandantes** (Nestlé, Colun) como para **marca propia CCAA**. No es una planta de quesos/yogur.

El flujo productivo de alto nivel es:

```
Recepción de leche cruda (camiones)
   → Análisis y liberación de la leche (Delvo, inhibidores, crioscopía, acidez…)
   → Almacenamiento en silos / estanques (SILO 1–8, TK LD, TK CREMA)
   → Estandarización / descremado
   → Secado en torres (líneas E1 y E2) → polvo  |  crema
   → Control de parámetros del producto (Humedad, MG, SNG, ST, Acidez, pH…)
   → Liberación de producto por Calidad (checklist de documentos)
   → Despacho a mandante / destino (Los Ángeles, Stock, etc.)
```

**Catálogos base:**

- **Productos:** `P. Entero ST 48%`, `P. Semidescremado ST 45%` (y variante `CCAA`), `Crema 42% NESTLÉ`, `Crema 42% CCAA`, `LEP NESTLÉ`, `LEP COLUN`, `Rwk NESTLÉ` (Rwk = retrabajo/rework), `Mantequilla sin Sal`, `Suero en Polvo`, `Leche Descremada en Polvo`.
- **Mandantes:** Nestlé, Colun, CCAA (propia), Surlat, Lácteos Nebe.
- **Líneas de secado:** `E1`, `E2` (evaporadores/torres). También hay envasadoras "Rovema 3 y 4".
- **Destinos:** Los Ángeles, Stock, Nestlé, Surlat, Colun, Macul, Chilolac, Cancura.
- **Silos y estanques:** `SILO 1`…`SILO 8`, `TK LD 1`…`TK LD 6` (leche descremada), `TK CREMA 1`…`TK CREMA 5`.
- **Procedencia de la leche:** Nestlé, P. Unión.
- **Turnos:** A, B, C.

**Parámetros fisicoquímicos** (se miden en leche y en producto): Humedad, Materia Grasa (MG), Sólidos No Grasos (SNG), Sólidos Totales (ST), Acidez (°D = grados Dornic), pH, Temperatura (°C), Peso Específico, Proteína.

**Codificación de documentos de calidad:** `CCAA.<AREA>.FORM.<nnn>.<vv>` (ej.: `CCAA.REC.FORM.002.01` recepción, `CCAA.Calidad.FORM.016.02` certificado de análisis, `CCAA.REC.FORM.005.01` trazabilidad de silos).

---

## 2. Archivos fuente (Excel) y su lógica

Hay cinco archivos. Dos son **datos operativos** (Producción, Trazabilidad de silos), uno es un **libro operativo de recepción** (Instructivo) y dos son **levantamientos de proceso** (formularios de Fabricación y de Calidad).

### 2.1 `Produccion.xlsx` — base de datos de producción **(fuente principal)**

Hoja **`Produccion`** (~954 filas, una por lote producido, jul-2025 a may-2026). Fila 2 = encabezados, datos desde la fila 3.

| Col | Campo | Notas |
|-----|-------|-------|
| B | Semana (W) | número de semana |
| C | Año | |
| D | Fecha | fecha de elaboración |
| E | **Producto** | ver catálogo; el nombre indica el mandante (contiene "NESTLÉ"/"COLUN"/"CCAA") |
| F | OC | orden de compra |
| G | GD | guía de despacho |
| H | **kg** | kilos producidos del lote |
| I | Bolsas y/o Cajas | a veces "N/A" |
| J | Destino | |
| K | OP | orden de producción |
| L | **Lote** | código de lote (ej. `CCAA6134N`, `00825186`) |
| M–U | **Parámetros**: Humedad, Materia Grasa, SNG, ST, Acidez, pH, Temperatura, Peso Específico, Proteína | pueden venir vacíos |
| V | Fecha Vencimiento | |
| W | Observación | |
| X | Línea | `E1` / `E2` |
| Y–AB | Hora Inicio, Hora Término, Total Horas, Producción x Hora | productividad |
| AC | X1 | columna auxiliar/concatenación (ignorar) |

Hojas secundarias: **`rc`** (48 filas con parámetros + rangos `Inferior`/`Máximo` de referencia), **`Entregas Colun`** (despachos a Colun: fecha, N° GD, lote, bolsas, kilos), **`Hoja2`** (tabla dinámica: suma de kg por producto y mes).

> **Regla de mandante** (implementada en la app): si el nombre del producto contiene "NESTL" → Nestlé; "COLUN" → Colun; "CCAA" → CCAA; "NEBE" → Lácteos Nebe; en otro caso → CCAA.

### 2.2 `17012025 Trazabilidad_leche_en_silos.xlsx` — trazabilidad de recepción por silo

Formato `CCAA.REC.FORM.005.01` ("Aviso Estandarización / Trazabilidad de leche en silos"). Es un formulario visual (no tabla limpia): registra, por vale, la leche que entra/sale de cada silo, con Fecha, Silo/TK, procedencia, si es leche certificada, N° de camión predial/interfábrica, litros, y **destino de trazabilidad** (Descremación, RC 0,422, RC 0,201, etc.).

Hoja **`Origen de datos`** = **maestros** de este dominio: lista de destinos, tipo (Leche Entera/Descremada), **operadores** (~18 nombres), **turnos** (A/B/C), lista de **silos y TK**, y **procedencia** (Nestlé, P Unión). Estos maestros alimentan los catálogos de la app.

### 2.3 `04052026 Instructivo Campos Austral.xlsx` — libro operativo de recepción

El más grande (21 hojas). Es el instructivo/registro diario de recepción de leche. Hojas clave:

- **`Base DATOS`** — maestro de **vehículos/transportistas**: N° vehículo, placa/patente, tipo (Camión), capacidad (L), transportista, **chofer A.M./P.M.**, remolque, flota. → alimenta el módulo **Maestros** de la app.
- **`Descarga Camiones`** — litros descargados por silo (Silo 1…8) por camión.
- **`Litros-kilos`** — tabla de conversión litros→kilos (`0082.MAN.FORM.000112`).
- **`Rec Silos`** — recepción en silos de leche fresca (`0082.MAN.FORM.000114`).
- **`C. P.Recepción`** — control de leche con permanencia (Fecha, Hora, Silo, Temperatura, Prueba, Acidez, pH, Organoléptico, Producto, Parte).
- **`Control Descr.`** — control de descremada (Fecha, Hora, %, SNG, Estanque, Acidez, pH, T°, Test, Aseo filtros, Operario, Destino).
- **`Delvo Test`** — análisis Delvo por silo (antibióticos): Nº Silo, kg, producto, horas, resultado, operador.
- **`Inhibidores`** — control de inhibidores (PPRO N°1…), total recepción.
- **`Pool Crioscopia`** — crioscopía por camión/módulo (detecta aguado).

Interpretación: cada camión que llega se **pesa/afora, se muestrea y se analiza** (Delvo, inhibidores, crioscopía, acidez, pH, T°). Si cumple, la leche se **libera** y se descarga al silo/TK asignado; si no cumple, se **retiene/rechaza**. Todo queda con trazabilidad (silo, operador, turno, destino).

### 2.4 `Formulario_Levantamiento_Procesos_..._Dpto.Fabricación.xlsx` — procesos de Recepción

Levantamiento de procesos del **área de Recepción** (completado por Jair Corbari, 2026-06-12). Dos hojas:

- **`1. Inventario de procesos`** — 9 procesos, cada uno con: objetivo, responsable, disparador (inicio), resultado (fin), áreas que coordina, documentos, sistemas, frecuencia y criticidad. Los 9 procesos: (1) Trazabilidad de recepción y despacho, (2) Registro de análisis de camiones, (3) Despacho de leche a empresas mandantes, (4) Recepción y verificación documental de camiones, (5) Muestreo de leche y entrega a laboratorio, (6) Control de parámetros de calidad e inocuidad, (7) Pesaje y conciliación de kilos, (8) Limpieza y sanitización (CIP), (9) Gestión de desviaciones y no conformidades.
- **`2. Detalle por actividad`** — pasos numerados por proceso: actividad, responsable, si es decisión (con criterio), documento de entrada/salida, sistema, área externa, SLA (tiempo) y qué pasa si falla (excepción).

Sirve para modelar **flujos y estados** (por ejemplo, la máquina de estados de una recepción: documentado → muestreado → analizado → liberado/retenido → descargado → conciliado → cerrado).

### 2.5 `Formulario_Levantamiento_Procesos_..._Dpto.Calidad.xlsx` — liberación de producto

Levantamiento del área de **Calidad** (Juan Calderón y Camila Rauque). El proceso central es **"Liberación de producto (semielaborado 25 kg)"**: asegurar que el lote cumple calidad, inocuidad, requisitos legales y especificaciones **antes de autorizar el despacho**.

- **Disparador:** se genera una OP / lote de producción.
- **Resultado:** se autoriza el despacho al cliente.
- **Documentos obligatorios** (checklist que la app reproduce): Planilla de Instructivo `CCAA.REC.FORM.002.01`, Formularios de control de proceso (PCC), Checklist de cuerpos extraños evaporadores, Hoja de pulverización E1/E2, Disco de uperización, Inspección preoperativa E1/E2, Conexión de tierra E1-E2, Formulario fisicoquímicos E1/E2, Formulario de filtros de limpieza, Monitoreo PPRO E1/E2, Monitoreo PPRO Rovemas 3 y 4, Checklist cuerpos extraños Rovema 3/4, Seguimiento FEFO, Monitoreo PPRO Detector de metales, Control de consumo de materiales, Control de hermeticidad y peso neto, Registro de evaluación sensorial, Informe de laboratorio externo, Certificado de Análisis `CCAA.Calidad.FORM.016.02`.

Lógica: **el lote no se libera hasta que todos los documentos están completos**. Ese es exactamente el comportamiento del módulo *Liberación* de la app (botón "Autorizar despacho" deshabilitado hasta el 100%).

---

## 3. Cómo se mapean los archivos a la app

| Archivo fuente | Módulo de la app | Colección JSON |
|----------------|------------------|----------------|
| `Produccion.xlsx` (hoja Produccion) | **Producción** | `produccion[]` |
| `Trazabilidad_leche_en_silos.xlsx` + Instructivo (controles de camión) | **Recepción y silos** | `recepcion[]` |
| `Formulario Calidad` (checklist) | **Liberación (Calidad)** | `liberaciones[]` |
| `Instructivo` → hoja `Base DATOS` | **Maestros** | `maestros[]` |
| `Trazabilidad` → `Origen de datos` + catálogos derivados | (alimenta selects/catálogos) | `catalogos{}` |

### 3.1 Modelo de datos de la app (`js/datos.js` → `DATOS_SEMILLA`)

```jsonc
{
  "produccion": [
    {
      "semana": 20, "anio": 2026, "fecha": "2026-05-14",
      "producto": "P. Semidescremado ST 45% CCAA", "mandante": "CCAA",
      "oc": 4581469422, "gd": 1258, "kg": 26120, "bolsas": "N/A",
      "destino": "Los Angeles", "op": null, "lote": "CCAA6134N",
      "humedad": null, "mg": 1.81, "sng": 9.44, "st": 11.25,
      "acidez": 24.7, "ph": 6.37, "temperatura": 8, "pesoEsp": null, "proteina": null,
      "vencimiento": null, "linea": "", "horaInicio": "", "horaTermino": "",
      "observacion": "", "resultadoCalidad": "No conforme"   // calculado
    }
  ],
  "recepcion": [
    {
      "id": "REC-260504-01", "fecha": "2026-05-04", "silo": "SILO 1",
      "procedencia": "Nestlé", "tipoLeche": "Entera", "litros": 56488,
      "camion": "BKSX97", "operador": "Cristian Navarro", "turno": "A",
      "temperatura": 4.2, "acidez": 15.5, "ph": 6.7,
      "delvoTest": "Negativo", "inhibidores": "Negativo", "crioscopia": -0.520,
      "destino": "Descremación", "estado": "Liberada"   // Liberada | Retenida
    }
  ],
  "liberaciones": [
    {
      "id": "LIB-6134", "lote": "CCAA6134N", "producto": "P. Semidescremado ST 45% CCAA",
      "fecha": "2026-05-14", "especialista": "Camila Rauque",
      "estado": "Liberado",   // Pendiente | En revisión | Liberado
      "checklist": [ { "documento": "…", "completado": true } ]
    }
  ],
  "maestros": [
    { "vehiculo": 6017041, "placa": "BKSX97", "transportista": "Luis Flores",
      "tipo": "Camión", "capacidad": 16000, "choferAM": "…", "choferPM": "…" }
  ],
  "catalogos": {
    "productos": [...], "mandantes": [...], "lineas": ["E1","E2"],
    "destinos": [...], "silos": [...], "procedencias": ["Nestlé","P Unión"],
    "operadores": [...], "turnos": ["A","B","C"],
    "especificaciones": { "<producto>": { "humedad":[0,4], "mg":[26,30], ... } },
    "documentosLiberacion": [ "…19 documentos…" ]
  }
}
```

### 3.2 Lógica de evaluación de calidad (clave)

Función `evaluarCalidad(lote)` en `js/app.js` (y su gemela en `gen.py` que generó la semilla):

1. Busca `catalogos.especificaciones[lote.producto]`. Si no existe → `"Sin especificación"`.
2. Para cada parámetro con rango `[lo, hi]` **que tenga valor** en el lote, comprueba `lo <= valor <= hi`.
3. Si ningún parámetro tiene valor → `"Sin control"`.
4. Si todos los presentes están en rango → `"Conforme"`; si alguno se sale → `"No conforme"`.

> **Importante:** los rangos actuales son **referenciales** (aproximados a partir de los datos). Deben reemplazarse por las **especificaciones oficiales** por producto/mandante. Es el primer punto a validar con Calidad.

### 3.3 Lógica de liberación

- `estado` del lote depende del avance del `checklist`: `Pendiente` → `En revisión` → `Liberado`.
- El botón "Autorizar despacho" solo se habilita cuando **el 100%** de los documentos están `completado: true`.
- Al desmarcar un documento de un lote ya `Liberado`, vuelve a `En revisión`.

### 3.4 Persistencia (etapa actual)

- Sin servidor: la app corre con `file://`. Los datos semilla están **embebidos** en `datos.js` (porque `fetch()` de JSON local falla en `file://`).
- Los cambios se guardan en **`localStorage`** (`clave: gpl_ccaa_v1`).
- **Exportar/Importar JSON** permite respaldar y mover datos entre equipos. `restablecerDatos()` vuelve a la semilla.

---

## 4. Tareas típicas al extender la app (para el asistente de código)

Al implementar cambios, respeta el modelo de datos anterior y estas convenciones:

- **Carga del histórico real:** convertir las ~954 filas de `Produccion.xlsx` a `produccion[]` (script Python con `openpyxl`; aplicar la regla de mandante y `evaluarCalidad`). Cuidado con celdas vacías (`null`) y fechas (`datetime` → `"YYYY-MM-DD"`).
- **Edición/borrado de registros:** hoy solo hay alta. Añadir editar/eliminar en cada módulo, persistiendo con `guardarDatos()`.
- **Formulario de recepción de camión:** modelar controles Delvo/inhibidores/crioscopía con decisión libera/retiene (ver `Formulario Fabricación`, proceso 6).
- **Especificaciones por producto:** mover `catalogos.especificaciones` a un editor en la UI (Calidad) en vez de editar `datos.js` a mano.
- **Reportes:** kg por producto/mandante/mes (ver `Hoja2` de Produccion como referencia de agregación), exportables a Excel/PDF.
- **Migración a backend (fase futura):** el usuario aún NO quiere servidor/BD. Cuando llegue, mantener el mismo esquema JSON como contrato de API.

## 5. Convenciones y advertencias

- Español en UI, nombres de datos y comentarios.
- Fechas en formato ISO `YYYY-MM-DD`; números con `toLocaleString("es-CL")` solo para mostrar.
- Los IDs de lote pueden ser numéricos o alfanuméricos (`CCAA6134N`, `00825186`); tratarlos como **string**.
- `°D` = grados Dornic (acidez). `ST` = sólidos totales. `SNG` = sólidos no grasos. `MG` = materia grasa. `Rwk` = retrabajo. `LEP` = leche entera en polvo. `PPRO` = programa prerrequisito operativo. `FEFO` = first-expired-first-out.
- Los datos de ejemplo son reales pero **parciales** (muestra de 24 lotes); no asumir que la muestra representa volúmenes totales.
- Archivos fuente originales están en la carpeta de trabajo del usuario; este prototipo vive en `Gestión TI\App Gestión Productiva CCAA`.
