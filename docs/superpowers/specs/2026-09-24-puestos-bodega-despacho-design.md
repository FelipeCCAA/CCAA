# Puestos de Bodega y Despacho

**Fecha:** 2026-09-24
**Origen:** revisión UX del módulo «Inventario y despacho»
(artifact `Ti8j2PBoFmVNx4rxxEUMbN`), sus tres tandas de mejora.
**Guía de criterio:** `.agents/skills/disenador-ux-industrial/SKILL.md`.

---

## 1. El problema

`/inventario` es un panel de consulta con los formularios al final. Para Bodega es al
revés: su trabajo es mover, y la información sirve solo para decidir un movimiento. La
revisión encontró, además:

| Severidad | Hallazgo | Dónde |
|---|---|---|
| Crítico | Cantidades crudas: «13.000» son 13 unidades y se lee trece mil | `OperacionesBodega.tsx:85, :94, :96` |
| Crítico | «Confirmar salida» despacha con un clic, sin resumen | `Inventario.tsx:215` |
| Alto | Las listas se cortan en la primera página (50) sin avisar | `inventario.service.ts:296-299` |
| Alto | Las acciones empiezan a 1.160 px, debajo de dos tablas | `Inventario.tsx:206` |
| Alto | El origen de un movimiento no dice su ubicación | `OperacionesBodega.tsx:85` |
| Alto | Un despacho admite un solo pallet (el backend acepta varios) | `OperacionesBodega.tsx:47` |
| Alto | Pantalla y servidor deciden distinto quién despacha | `access-control.ts:33` vs `inventario/views.py:63` |
| Alto | 12 pantallas de Abastecimiento inalcanzables desde `2430350` | `routes.tsx:141` |
| Alto | Número de despacho tecleado | `OperacionesBodega.tsx:87` |
| Alto | Formularios sin etiquetas ni búsqueda | `OperacionesBodega.tsx:83-100` |
| Medio | Tarjetas de kilos, pestañas duplicadas, tabla de ceros, movimientos sin datos, errores pegados | `Inventario.tsx` |

## 2. Decisiones

Tomadas con el usuario el 2026-09-24.

| Decisión | Elegido |
|---|---|
| Orden | **Directo a los puestos**: bases compartidas → backend → puestos nuevos que ya incorporan los arreglos de pantalla. No se parchea la pantalla que se reemplaza. |
| Abastecimiento | Lo de **bodega** (ubicaciones, materiales, recepción de compras, ajustes) entra a los puestos; **compras** (Compras, Proveedores, MRP, Pedidos, Calidad de materiales, No conformidades, Panel) vuelve a ser alcanzable como sección tal como está. |
| Número de despacho | **Automático** `DE` + año + día juliano + `-` + correlativo (`DE6267-01`), con **guía de despacho** opcional aparte. |

## 3. Lo que ya existe y no se rehace

El backend tiene casi todo; faltaba pantalla.

- Traslado de material entre ubicaciones (`movimientos/trasladar/`), salida (`movimientos/salida/`), ingreso de material (`movimientos/ingresar-material/`).
- Pallets: `producto-terminado/ingresar/` (de cuarentena a disponible, solo liberados) y `producto-terminado/{id}/transferir/` (entre ubicaciones).
- Ajustes con cuatro ojos: `ajustes/` (crear) y `ajustes/{id}/decidir/`. `decidir_y_aplicar_ajuste` ya rechaza «El solicitante no puede aprobar su propio ajuste» y el stock negativo.
- Despacho con varios pallets y graneles (`pallet_ids` y `graneles` son listas, `inventario/serializers.py:864`), y los campos `guia_despacho`, `transportista`, `patente` en el modelo.
- Un despacho no se borra (`Despacho.delete` lo impide) y el número es único por planta (`despacho_numero_sucursal`).
- `MovimientoInventario` guarda tipo, cantidad, origen, destino, usuario, fecha y motivo; `MovimientoProductoTerminado`, lo mismo para pallets.
- Capacidades en la sesión (`usuario.capacidades`): bodega → `inventario_transferir`, `inventario_ajustar`; despacho → `despacho_crear`; aparte, `despacho_autorizar`.

## 4. Estructura

### 4.1 Navegación

| Entrada | Ruta | Acceso | Abre en |
|---|---|---|---|
| **Bodega** | `/bodega` | área bodega o admin | pendientes + acciones |
| **Despacho** | `/despacho` | capacidad `despacho_crear` o `despacho_autorizar` | hojas de carga por estado |
| **Existencias** | `/inventario` | lectura, como hoy | consulta |
| **Abastecimiento** | `/abastecimiento/*` | como antes de `2430350` | compras |

Se quita `<Navigate to="/inventario">` de `/abastecimiento/*` y se restauran sus rutas hijas,
sin las cuatro de bodega. Los accesos por área se declaran en `access-control.ts` y el menú en
`navegacion-operacional.ts`.

### 4.2 Bases compartidas (tanda 1)

1. **Listas completas.** `lista()` sigue `next` hasta la última página; se usa solo donde se
   necesita el conjunto completo y es acotado. Las listas largas que se muestran se paginan
   en el servidor (§4.6), y los selectores buscan en el servidor.
2. **Cantidades.** Una función `cantidad(valor, unidad)` en `services/formato.ts` con
   `Intl.NumberFormat("es-CL")`. Ninguna cantidad cruda en pantalla: se reemplazan todas las
   del módulo.
3. **Permisos de despacho.** `puedeDespachar(usuario)` y `puedeAutorizarDespacho(usuario)`
   deciden solo con `usuario.capacidades`. El superusuario queda cubierto: `capacidades_de()`
   le devuelve todos los permisos (`usuarios/permisos_industriales.py:81`). Nunca con el rol ni
   el área.
4. **Componentes.** `ConfirmarAccion` (panel con resumen y botón de confirmar) para toda
   operación irreversible; `CampoEtiquetado` con `<label>` visible; `BuscadorCodigo` (campo con
   foco que acepta tecleo o lector de código de barras y dispara la búsqueda con Enter).

### 4.3 Puesto de Bodega — `/bodega`

- **Buscador** arriba, con foco al entrar: código de pallet, lote o material. El resultado abre
  una **ficha** (qué es, ubicación, cantidad con unidad, estado de Calidad) con las acciones
  que le corresponden.
- **Acciones**: *Recibir material*, *Reubicar*, *Consumir*, *Ajustar por conteo*. Cada una abre
  un **panel guiado**: 1) qué, 2) adónde y cuánto (solo destinos válidos; cantidad con unidad),
  3) **resumen y confirmar**. Al terminar, el panel dice el movimiento y el saldo resultante.
- **Pendientes** (`inventario/pendientes-bodega/`), cada fila con su acción:
  - pallets liberados en ubicación de cuarentena → **Reubicar** (usa `producto-terminado/ingresar/`);
  - material en cuarentena → informativo (lo decide Calidad);
  - bajo mínimo → informativo;
  - ajustes pendientes → **Aprobar / Rechazar**, solo si el usuario no es el solicitante.
- **Configuración** (pestaña secundaria): ubicaciones y materiales, reusando `Bodegas.tsx` y
  `Materiales.tsx`.
- **Recepción de compras** reusa `Abastecimiento/Recepcion.tsx` como pestaña del puesto.

### 4.4 Puesto de Despacho — `/despacho`

- **Hojas de carga** en tres grupos: *Borrador*, *Autorizada*, *Despachada hoy*.
- **Nueva hoja de carga**: cliente, transportista, patente, guía de despacho (opcional); se
  **agregan varios pallets** (buscador o marcando de la lista de disponibles) y graneles, con
  **total de pallets y kg** siempre visible. El número lo asigna el sistema.
- **Autorizar** y **Ejecutar salida** son botones visualmente distintos. Ejecutar abre
  `ConfirmarAccion` con cliente, pallets, kg y ubicaciones de origen.
- **Cancelar**, con motivo, mientras no esté despachada.
- Los botones se muestran según `puedeDespachar` / `puedeAutorizarDespacho` (§4.2).

### 4.5 Existencias — `/inventario`

Consulta de solo lectura. Pestañas: *Materiales*, *Producto terminado*, *Movimientos de
materiales*, *Movimientos de pallets*. Todas paginadas en el servidor, con filtro de texto,
estado, ubicación y rango de fechas. Movimientos con tipo legible (etiqueta del `TextChoices`),
cantidad con unidad, *origen → destino*, usuario y fecha. Errores por pestaña, no pegados.
Rework conserva su pestaña. `OperacionesBodega.tsx` desaparece.

### 4.6 Backend nuevo

1. **Número de despacho.** Al crear, `numero = DE` + último dígito del año + día juliano (3) +
   `-` + correlativo del día (2+), sobre la fecha local de creación. Máximo existente con ese
   prefijo en la planta, más uno; reintento ante colisión dentro de un savepoint, hasta 5
   intentos, como `ValeEstandarizacion.asignar_codigo`. `numero` pasa a solo lectura en el
   serializer; un cliente que lo mande se ignora.
2. **Un pallet, una hoja de carga activa.** Hoy nada impide que el mismo pallet entre en dos
   despachos en borrador o autorizados; el segundo recién falla al ejecutar. Al crear, se
   rechaza un pallet que ya esté en otro despacho `borrador` o `autorizado`, nombrando ese
   despacho en el motivo. La lista de pallets disponibles para cargar los excluye.
3. **Cancelar despacho.** `POST despachos/{id}/cancelar/` con `motivo` obligatorio; solo desde
   borrador o autorizado. Al pasar a `cancelado`, sus pallets vuelven a estar disponibles para
   otra hoja de carga (efecto directo de la regla 2). Mismo permiso que autorizar.
4. **Pendientes de bodega.** `GET inventario/pendientes-bodega/` devuelve: pallets disponibles en
   ubicación de cuarentena; lotes de material en cuarentena; materiales con disponible ≤
   mínimo; ajustes pendientes. Acotado por tenant.
5. **Búsqueda y filtros** en `existencias/`, `producto-terminado/`, `movimientos/` y
   `movimientos-producto-terminado/`: `q` (código de lote, pallet, material), `estado`,
   `ubicacion`, `desde`, `hasta`. Implementados en `get_queryset`, sin dependencias nuevas.

## 5. Pruebas

- **Backend**: número de despacho (formato, correlativo, colisión, ignora el del cliente);
  un pallet en dos hojas activas se rechaza, y vuelve a poder cargarse tras cancelar;
  cancelar (motivo obligatorio, estados permitidos, no desde despachado);
  pendientes (cada grupo, tenant); filtros (`q`, `estado`, `ubicacion`, fechas).
- **Frontend (unitarias, `node --test`)**: `cantidad()` (miles, decimales, unidad); `lista()`
  que recorre páginas; `puedeDespachar` / `puedeAutorizarDespacho` desde capacidades.
- **Tipos y lint**: `npx tsc -b` y ESLint limpios.
- **E2E de aceptación**: la cadena `circuito → evaporacion → flujo-polvo` sigue 4/4 (su paso
  final verifica el pallet en Inventario y puede requerir ajustar selectores a la nueva
  pantalla); la auditoría de accesibilidad no suma reglas nuevas en las pantallas nuevas.

## 6. Fuera de alcance

- Rediseñar las pantallas de compras (Compras, MRP, Proveedores…): vuelven como están.
- Integración con hardware de etiquetas o lectores más allá del modo teclado.
- Cambiar reglas de negocio de inventario (FEFO, cuarentena, reservas).
