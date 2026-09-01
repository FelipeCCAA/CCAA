# Flujo productivo CCAA

La fuente de trazabilidad es la cadena `EjecucionProceso -> EntradaProceso -> SalidaProceso`.
Los lotes, vales, corridas especializadas, envases y pallets complementan esa cadena; no la
reemplazan.

## Rutas operativas

- Leche en polvo: estandarización -> evaporación -> secado -> envasado -> Calidad -> inventario.
- Mantequilla: crema liberada -> mantequilla -> envasado en cajas -> Calidad -> inventario.
- Precondensado: estandarización -> evaporación -> Calidad -> despacho directo a granel.
- Descremación: leche -> leche descremada + crema. Cada salida conserva saldo y destino propio.

Las rutas se configuran con `RutaProducto`. El flujo histórico genérico continúa disponible como
respaldo para registros antiguos, pero una ruta específica tiene prioridad.

## Clases y destinos

Cada salida declara una clase (`intermedio`, `granel`, `subproducto`, `terminado` o `merma`) y un
destino operacional. Un intermedio no puede ingresar a inventario de producto terminado. Una
continuación sólo puede tomar la siguiente etapa activa de la ruta y registra la salida de origen.

El reproceso utiliza una entrada de tipo `reproceso`, exige lote, motivo y autorización vigente de
Calidad. Nunca se corrige el saldo del lote original para simularlo.

## Pantallas

- **Producción** muestra accesos por proceso, intermedios liberados, evaporadores y lotes.
- **Procesamiento / seguimiento** muestra corridas, estados y la cadena de transformaciones.
- **Envasado** permanece separado y genera unidades, kilos y pallets.
- **Calidad** muestra clase y destino antes de liberar una salida intermedia.
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

Las altas también son guiadas. Una nueva evaporación solo puede elegirse desde un lote
abierto con vale, OP estructurada, entrada en litros y evaporador ya trazados; el operador
solo define el silo de concentrado con capacidad suficiente. Una nueva corrida de mantequilla
solo muestra OP de mantequilla programadas, lotes de crema producidos con saldo en kg y líneas
compatibles. La ejecución, el lote de mantequilla y la corrida se crean en una transacción.

## Reglas de balance

Las cantidades se conservan con su unidad. Sólo se comparan directamente entradas y salidas en la
misma unidad. En descremación, la diferencia medida entre litros de entrada y las dos salidas se
registra como merma explícita; no queda escondida en una fórmula.
