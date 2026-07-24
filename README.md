# Gestión Productiva · Planta CCAA (leche en polvo y crema)

Aplicación web (HTML/CSS/JavaScript) para la gestión productiva de la planta de secado de Campos Australes. Corre **abriendo `index.html` en el navegador**, sin servidor ni instalación. Los datos de ejemplo provienen de los archivos reales de la planta (Producción, Trazabilidad de silos, Instructivo de recepción y formularios de levantamiento de Fabricación y Calidad).

## Módulos

**Panel general.** Kilos producidos, cumplimiento de parámetros de calidad, litros recepcionados en silos, recepciones retenidas y liberaciones pendientes. Gráficos de kg por producto y por mandante.

**Producción (polvo y crema).** Registro de lotes con producto, mandante, lote, guía de despacho, kg, destino, línea (E1/E2) y parámetros fisicoquímicos (Humedad, Materia Grasa, SNG, ST, Acidez, pH, Temperatura). Cada lote se evalúa automáticamente como **Conforme / No conforme** contra las especificaciones referenciales por producto. Incluye alta de nuevos lotes y filtros por producto y por resultado de calidad.

**Recepción y trazabilidad de silos.** Leche recibida por silo/estanque (SILO 1–8, TK LD, TK CREMA), procedencia (Nestlé, P. Unión), tipo (entera/descremada), litros, camión, operador, turno y controles de camión (Delvo Test, inhibidores, crioscopía, acidez, pH, temperatura), con estado Liberada/Retenida y gráfico de ocupación por silo.

**Liberación de producto (Calidad).** Cada lote muestra el checklist de documentos obligatorios antes de autorizar despacho (PCC, monitoreo PPRO E1/E2 y Rovemas, checklist de cuerpos extraños, detector de metales, FEFO, hermeticidad y peso neto, evaluación sensorial, certificado de análisis CCAA.Calidad.FORM.016.02, etc.). El botón **Autorizar despacho** se habilita solo cuando el checklist está completo.

**Maestros.** Catálogo de camiones y transportistas (vehículo, placa, tipo, capacidad y choferes A.M./P.M.) tomado del instructivo de recepción.

## Uso

1. Abre `index.html` con doble clic.
2. Navega con el menú lateral.
3. **+ Nuevo lote** registra una producción; el resultado de calidad se calcula solo.
4. Los cambios se guardan automáticamente en el navegador de ese equipo.

## Datos (importar / exportar)

Como esta etapa trabaja con archivos JSON, en la barra lateral tienes **Exportar JSON** (descarga todo lo actual para respaldar o compartir), **Importar JSON** (carga un archivo del mismo formato) y **Restablecer datos** (vuelve a los datos de ejemplo). La carpeta `datos/` contiene los archivos de referencia por módulo.

## Especificaciones de calidad (importante)

Los rangos que determinan Conforme/No conforme son **referenciales** y están definidos en `js/datos.js`, dentro de `catalogos.especificaciones`. Ajústalos a las especificaciones oficiales de cada producto/mandante. Los lotes sin especificación definida aparecen como "Sin especificación", y los que no tienen parámetros cargados como "Sin control".

## Estructura

```
App Gestión Productiva CCAA/
├── index.html
├── css/estilos.css
├── js/
│   ├── datos.js        Datos semilla (reales), guardado local, importar/exportar
│   └── app.js          Lógica de los módulos, dashboard y formularios
├── datos/
│   ├── produccion.json
│   ├── recepcion-silos.json
│   ├── liberacion-calidad.json
│   └── maestros.json
└── README.md
```

## Próximos pasos sugeridos

Los datos viven en cada navegador; para trabajo compartido conviene un servidor o base de datos central. Se pueden agregar: edición/borrado de registros, carga masiva del histórico completo de Producción.xlsx (954 registros), registro de controles de recepción por camión (Delvo/inhibidores/crioscopía como formulario), reportes exportables (PDF/Excel), y control de usuarios por área (Recepción, Producción, Calidad).

---
Prototipo v2 · datos reales de ejemplo · julio 2026
