# Inventario y roles — dónde engancha, y qué no duplicar

> Para el módulo de **inventario** (materias primas distintas de la leche, y producto terminado)
> y el de **administración de roles**. Escrito el 2026-07-31 contra `main` en `5c96843`.
>
> No es una especificación de lo que hay que construir: es el mapa de lo que **ya existe** y de
> las costuras que quedaron preparadas, para que las dos mitades encajen en vez de competir.

---

## 1. La regla que gobierna todo el stock del sistema

**El saldo no se guarda: se deriva de un libro de movimientos.**

Está aplicada hoy en los silos (`recepcion.MovimientoSilo` + `recepcion.dominio.ocupacion_silo`)
y es la misma decisión que hace que el veredicto de calidad y el avance del checklist tampoco se
persistan (`prototipo/MODELO_DATOS.md` §2.2). Del docstring del modelo:

> Nunca se edita la ocupación: se agrega un movimiento. Un error se corrige con un ajuste que
> deja rastro, no borrando el histórico.

Por qué importa para el inventario nuevo: si un producto guarda un campo `stock` que alguien
edita, y además existen movimientos, hay **dos verdades para la misma cantidad**. La escrita a
mano gana en pantalla mientras el libro dice otra cosa, y la diferencia no aparece hasta que
alguien la busca. La forma probada es un asiento por cada entrada, salida y ajuste, y el saldo
como suma.

`MovimientoSilo` ya tiene esa forma —`Tipo` (ingreso/salida/ajuste) y `OrigenTipo`
(recepcion/lote/ajuste)— y sirve de plantilla para el libro de otras materias primas. **No hace
falta reutilizar la tabla**: un silo tiene capacidad en litros y una bodega de sacos no, así que
un modelo hermano con la misma estructura es más honesto que forzar el existente.

---

## 2. Materias primas que no son leche

Hoy no existen: **0 productos con `naturaleza = materia_prima`** y **0 componentes de receta**
cargados. La lecitina, la sal, los sacos de papel, el film y las cajas están en el Excel de
recetas (`docs/levantamiento-2026-07/Recetas_Cod_Producto.xlsx`, hojas «Recetas (detalle)» y
«Resumen por receta»: lista de materiales por 100 kg) pero nunca se sembraron.

### Lo que ya está construido y espera datos

`maestros.Receta` + `RecetaComponente` con **explosión multinivel** (`maestros/recetas.py`):
la mantequilla sale de crema y la crema de leche, así que `explosionar` baja por el árbol hasta
la materia prima. Está probado y hoy no tiene de qué tirar.

La función que conecta receta e inventario:

```python
litros_de_leche(productos, recetas, producto_id, kilos, fecha, materia_prima_id=None)
```

El nombre habla de leche por su primer uso, pero `materia_prima_id` **ya acota a cualquier
materia prima concreta cuando la receta consume varias**. Es decir: cuánta lecitina consume un
lote de 1.000 kg sale de ahí sin escribir nada nuevo. Si el nombre estorba, renombrarla es
seguro — tiene un solo llamador (`produccion/views.py`, `_litros_de_receta`).

### Lo que devuelve `None`, y por qué no hay que rellenarlo

`explosionar` devuelve `None` si la cadena está incompleta: un producto intermedio sin receta, o
un ciclo. Del docstring:

> descontar una cantidad inventada de un silo es peor que no descontar nada: el saldo mentiría
> sin que nadie lo note.

El inventario tiene que respetar eso. Un consumo que no se puede calcular se informa, no se
estima.

### La decisión que sigue abierta

`produccion` registra hoy la **asignación de leche declarada por el operador**, no derivada de la
receta (`POST /api/produccion/lotes/<id>/asignacion/`). Fue deliberado: el libro del silo guarda
lo que realmente se sacó, y lo que la receta decía es otra cosa —su diferencia es el rendimiento
real del lote—.

Para los demás materiales hay que decidir lo mismo: **¿se declaran o se derivan de la receta?**
Declarar exige que alguien cuente sacos; derivar da un número consistente pero ficticio. La
respuesta puede ser distinta por material (los sacos se cuentan, la lecitina se deriva), y
conviene que sea explícita antes de escribir el modelo.

---

## 3. Producto terminado

`Despacho` **no existe todavía**, y el hueco está marcado en el código. De
`produccion/dominio.py`:

```python
def kg_disponibles(lote, kg_despachados=0):
    """
    Los despachos aún no existen como entidad, así que por ahora recibe el
    total despachado como parámetro. Cuando exista el módulo, se calculará
    desde ahí sin cambiar la firma para quien llame.
    """
```

Ese es el punto de enganche: cuando exista `Despacho`, esta función lo suma y **nadie más cambia**.
Devuelve `None` si el lote todavía no declaró kilos, que es el caso de un lote en proceso.

### Lo que el inventario consume y no debe reimplementar

`calidad.Liberacion.puede_despachar` ya decide si el producto puede salir. Del modelo:

> ¿El producto puede salir? Es lo único que Despachos necesita saber.

Un lote no liberado no se despacha, y esa decisión tiene detrás el checklist de 19 documentos, el
veredicto de calidad y —desde hoy— el PCC 1 y los PPRO. El inventario **pregunta**; no vuelve a
juzgar.

### FEFO

El backlog lo pide (#14: regla y seguimiento FEFO en el despacho). `Lote.vencimiento` ya existe y
es el campo con el que se ordena.

---

## 4. Roles

Lo que hay: `usuarios.Rol` (cinco valores como `TextChoices`), `usuarios.PerfilUsuario` (asigna el
rol, el cargo y el área) y `usuarios.permisos.PermisoPorRol` con cuatro clases —
`EscribeAdministracion`, `EscribeProduccion`, `EscribeRecepcion`, `EscribeCalidad`—.

### La línea que no puede romperse

```python
# calidad/dominio.py
ROLES_AUTORIZADORES = ("calidad", "admin")
```

Está **duplicada a propósito** como texto, para que el dominio de calidad no dependa de Django y
se pueda probar sin base de datos. Hay una prueba que vigila la duplicación: si alguien renombra
un rol en `usuarios.Rol` y no aquí, la prueba lo detiene.

Si los roles pasan a ser un modelo editable, esa prueba deja de tener con qué comparar y hay que
decidir cómo se mantiene la garantía de que **solo Calidad y Administración firman una
liberación**. No es una preferencia administrativa: es la regla central del sistema.

Sugerencia: que el modelo de rol traiga un campo `autoriza_liberacion` y que la prueba compare
`ROLES_AUTORIZADORES` contra los roles que lo tengan marcado. Es lo mismo que se hizo con
`Equipo.consume_leche`, que reemplazó una tupla fija por un campo del maestro sin perder la regla
(ver `CLAUDE.md`, «Decisiones vigentes»).

### Auditoría

Cualquier cambio de rol o de perfil **ya queda auditado**: `usuarios` está en `APPS_AUDITADAS`
(`auditoria/registro.py`), así que se registra quién lo cambió y de qué a qué. No hay que hacer
nada para eso, pero conviene saberlo antes de agregar un registro propio de cambios de rol.

---

## 5. Cosas del proyecto que cuestan tiempo si se descubren tarde

Están todas en `CLAUDE.md` («Trampas conocidas»), pero estas tres muerden en un módulo nuevo:

1. **Las migraciones de datos siembran también la base de pruebas.** Un `create()` en `setUp` con
   una clave que la siembra ya insertó choca con la unicidad: usar `update_or_create`.
2. **`frontend/tsconfig.json` es de tipo solución**, así que `npx tsc --noEmit` a secas no
   comprueba nada y sale con 0. Usar `npx tsc -b`.
3. **Dentro de `transaction.atomic()`, salir con `return` confirma la transacción**; solo una
   excepción revierte. Un `return Response(...)` de validación a mitad de un lote de escrituras
   deja media operación guardada.

Y una de DRF que apareció esta semana: **los campos que participan en una `UniqueConstraint` son
obligatorios** aunque el modelo los declare `blank=True`. `required=False` no basta; hace falta
además un `default` en `extra_kwargs`.

---

## 6. Resumen de la frontera

| Área | Quién | Estado |
|---|---|---|
| Leche en silos | ya hecho | `MovimientoSilo` + `ocupacion_silo` |
| Asignación de leche a lote | ya hecho | declarada por Producción, con trazabilidad |
| Otras materias primas | **inventario** | no existe: 0 productos, 0 componentes |
| Producto terminado / despachos | **inventario** | `Despacho` no existe; `kg_disponibles` espera |
| Explosión de recetas | ya hecho | multinivel, probada, sin datos |
| Liberación y su checklist | ya hecho | `puede_liberar`, 19 documentos |
| PCC 1 y PPRO | ya hecho | bloquean la liberación, con captura |
| Roles y permisos | **roles** | `Rol` fijo hoy; ojo con `ROLES_AUTORIZADORES` |
| Plantillas de los 19 documentos | en curso | hoy son atestación |
