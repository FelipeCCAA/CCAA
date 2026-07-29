# Gestión Productiva · Planta CCAA

Aplicación web para la gestión productiva de la planta de secado de Campos Australes
(leche en polvo y crema). Corre **abriendo `index.html` en el navegador**: sin servidor,
sin instalación y sin dependencias externas.

Estado: **MVP en construcción**. El modelo de datos y las reglas de negocio están cerrados
y probados; falta decidir la persistencia compartida y migrar el histórico de los Excel.

---

## Cómo se usa

1. Abre `index.html` con doble clic.
2. Elige arriba a la derecha **con qué usuario operas**: el rol condiciona lo que puedes hacer
   (solo Calidad y Administrador autorizan liberaciones).
3. Navega con el menú lateral. Cada vista tiene su propia dirección (`index.html#produccion`),
   así que se puede enlazar y el botón «atrás» del navegador funciona.
4. Los cambios se guardan solos en el navegador de ese equipo.

Para comprobar que todo funciona: abre **`pruebas.html`**. Ejecuta 110 pruebas del modelo
y muestra el resultado en pantalla.

---

## La regla que gobierna el sistema

> **Un despacho exige un lote liberado.**
> Un lote se libera si **todos sus formularios de calidad están completos y firmados** *y* su
> **calidad es conforme** contra la especificación vigente a la fecha del lote.
> Si no es conforme, solo puede salir como **liberación bajo concesión**: con motivo escrito,
> autorizador identificado y marca permanente.

La aplicación no deja saltarse esa regla, y cuando bloquea algo **explica por qué** en vez de
mostrar un botón gris sin motivo.

---

## Módulos

**Panel general.** Kilos producidos, cumplimiento de calidad *con su cobertura* (un 90 % sobre
3 de 40 lotes no es una buena noticia, y el panel lo dice), litros recepcionados, retenciones y
liberaciones pendientes. Avisa cuando los indicadores se apoyan en especificaciones sin validar.

**Planificador.** Programa semanal de planta en carta tipo Gantt (`equipos × horas`) acoplado
al **balance de leche**. Los dos bloques están ligados: el consumo del balance **se deduce de
los bloques programados en evaporadores** — mover un bloque recalcula el consumo del día y, por
arrastre, el stock de toda la semana. Ni el consumo ni los stocks se guardan nunca.
Solo los evaporadores (Scheffers 2/3 y VEB) consumen leche cruda; las líneas de secado trabajan
precondensado y la de mantequilla, crema, así que se programan pero no entran al balance —
si entraran, la misma leche se contaría dos veces. Un saldo negativo por origen es una alarma
e impide publicar la semana. Editan Producción y Administración; el resto ve en modo lectura.

**Producción.** Lotes con producto, línea, turno, kilos y estado. Cada lote tiene sus **análisis
de calidad** (uno o varios, según muestra o guía) y su resultado se **recalcula siempre**: al
corregir una especificación, todo el histórico se reevalúa solo. Alta, edición y borrado.

**Recepción y silos.** Recepciones de leche con controles de camión (Delvo, inhibidores,
crioscopía, acidez, pH, temperatura) y descarga al silo. La **ocupación de silos es un saldo**
—ingresos menos consumo—, no un acumulado histórico, y avisa si un silo supera su capacidad.

**Calidad.** Módulo propio, en dos niveles: una **bandeja priorizada** por antigüedad (con los
kilos retenidos, los no conformes y los avisos de cotejo) y, al abrir un lote, su **expediente**.

Los documentos del checklist son **formularios digitales**: cada uno se abre, se completa y
queda firmado con usuario y fecha; volver a abrirlo muestra el registro tal como se llenó.
Los campos se declaran como datos en el catálogo de documentos, así que Calidad puede cambiar
un formulario desde Administración sin tocar código.

Tres cosas que el papel no puede hacer y aquí sí:
- Los datos que el sistema ya conoce (lote, producto, fecha) **se prellenan solos**.
- Lo que se escribe se **coteja contra el análisis del lote y la especificación vigente**: si
  el formulario dice una materia grasa distinta de la del laboratorio, avisa antes de firmar.
- Un documento **marcado con observación bloquea la liberación** aunque el resto esté completo.

Solo cuentan los documentos que **corresponden a la familia del producto** (a la crema no se le
exigen los de las líneas de polvo). Reabrir un formulario de un lote ya liberado lo devuelve a
revisión. Cada expediente tiene dirección propia (`index.html#calidad/<lote>`).

**Despachos.** Guías emitidas contra lotes liberados. No se puede despachar más kilos de los
que el lote tiene disponibles.

**Administración.** Edición completa de las 20 entidades: productos, **recetas**, mandantes,
**especificaciones de calidad** (con editor de rangos por parámetro), documentos de liberación,
silos, camiones, usuarios y todos los registros. Incluye la **bitácora de auditoría**.

**Recetas.** Maestro de transformación de la leche, **multinivel**: 1 kg de crema son 4 L de
leche fresca, y 1 kg de mantequilla son 2 kg de crema — o sea 8 L de leche. La explosión recorre
la cadena completa. De ahí sale lo que el planificador no sabía decir: **cuántos kilos de
producto deja cada bloque programado**, dividiendo los litros/hora del evaporador por los litros
que cuesta cada kilo. Se validan contra ciclos y contra unidades incoherentes.

---

## Estructura

```
App Gestión Productiva CCAA/
├── index.html              Aplicación
├── pruebas.html            Banco de pruebas (abrir en el navegador)
├── css/estilos.css         Sistema de diseño
├── js/
│   ├── datos.js            Datos de ejemplo en formato plano (origen Excel)
│   ├── modelo/
│   │   ├── esquema.js      Entidades, tipos, estados y validación
│   │   ├── dominio.js      Reglas de negocio (funciones puras)
│   │   ├── repositorio.js  Persistencia, integridad y auditoría
│   │   ├── recetas.js      Recetas multinivel: leche → crema → mantequilla
│   │   ├── planificador.js Programa semanal y balance de leche (reglas puras)
│   │   ├── semilla.js      Migración de los datos planos al modelo
│   │   └── pruebas.js      110 pruebas
│   ├── ui/componentes.js   Modales, avisos, tablas y formularios
│   └── app.js              Vistas y flujo de la aplicación
├── MODELO_DATOS.md         El modelo explicado y sus decisiones
└── CONTEXTO_ARCHIVOS_FUENTE.md   Descripción de los Excel de origen
```

Detalle del modelo, decisiones de diseño y definiciones pendientes: **[MODELO_DATOS.md](MODELO_DATOS.md)**.

---

## Notas para quien siga el desarrollo

- **Sin módulos ES.** `file://` los bloquea por CORS. Se usan `<script>` globales con espacios
  de nombre: `Esquema`, `Dominio`, `Repositorio`, `Semilla`, `UI`, `App`.
- **El repositorio es asíncrono** aunque hoy escriba en `localStorage`. Cambiar de almacenamiento
  significa reescribir **un solo archivo**: el adaptador.
- **Los formularios se generan desde el esquema.** Agregar un campo en `esquema.js` lo hace
  aparecer en pantalla, validado, sin tocar la interfaz.
- **El dominio no importa nada** (ni DOM, ni red, ni almacenamiento). Por eso es testeable.

## Limitaciones actuales

- Los datos viven en el navegador de cada equipo. **El flujo completo entre Recepción, Producción
  y Calidad no puede operar así**: son personas distintas en turnos distintos. Hay que definir un
  almacenamiento compartido antes de poner esto en producción.
- No hay autenticación: el selector de usuario es una simulación para probar los roles.
- Las **especificaciones de calidad son referenciales** y hay que reemplazarlas por las oficiales.
  Ya son editables desde Administración.
- Las capacidades de silo son provisorias; también se editan desde Administración.
- Falta el importador del histórico de `Produccion.xlsx` (~954 filas).
