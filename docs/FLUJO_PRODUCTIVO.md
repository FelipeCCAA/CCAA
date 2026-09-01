# Flujo productivo CCAA

La fuente de trazabilidad es la cadena `EjecucionProceso -> EntradaProceso -> SalidaProceso`.
Los lotes, vales, corridas especializadas, envases y pallets complementan esa cadena; no la
reemplazan.

## Rutas operativas

- Leche en polvo: estandarización -> evaporación -> secado -> envasado -> Calidad -> inventario.
- Mantequilla: crema liberada -> mantequilla -> envasado en cajas -> Calidad -> inventario.
- Precondensado: estandarización -> evaporación -> Calidad -> despacho directo a granel.
- Descremación: leche -> leche descremada + crema. Cada salida crea su lote intermedio,
  conserva TK y saldo propio, y convierte litros a kilos con la densidad que aprobó Calidad.

Las rutas se configuran con `RutaProducto`. El flujo histórico genérico continúa disponible como
respaldo para registros antiguos, pero una ruta específica tiene prioridad.

## Clases y destinos

Cada salida declara una clase (`intermedio`, `granel`, `subproducto`, `terminado` o `merma`) y un
destino operacional. Un intermedio no puede ingresar a inventario de producto terminado. Una
continuación sólo puede tomar la siguiente etapa activa de la ruta y registra la salida de origen.

El reproceso utiliza una entrada de tipo `reproceso`, exige lote, motivo y una
`AutorizacionReproceso` vigente de Calidad. La autorización identifica origen, cantidad y decisión
(`aprobado`, `bloqueado` o `destruido`); Producción no puede consumir más kilos que los aprobados.
Los registros históricos que ya tenían liberación o concesión conservan compatibilidad. Nunca se
corrige el saldo del lote original para simularlo.

## Pantallas

- **Producción** muestra accesos por proceso, intermedios liberados, evaporadores y lotes.
- **Procesamiento / seguimiento** muestra corridas, estados y la cadena de transformaciones.
- **Envasado** permanece separado y genera unidades, kilos y pallets.
- **Calidad** muestra clase y destino antes de liberar una salida intermedia.
- **Calidad > Rework** permite identificar producto rechazado, sacos dañados, excedentes o
  material recuperable, registrar kilos y tomar la decisión sin usar el administrador Django.
- **Procesamiento > Rework autorizado** consulta bajo demanda el saldo aprobado y lo incorpora a
  una ejecución dejando genealogía, cantidad y motivo visibles.
- **Inventario > Despachos** autoriza y confirma pallets o granel liberado. El granel no crea un
  pallet ni una existencia ficticia de producto terminado.

## Operación de las etapas

- Evaporación permite iniciar una corrida preparada y cerrarla registrando litros de
  precondensado, sólidos, densidad, temperatura, flujo, vacío y presión. El cierre deja la
  salida pendiente de Calidad cuando la etapa lo exige.
- Mantequilla permite iniciar exclusivamente con su lote de crema ya asignado. El cierre
  separa mantequilla, suero y merma, muestra el balance antes de guardar y envía el resultado
  principal a Calidad antes de Envasado.
- Secado conserva como documento operativo el lote de producción existente: allí se declaran
  los kilos reales y se genera la salida a granel destinada a Envasado. No se creó un segundo
  formulario ni un lote duplicado.
- Envasado sólo muestra y acepta productos finales. Si el lote posee una salida de proceso, ésta
  debe declarar Envasado como destino. Los pallets nacen en cuarentena, con máximo 500 kg, y el
  mismo lote sigue hasta Calidad e Inventario.

Las altas también son guiadas. Una nueva evaporación solo puede elegirse desde un lote
abierto con vale, OP estructurada, entrada en litros y evaporador ya trazados; el operador
solo define el silo de concentrado con capacidad suficiente. Una nueva corrida de mantequilla
solo muestra OP de mantequilla programadas, lotes de crema producidos con saldo en kg y líneas
compatibles. La ejecución, el lote de mantequilla y la corrida se crean en una transacción.

## Reglas de balance

Las cantidades se conservan con su unidad. Sólo se comparan directamente entradas y salidas en la
misma unidad. En descremación, la diferencia medida entre litros de entrada y las dos salidas se
registra como merma explícita; no queda escondida en una fórmula.

## Cuándo termina cada producto

| Producto | Última transformación | Control final | Destino operativo |
| --- | --- | --- | --- |
| Leche en polvo | Secado y luego Envasado | Calidad libera el lote y sus pallets | Inventario de producto terminado |
| Mantequilla | Elaboración y luego Envasado | Calidad libera el lote y sus unidades | Inventario de producto terminado |
| Precondensado | Evaporación | Calidad libera la salida a granel | Despacho directo; no crea pallets ni stock terminado |
| Leche semidescremada | Descremación o estandarización, según la ruta | Calidad cuando la ruta lo exige | Despacho a granel o siguiente proceso configurado |

Cerrar una máquina no equivale a terminar comercialmente el producto. La orden queda
`pendiente_calidad` al finalizar su última operación y sólo pasa a `liberada` con la decisión
de Calidad. Si aún existe una etapa productiva, la salida conserva el lote y se enlaza como
entrada de la siguiente ejecución, sin reiniciar la trazabilidad.

Una salida intermedia que identifica producto sólo puede liberarse con un análisis confirmado,
vigente, posterior a la corrida y conforme con la versión de especificación que regía al producirla.
La bandeja de Calidad muestra los rangos, los parámetros faltantes y cada desviación antes de
habilitar la firma. Las nuevas descremaciones exigen producto explícito para sus dos salidas; sólo
las salidas históricas sin esa identidad conservan temporalmente el control firmado anterior.

## Estado de implementación por fases

1. **Rutas y final de producto:** implementado para polvo, mantequilla y precondensado.
2. **Intermedios y descremación:** implementado con lotes, Calidad, densidad, TK y consumo de crema.
3. **Rework:** implementado con decisión independiente de Calidad y límite de kilos reutilizables.
4. **Envasado e Inventario:** implementado sobre el mismo lote, pallets en cuarentena y liberación.
5. **Indicadores iniciales:** el resumen gerencial incorpora calidad de primera pasada, lotes
   bloqueados y kilos/lotes de rework sin agregar otra llamada desde el panel.

Pendientes evolutivos, no bloqueantes para operar: rendimiento específico de secado y mantequilla,
pérdidas de materia grasa por balance composicional y tendencias históricas por turno/equipo.
