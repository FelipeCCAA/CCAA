# Fecha de creación y fecha de ejecución del vale — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El vale deja de pedir fecha: el sistema sella la fecha de creación al confirmar (junto al código) y la de ejecución al transferir.

**Architecture:** `ValeEstandarizacion.asignar_codigo()` —que el `save()` ya llama al confirmar— sella `fecha = timezone.localdate()` antes de componer el código. Un campo nuevo `ejecutado_en` lo sella `servicios.transferir` con la misma hora de los movimientos de silo. Ambas fechas son de solo lectura en serializer y admin; el formulario deja de pedir fecha y la ficha muestra las dos.

**Tech Stack:** Django 6.0.7 + DRF, PostgreSQL, React 19 + TypeScript, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-23-fechas-vale-creacion-ejecucion-design.md`

## Global Constraints

- **Antes de la Task 1**: los cambios del bloqueo de borrado de vales (`backend/estandarizacion/views.py`, `admin.py`, `tests_vale.py`, `CLAUDE.md`) deben estar commiteados. Este plan toca `admin.py`, `tests_vale.py` y `CLAUDE.md`; si siguen sin commitear, el commit de una tarea se los llevaría mezclados.
- La fecha de creación (`fecha`) la sella el sistema en `asignar_codigo()` con `timezone.localdate()` (servidor en `America/Santiago`, `USE_TZ`), **en el mismo guardado** que el código. No se teclea.
- La fecha de ejecución (`ejecutado_en`) la sella `servicios.transferir` con **el mismo `ahora`** de la `fecha_hora` de los movimientos de silo.
- `fecha` y `ejecutado_en` son de solo lectura en serializer y admin. Un cliente que mande `fecha` se **ignora, no se rechaza**.
- Mientras el vale es borrador, `fecha` es provisional (el día en que se abrió) y se reemplaza al confirmar.
- Sin migración de datos. Una sola migración de esquema: `AddField` de `ejecutado_en`.
- Django 6: `Model.save()` solo acepta argumentos por nombre.
- Español en código, comentarios y UI. Pruebas del backend con `DJANGO_ENV=test` y en serie (`--parallel` se cae en este equipo).

## Mapa de archivos

| Archivo | Cambio |
|---|---|
| `backend/estandarizacion/models.py` | `asignar_codigo()` sella `fecha`; `fecha` sale de obligatorios; campo `ejecutado_en` |
| `backend/estandarizacion/migrations/0009_valeestandarizacion_ejecutado_en.py` | `AddField` (generada) |
| `backend/estandarizacion/servicios.py` | `transferir` sella `ejecutado_en` |
| `backend/estandarizacion/serializers.py` | `fecha` y `ejecutado_en` de solo lectura; `fecha` sale de obligatorios |
| `backend/estandarizacion/views.py` | `crear_borrador` fija la fecha provisional sin leer el cuerpo |
| `backend/estandarizacion/admin.py` | `fecha` y `ejecutado_en` en `readonly_fields` |
| `backend/estandarizacion/tests_codigo_vale.py` | reloj fijado en `DIA`; pruebas de fecha sellada |
| `backend/estandarizacion/tests_vale.py` | pruebas de `ejecutado_en` y admin |
| `frontend/src/pages/Estandarizacion/FormularioVale.tsx` | sale el campo «Fecha» |
| `frontend/src/pages/Estandarizacion/Estandarizacion.tsx` | ficha: «Creado» y «Ejecutado» |
| `frontend/src/services/estandarizacion.service.ts` | tipos |
| `frontend/e2e/circuito-polvo.spec.ts` | deja de teclear «Fecha» |
| `CLAUDE.md` | regla del código y de la ejecución |

---

### Task 1: La confirmación sella la fecha de creación

**Files:**
- Modify: `backend/estandarizacion/models.py` (`CAMPOS_OBLIGATORIOS_AL_CONFIRMAR` ~87-91; `asignar_codigo` ~313-350)
- Modify: `backend/estandarizacion/serializers.py` (`read_only_fields`; `validate` ~91-95)
- Modify: `backend/estandarizacion/views.py` (`crear_borrador`, ~146)
- Modify: `backend/estandarizacion/admin.py` (`readonly_fields`)
- Test: `backend/estandarizacion/tests_codigo_vale.py`

**Interfaces:**
- Produces: `ValeEstandarizacion.fecha` es la fecha de creación sellada al confirmar; la API la expone de solo lectura.

- [ ] **Step 1: Fijar el reloj y escribir las pruebas que fallan**

En `backend/estandarizacion/tests_codigo_vale.py`:

1a. Reemplazar el bloque de imports:

```python
from datetime import date, timedelta
from unittest.mock import patch

from django.utils import timezone

from .dominio import prefijo_codigo_vale
from .models import CodigoValeNoAsignado, ValeEstandarizacion
from .tests_vale import BaseVale
```

por:

```python
from datetime import date
from unittest.mock import patch

from .models import CodigoValeNoAsignado, ValeEstandarizacion
from .tests_vale import BaseVale
```

1b. Justo después de `ANULADO = ValeEstandarizacion.Estado.ANULADO`, agregar:

```python

#: Otro día cualquiera, para comprobar que la fecha que se pasa no manda.
OTRO_DIA = date(2026, 1, 1)


def fijar_reloj(prueba):
    """
    Fija `timezone.localdate()` en `DIA` durante la prueba.

    La fecha de creación la sella el sistema al confirmar con el día de hoy, así
    que los códigos esperados (`VE6266-…`) dependen del reloj.
    """
    reloj = patch("django.utils.timezone.localdate", return_value=DIA)
    reloj.start()
    prueba.addCleanup(reloj.stop)
```

1c. En `AsignacionCodigoValeTests`, reemplazar los dos ayudantes:

```python
    def confirmado(self, **extra):
        """Un vale ya confirmado (`calculado`) sin código: el modelo se lo asigna."""
        return self.crear_vale(codigo="", fecha=DIA, **extra)

    def borrador(self, **extra):
        vale = self.crear_vale(
            codigo=ValeEstandarizacion.nuevo_codigo_borrador(),
            fecha=DIA, estado=BORRADOR, **extra,
        )
```

por:

```python
    def setUp(self):
        fijar_reloj(self)

    def confirmado(self, **extra):
        """Un vale ya confirmado (`calculado`) sin código: el modelo se lo asigna."""
        return self.crear_vale(codigo="", **extra)

    def borrador(self, **extra):
        vale = self.crear_vale(
            codigo=ValeEstandarizacion.nuevo_codigo_borrador(),
            estado=BORRADOR, **extra,
        )
```

1d. Reemplazar la prueba que queda invertida:

```python
    def test_el_dia_sale_de_la_fecha_del_vale_y_no_del_reloj(self):
        ayer = timezone.localdate() - timedelta(days=1)

        vale = self.crear_vale(codigo="", fecha=ayer)

        self.assertEqual(vale.codigo, f"{prefijo_codigo_vale(ayer)}01")
```

por:

```python
    def test_la_fecha_la_sella_la_confirmacion_y_no_quien_crea_el_vale(self):
        """Fecha y código se sellan juntos: no pueden decir días distintos."""
        vale = self.confirmado(fecha=OTRO_DIA)

        self.assertEqual(vale.fecha, DIA)
        self.assertEqual(vale.codigo, "VE6266-01")

    def test_confirmar_un_borrador_sella_la_fecha_de_hoy(self):
        vale = self.borrador(fecha=OTRO_DIA)

        self.assertEqual(vale.confirmar(self.usuario), [])

        vale.refresh_from_db()
        self.assertEqual(vale.fecha, DIA)
        self.assertEqual(vale.codigo, "VE6266-01")

    def test_un_borrador_conserva_su_fecha_provisional(self):
        self.assertEqual(self.borrador(fecha=OTRO_DIA).fecha, OTRO_DIA)
```

1e. En `CodigoValeApiTests.setUp`, agregar como **primera** línea del método:

```python
        fijar_reloj(self)
```

1f. En `CodigoValeApiTests.cuerpo`, borrar la línea `"fecha": DIA.isoformat(),` (la fecha ya no se manda).

1g. Agregar al final de `CodigoValeApiTests`:

```python
    def test_la_creacion_directa_ignora_la_fecha_del_cliente(self):
        respuesta = self.cliente.post(
            "/api/estandarizacion/vales/",
            self.cuerpo(fecha=OTRO_DIA.isoformat()),
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.json())
        self.assertEqual(respuesta.json()["fecha"], DIA.isoformat())

    def test_un_patch_no_cambia_la_fecha(self):
        vale = self.crear_vale(codigo="")

        respuesta = self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.id}/",
            {"fecha": OTRO_DIA.isoformat()},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        vale.refresh_from_db()
        self.assertEqual(vale.fecha, DIA)
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test estandarizacion.tests_codigo_vale --noinput`
Expected: FAIL en `test_la_fecha_la_sella_la_confirmacion_y_no_quien_crea_el_vale` (`2026-01-01 != 2026-09-23`), `test_confirmar_un_borrador_sella_la_fecha_de_hoy`, `test_la_creacion_directa_ignora_la_fecha_del_cliente` y `test_un_patch_no_cambia_la_fecha`. El resto pasa (el reloj fijado mantiene `VE6266-…`).

- [ ] **Step 3: Modelo**

En `backend/estandarizacion/models.py`:

3a. Reemplazar:

```python
    CAMPOS_OBLIGATORIOS_AL_CONFIRMAR = (
        "fecha", "producto", "rc_objetivo", "volumen",
```

por:

```python
    # `fecha` no está: la sella el sistema al confirmar (`asignar_codigo`).
    CAMPOS_OBLIGATORIOS_AL_CONFIRMAR = (
        "producto", "rc_objetivo", "volumen",
```

3b. En `asignar_codigo`, reemplazar desde el docstring hasta `prefijo = dominio.prefijo_codigo_vale(fecha)`:

```python
        """
        Guarda el vale con el siguiente código libre del día de `fecha`.

        La unicidad la garantiza la base: si dos confirmaciones calculan el
        mismo número, `unique` rechaza a la segunda y se reintenta con el
        siguiente. Cada intento va en su propio savepoint; sin él, el
        `IntegrityError` deja inutilizable la transacción de la confirmación.
        """
        if self.fecha is None:
            raise ValidationError({"fecha": "Falta la fecha del vale: sin ella no hay código."})
        fecha = self.fecha if isinstance(self.fecha, date) else date.fromisoformat(str(self.fecha))

        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = {*kwargs["update_fields"], "codigo"}

        provisional = self.codigo
        prefijo = dominio.prefijo_codigo_vale(fecha)
```

por:

```python
        """
        Sella la fecha de creación y guarda el vale con el siguiente código libre.

        La fecha es la de hoy en hora local (el servidor trabaja en
        America/Santiago) y se escribe **en el mismo guardado** que el código:
        son el mismo dato, y así no pueden decir días distintos. Nadie la teclea.

        La unicidad la garantiza la base: si dos confirmaciones calculan el
        mismo número, `unique` rechaza a la segunda y se reintenta con el
        siguiente. Cada intento va en su propio savepoint; sin él, el
        `IntegrityError` deja inutilizable la transacción de la confirmación.
        """
        fecha_provisional = self.fecha
        self.fecha = fecha = timezone.localdate()

        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = {*kwargs["update_fields"], "codigo", "fecha"}

        provisional = self.codigo
        prefijo = dominio.prefijo_codigo_vale(fecha)
```

3c. En el mismo método, en los **dos** sitios donde se restaura el código ante fallo, restaurar también la fecha. Reemplazar:

```python
                if not ocupado:
                    # No fue el código: otra restricción. No se enmascara.
                    self.codigo = provisional
                    raise
```

por:

```python
                if not ocupado:
                    # No fue el código: otra restricción. No se enmascara.
                    self.codigo, self.fecha = provisional, fecha_provisional
                    raise
```

y reemplazar:

```python
        self.codigo = provisional
        raise CodigoValeNoAsignado(
```

por:

```python
        self.codigo, self.fecha = provisional, fecha_provisional
        raise CodigoValeNoAsignado(
```

3d. Borrar la línea `from datetime import date` (~línea 20): su único uso era la conversión que 3b eliminó. `from django.core.exceptions import ValidationError` se queda: se usa en otras partes del archivo.

- [ ] **Step 4: Serializer**

En `backend/estandarizacion/serializers.py`:

En `read_only_fields`, reemplazar:

```python
        read_only_fields = [
            "codigo",
```

por:

```python
        # La fecha de creación también: la sella el sistema junto al código.
        read_only_fields = [
            "codigo", "fecha",
```

En `validate`, reemplazar:

```python
            obligatorios = (
                "fecha", "producto", "rc_objetivo", "volumen",
```

por:

```python
            obligatorios = (
                "producto", "rc_objetivo", "volumen",
```

- [ ] **Step 5: Borrador**

En `backend/estandarizacion/views.py`, en `crear_borrador`, reemplazar:

```python
            fecha=serializer.validated_data.get("fecha", timezone.localdate()),
```

por:

```python
            # Provisional: la fecha de creación se sella al confirmar.
            fecha=timezone.localdate(),
```

- [ ] **Step 6: Admin**

En `backend/estandarizacion/admin.py`, reemplazar:

```python
    readonly_fields = (
        "codigo", "estado", "agitacion_desde", "muestreado_en", "grasa_real",
        "sng_real", "creado_en",
    )
```

por:

```python
    readonly_fields = (
        "codigo", "fecha", "estado", "agitacion_desde", "muestreado_en",
        "grasa_real", "sng_real", "creado_en",
    )
```

- [ ] **Step 7: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test estandarizacion --noinput`
Expected: `OK`. Si falla alguna prueba de otra clase por la fecha sellada (por ejemplo una que compare `vale.fecha` con la que pasó al crear un vale **sin** código explícito), detenerse y reportar: no ajustarla sin decirlo.

- [ ] **Step 8: Commit**

```bash
git add backend/estandarizacion/models.py backend/estandarizacion/serializers.py backend/estandarizacion/views.py backend/estandarizacion/admin.py backend/estandarizacion/tests_codigo_vale.py
git commit -m "feat(estandarizacion): la confirmación sella la fecha de creación del vale"
```

---

### Task 2: La transferencia sella la fecha de ejecución

**Files:**
- Modify: `backend/estandarizacion/models.py` (campo nuevo después de `muestreado_en`, ~214-221)
- Create: `backend/estandarizacion/migrations/0009_valeestandarizacion_ejecutado_en.py` (generada)
- Modify: `backend/estandarizacion/servicios.py` (`transferir`, guardado del vale ~173)
- Modify: `backend/estandarizacion/serializers.py` (`fields`, `read_only_fields`)
- Modify: `backend/estandarizacion/admin.py` (`readonly_fields`)
- Test: `backend/estandarizacion/tests_vale.py` (`AgitacionTests`, `ApiTests`, `AdminValeTests`)
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `fecha` sellada (Task 1).
- Produces: `ValeEstandarizacion.ejecutado_en: datetime | None`; la API expone `"ejecutado_en"` (ISO 8601 o `null`), de solo lectura.

- [ ] **Step 1: Escribir las pruebas que fallan**

En `backend/estandarizacion/tests_vale.py`:

En `AgitacionTests`, justo antes de `def test_transferir_mueve_litros_entre_silos(self):`, agregar:

```python
    def test_transferir_sella_la_ejecucion_con_la_hora_del_libro(self):
        """
        La ejecución es cuándo se mezcló la leche: la misma hora que queda en
        los movimientos de silo, no una que se teclea.
        """
        vale = self.crear_vale()
        self.abastecer_origenes()
        self.analizar_origenes()
        self.assertIsNone(ValeEstandarizacion.objects.get(pk=vale.pk).ejecutado_en)

        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)

        vale.refresh_from_db()
        horas_del_libro = set(
            MovimientoSilo.objects.filter(
                origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
                origen_id=vale.id,
            ).values_list("fecha_hora", flat=True)
        )
        self.assertIsNotNone(vale.ejecutado_en)
        self.assertEqual(horas_del_libro, {vale.ejecutado_en})

```

En `ApiTests`, justo antes de `def test_un_vale_no_se_borra_se_anula(self):`, agregar:

```python
    def test_la_ejecucion_se_expone_y_no_se_escribe(self):
        vale = self.crear_vale()

        respuesta = self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.id}/",
            {"ejecutado_en": "2026-01-01T10:00:00-03:00"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        self.assertIsNone(respuesta.json()["ejecutado_en"])

```

En `AdminValeTests`, agregar al final de la clase:

```python

    def test_las_fechas_del_vale_no_se_editan_en_el_admin(self):
        peticion = RequestFactory().get("/")
        peticion.user = get_user_model().objects.create_superuser(
            username="admin-fechas", password="x"
        )

        solo_lectura = admin.site._registry[ValeEstandarizacion].get_readonly_fields(
            peticion
        )

        self.assertIn("fecha", solo_lectura)
        self.assertIn("ejecutado_en", solo_lectura)
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test estandarizacion.tests_vale.AgitacionTests.test_transferir_sella_la_ejecucion_con_la_hora_del_libro estandarizacion.tests_vale.ApiTests.test_la_ejecucion_se_expone_y_no_se_escribe estandarizacion.tests_vale.AdminValeTests.test_las_fechas_del_vale_no_se_editan_en_el_admin --noinput`
Expected: las tres fallan — `AttributeError: 'ValeEstandarizacion' object has no attribute 'ejecutado_en'`, `KeyError: 'ejecutado_en'` y `'ejecutado_en' not found in (...)`.

- [ ] **Step 3: Campo**

En `backend/estandarizacion/models.py`, justo después de la definición completa de `muestreado_en` (el bloque que termina en `),` tras su `help_text`), agregar:

```python
    ejecutado_en = models.DateTimeField(
        "Ejecutado en", null=True, blank=True,
        help_text=(
            "Cuándo se mezcló la leche: lo sella `transferir` con la misma hora "
            "de los movimientos de silo. Nadie lo teclea; nulo hasta transferir."
        ),
    )
```

- [ ] **Step 4: Generar y revisar la migración**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py makemigrations estandarizacion -n valeestandarizacion_ejecutado_en`
Expected: crea `estandarizacion/migrations/0009_valeestandarizacion_ejecutado_en.py` con **una sola** operación `AddField(model_name="valeestandarizacion", name="ejecutado_en", ...)`. Si genera cualquier otra operación, detenerse y reportar.

Run: `cd backend && ./.venv/Scripts/python.exe manage.py makemigrations --check --dry-run`
Expected: `No changes detected`

No correr `migrate` sobre la base de desarrollo: lo hace la Task 4.

- [ ] **Step 5: Servicio**

En `backend/estandarizacion/servicios.py`, en `transferir`, reemplazar:

```python
    vale.estado = ValeEstandarizacion.Estado.TRANSFERIDO
    vale.responsable = vale.responsable or usuario
    vale.save(update_fields=["estado", "responsable"])
```

por:

```python
    vale.estado = ValeEstandarizacion.Estado.TRANSFERIDO
    vale.responsable = vale.responsable or usuario
    # La ejecución es este momento: el mismo `ahora` de los movimientos.
    vale.ejecutado_en = ahora
    vale.save(update_fields=["estado", "responsable", "ejecutado_en"])
```

- [ ] **Step 6: Serializer y admin**

En `backend/estandarizacion/serializers.py`, en `fields`, reemplazar:

```python
            "estado", "agitacion_desde", "muestreado_en",
            "grasa_real", "sng_real",
            "rc_real", "minutos_agitando", "avisos", "evaluacion",
```

por:

```python
            "estado", "agitacion_desde", "muestreado_en", "ejecutado_en",
            "grasa_real", "sng_real",
            "rc_real", "minutos_agitando", "avisos", "evaluacion",
```

y en `read_only_fields`, reemplazar:

```python
            "estado", "agitacion_desde", "muestreado_en",
            "grasa_real", "sng_real",
            "responsable", "creado_en", "es_borrador",
```

por:

```python
            "estado", "agitacion_desde", "muestreado_en", "ejecutado_en",
            "grasa_real", "sng_real",
            "responsable", "creado_en", "es_borrador",
```

En `backend/estandarizacion/admin.py`, reemplazar:

```python
        "codigo", "fecha", "estado", "agitacion_desde", "muestreado_en",
        "grasa_real", "sng_real", "creado_en",
```

por:

```python
        "codigo", "fecha", "estado", "agitacion_desde", "muestreado_en",
        "ejecutado_en", "grasa_real", "sng_real", "creado_en",
```

- [ ] **Step 7: CLAUDE.md**

En `CLAUDE.md`, entrada «Código de vale», reemplazar:

```
El día sale de `vale.fecha`, no del reloj; el correlativo
```

por:

```
El día es el de la **confirmación**: `asignar_codigo` sella `vale.fecha` con `timezone.localdate()` en el mismo guardado que el código, así que fecha y código no pueden decir días distintos, y nadie teclea la fecha (desde 2026-09-23). La **ejecución** es otro dato: `ejecutado_en`, que sella `transferir` con la misma hora de los movimientos de silo. El correlativo
```

- [ ] **Step 8: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test estandarizacion produccion --noinput`
Expected: `OK`

- [ ] **Step 9: Commit**

```bash
git add backend/estandarizacion CLAUDE.md
git commit -m "feat(estandarizacion): la transferencia sella la fecha de ejecución del vale"
```

---

### Task 3: El formulario deja de pedir fecha y la ficha muestra las dos

**Files:**
- Modify: `frontend/src/services/estandarizacion.service.ts` (`ValeEstandarizacion` ~24-60; `NuevoVale` ~145; `DatosBorradorVale` ~170)
- Modify: `frontend/src/pages/Estandarizacion/FormularioVale.tsx` (~15, ~33, ~36, ~96, ~136, ~334-340)
- Modify: `frontend/src/pages/Estandarizacion/Estandarizacion.tsx` (ficha, ~341-368)

**Interfaces:**
- Consumes: API con `fecha` (creación) y `ejecutado_en: string | null` (Tasks 1-2).

- [ ] **Step 1: Tipos**

En `frontend/src/services/estandarizacion.service.ts`:
- En `interface ValeEstandarizacion`, justo después de la línea `  muestreado_en: string | null;`, agregar `  ejecutado_en: string | null;`.
- En `interface NuevoVale`, borrar la línea `  fecha: string;`.
- En `interface DatosBorradorVale`, borrar la línea `  fecha: string;`.

- [ ] **Step 2: Comprobar que el compilador señala los usos**

Run: `cd frontend && npx tsc -b --pretty false`
Expected: FAIL con errores en `FormularioVale.tsx` (usos de `fecha` en el borrador que se envía y en la recuperación).

- [ ] **Step 3: Formulario**

En `frontend/src/pages/Estandarizacion/FormularioVale.tsx`:
- Borrar `import { fechaLocalISO } from "../../services/fechas";` y `const hoy = () => fechaLocalISO();`.
- En `const inicial = {`, borrar `  fecha: hoy(),`.
- En `const datosBorrador: DatosBorradorVale = {`, borrar `    fecha: datos.fecha,`.
- En el `setDatos({ ...inicial, ...` que recupera el borrador, borrar `        fecha: guardado.fecha,`.
- Borrar el campo completo:

```tsx
          <Campo label="Fecha">
            <input
              required type="date" value={datos.fecha}
              onChange={(e) => cambiar("fecha", e.target.value)}
              className="control"
            />
          </Campo>
```

El helper `fechaLocalISO` se queda en `services/fechas.ts`: lo usarán las otras pantallas que hoy calculan la fecha en UTC.

- [ ] **Step 4: Ficha del vale**

En `frontend/src/pages/Estandarizacion/Estandarizacion.tsx`, en la grilla de la ficha, reemplazar:

```tsx
                  <Dato etiqueta="RC objetivo" valor={rc(vale.rc_objetivo)} />
```

por:

```tsx
                  {/* Las dos fechas las sella el sistema: la creación al
                      confirmar (junto al código) y la ejecución al transferir. */}
                  <Dato etiqueta="Creado" valor={vale.fecha} />
                  <Dato
                    etiqueta="Ejecutado"
                    valor={
                      vale.ejecutado_en
                        ? new Date(vale.ejecutado_en).toLocaleString("es-CL", {
                            dateStyle: "short",
                            timeStyle: "short",
                          })
                        : "Pendiente"
                    }
                    pie={vale.ejecutado_en ? undefined : "se registra al transferir"}
                  />
                  <Dato etiqueta="RC objetivo" valor={rc(vale.rc_objetivo)} />
```

- [ ] **Step 5: Verificar**

Run: `cd frontend && npx tsc -b --pretty false && npx eslint src/pages/Estandarizacion/FormularioVale.tsx src/pages/Estandarizacion/Estandarizacion.tsx src/services/estandarizacion.service.ts && npm test`
Expected: `tsc` sin errores, `eslint` sin salida, `node --test` todo en verde.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services/estandarizacion.service.ts frontend/src/pages/Estandarizacion/FormularioVale.tsx frontend/src/pages/Estandarizacion/Estandarizacion.tsx
git commit -m "feat(estandarizacion): el vale muestra su creación y su ejecución, y no pide fecha"
```

---

### Task 4: E2E — prueba de aceptación

**Files:**
- Modify: `frontend/e2e/circuito-polvo.spec.ts` (~337)

**Interfaces:**
- Consumes: formulario sin «Fecha» (Task 3); migración `0009` (Task 2).

- [ ] **Step 1: Dejar de teclear la fecha del vale**

En `frontend/e2e/circuito-polvo.spec.ts`, en el paso 4, borrar:

```ts
    await campo(page, "Fecha").fill(HOY);
```

`HOY` se queda: lo usan otros pasos.

- [ ] **Step 2: Lint**

Run: `cd frontend && npx eslint e2e/circuito-polvo.spec.ts`
Expected: sin salida.

- [ ] **Step 3: Poner el backend en el código nuevo**

El backend corre con `--noreload`: sigue sirviendo el código viejo. Aplicar la migración a la base de desarrollo y reiniciarlo:

Run: `cd backend && ./.venv/Scripts/python.exe manage.py migrate`
Expected: `Applying estandarizacion.0009_valeestandarizacion_ejecutado_en... OK`

Detener el proceso que escucha en el 8000 y levantar de nuevo, en segundo plano: `cd backend && ./.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --noreload`
Verificar: `curl -s http://127.0.0.1:8000/api/salud/` → `{"estado": "ok"}`

- [ ] **Step 4: Preparar la planta**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py preparar_circuito_polvo --aplicar`
Expected: termina con `Circuito preparado.`

Comprobar que haya al menos un evaporador libre (cada corrida fallida deja uno ocupado y no hay API para cancelar). Si no hay ninguno, detenerse y avisar.

- [ ] **Step 5: Correr la cadena completa — una sola vez**

Run: `cd frontend && E2E_USUARIO=e2e_auditoria E2E_CLAVE=auditoria-e2e-ccaa E2E_CLAVE_AREAS=flujo-e2e-ccaa npx playwright test --project=circuito --project=flujo-polvo`
Expected: `4 passed` (sesion, circuito, evaporacion, flujo-polvo).

Verificar en la base que el último vale tiene las dos fechas selladas:

Run: `cd backend && ./.venv/Scripts/python.exe manage.py shell -c "from estandarizacion.models import ValeEstandarizacion as V; v = V.objects.exclude(estado='borrador').order_by('-id').first(); print(v.codigo, v.fecha, v.ejecutado_en)"`
Expected: código `VE<año><juliano>-NN` cuyo día coincide con `fecha` (la de hoy), y `ejecutado_en` con fecha y hora (no `None`).

- [ ] **Step 6: Commit**

```bash
git add frontend/e2e/circuito-polvo.spec.ts
git commit -m "test(e2e): el circuito ya no teclea la fecha del vale"
```
