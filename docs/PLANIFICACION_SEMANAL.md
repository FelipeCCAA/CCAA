# Planificación semanal de planta

El módulo reemplaza la operación semanal del Excel sin convertir sus celdas en tablas. La fuente de verdad es el programa de actividades y los movimientos de leche; consumo, stock y utilización siempre se derivan.

## Entidades reutilizadas

- `SemanaPlan`: semana lunes 00:00 a domingo 24:00, con estados borrador, publicada, cerrada y cancelada.
- `Equipo`: recursos de planta. Incluye Scheffers 2, Scheffers 3, VEB, Egron/Línea 1, Egron/Línea 2 y Línea de Mantequilla.
- `Producto`, `Mandante`, `OrdenProduccion`, `ClienteDespacho` y `User`: catálogos existentes. No se duplican.
- `BloquePlan`: actividad programada. Mantiene los campos horarios antiguos y agrega fecha/hora, tipo catalogado, producto, orden, origen, cliente, capacidad congelada y color.
- `Recepcion` y `Despacho`: hechos reales que continúan en sus módulos. `MovimientoPlan` guarda solamente la proyección semanal.
- `RegistroAuditoria`: registra automáticamente quién creó o modificó semanas, actividades, capacidades y movimientos.

## Entidades nuevas

- `TipoActividadPlan`: Producción, Aseo, PNP, Mantenimiento, Preparación, Atraso de partida, Recepción, Despacho, Trasvasije, Ensayo y Capacitación.
- `CapacidadProceso`: capacidad por equipo y fecha de vigencia. La actividad copia la capacidad aplicable para que una modificación futura no cambie el histórico.
- `MovimientoPlan`: stock inicial, recepción, despacho, trasvasije de entrada/salida o ajuste identificado por propietario.
- `StockSeguridadPlan`: mínimo por propietario con vigencia.
- `VersionSemanaPlan`: fotografía inmutable generada en cada publicación.

El tipo de actividad “Mantenimiento” solo reserva tiempo del recurso. No habilita el módulo de Mantención, que permanece desactivado.

## Reglas

- Consumo: horas solapadas con cada día × capacidad congelada de la actividad.
- Stock: stock anterior + entradas − consumo − despachos − trasvasijes de salida + trasvasijes de entrada ± ajustes identificados.
- El saldo se conserva por `Mandante`; nunca se compensa silenciosamente un propietario con otro.
- Dos actividades del mismo equipo no pueden solaparse, incluso al cruzar medianoche.
- Solo una semana en borrador admite cambios.
- Publicar conserva una versión. Reabrir, modificar y volver a publicar crea otra versión en lugar de sobrescribir la anterior.
- Las semanas antiguas siguen funcionando con `BalanceDia`; las nuevas pueden incorporar movimientos explícitos gradualmente.

## API

- `GET/POST /api/planificacion/semanas/`
- `POST /api/planificacion/semanas/{id}/duplicar/`
- `POST /api/planificacion/semanas/{id}/publicar/`
- `POST /api/planificacion/semanas/{id}/reabrir/`
- `POST /api/planificacion/semanas/{id}/cerrar/`
- `GET /api/planificacion/semanas/{id}/programa/`: actividades, balances, indicadores, alertas, movimientos y versiones en una llamada.
- `GET /api/planificacion/semanas/{id}/comparar-versiones/?desde=1&hasta=2`
- CRUD `/api/planificacion/bloques/`, `/movimientos/`, `/capacidades/` y `/stocks-seguridad/`.
- Lectura `/api/planificacion/tipos-actividad/` y `/versiones/`.

Producción/Planificación puede escribir. Calidad conserva acceso de consulta transversal; el backend rechaza sus POST, PATCH y DELETE. Administración mantiene acceso completo.

## Interfaz

La pantalla `/planificacion` ofrece zoom de 1, 2, 4 y 8 horas. El centro de un bloque lo mueve y los bordes cambian su duración, con ajuste a 30 minutos. Cada cambio se valida en el backend y vuelve a cargar el programa completo, por lo que consumo, stock, utilización y alertas quedan sincronizados inmediatamente.
