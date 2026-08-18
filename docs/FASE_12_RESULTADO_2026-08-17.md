# Fase 12 · Inventario y despacho

## Hallazgo y problema

El inventario existente cubría insumos, MRP, compras, reservas y consumo, pero no producto terminado. Los pallets terminaban en Calidad sin ubicación física ni documento de despacho.

## Arquitectura e implementación

- Se mantuvo `PalletProducto` como unidad física y se creó un libro separado del inventario de materiales.
- `ExistenciaProductoTerminado` conserva una ubicación vigente por pallet.
- `MovimientoProductoTerminado` registra ingreso, transferencia y despacho con operación UUID e historial inmutable.
- `ClienteDespacho`, `Despacho` y `DetalleDespacho` separan borrador, autorización y salida física.
- Los servicios usan `transaction.atomic()` y `select_for_update()`; validan planta, disponibilidad, liberación vigente y compromiso en otro despacho.
- La salida se revalida contra Calidad, aunque el despacho ya estuviera autorizado, y repetirla no duplica movimientos.
- API: `clientes-despacho`, `producto-terminado`, `movimientos-producto-terminado` y `despachos`, con acciones `ingresar`, `transferir`, `autorizar` y `ejecutar`.
- Frontend: nueva pestaña **Abastecimiento → Producto terminado** con stock por pallet y flujo de despacho.

## Archivos, migraciones, permisos y riesgos

Se modificaron `inventario/models.py`, `servicios.py`, `serializers.py`, `views.py`, `urls.py`, los servicios/rutas React y se añadió `ProductoTerminado.tsx`. Migraciones `inventario/0021` y `0022`. Se reutilizan `despacho_crear`, `despacho_autorizar` e `inventario_transferir`; la autoridad permanece en backend. El riesgo principal —dos despachos sobre el mismo pallet— queda bloqueado al autorizar y nuevamente al ejecutar.

## Tests

`inventario/tests_producto_terminado.py` cubre rechazo sin Calidad, ingreso, salida idempotente y bloqueo posterior a la autorización. También pasaron los 58 tests históricos de Inventario.
