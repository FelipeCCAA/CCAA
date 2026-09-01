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

## Reglas de balance

Las cantidades se conservan con su unidad. Sólo se comparan directamente entradas y salidas en la
misma unidad. En descremación, la diferencia medida entre litros de entrada y las dos salidas se
registra como merma explícita; no queda escondida en una fórmula.
