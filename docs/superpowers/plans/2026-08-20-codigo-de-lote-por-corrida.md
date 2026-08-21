# Código de lote por corrida — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sacar el SKU del código de lote y reemplazarlo por la máquina de la corrida, de modo que el código identifique **una corrida** y no describa el producto.

**Architecture:** El código pasa a ser `CCAA` + último dígito del año + día juliano + **sigla del equipo** + `-` + correlativo del día en esa máquina. La sigla es un campo nuevo del maestro de equipos —configurable, no un mapa en el código—, porque `Equipo.codigo` es un slug de hasta 19 caracteres (`carga_precondensado`) y no cabe en un identificador. El correlativo pasa a contarse por `(fecha, equipo)` en vez de por `(producto, fecha)`, y la unicidad se garantiza en la base sobre el código solo.

**Tech Stack:** Django REST + PostgreSQL, TypeScript + React.

**Decisiones de planta que fijan este diseño** (respondidas el 2026-08-20):

- **Una corrida de torre es un lote, sin importar el turno.** Una corrida que cruza del turno A al B es **un** lote. `Lote.turno` sigue siendo informativo y no entra en el código.
- **Dos formatos de envase son el mismo lote.** No hace falta un nivel de sublote de envasado; `RegistroEnvase` y `PalletProducto` ya cuelgan del lote.
- **Un aseo intermedio parte el lote solo si hubo un tema de inocuidad**, no si es parte normal del proceso. El sistema **no puede deducirlo**: es una declaración de quien opera, y por eso es una acción explícita con motivo obligatorio.

## Global Constraints

- **El sistema parte en blanco**: no hay códigos de lote emitidos, así que este cambio **no arrastra migración de datos ni reimpresión**. No escribir código de compatibilidad con el formato anterior.
- **PostgreSQL** es el motor (`DECISIONES.md` §001).
- **Español** en UI, datos, nombres de campo y comentarios. Fechas ISO `YYYY-MM-DD`.
- Las reglas puras van en `dominio.py`, sin ORM, y se cubren en `tests_dominio*.py`.
- **`codigo_lote_valido` avisa, no restringe**: no colgarlo del `clean()` de `Lote`.
- Las decisiones devuelven **motivos**, no booleanos.
- Después de `makemigrations`, correr `migrate`: el runner migra solo la base de pruebas.
- Las migraciones de datos siembran también la base de pruebas: usar `update_or_create`, nunca `create`.
- Comandos del backend desde `backend/`: `.venv\Scripts\python.exe manage.py ...`
- Frontend: comprobar con **`npx tsc -b`**.

---

### Task 1: La sigla del equipo

**Files:**
- Modify: `backend/maestros/models.py` (campo en `Equipo`)
- Create: `backend/maestros/migrations/0024_equipo_sigla.py` (la genera `makemigrations`)
- Create: `backend/maestros/migrations/0025_sembrar_siglas.py` (migración de datos, escrita a mano)
- Modify: `backend/maestros/serializers.py`, `backend/maestros/admin.py`
- Create: `backend/maestros/tests_sigla.py`

**Interfaces:**
- Produces: `Equipo.sigla` — `CharField(max_length=3, blank=True)`, único por sucursal cuando no está vacío, con constraint `equipo_sigla_unica_sucursal`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `backend/maestros/tests_sigla.py`:

```python
"""
La sigla del equipo: lo que entra en el código de lote.

`Equipo.codigo` es un slug pensado para identificar y comparar
(`carga_precondensado`, 19 caracteres). Meterlo en un código impreso daría
`CCAA6232carga_precondensado-01`. La sigla es corta, estable y **se
configura**: no es un mapa en el código, porque qué máquinas tiene esta
planta es configuración del despliegue.
"""

from django.db.utils import IntegrityError
from django.test import TestCase

from maestros.models import Equipo


class SiglaDeEquipoTests(TestCase):
    def test_los_equipos_sembrados_traen_su_sigla(self):
        self.assertEqual(Equipo.objects.get(codigo="e1").sigla, "E1")
        self.assertEqual(Equipo.objects.get(codigo="scheffers2").sigla, "S2")
        self.assertEqual(Equipo.objects.get(codigo="rovema4").sigla, "R4")

    def test_dos_equipos_no_comparten_sigla(self):
        """
        Dos siglas iguales producen dos corridas distintas con el mismo
        código de lote, que es exactamente lo que este cambio viene a
        impedir.
        """
        e1 = Equipo.objects.get(codigo="e1")

        with self.assertRaises(IntegrityError):
            Equipo.objects.create(
                sucursal_id=e1.sucursal_id,
                codigo="torre-nueva",
                nombre="Torre nueva",
                tipo=e1.tipo,
                sigla="E1",
            )

    def test_la_sigla_vacia_puede_repetirse(self):
        """
        Un equipo que no encabeza lotes no necesita sigla. Exigirla a todos
        obligaría a inventar dos letras para una bomba.
        """
        e1 = Equipo.objects.get(codigo="e1")
        Equipo.objects.create(
            sucursal_id=e1.sucursal_id, codigo="bomba-1", nombre="Bomba 1",
            tipo=e1.tipo, sigla="",
        )
        Equipo.objects.create(
            sucursal_id=e1.sucursal_id, codigo="bomba-2", nombre="Bomba 2",
            tipo=e1.tipo, sigla="",
        )

        self.assertEqual(Equipo.objects.filter(sigla="").count(), 2)
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

```
cd backend
.venv\Scripts\python.exe manage.py test maestros.tests_sigla -v 2
```

Esperado: FAIL — `TypeError: Equipo() got unexpected keyword arguments: 'sigla'`

- [ ] **Step 3: Agregar el campo**

En `backend/maestros/models.py`, dentro de `Equipo`, después de `nombre`:

```python
    sigla = models.CharField(
        "Sigla",
        max_length=3,
        blank=True,
        help_text=(
            "Dos o tres caracteres que identifican la máquina dentro del código "
            "de lote (E1, S2, R4). Solo la necesitan los equipos que encabezan "
            "una corrida."
        ),
    )
```

Y en su `Meta.constraints`, agregar:

```python
            models.UniqueConstraint(
                fields=["sucursal", "sigla"],
                condition=~models.Q(sigla=""),
                name="equipo_sigla_unica_sucursal",
            ),
```

- [ ] **Step 4: Generar la migración de esquema**

```
cd backend
.venv\Scripts\python.exe manage.py makemigrations maestros --name equipo_sigla
```

- [ ] **Step 5: Escribir la migración de datos**

Crear `backend/maestros/migrations/0025_sembrar_siglas.py`. Ajustar el número y la
dependencia al nombre real que generó el paso anterior:

```python
"""
Siglas de los equipos que encabezan una corrida.

Se siembran porque los equipos también se siembran por migración: dejar la
sigla vacía haría que ningún lote pudiera proponer su código recién
instalado. Las que no encabezan corrida quedan en blanco a propósito.
"""

from django.db import migrations

SIGLAS = {
    "e1": "E1",
    "e2": "E2",
    "veb": "VB",
    "scheffers2": "S2",
    "scheffers3": "S3",
    "rovema3": "R3",
    "rovema4": "R4",
    "linea_mantequilla": "LM",
}


def sembrar(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")
    for codigo, sigla in SIGLAS.items():
        Equipo.objects.filter(codigo=codigo).update(sigla=sigla)


def revertir(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")
    Equipo.objects.filter(codigo__in=SIGLAS).update(sigla="")


class Migration(migrations.Migration):

    dependencies = [("maestros", "0024_equipo_sigla")]

    operations = [migrations.RunPython(sembrar, revertir)]
```

- [ ] **Step 6: Aplicar y verificar**

```
cd backend
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py test maestros -v 2
```

Esperado: PASS

- [ ] **Step 7: Exponer la sigla en el maestro**

En `backend/maestros/serializers.py`, agregar `"sigla"` a la lista `fields` del
serializer de `Equipo`. En `backend/maestros/admin.py`, agregar `"sigla"` a
`list_display` de `EquipoAdmin`.

Correr de nuevo `manage.py test maestros usuarios -v 2` y confirmar PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/maestros/models.py backend/maestros/migrations/ backend/maestros/serializers.py backend/maestros/admin.py backend/maestros/tests_sigla.py
git commit -m "Sigla del equipo: lo corto y estable que entra en el código de lote"
```

---

### Task 2: El código nuevo, en el dominio puro

**Files:**
- Modify: `backend/produccion/dominio.py`
- Modify: `backend/produccion/tests_codigo_lote.py` (se reescribe)

**Interfaces:**
- Consumes: nada del ORM.
- Produces: `generar_codigo_lote(fecha, sigla, correlativo=1) -> str | None` y `codigo_lote_valido(codigo) -> bool`. **La firma cambia**: el segundo parámetro era el SKU y ahora es la sigla del equipo.

- [ ] **Step 1: Reescribir las pruebas**

Reemplazar el contenido de `backend/produccion/tests_codigo_lote.py`:

```python
"""
El código de lote identifica una corrida, no describe un producto.

Antes llevaba el SKU de 12 dígitos adentro. Eso lo hacía largo (23
caracteres) y, sobre todo, lo ataba a un **valor derivado**: `Producto.save()`
recalcula el SKU desde los atributos, así que corregir la categoría de un
producto dejaba códigos ya impresos describiendo algo que ese producto ya no
era. Un identificador que codifica datos hay que reemitirlo cuando el dato
cambia; uno que identifica una corrida no envejece.

La corrida se identifica por **día y máquina**, que es lo que el POE.009.02
codificaba con el dígito de torre antes de que el esquema del SKU lo perdiera.
"""

from datetime import date

from django.test import TestCase

from .dominio import codigo_lote_valido, generar_codigo_lote


class GenerarCodigoLoteTests(TestCase):
    fecha = date(2026, 8, 20)  # día juliano 232

    def test_arma_el_codigo_con_anio_dia_juliano_sigla_y_correlativo(self):
        self.assertEqual(generar_codigo_lote(self.fecha, "E1"), "CCAA6232E1-01")

    def test_el_correlativo_va_siempre_desde_01(self):
        """
        Ponerlo solo a partir del segundo lote deja dos formas conviviendo, y
        quien lee, ordena o busca tiene que conocer la excepción.
        """
        self.assertTrue(generar_codigo_lote(self.fecha, "E1").endswith("-01"))

    def test_el_correlativo_distingue_dos_corridas_de_la_misma_maquina(self):
        primero = generar_codigo_lote(self.fecha, "E1", 1)
        segundo = generar_codigo_lote(self.fecha, "E1", 2)

        self.assertNotEqual(primero, segundo)
        self.assertEqual(segundo, "CCAA6232E1-02")

    def test_dos_maquinas_el_mismo_dia_no_comparten_codigo(self):
        """
        Es lo que el esquema anterior no distinguía: el mismo producto secado
        en las dos torres a la vez son dos lotes, y el POE viejo lo codificaba
        justamente por eso.
        """
        torre1 = generar_codigo_lote(self.fecha, "E1", 1)
        torre2 = generar_codigo_lote(self.fecha, "E2", 1)

        self.assertNotEqual(torre1, torre2)

    def test_sin_sigla_no_hay_codigo(self):
        """
        Es lo único que el sistema no puede deducir. Componerlo con un relleno
        inventado imprimiría en el saco algo que no identifica la corrida.
        """
        self.assertIsNone(generar_codigo_lote(self.fecha, ""))
        self.assertIsNone(generar_codigo_lote(self.fecha, None))

    def test_el_correlativo_de_tres_digitos_no_se_recorta(self):
        self.assertEqual(generar_codigo_lote(self.fecha, "E1", 100), "CCAA6232E1-100")

    def test_el_primero_de_enero_es_el_dia_001(self):
        self.assertEqual(generar_codigo_lote(date(2026, 1, 1), "E1"), "CCAA6001E1-01")


class CodigoLoteValidoTests(TestCase):
    def test_acepta_la_forma_vigente(self):
        self.assertTrue(codigo_lote_valido("CCAA6232E1-01"))
        self.assertTrue(codigo_lote_valido("CCAA6232VB-100"))

    def test_rechaza_el_formato_anterior_con_sku(self):
        self.assertFalse(codigo_lote_valido("CCAA6212010102010201-01"))

    def test_rechaza_basura(self):
        self.assertFalse(codigo_lote_valido(""))
        self.assertFalse(codigo_lote_valido(None))
        self.assertFalse(codigo_lote_valido("LOTE-1"))
```

- [ ] **Step 2: Correr y verificar que falla**

```
cd backend
.venv\Scripts\python.exe manage.py test produccion.tests_codigo_lote -v 2
```

Esperado: FAIL — el generador todavía arma el formato con SKU.

- [ ] **Step 3: Reemplazar la función y el patrón**

En `backend/produccion/dominio.py`, reemplazar `_PATRON_CODIGO` y
`generar_codigo_lote` por:

```python
# La sigla son 1 a 3 caracteres en mayúsculas o dígitos; el correlativo, dos o
# más. El formato anterior —con el SKU de 12 dígitos— no valida contra esto, y
# está bien: `codigo_lote_valido` avisa, no restringe, así que un código viejo
# se puede registrar igual y la pantalla dirá que no sigue la forma vigente.
_PATRON_CODIGO = re.compile(r"^CCAA\d{4}[A-Z0-9]{1,3}-\d{2,}$")


def generar_codigo_lote(fecha: date, sigla: str, correlativo: int = 1) -> str | None:
    """
    Arma el código de una corrida: CCAA + año + día juliano + sigla + correlativo.

    Identifica **una corrida**, no describe un producto. El producto, el turno
    y el vale son campos del lote y están indexados; meterlos en el código los
    duplicaría, y un identificador que carga datos envejece cuando esos datos
    cambian.

    La sigla sale de `Equipo.sigla`, que es configuración del maestro. Devuelve
    `None` si falta: es lo único que no se puede deducir, y un relleno
    inventado imprimiría en el saco algo que no identifica la corrida.

    Es una función pura. **No garantiza unicidad**: eso lo hace la restricción
    `lote_codigo_unico_sucursal` en la base.
    """
    limpia = (sigla or "").strip().upper()

    if not limpia:
        return None

    base = f"CCAA{fecha.year % 10}{fecha.timetuple().tm_yday:03d}"

    return f"{base}{limpia}-{correlativo:02d}"
```

`codigo_lote_valido` no cambia de cuerpo: sigue siendo el `match` contra
`_PATRON_CODIGO`. Sí hay que revisar su docstring, que menciona el POE anterior.

- [ ] **Step 4: Correr y verificar que pasa**

```
cd backend
.venv\Scripts\python.exe manage.py test produccion.tests_codigo_lote -v 2
```

Esperado: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/produccion/dominio.py backend/produccion/tests_codigo_lote.py
git commit -m "El código de lote identifica una corrida, no describe un producto"
```

---

### Task 3: La unicidad la garantiza la base

**Files:**
- Modify: `backend/produccion/models.py` (`Lote.Meta.constraints`)
- Create: `backend/produccion/migrations/00XX_lote_codigo_unico.py`
- Create: `backend/produccion/tests_unicidad_lote.py`

**Interfaces:**
- Produces: constraint `lote_codigo_unico_sucursal` sobre `(sucursal, codigo_lote)`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `backend/produccion/tests_unicidad_lote.py`:

```python
"""
Dos lotes no comparten código, aunque sean de productos distintos.

La restricción anterior era sobre `(sucursal, codigo_lote, producto, fecha)`.
Con el SKU adentro del código eso alcanzaba casi siempre — salvo en los cuatro
pares de productos que comparten SKU, donde dos lotes distintos del mismo día
salían con el mismo código impreso y la base los aceptaba porque el `producto`
difería.
"""

from datetime import date
from decimal import Decimal

from django.db.utils import IntegrityError
from django.test import TestCase

from maestros.models import Mandante, Producto
from produccion.models import Lote


class UnicidadDelCodigoTests(TestCase):
    def setUp(self):
        mandante = Mandante.objects.create(nombre="Nestlé")
        self.uno = Producto.objects.create(
            nombre="Leche entera en polvo", familia=Producto.Familia.POLVO,
            mandante=mandante,
        )
        self.otro = Producto.objects.create(
            nombre="Leche entera regular", familia=Producto.Familia.POLVO,
            mandante=mandante,
        )

    def test_dos_productos_distintos_no_comparten_codigo(self):
        Lote.objects.create(
            codigo_lote="CCAA6232E1-01", producto=self.uno,
            fecha=date(2026, 8, 20), kg_producidos=Decimal("1000"),
        )

        with self.assertRaises(IntegrityError):
            Lote.objects.create(
                codigo_lote="CCAA6232E1-01", producto=self.otro,
                fecha=date(2026, 8, 20), kg_producidos=Decimal("1000"),
            )
```

- [ ] **Step 2: Correr y verificar que falla**

```
cd backend
.venv\Scripts\python.exe manage.py test produccion.tests_unicidad_lote -v 2
```

Esperado: FAIL — no se levanta `IntegrityError`, porque la restricción actual
incluye `producto`.

- [ ] **Step 3: Reemplazar la restricción**

En `backend/produccion/models.py`, dentro de `Lote.Meta.constraints`, sustituir
la `UniqueConstraint` de `lote_clave_natural_unica` por:

```python
            # El código identifica la corrida por sí solo: día, máquina y
            # correlativo. Incluir `producto` en la clave —como hacía la
            # restricción anterior— permitía que dos lotes de productos
            # distintos llevaran el mismo código impreso.
            models.UniqueConstraint(
                fields=["sucursal", "codigo_lote"],
                name="lote_codigo_unico_sucursal",
            ),
```

- [ ] **Step 4: Migrar y verificar**

```
cd backend
.venv\Scripts\python.exe manage.py makemigrations produccion --name lote_codigo_unico
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py test produccion -v 2
```

Esperado: PASS. Si alguna prueba existente reutilizaba un mismo `codigo_lote`
para dos productos, ahora falla: corregirla dándole códigos distintos, que es
lo que la restricción viene a exigir.

- [ ] **Step 5: Commit**

```bash
git add backend/produccion/models.py backend/produccion/migrations/ backend/produccion/tests_unicidad_lote.py
git commit -m "Un código de lote, un lote: la unicidad deja de depender del producto"
```

---

### Task 4: `codigo-sugerido` cuenta por máquina y día

**Files:**
- Modify: `backend/produccion/views.py` (acción `codigo_sugerido`)
- Modify: `backend/produccion/tests_apertura.py`

**Interfaces:**
- Consumes: `Equipo.sigla`, `dominio.generar_codigo_lote`
- Produces: `GET /api/produccion/lotes/codigo-sugerido/?equipo=<id>&fecha=<AAAA-MM-DD>` → `{"codigo", "correlativo", "motivo"}`. **El parámetro `producto` deja de usarse.**

- [ ] **Step 1: Escribir las pruebas que fallan**

Agregar a `backend/produccion/tests_apertura.py` (reutilizando el cliente y los
objetos que su `setUp` ya crea; si el equipo no está entre ellos, obtenerlo con
`Equipo.objects.get(codigo="e1")`, que la migración siembra):

```python
class CodigoSugeridoPorMaquinaTests(BaseAperturaLote):
    def test_propone_el_codigo_de_la_maquina_y_el_dia(self):
        equipo = Equipo.objects.get(codigo="e1")

        respuesta = self.cliente.get(
            "/api/produccion/lotes/codigo-sugerido/",
            {"equipo": equipo.id, "fecha": "2026-08-20"},
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["codigo"], "CCAA6232E1-01")
        self.assertEqual(respuesta.data["correlativo"], 1)

    def test_el_correlativo_cuenta_por_maquina_no_por_producto(self):
        """
        Dos productos distintos secados en la misma torre el mismo día son la
        segunda corrida de esa torre, no la primera de cada uno.
        """
        equipo = Equipo.objects.get(codigo="e1")
        Lote.objects.create(
            codigo_lote="CCAA6232E1-01", producto=self.producto,
            equipo=equipo, fecha=date(2026, 8, 20),
        )

        respuesta = self.cliente.get(
            "/api/produccion/lotes/codigo-sugerido/",
            {"equipo": equipo.id, "fecha": "2026-08-20"},
        )

        self.assertEqual(respuesta.data["codigo"], "CCAA6232E1-02")

    def test_la_otra_torre_arranca_en_01_el_mismo_dia(self):
        equipo = Equipo.objects.get(codigo="e1")
        otra = Equipo.objects.get(codigo="e2")
        Lote.objects.create(
            codigo_lote="CCAA6232E1-01", producto=self.producto,
            equipo=equipo, fecha=date(2026, 8, 20),
        )

        respuesta = self.cliente.get(
            "/api/produccion/lotes/codigo-sugerido/",
            {"equipo": otra.id, "fecha": "2026-08-20"},
        )

        self.assertEqual(respuesta.data["codigo"], "CCAA6232E2-01")

    def test_un_equipo_sin_sigla_devuelve_codigo_nulo_con_motivo(self):
        """
        200 y no 400: el formulario sigue abierto y el operador escribe el
        código a mano. Un 400 se leería como que el lote no se puede crear.
        """
        equipo = Equipo.objects.get(codigo="e1")
        equipo.sigla = ""
        equipo.save()

        respuesta = self.cliente.get(
            "/api/produccion/lotes/codigo-sugerido/",
            {"equipo": equipo.id, "fecha": "2026-08-20"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.data["codigo"])
        self.assertIn("sigla", respuesta.data["motivo"].lower())
```

- [ ] **Step 2: Correr y verificar que fallan**

```
cd backend
.venv\Scripts\python.exe manage.py test produccion.tests_apertura -v 2
```

Esperado: FAIL — la vista aún exige `producto`.

- [ ] **Step 3: Reescribir la acción**

En `backend/produccion/views.py`, reemplazar el cuerpo de `codigo_sugerido` por:

```python
    @action(detail=False, methods=["get"], url_path="codigo-sugerido")
    def codigo_sugerido(self, request):
        """
        El código que le tocaría a una corrida nueva de esa máquina ese día.

        Se **sugiere**, no se impone: el operador puede cambiarlo, por la misma
        razón que `codigo_lote_valido` avisa y no restringe.

        El correlativo se cuenta por `(equipo, fecha)` y no se pregunta: dos
        corridas de la misma torre el mismo día son la primera y la segunda,
        sin importar qué producto salió de cada una.
        """
        equipo_id = request.query_params.get("equipo")
        fecha_texto = request.query_params.get("fecha")

        if not equipo_id or not fecha_texto:
            return Response(
                {"detail": "Indica la máquina y la fecha."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fecha = parse_date(fecha_texto)

        if fecha is None:
            return Response(
                {"detail": f"Fecha no reconocida: {fecha_texto!r} (usa AAAA-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        equipo = get_object_or_404(
            filtrar_por_scope(
                Equipo.objects.all(), request.user,
                campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
            ),
            pk=equipo_id,
        )

        anteriores = self.get_queryset().filter(equipo=equipo, fecha=fecha).count()
        correlativo = anteriores + 1

        codigo = dominio.generar_codigo_lote(fecha, equipo.sigla, correlativo)

        if codigo is None:
            return Response(
                {
                    "codigo": None,
                    "correlativo": correlativo,
                    "motivo": (
                        f"«{equipo.nombre}» no tiene sigla cargada en Maestros, y la "
                        "sigla es parte del código de lote. Escríbelo a mano o "
                        "completa el maestro de equipos."
                    ),
                }
            )

        return Response({"codigo": codigo, "correlativo": correlativo, "motivo": ""})
```

Asegurar que `Equipo` esté importado en la cabecera de `views.py`.

- [ ] **Step 4: Correr y verificar**

```
cd backend
.venv\Scripts\python.exe manage.py test produccion -v 2
```

Esperado: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/produccion/views.py backend/produccion/tests_apertura.py
git commit -m "El código sugerido se cuenta por máquina y día, no por producto"
```

---

### Task 5: El formulario pide el código por máquina

**Files:**
- Modify: `frontend/src/services/produccion.service.ts`
- Modify: `frontend/src/pages/Produccion/FormularioLote.tsx`

**Interfaces:**
- Consumes: `GET /api/produccion/lotes/codigo-sugerido/?equipo=&fecha=`

- [ ] **Step 1: Cambiar la firma en el servicio**

En `frontend/src/services/produccion.service.ts`, la función que llama a
`codigo-sugerido` pasa a recibir el id del equipo en vez del producto:

```ts
export async function codigoSugerido(
  equipoId: number,
  fecha: string,
): Promise<{ codigo: string | null; correlativo: number; motivo: string }> {
  const { data } = await api.get("/produccion/lotes/codigo-sugerido/", {
    params: { equipo: equipoId, fecha },
  });
  return data;
}
```

- [ ] **Step 2: Cambiar quién dispara la sugerencia**

En `frontend/src/pages/Produccion/FormularioLote.tsx`, el efecto que pide el
código sugerido depende hoy de `producto` y `fecha`. Pasa a depender de
`equipo` y `fecha`: el estado `equipo` ya existe (línea ~54) y el campo ya está
en el formulario como «Máquina / equipo *».

Reemplazar el disparador por:

```tsx
  useEffect(() => {
    if (!equipo || !fecha) return;

    let vigente = true;
    codigoSugerido(Number(equipo), fecha)
      .then((r) => {
        if (!vigente) return;
        if (r.codigo) setCodigoLote(r.codigo);
        setAvisoCodigo(r.motivo);
      })
      .catch(() => { if (vigente) setAvisoCodigo(""); });

    return () => { vigente = false; };
  }, [equipo, fecha]);
```

Si el componente no tenía `avisoCodigo`, agregarlo con
`const [avisoCodigo, setAvisoCodigo] = useState("");` y mostrarlo bajo el campo
de código cuando no esté vacío.

- [ ] **Step 3: Comprobar tipos**

```
cd frontend
npx tsc -b
```

Esperado: sin errores. Corregir cualquier llamada que siguiera pasando el
producto.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/produccion.service.ts frontend/src/pages/Produccion/FormularioLote.tsx
git commit -m "El formulario de lote pide su código por máquina y fecha"
```

---

### Task 6: Partir un lote por inocuidad

**Files:**
- Modify: `backend/produccion/models.py` (dos campos en `Lote`)
- Create: `backend/produccion/migrations/00XX_lote_corte.py`
- Modify: `backend/produccion/views.py` (acción `partir`)
- Modify: `backend/produccion/serializers.py`
- Create: `backend/produccion/tests_corte_lote.py`

**Interfaces:**
- Produces: `Lote.lote_anterior` (FK a sí mismo, nulable, `related_name="continuaciones"`), `Lote.motivo_corte` (TextField), y `POST /api/produccion/lotes/{id}/partir/` con cuerpo `{"motivo": "..."}` que devuelve el lote nuevo.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `backend/produccion/tests_corte_lote.py`:

```python
"""
Un aseo intermedio parte el lote solo si hubo un tema de inocuidad.

Decisión de planta (2026-08-20): una corrida de torre es un lote aunque cruce
turnos y aunque se envase en dos formatos. Una detención **no** parte el lote
si es parte normal del proceso.

El sistema no puede deducir si el aseo fue rutinario o por inocuidad, así que
**el que continúa es el comportamiento por omisión** y partir es un acto
explícito con motivo obligatorio. Ese orden no es arbitrario: partir es
afirmar que el producto de después es separable del de antes, y esa
afirmación es la que carga el riesgo. Quien la hace, la firma.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from maestros.models import Equipo, Mandante, Producto
from produccion.models import Lote
from produccion.tests_apertura import BaseAperturaLote


class PartirLoteTests(BaseAperturaLote):
    def _lote(self):
        return Lote.objects.create(
            codigo_lote="CCAA6232E1-01",
            producto=self.producto,
            equipo=Equipo.objects.get(codigo="e1"),
            fecha=date(2026, 8, 20),
            estado=Lote.Estado.EN_PROCESO,
        )

    def test_partir_abre_el_siguiente_con_el_correlativo_que_sigue(self):
        lote = self._lote()

        respuesta = self.cliente.post(
            f"/api/produccion/lotes/{lote.id}/partir/",
            {"motivo": "Aseo intermedio por hallazgo de cuerpo extraño en el ciclón."},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["codigo_lote"], "CCAA6232E1-02")

    def test_el_nuevo_apunta_al_anterior_y_conserva_el_motivo(self):
        lote = self._lote()
        motivo = "Aseo intermedio por hallazgo de cuerpo extraño en el ciclón."

        respuesta = self.cliente.post(
            f"/api/produccion/lotes/{lote.id}/partir/", {"motivo": motivo},
            format="json",
        )

        nuevo = Lote.objects.get(pk=respuesta.data["id"])
        self.assertEqual(nuevo.lote_anterior_id, lote.id)
        self.assertEqual(nuevo.motivo_corte, motivo)

    def test_sin_motivo_no_se_parte(self):
        """
        Un corte sin motivo no se puede auditar, y es justo el que hay que
        poder auditar: dice que el producto de después es otro.
        """
        lote = self._lote()

        respuesta = self.cliente.post(
            f"/api/produccion/lotes/{lote.id}/partir/", {"motivo": "   "},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(Lote.objects.filter(lote_anterior=lote).count(), 0)

    def test_el_nuevo_hereda_producto_maquina_y_fecha(self):
        lote = self._lote()

        respuesta = self.cliente.post(
            f"/api/produccion/lotes/{lote.id}/partir/",
            {"motivo": "Filtro roto en la torre."}, format="json",
        )

        nuevo = Lote.objects.get(pk=respuesta.data["id"])
        self.assertEqual(nuevo.producto_id, lote.producto_id)
        self.assertEqual(nuevo.equipo_id, lote.equipo_id)
        self.assertEqual(nuevo.fecha, lote.fecha)
```

- [ ] **Step 2: Correr y verificar que fallan**

```
cd backend
.venv\Scripts\python.exe manage.py test produccion.tests_corte_lote -v 2
```

Esperado: FAIL con 404 en `partir/`.

- [ ] **Step 3: Agregar los campos**

En `backend/produccion/models.py`, dentro de `Lote`, después de `observacion`:

```python
    # Una corrida partida por inocuidad. Nulo es el caso normal: la mayoría de
    # los lotes son una corrida completa, y una detención rutinaria **no**
    # parte el lote (decisión de planta, 2026-08-20).
    lote_anterior = models.ForeignKey(
        "self", on_delete=models.PROTECT, related_name="continuaciones",
        null=True, blank=True, verbose_name="Continúa a",
    )
    motivo_corte = models.TextField(
        "Motivo del corte", blank=True,
        help_text="Por qué la corrida se partió. Obligatorio si continúa a otro lote.",
    )
```

Y en `clean()` de `Lote` (o creándolo si no existe):

```python
        if self.lote_anterior_id and not self.motivo_corte.strip():
            raise ValidationError(
                {"motivo_corte": "Un corte sin motivo no se puede auditar."}
            )
```

- [ ] **Step 4: Migrar**

```
cd backend
.venv\Scripts\python.exe manage.py makemigrations produccion --name lote_corte
.venv\Scripts\python.exe manage.py migrate
```

- [ ] **Step 5: Escribir la acción**

En `backend/produccion/views.py`, dentro de `LoteViewSet`:

```python
    @action(detail=True, methods=["post"])
    def partir(self, request, pk=None):
        """
        Cierra la corrida actual y abre la siguiente en la misma máquina.

        Es para el aseo intermedio **por inocuidad**. Una detención normal del
        proceso no parte el lote: eso lo decide quien opera, no el sistema, y
        por eso el motivo es obligatorio. Partir afirma que el producto de
        después es separable del de antes, y esa afirmación tiene que quedar
        firmada.
        """
        lote = self.get_object()
        motivo = (request.data.get("motivo") or "").strip()

        if not motivo:
            return Response(
                {"motivo": "Indica por qué se parte la corrida."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            anteriores = self.get_queryset().filter(
                equipo=lote.equipo, fecha=lote.fecha
            ).count()
            codigo = dominio.generar_codigo_lote(
                lote.fecha,
                lote.equipo.sigla if lote.equipo_id else "",
                anteriores + 1,
            )

            nuevo = Lote.objects.create(
                sucursal=lote.sucursal,
                codigo_lote=codigo or "",
                producto=lote.producto,
                equipo=lote.equipo,
                fecha=lote.fecha,
                turno=lote.turno,
                estado=Lote.Estado.EN_PROCESO,
                lote_anterior=lote,
                motivo_corte=motivo,
            )

        serializer = self.get_serializer(nuevo)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
```

Verificar que `transaction` esté importado en `views.py` (lo está).

- [ ] **Step 6: Exponer los campos**

En `backend/produccion/serializers.py`, agregar `"lote_anterior"` y
`"motivo_corte"` a la lista `fields` del serializer de `Lote`, ambos en
`read_only_fields`: se escriben por la acción `partir/`, no por un `PATCH`.

- [ ] **Step 7: Correr y verificar**

```
cd backend
.venv\Scripts\python.exe manage.py test produccion -v 2
```

Esperado: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/produccion/models.py backend/produccion/migrations/ backend/produccion/views.py backend/produccion/serializers.py backend/produccion/tests_corte_lote.py
git commit -m "Partir un lote por inocuidad: acto explícito, con motivo"
```

---

### Task 7: Dejar la decisión escrita

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/levantamiento-2026-07/SKU_PRODUCTOS.md`
- Modify: `prototipo/MODELO_DATOS.md`

- [ ] **Step 1: Reemplazar la decisión en `CLAUDE.md`**

La viñeta que empieza con «**Código de lote** (vigente desde 2026-07-31)» y el
bloque «**Resuelto (2026-07-31): el código de lote lleva el SKU completo…**»
quedan obsoletos. Reemplazarlos por:

```markdown
- **Código de lote** (vigente desde 2026-08-20): `CCAA` + último dígito del año + día
  juliano (3) + **sigla del equipo** + `-` + correlativo del día en esa máquina — p. ej.
  `CCAA6232E1-01`. El correlativo va **siempre**, desde `-01`.

  **Identifica una corrida; no describe el producto.** El esquema anterior metía el SKU de
  12 dígitos adentro (23 caracteres) y eso lo ataba a un **valor derivado**:
  `Producto.save()` recalcula el SKU desde los atributos, así que corregir la categoría de
  un producto —que `SKU_PRODUCTOS.md` §4.2 documenta como necesario— dejaba códigos ya
  impresos describiendo algo que ese producto ya no era. No se rompían: mentían, y nada
  avisaba. Además los cuatro pares de productos que comparten SKU podían producir el mismo
  código el mismo día.

  La máquina viene de `Equipo.sigla`, dos o tres caracteres del maestro, **configurables**:
  `Equipo.codigo` es un slug de hasta 19 caracteres (`carga_precondensado`) y no cabe en un
  código impreso. Repone lo que el POE.009.02 codificaba con el dígito de torre y que el
  esquema del SKU había perdido: el mismo producto secado a la vez en E1 y E2 son dos lotes.

  La unicidad la garantiza `lote_codigo_unico_sucursal` sobre `(sucursal, codigo_lote)`. La
  anterior incluía `producto`, que es lo que permitía el código repetido.

- **Dónde termina un lote** (decisión de planta, 2026-08-20): una **corrida de torre** es un
  lote, **aunque cruce turnos** —`turno` es informativo y no entra en el código— y **aunque
  se envase en dos formatos** —por eso no hay nivel de sublote de envasado—. Una detención
  con aseo intermedio **parte** el lote **solo si hubo un tema de inocuidad**, no si es parte
  normal del proceso.

  El sistema no puede deducir cuál de las dos fue, así que **continuar es el comportamiento
  por omisión** y partir es la acción explícita `POST lotes/{id}/partir/`, con motivo
  obligatorio. El orden importa: partir afirma que el producto de después es separable del
  de antes, y esa afirmación es la que carga el riesgo. `Lote.lote_anterior` encadena la
  corrida y `motivo_corte` la justifica.
```

- [ ] **Step 2: Corregir las menciones cruzadas**

- En `CLAUDE.md`, la viñeta «Un código de cliente, un mandante» dice «como el código de lote
  lleva el SKU dentro». Quitar esa cláusula: el argumento sobre el SKU duplicado sigue en
  pie por sí solo.
- En `CLAUDE.md`, la tabla de los cuatro pares que comparten SKU dice «el código de lote
  lleva el SKU, así que dos lotes de productos distintos del mismo día pueden salir con el
  mismo código de lote». Reemplazar por: «Ya no afecta al código de lote, que identifica la
  corrida; sigue siendo una decisión pendiente para el maestro de productos.»
- En `docs/levantamiento-2026-07/SKU_PRODUCTOS.md`, revisar §7 y quitar la afirmación de que
  el SKU forma parte del código de lote.
- En `prototipo/MODELO_DATOS.md` §2.1, corregir la clave natural del lote.

- [ ] **Step 3: Correr la suite completa**

```
cd backend
.venv\Scripts\python.exe manage.py test
```

Esperado: PASS sin regresiones.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/levantamiento-2026-07/SKU_PRODUCTOS.md prototipo/MODELO_DATOS.md
git commit -m "Documenta el código de lote por corrida y dónde termina un lote"
```

---

## Qué queda fuera, y por qué

| Fuera | Motivo |
|---|---|
| Compatibilidad con el formato anterior | El sistema parte en blanco: no hay códigos emitidos. Escribir un lector de dos formatos sería mantener una rama que nunca se ejercita |
| Nivel de sublote por formato de envase | Decisión de planta: dos formatos son el mismo lote |
| `turno` dentro del código | Decisión de planta: una corrida que cruza turnos es un lote |
| Reemitir el código al cambiar la máquina de un lote | Un lote que cambia de torre es otra corrida; si aparece el caso, se parte |
| Retirar `Lote.linea` (el `TextChoices` heredado que convive con `equipo`) | Es una limpieza aparte y no bloquea esto. Anotarla como deuda |
