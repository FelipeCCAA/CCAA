# Backlog de mejoras — App Gestión Productiva CCAA

**Origen:** levantamiento de la carpeta *Documentos Planta* (Sistema de Aseguramiento de Calidad, HACCP / FSSC 22000) — 1.567 archivos, 204 documentos codificados, 99 formatos de registro.
**Objetivo:** cerrar la brecha entre lo que la planta ya controla en planillas y lo que la app modela hoy.
**Fecha:** 2026-07-30.

El backlog respeta la arquitectura vigente (`esquema.js` / `dominio.js` / `repositorio.js`, formularios dibujados desde `plantilla`, especificaciones y recetas versionadas, veredictos que no se persisten sino se recalculan). Nada de esto exige aún un servidor: casi todo son entidades y plantillas nuevas sobre el mismo modelo local.

Prioridad: **P0** = habilita la regla central (liberar/despachar bien) o cierra un hueco de inocuidad · **P1** = completa un proceso real que hoy no tiene dónde registrarse · **P2** = mejora de gestión y reportería.

---

## P0 — Núcleo de liberación e inocuidad

### 1. Convertir el Dossier de Liberación en la plantilla real del checklist
**Qué:** el catálogo `documentoLiberacion` debe reproducir los **19 registros reales** de `CCAA.Calidad.FORM.023`, en orden y con su **área de origen** (Recepción / Condensación / Secado / Envase) y su `aplicaA` por familia de producto (polvo entero, LEP 27%, mantequilla, crema).
**Por qué:** hoy el checklist es genérico; el dossier real es la definición auditable de "lote liberable". El orden y el área permiten mostrar el avance como el flujo físico y detectar qué área tiene el registro pendiente.
**Dónde:** `documentoLiberacion` → agregar campos `area`, `orden`, refinar `aplicaA` y `plantilla[]`. Sembrar los 19 desde la hoja *Portada de Dossier*.
**Nota:** el registro #4 (Disco de Uperización) es un adjunto sin código → soportar documentos tipo "evidencia/foto".

### 2. Entidad `controlProceso` (condensación + secado) con el PCC 1
**Qué:** captura de parámetros **horarios por equipo, turno y lote**: flujo de entrada, densidad, T° DSI, T° calandria, vacío condensador, presión termocompresor, nivel TK balanza — y el **PCC 1 de uperización** (T° mínima y caudal máximo con su límite crítico: VEB 80 °C / 14.175 kg·h; Sch2 81,2 °C / 17.100 kg·h).
**Por qué:** es el corazón del control de proceso y el punto crítico de control (PCC1) que gatilla la liberación. Hoy vive en `CCAA.Cond.FORM.*` y `CCAA.Sec.FORM.002/025/026`.
**Dónde:** nueva entidad `controlProceso` en `esquema.js`; regla en `dominio.js` que marca "PCC1 no conforme" si una lectura viola el límite crítico, y que **bloquea la liberación** del lote afectado.

### 3. Entidad `monitoreoPPRO` (incluye PCC detector de metales)
**Qué:** chequeos **OK / No-OK por hora y turno** de: presión de aire de transporte fluidizado, presión de aire secundario, roce de válvulas fluidificadoras, cuerpos extraños, y el **detector de metales** (patrones Fe / no-Fe / inox con cantidad de rechazos y alarmas). Cada No-OK exige acción correctiva registrada.
**Por qué:** son los PPRO/PCC de inocuidad (registros 3, 11, 12, 13, 14, 17 del dossier). Un No-OK sin acción correctiva debe bloquear la liberación.
**Dónde:** nueva entidad `monitoreoPPRO`; regla de bloqueo en `dominio.js` análoga a la del PCC1.

### 4. Autogeneración y validación del `codigoLote`
**Qué:** generar el código según `CCAA.Calidad.POE.009.02`: `CCAA + <año><día juliano> + sufijo` (**N** nacional · **1** Egron 1 · **2** Egron 2 · sin sufijo crema · **A** segunda producción del día).
**Por qué:** hoy el código se teclea y se duplica (el propio `MODELO_DATOS.md` documenta colisiones). Autogenerarlo desde fecha + línea + destino elimina el error y da la clave natural correcta.
**Dónde:** helper en `dominio.js`; el alta de `lote` lo propone y valida unicidad contra `codigoLote + productoId + fecha`.

---

## P1 — Procesos reales sin lugar de registro

### 5. Entidad `analisis` ampliada al formato Egron real
**Qué:** además de humedad/MG/proteína, agregar: peso específico, solubilidad, tamiz, separación F.C., limpieza, **evaluación sensorial (sabor/olor, apariencia — IN/OUT)**, acidez inicio/medio/fin, N° de bolsa, muestra microbiológica. Los rangos objetivo/mín/máx por producto vienen en el propio formato.
**Por qué:** el análisis fisicoquímico Egron (registro 8 del dossier) es mucho más rico que los 9 parámetros actuales, y esos campos son parte de la conformidad.
**Dónde:** ampliar `analisis` en `esquema.js`; poblar `especificacion` con los rangos del formato.

### 6. Entidad `registroLimpiezaCIP`
**Qué:** aseo CIP/COP por equipo: etapas (enjuague, soda, agua, ácido nítrico) con hora, caudal, T°, conductividad; **pH final (rango 5,5–8,5)**; verificación visual IN/OUT; operador. Incluye filtros de limpieza de producto (registro 9 del dossier).
**Por qué:** el saneamiento es prerrequisito y hoy no tiene entidad; aparece en `CCAA.Cond.FORM.001`, `CCAA.Rec.FORM.013/015`, `CCAA.Sec.FORM.020`, mantequilla.
**Dónde:** nueva entidad; opcionalmente gatilla "equipo apto para producir".

### 7. Entidad `controlPesoNeto` + hermeticidad
**Qué:** peso bruto / tara / neto por muestra y hora + chequeo por unidad (aspecto, etiquetado, sellado) + control de hermeticidad (registro 19 del dossier).
**Por qué:** cierra el control de envasado y es requisito de liberación. Formatos `CCAA.ENV.FORM.004`, `CCAA.MAN.FORM.005`.
**Dónde:** nueva entidad `controlPesoNeto` ligada a `lote`.

### 8. Entidad `noConformidad` (TNC / PNC / reclamos)
**Qué:** incidente, título, área donde ocurrió, razón de detección, responsable de apertura, tipo de desviación, **reincidente sí/no**, acción correctiva y preventiva, estado y cierre. Vínculo opcional a lote.
**Por qué:** el proceso de no conformidades (`CCAA.Calidad.FORM.025/026`, PNC `029`, reclamos `027`) es un pilar FSSC sin representación en la app. Se conecta con la liberación bajo concesión.
**Dónde:** nueva entidad; enlazar `liberacion.concesion` → `noConformidad`.

### 9. Entidad `calibracionInstrumento` (Planes de Autocontrol / PAC)
**Qué:** calibración/contrastación de pHmetro, crioscopio, balanza analítica, termómetros, Infralab: fecha, patrón, lecturas vs. referencia con tolerancia, offset, pendiente, conforme/no, analista. Frecuencia diaria / según uso.
**Por qué:** la metrología condiciona la validez de todos los análisis; formatos `CCAA.Calidad.FORM.004/007/009/020/033/047`. Un instrumento fuera de calibración debería advertir sobre los análisis que dependen de él.
**Dónde:** nueva entidad; maestro `equipo` como referencia.

### 10. Entidad `evaluacionMateriaPrima` (MEE y MP)
**Qué:** evaluación al ingreso de materias primas y material de empaque (lecitina, film coextruido, bolsa de papel/polietileno, caja mantequilla, protomalt): proveedor, lote, parámetros, **declaración de alérgenos**, resultado aceptado/rechazado.
**Por qué:** `CCAA.Calidad.FORM.024` + POE.023/024/025; entra a la trazabilidad y a la evaluación de proveedores.
**Dónde:** nueva entidad; enlazar a `proveedor` (maestro nuevo) y a `movimientoSilo`/consumo.

### 11. Maestro `equipo` con límites críticos
**Qué:** catálogo de equipos (VEB, Scheffers 2/3, Egron 1/2, Rovema 3/4, mantequera, descremadora) con sus **límites críticos por PCC** (T° mínima, caudal máximo, rangos de proceso). Hoy esos límites están repetidos dentro de cada formato.
**Por qué:** centralizarlos permite que `controlProceso` y `monitoreoPPRO` validen contra una sola fuente y que cambien sin tocar código.
**Dónde:** nuevo maestro `equipo`; referenciado por lote, controlProceso, monitoreoPPRO, calibración, CIP.

---

## P2 — Gestión, trazabilidad y reportería

### 12. Certificado de análisis como salida imprimible
**Qué:** generar el `certificadoAnalisis` (producto, lote, fechas elab/venc, kg, cajas, fisicoquímicos con método/unidad/spec/resultado) a partir de los datos ya capturados, exportable a PDF. Formatos `CCAA.Calidad.FORM.016/041`.
**Por qué:** es el documento que acompaña al despacho; hoy se rehace a mano.

### 13. Checklists pre-operativos e inspección en operación
**Qué:** inspección pre-operativa E1/E2, conexión a tierra, inspección en operación Rovema (registros 6, 7, 15). Plantillas simples de ítems OK/No-OK.
**Por qué:** completan el dossier; encajan como `documentoLiberacion` con `plantilla` de checkboxes.

### 14. Regla y seguimiento **FEFO** en el despacho
**Qué:** al despachar, sugerir/forzar el lote con vencimiento más próximo primero (registro 16). `dominio.js` ya devuelve motivos de bloqueo; agregar aviso FEFO.
**Por qué:** requisito de envase y de rotación de stock.

### 15. Editor de especificaciones y de plantillas desde la UI (rol Calidad)
**Qué:** mover `catalogos.especificaciones` y las `plantilla` de formularios a un editor en Administración, versionado.
**Por qué:** ya está previsto en el modelo (§2.6/§2.3 de `MODELO_DATOS.md`); habilita que Calidad ajuste rangos sin tocar `datos.js`.

### 16. Reportería operativa
**Qué:** kg por producto/mandante/mes, tasa de conformidad, no conformidades por área, cumplimiento de PPRO por turno, exportables a Excel/PDF.
**Por qué:** cierra el ciclo de gestión; la agregación de `Hoja2` de Producción es la referencia.

### 17. Carga del histórico y saneamiento del repositorio documental
**Qué:** importar las ~954 filas de `Produccion.xlsx` a `lote`/`despacho`; además, la carpeta fuente tiene **duplicados y versiones** (copias "-camila", "(1)", "Volver a imprimir", "Obsoleto") — conviene un criterio de versión vigente por código al sembrar catálogos.
**Por qué:** el importador ya está previsto (`semilla.js` es su plantilla); la limpieza evita arrastrar documentos obsoletos.

---

## Prerrequisito de operación (decisión, no desarrollo)

- **Persistencia compartida.** Recepción (turnos A/B/C), Producción y Calidad son personas y momentos distintos: el flujo completo no funciona sobre `localStorage` por equipo. La capa `repositorio.js` está diseñada para que sea el cambio de **un solo archivo** (adaptador API / SharePoint), pero hay que tomar la decisión antes de poner el MVP en producción. Todo el backlog anterior es válido con o sin servidor.

## Definiciones a confirmar con Calidad y Producción

1. Especificaciones oficiales por producto **y mandante** (Nestlé vs. CCAA pueden diferir).
2. ¿Los análisis son por lote o por despacho? El modelo admite N por lote y agrega por el peor caso.
3. Límites de control de recepción (acidez, pH, crioscopía) — hoy son referenciales.
4. ¿La columna `OP` (orden de producción) está poblada? Si lo está, puede ser la clave natural del lote.
5. Confirmar el mapa de abastecimiento (¿el secado Colun se abastece de leche de P. Unión?).
