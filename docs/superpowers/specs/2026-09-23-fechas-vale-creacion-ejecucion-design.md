# Estandarización — fecha de creación y fecha de ejecución del vale

**Fecha:** 2026-09-23
**Pedido:** distinguir en el vale la fecha de creación de la fecha de ejecución.
**Antecedente:** `docs/superpowers/specs/2026-09-23-codigo-vale-automatico-design.md` — el
código del vale (`VE6266-01`) lo asigna el sistema al confirmar.

---

## 1. El problema

El vale tiene una sola fecha, `fecha`, que teclea el operador (por defecto, hoy) y que se
puede editar después de confirmar. De ella sale el código. Dos consecuencias:

- **Editar la fecha desincroniza el código.** Un vale `VE6266-01` al que se le cambia la
  fecha al 25 sigue llamándose `VE6266-01`: el código dice un día y la fecha otro.
- **La fecha no dice cuándo pasó nada.** Un vale se puede armar de noche y transferir de
  madrugada; el momento en que la leche se mezcló **no queda en el vale**. Solo aparece
  como `fecha_hora` en los movimientos de silo que genera `transferir`.

Además, el formulario proponía la fecha en UTC (`toISOString()`): en Chile (UTC-3), desde
las 21:00 marcaba el día siguiente. Se corrigió en `ea2fc70`, pero sigue siendo un dato
tecleado.

## 2. Decisiones

Tomadas con el usuario el 2026-09-23.

| Decisión | Elegido | Descartado |
|---|---|---|
| Fecha de ejecución | **La registra el sistema** al transferir | Declarada por el operador; o planificada + real |
| Campo «Fecha» del formulario | **Desaparece**: el operador no teclea fechas | Conservarlo como dato informativo |
| Enfoque | **A**: `fecha` pasa a ser la de creación, sellada; nuevo `ejecutado_en` | B: renombrar a `fecha_creacion`; C: derivar de timestamps existentes |

**Por qué el sistema y no el operador.** Las dos fechas describen hechos que ocurren
*dentro* del sistema —confirmar el vale, transferir la leche—, y el sistema ya los
presencia. Pedirlas a mano solo agrega una forma de equivocarlas.

**Por qué reutilizar `fecha` (A) y no renombrarla (B).** Sus consumidores —la lista de
vales y la guía de RC— ya la tratan como «el día del vale»; renombrarla toca el contrato
de la API, el frontend y las pruebas solo para ganar legibilidad. CLAUDE.md: extender el
modelo, no reescribirlo.

**Por qué no derivarlas (C).** `creado_en` es la hora en que se abrió el *borrador*, no la
de confirmación; y la ejecución obligaría a consultar el libro de movimientos cada vez que
se muestra un vale.

## 3. La regla

### 3.1 Fecha de creación — `fecha`, sellada al confirmar

`asignar_codigo()` —el método que el `save()` del vale ya llama para asignar el código—
**primero** hace `self.fecha = timezone.localdate()` y **después** compone el código desde
esa fecha. Las dos se escriben en el mismo guardado:

- **No pueden divergir**: la fecha de creación y el día del código son el mismo dato, sellado
  una sola vez.
- **Es la fecha local de Chile**: el servidor trabaja en `America/Santiago` con `USE_TZ`, así
  que `timezone.localdate()` no tiene el defecto UTC del navegador.
- Cubre los mismos caminos que el código: confirmación, creación directa, admin, scripts.

Mientras el vale es borrador, `fecha` lleva un valor **provisional** —el día en que se abrió—,
igual que el código lleva `BORRADOR-…`. No aparece en ninguna lista operativa y se reemplaza
al confirmar. Así la columna sigue siendo obligatoria y no hay migración de datos.

Esto **cambia la regla del código**: CLAUDE.md dice hoy *«el día sale de `vale.fecha`, no del
reloj»*. Pasa a ser: **el día es el de la confirmación, sellado junto al código**.

### 3.2 Fecha de ejecución — `ejecutado_en`, sellada al transferir

Campo nuevo, `DateTimeField`, nulo hasta la transferencia.

`servicios.transferir` lo sella con **el mismo `ahora`** (`timezone.now()`, línea ~123) que
usa para la `fecha_hora` de los movimientos de silo: la ficha del vale y el libro dicen
exactamente la misma hora.

`transferir` ocurre **una sola vez por vale** —al estado `transferido` solo se llega desde
`calculado` (`TRANSICIONES`)—, así que no hace falta comprobar si ya estaba lleno. Corregir
un vale (agregar leche) no lo toca: es la hora de la mezcla, no de sus ajustes.

## 4. Dónde cambia

### 4.1 Modelo — `backend/estandarizacion/models.py`

- `asignar_codigo()`: sella `self.fecha = timezone.localdate()` antes de calcular el prefijo;
  suma `"fecha"` a `update_fields` junto a `"codigo"`; elimina el guardia
  *«Falta la fecha del vale: sin ella no hay código»*, que ya no puede darse.
- `CAMPOS_OBLIGATORIOS_AL_CONFIRMAR` pierde `"fecha"`.
- Campo nuevo `ejecutado_en = models.DateTimeField("Ejecutado en", null=True, blank=True)`.

### 4.2 Migración

Una sola, de esquema: `AddField` de `ejecutado_en`. `fecha` no cambia de columna. Sin
migración de datos: los vales existentes conservan la fecha que se tecleó y quedan con
`ejecutado_en` vacío (el sistema parte en blanco; no hay datos reales que reconstruir).

### 4.3 Servicio — `backend/estandarizacion/servicios.py`

`transferir`: `vale.ejecutado_en = ahora`, y el guardado del vale pasa de
`update_fields=["estado", "responsable"]` a `["estado", "responsable", "ejecutado_en"]`.
`ahora` ya existe en ese punto: se calcula (~línea 123) antes del guardado (~línea 173).

### 4.4 Serializer, vistas y admin

- Serializer: `fecha` y `ejecutado_en` en `read_only_fields`; `ejecutado_en` en `fields`;
  `"fecha"` sale de la tupla de obligatorios de `validate()`.
- Un cliente antiguo que mande `fecha` **se ignora, no se rechaza** —mismo criterio que
  `codigo`—.
- `crear_borrador` sigue dando la fecha provisional con `timezone.localdate()` (ya lo hace
  cuando no llega en el cuerpo).
- Admin: `fecha` y `ejecutado_en` en `readonly_fields`.
- **Efecto conocido en `sembrar_flujo_demo --fecha X`**: el comando crea el vale con
  `fecha=X`, pero el sistema la reemplaza al asignar el código, así que el vale del flujo de
  demostración queda con la fecha del día en que se corre el comando, mientras el resto de
  los documentos del flujo lleva `X`. Es la consecuencia directa de §3.1 —la fecha la sella el
  sistema, no quien crea el vale— y se acepta en datos de demostración. No se agrega una
  excepción para el comando: sería una puerta para fechar vales a mano.

### 4.5 Frontend

- `pages/Estandarizacion/FormularioVale.tsx`: sale el campo «Fecha» (~línea 336) y `fecha`
  del estado, del borrador que se envía y de la recuperación. Se quita el `import` de
  `fechaLocalISO`, que deja de usarse aquí; el helper se queda en `services/fechas.ts` para
  las otras pantallas.
- `pages/Estandarizacion/Estandarizacion.tsx`, ficha del vale (grilla de `Dato`, ~línea 341):
  - **Creado**: `vale.fecha`.
  - **Ejecutado**: `ejecutado_en` en formato local de fecha y hora; si es nulo, *«Pendiente»*
    con el pie *«se registra al transferir»*.
- La lista de vales y la guía de RC siguen mostrando `fecha`, que ahora es la de creación.
- `services/estandarizacion.service.ts`: `ejecutado_en: string | null` en
  `ValeEstandarizacion`; `fecha` sale de `DatosBorradorVale`.

### 4.6 Documentación

CLAUDE.md, entrada «Código de vale»: el día del código es el de la confirmación, sellado
junto a `fecha`; y la ejecución la registra el sistema al transferir, con la misma hora del
libro de movimientos.

## 5. Pruebas

### 5.1 Backend

- **La confirmación sella la fecha**: con el reloj fijado (`patch` de
  `estandarizacion.models.timezone.localdate`), un vale confirmado queda con `fecha` = ese día
  y código de ese día, **aunque se haya creado con otra fecha**. Reemplaza a
  `test_el_dia_sale_de_la_fecha_del_vale_y_no_del_reloj`, que queda invertida a propósito.
- Un `PATCH` con `fecha` no la cambia.
- Una creación directa con `fecha` en el cuerpo la ignora y sella la de hoy.
- **`transferir` sella `ejecutado_en`** con exactamente la `fecha_hora` de los movimientos de
  silo que genera.
- Un vale sin transferir tiene `ejecutado_en` nulo.
- Ajustar `tests_codigo_vale.py`: las pruebas que hoy pasan `fecha=DIA` y esperan
  `VE6266-…` pasan a fijar el reloj en `DIA`.

### 5.2 Frontend

`npx tsc -b` y `npm test` limpios.

### 5.3 E2E — prueba de aceptación

`frontend/e2e/circuito-polvo.spec.ts` deja de rellenar «Fecha» en el vale (línea 337). La
cadena `circuito → evaporacion → flujo-polvo` tiene que seguir 4 de 4.

## 6. Fuera de alcance

- Las otras 10 pantallas que calculan la fecha en UTC (entre ellas `FormularioLote.tsx`):
  seguimiento aparte, con el helper `fechaLocalISO()`.
- Una fecha de ejecución *planificada*: descartada (§2).
- Reconstruir `ejecutado_en` de vales antiguos desde el libro de movimientos.
