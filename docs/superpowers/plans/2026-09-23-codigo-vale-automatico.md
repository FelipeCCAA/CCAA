# Código de vale automático — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El código del vale de estandarización lo asigna el sistema al confirmar (`VE6266-01`) y deja de teclearse.

**Architecture:** Tres funciones puras en `estandarizacion/dominio.py` arman y leen el código. El `save()` de `ValeEstandarizacion` asigna el código a todo vale que deja de ser borrador sin código definitivo, reintentando ante colisión dentro de un savepoint. El código deja de ser escribible en serializer, admin y formulario.

**Tech Stack:** Django 6.0.7 + DRF, PostgreSQL, React 19 + TypeScript, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-23-codigo-vale-automatico-design.md`

## Global Constraints

- Formato: `VE` + último dígito del año + día juliano (3 dígitos) + `-` + correlativo (2 o más dígitos). Ejemplo: `VE6266-01`.
- El día sale de `vale.fecha`, nunca del reloj.
- Correlativo = máximo existente con ese prefijo + 1. Un número asignado no se reutiliza.
- Se asigna al confirmar. Un borrador (o borrador descartado, anulado con `BORRADOR-…`) no recibe número.
- Un código explícito (pruebas, histórico) se respeta; solo se asigna si el código falta o empieza por `BORRADOR-`.
- Colisión: hasta **5** intentos, cada uno en su propio `transaction.atomic()`. Agotados: motivo `"No se pudo asignar un código de vale; vuelve a confirmar."`.
- Los códigos históricos no se reescriben.
- Django 6: `Model.save()` acepta **solo argumentos por nombre**.
- Español en código, comentarios y mensajes. Pruebas del backend con `DJANGO_ENV=test` y en serie (`--parallel` se cae en este equipo).

## Mapa de archivos

| Archivo | Cambio |
|---|---|
| `backend/estandarizacion/dominio.py` | + `prefijo_codigo_vale`, `generar_codigo_vale`, `correlativo_de_codigo` |
| `backend/estandarizacion/tests_dominio.py` | + `CodigoValeTests` |
| `backend/estandarizacion/models.py` | + `CodigoValeNoAsignado`, `save()`, `asignar_codigo()`; `confirmar()` y `motivos_para_confirmar()` sin `codigo_propuesto`; − campo `codigo_propuesto` |
| `backend/estandarizacion/migrations/0008_…` | `RemoveField` de `codigo_propuesto` (generada) |
| `backend/estandarizacion/tests_codigo_vale.py` | **Nuevo.** Regla de asignación y API |
| `backend/estandarizacion/serializers.py` | `codigo` solo lectura; − `codigo_propuesto`; − `codigo` de obligatorios |
| `backend/estandarizacion/views.py` | `perform_create` sin `codigo_propuesto`; 400 si se agotan intentos |
| `backend/estandarizacion/admin.py` | `codigo` en `readonly_fields` |
| `backend/usuarios/management/commands/sembrar_flujo_demo.py` | deja de componer el código |
| `backend/estandarizacion/tests_borrador.py`, `backend/produccion/tests_borrador.py` | sin `codigo_propuesto` |
| `frontend/src/pages/Estandarizacion/FormularioVale.tsx` | sale el campo; texto «Se asignará al confirmar» |
| `frontend/src/services/estandarizacion.service.ts` | − `codigo_propuesto` de dos tipos |
| `frontend/e2e/circuito-polvo.spec.ts` | lee el código de la respuesta de confirmación |
| `CLAUDE.md` | decisión vigente |

---

### Task 1: Dominio — armar y leer el código

**Files:**
- Modify: `backend/estandarizacion/dominio.py` (imports al inicio; funciones nuevas al final)
- Test: `backend/estandarizacion/tests_dominio.py`

**Interfaces:**
- Produces:
  - `prefijo_codigo_vale(fecha: date) -> str` — `"VE6266-"`
  - `generar_codigo_vale(fecha: date, correlativo: int) -> str` — `"VE6266-01"`
  - `correlativo_de_codigo(codigo: str, prefijo: str) -> int | None`

- [ ] **Step 1: Escribir las pruebas que fallan**

En `backend/estandarizacion/tests_dominio.py`, reemplazar el bloque de imports:

```python
from unittest import TestCase

from .dominio import (
    Leche, calcular_mezcla, evaluar_rc, litros_a_agregar,
    sugerir_mezcla_con_crema,
)
```

por:

```python
from datetime import date
from unittest import TestCase

from .dominio import (
    Leche, calcular_mezcla, correlativo_de_codigo, evaluar_rc,
    generar_codigo_vale, litros_a_agregar, prefijo_codigo_vale,
    sugerir_mezcla_con_crema,
)
```

Y agregar al final del archivo:

```python
class CodigoValeTests(TestCase):
    """
    El código del vale: VE + año + día juliano + correlativo del día.

    Misma familia que el código de lote (`CCAA6266E1-01`): quien ya lee el día
    juliano en los lotes lo lee igual aquí.
    """

    def test_arma_ve_anio_juliano_y_correlativo(self):
        self.assertEqual(generar_codigo_vale(date(2026, 9, 23), 1), "VE6266-01")

    def test_el_dia_juliano_lleva_ceros(self):
        self.assertEqual(generar_codigo_vale(date(2026, 1, 1), 1), "VE6001-01")

    def test_el_anio_va_por_su_ultimo_digito(self):
        self.assertEqual(generar_codigo_vale(date(2030, 5, 5), 1), "VE0125-01")

    def test_el_correlativo_crece_mas_alla_de_dos_digitos(self):
        self.assertEqual(generar_codigo_vale(date(2026, 9, 23), 100), "VE6266-100")

    def test_el_prefijo_es_lo_que_comparten_los_vales_del_dia(self):
        self.assertEqual(prefijo_codigo_vale(date(2026, 9, 23)), "VE6266-")

    def test_lee_el_correlativo_de_un_codigo_del_dia(self):
        self.assertEqual(correlativo_de_codigo("VE6266-07", "VE6266-"), 7)
        self.assertEqual(correlativo_de_codigo("VE6266-100", "VE6266-"), 100)

    def test_un_codigo_con_otra_forma_no_tiene_correlativo(self):
        """
        En la base conviven códigos de antes de esta regla. Ninguno debe romper
        el cálculo del siguiente número, ni contar como si fuera del día.
        """
        for codigo in (
            "VE-316256", "VE-20260901-01", "jkjfd", "BORRADOR-2D9928CC",
            "VE6266-", "VE6266-0A", "VE6267-01", "",
        ):
            with self.subTest(codigo=codigo):
                self.assertIsNone(correlativo_de_codigo(codigo, "VE6266-"))
```

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test estandarizacion.tests_dominio --noinput`
Expected: ERROR — `ImportError: cannot import name 'correlativo_de_codigo'`

- [ ] **Step 3: Implementar**

En `backend/estandarizacion/dominio.py`, reemplazar:

```python
from dataclasses import dataclass, field
```

por:

```python
from dataclasses import dataclass, field
from datetime import date
```

Y agregar al final del archivo:

```python
# ---------------------------------------------------------- código de vale

def prefijo_codigo_vale(fecha: date) -> str:
    """
    Lo que comparten todos los vales de un día: `VE6266-`.

    VE + último dígito del año + día juliano con tres cifras. Como el código de
    lote, el año va por su último dígito y el prefijo se repite cada diez años;
    no choca, porque el correlativo sigue desde el máximo existente.
    """
    return f"VE{fecha.year % 10}{fecha.timetuple().tm_yday:03d}-"


def generar_codigo_vale(fecha: date, correlativo: int) -> str:
    """
    El código de un vale: `VE6266-01`.

    El correlativo va **siempre**, desde `-01` — mismo criterio que
    `produccion.dominio.generar_codigo_lote`: ponerlo solo desde el segundo deja
    dos formas conviviendo.

    Función pura: arma el texto. **No garantiza unicidad**; la garantiza la base.
    """
    return f"{prefijo_codigo_vale(fecha)}{correlativo:02d}"


def correlativo_de_codigo(codigo: str, prefijo: str) -> int | None:
    """
    El correlativo de un código con ese prefijo, o `None` si no tiene esa forma.

    `None` y no una excepción: en la base hay códigos de antes de esta regla
    (`VE-316256`, `jkjfd`), y ninguno debe romper el cálculo del siguiente.
    """
    if not codigo or not codigo.startswith(prefijo):
        return None

    resto = codigo[len(prefijo):]

    return int(resto) if resto.isdigit() else None
```

- [ ] **Step 4: Correr las pruebas y verificar que pasan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test estandarizacion.tests_dominio --noinput`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/estandarizacion/dominio.py backend/estandarizacion/tests_dominio.py
git commit -m "feat(estandarizacion): generar y leer el código de vale en el dominio"
```

---

### Task 2: Modelo — el vale recibe su código al dejar de ser borrador

**Files:**
- Modify: `backend/estandarizacion/models.py` (imports; `CAMPOS_OBLIGATORIOS_AL_CONFIRMAR` líneas ~73-77; `nuevo_codigo_borrador` ~243-245; `motivos_para_confirmar` ~263-265; `confirmar` ~268-273)
- Create: `backend/estandarizacion/tests_codigo_vale.py`
- Modify: `backend/estandarizacion/tests_borrador.py` (`test_confirmar_reserva_el_codigo_sin_mover_leche`)

**Interfaces:**
- Consumes: `dominio.prefijo_codigo_vale`, `dominio.generar_codigo_vale`, `dominio.correlativo_de_codigo` (Task 1)
- Produces:
  - `estandarizacion.models.CodigoValeNoAsignado(Exception)`
  - `estandarizacion.models.PREFIJO_BORRADOR = "BORRADOR-"`
  - `ValeEstandarizacion.asignar_codigo(**kwargs) -> None` (lanza `CodigoValeNoAsignado`)
  - `ValeEstandarizacion._siguiente_correlativo(self, prefijo: str) -> int`
  - `ValeEstandarizacion.tiene_codigo_provisional() -> bool`

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `backend/estandarizacion/tests_codigo_vale.py`:

```python
"""
El código del vale lo asigna el sistema.

Se prueba sobre el modelo porque la regla vive en su `save()`: así la cubren la
confirmación, la creación directa, el admin y los scripts, sin que ninguno tenga
que acordarse de llamarla.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.utils import timezone

from .dominio import prefijo_codigo_vale
from .models import CodigoValeNoAsignado, ValeEstandarizacion
from .tests_vale import BaseVale

#: Un día fijo, para que los códigos esperados no dependan de cuándo se corre.
DIA = date(2026, 9, 23)

BORRADOR = ValeEstandarizacion.Estado.BORRADOR
ANULADO = ValeEstandarizacion.Estado.ANULADO


class AsignacionCodigoValeTests(BaseVale):

    def confirmado(self, **extra):
        """Un vale ya confirmado (`calculado`) sin código: el modelo se lo asigna."""
        return self.crear_vale(codigo="", fecha=DIA, **extra)

    def borrador(self, **extra):
        return self.crear_vale(
            codigo=ValeEstandarizacion.nuevo_codigo_borrador(),
            fecha=DIA, estado=BORRADOR, **extra,
        )

    def anular(self, vale):
        vale.estado = ANULADO
        vale.save(update_fields=["estado", "actualizado_en"])
        vale.refresh_from_db()

    def test_el_primer_vale_del_dia_es_el_01(self):
        self.assertEqual(self.confirmado().codigo, "VE6266-01")

    def test_el_segundo_vale_del_dia_es_el_02(self):
        self.confirmado()

        self.assertEqual(self.confirmado().codigo, "VE6266-02")

    def test_el_dia_sale_de_la_fecha_del_vale_y_no_del_reloj(self):
        ayer = timezone.localdate() - timedelta(days=1)

        vale = self.crear_vale(codigo="", fecha=ayer)

        self.assertEqual(vale.codigo, f"{prefijo_codigo_vale(ayer)}01")

    def test_un_borrador_no_recibe_codigo(self):
        self.assertTrue(self.borrador().codigo.startswith("BORRADOR-"))

    def test_un_borrador_descartado_no_consume_numero(self):
        """Descartar anula el borrador; con su `BORRADOR-…` y sin número."""
        descartado = self.borrador()
        self.anular(descartado)

        self.assertTrue(descartado.codigo.startswith("BORRADOR-"))
        self.assertEqual(self.confirmado().codigo, "VE6266-01")

    def test_un_vale_anulado_conserva_su_numero_y_no_se_reutiliza(self):
        primero = self.confirmado()
        self.anular(primero)

        self.assertEqual(primero.codigo, "VE6266-01")
        self.assertEqual(self.confirmado().codigo, "VE6266-02")

    def test_los_codigos_de_antes_no_cuentan(self):
        for codigo in ("VE-316256", "VE-20260901-01", "jkjfd"):
            self.crear_vale(codigo=codigo, fecha=DIA)

        self.assertEqual(self.confirmado().codigo, "VE6266-01")

    def test_un_codigo_explicito_se_respeta(self):
        """Las pruebas y el histórico crean vales con código propio."""
        self.assertEqual(self.crear_vale(codigo="VE-1", fecha=DIA).codigo, "VE-1")

    def test_confirmar_un_borrador_le_asigna_el_codigo(self):
        vale = self.borrador()

        self.assertEqual(vale.confirmar(self.usuario), [])

        vale.refresh_from_db()
        self.assertEqual(vale.codigo, "VE6266-01")
        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.CALCULADO)

    def test_una_colision_reintenta_con_el_siguiente_libre(self):
        """
        Dos confirmaciones simultáneas calculan el mismo número. Se simula
        forzando el primer cálculo a proponer uno ya ocupado.
        """
        self.confirmado()  # ocupa VE6266-01
        original = ValeEstandarizacion._siguiente_correlativo
        propuestas = iter([1])

        def forzado(vale, prefijo):
            return next(propuestas, None) or original(vale, prefijo)

        with patch.object(ValeEstandarizacion, "_siguiente_correlativo", forzado):
            vale = self.confirmado()

        self.assertEqual(vale.codigo, "VE6266-02")

    def test_agotados_los_intentos_falla_sin_guardar(self):
        self.confirmado()  # ocupa VE6266-01

        with patch.object(
            ValeEstandarizacion, "_siguiente_correlativo", lambda vale, prefijo: 1
        ):
            with self.assertRaises(CodigoValeNoAsignado):
                self.confirmado()

        self.assertEqual(ValeEstandarizacion.objects.filter(fecha=DIA).count(), 1)

    def test_confirmar_sin_codigo_libre_devuelve_motivo_y_sigue_en_borrador(self):
        vale = self.borrador()
        self.confirmado()  # ocupa VE6266-01

        with patch.object(
            ValeEstandarizacion, "_siguiente_correlativo", lambda vale, prefijo: 1
        ):
            motivos = vale.confirmar(self.usuario)

        self.assertEqual(
            motivos, ["No se pudo asignar un código de vale; vuelve a confirmar."]
        )
        vale.refresh_from_db()
        self.assertEqual(vale.estado, BORRADOR)
        self.assertTrue(vale.codigo.startswith("BORRADOR-"))
```

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test estandarizacion.tests_codigo_vale --noinput`
Expected: ERROR — `ImportError: cannot import name 'CodigoValeNoAsignado'`

- [ ] **Step 3: Implementar en `backend/estandarizacion/models.py`**

3a. Imports. Reemplazar:

```python
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
```

por:

```python
import uuid
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone
```

3b. Justo antes de `class ValeEstandarizacion(DocumentoBorradorMixin, models.Model):`, agregar:

```python
#: El código provisional de un borrador. Un vale con este prefijo todavía no
#: tiene código para la planta.
PREFIJO_BORRADOR = "BORRADOR-"

#: Intentos de asignar un código libre ante confirmaciones simultáneas. Cinco
#: vales del mismo día confirmándose en el mismo instante no ocurren en planta.
INTENTOS_CODIGO = 5


class CodigoValeNoAsignado(Exception):
    """Se agotaron los intentos de asignar un código libre al vale."""
```

3c. `CAMPOS_OBLIGATORIOS_AL_CONFIRMAR`. Reemplazar:

```python
    CAMPOS_OBLIGATORIOS_AL_CONFIRMAR = (
        "codigo_propuesto", "fecha", "producto", "rc_objetivo", "volumen",
        "silo_entera", "silo_destino", "entera_grasa", "entera_sng",
        "litros_entera",
    )
```

por:

```python
    CAMPOS_OBLIGATORIOS_AL_CONFIRMAR = (
        "fecha", "producto", "rc_objetivo", "volumen",
        "silo_entera", "silo_destino", "entera_grasa", "entera_sng",
        "litros_entera",
    )
```

3d. `nuevo_codigo_borrador`. Reemplazar:

```python
        return f"BORRADOR-{uuid.uuid4().hex[:8].upper()}"
```

por:

```python
        return f"{PREFIJO_BORRADOR}{uuid.uuid4().hex[:8].upper()}"
```

3e. `motivos_para_confirmar`: borrar estas tres líneas (el código ya no lo teclea nadie, no puede repetirse):

```python
        codigo = self.codigo_propuesto.strip()
        if codigo and type(self).objects.exclude(pk=self.pk).filter(codigo=codigo).exists():
            motivos.append("El código de vale ya existe.")
```

3f. Reemplazar el `confirmar` completo:

```python
    def confirmar(self, usuario):
        motivos = self.motivos_para_confirmar()
        if motivos:
            return motivos
        self.codigo = self.codigo_propuesto.strip()
        return super().confirmar(usuario)
```

por:

```python
    def confirmar(self, usuario):
        """
        El código lo asigna el `save()` que hace el mixin al confirmar.

        Si no hay código libre, el vale sigue en borrador y el motivo va de
        vuelta al operador, en vez de un error 500.
        """
        estado_previo = self.estado
        try:
            return super().confirmar(usuario)
        except CodigoValeNoAsignado as error:
            self.estado = estado_previo
            return [str(error)]

    # --------------------------------------------------------------- código

    def tiene_codigo_provisional(self):
        return not self.codigo or self.codigo.startswith(PREFIJO_BORRADOR)

    def save(self, **kwargs):
        """
        Un vale que deja de ser borrador sin código definitivo recibe el suyo.

        Va aquí y no en cada camino que confirma, para que la confirmación, la
        creación directa, el admin y los scripts queden cubiertos sin acordarse.
        No toca un código explícito (pruebas, histórico) ni un borrador
        descartado, que pasa a anulado con su `BORRADOR-…` y sin número.
        """
        necesita_codigo = (
            self.estado not in (self.Estado.BORRADOR, self.Estado.ANULADO)
            and self.tiene_codigo_provisional()
        )
        if necesita_codigo:
            self.asignar_codigo(**kwargs)
            return
        super().save(**kwargs)

    def asignar_codigo(self, **kwargs):
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

        for _ in range(INTENTOS_CODIGO):
            self.codigo = dominio.generar_codigo_vale(
                fecha, self._siguiente_correlativo(prefijo)
            )
            try:
                with transaction.atomic():
                    super().save(**kwargs)
                return
            except IntegrityError:
                ocupado = type(self).objects.exclude(pk=self.pk).filter(
                    codigo=self.codigo
                ).exists()
                if not ocupado:
                    # No fue el código: otra restricción. No se enmascara.
                    self.codigo = provisional
                    raise

        self.codigo = provisional
        raise CodigoValeNoAsignado(
            "No se pudo asignar un código de vale; vuelve a confirmar."
        )

    def _siguiente_correlativo(self, prefijo):
        """El máximo correlativo con ese prefijo, más uno. Nunca reutiliza."""
        usados = type(self).objects.filter(codigo__startswith=prefijo).values_list(
            "codigo", flat=True
        )
        correlativos = (dominio.correlativo_de_codigo(c, prefijo) for c in usados)

        return max((n for n in correlativos if n is not None), default=0) + 1
```

- [ ] **Step 4: Ajustar la prueba de borrador que fijaba el código tecleado**

En `backend/estandarizacion/tests_borrador.py`, agregar a los imports:

```python
from django.utils import timezone

from .dominio import generar_codigo_vale
```

y en `test_confirmar_reserva_el_codigo_sin_mover_leche` reemplazar:

```python
        self.assertEqual(respuesta.json()["codigo"], "VE-BORRADOR-1")
```

por:

```python
        # El código ya no se teclea: lo asigna el sistema al confirmar.
        self.assertEqual(
            respuesta.json()["codigo"], generar_codigo_vale(timezone.localdate(), 1)
        )
```

- [ ] **Step 5: Correr las pruebas y verificar que pasan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test estandarizacion --noinput`
Expected: `OK` (todas las de la app, no solo las nuevas: el `save()` toca todo vale)

- [ ] **Step 6: Commit**

```bash
git add backend/estandarizacion/models.py backend/estandarizacion/tests_codigo_vale.py backend/estandarizacion/tests_borrador.py
git commit -m "feat(estandarizacion): el vale recibe su código al dejar de ser borrador"
```

---

### Task 3: Cerrar las puertas por las que se tecleaba el código

**Files:**
- Modify: `backend/estandarizacion/models.py` (borrar campo `codigo_propuesto`, líneas ~93-95)
- Create: `backend/estandarizacion/migrations/0008_remove_valeestandarizacion_codigo_propuesto.py` (generada)
- Modify: `backend/estandarizacion/serializers.py` (`fields`, `read_only_fields`, `validate`)
- Modify: `backend/estandarizacion/views.py` (imports; `perform_create` ~70-75)
- Modify: `backend/estandarizacion/admin.py` (`readonly_fields`)
- Modify: `backend/usuarios/management/commands/sembrar_flujo_demo.py` (~304-305)
- Modify: `backend/estandarizacion/tests_borrador.py`, `backend/produccion/tests_borrador.py`
- Modify: `backend/estandarizacion/tests_codigo_vale.py` (pruebas de API)
- Modify: `CLAUDE.md` (Decisiones vigentes)

**Interfaces:**
- Consumes: `CodigoValeNoAsignado`, asignación en `save()` (Task 2)
- Produces: API donde `codigo` es solo lectura y `codigo_propuesto` no existe

- [ ] **Step 1: Escribir las pruebas de API que fallan**

Agregar al final de `backend/estandarizacion/tests_codigo_vale.py`:

```python
class CodigoValeApiTests(BaseVale):
    """Ningún camino de la API deja escribir el código."""

    def setUp(self):
        from rest_framework.authtoken.models import Token
        from rest_framework.test import APIClient

        from usuarios.models import PerfilUsuario, Rol

        PerfilUsuario.objects.create(usuario=self.usuario, rol=Rol.RECEPCION)
        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.usuario).key}"
        )

    def cuerpo(self, **extra):
        datos = {
            "fecha": DIA.isoformat(),
            "producto": self.producto.id,
            "rc_objetivo": "0.2010",
            "volumen": "10000.00",
            "silo_entera": self.silo_entera.id,
            "silo_descremada": self.silo_descremada.id,
            "silo_destino": self.silo_destino.id,
            "entera_grasa": "3.90",
            "entera_sng": "8.60",
            "descremada_grasa": "0.05",
            "descremada_sng": "8.90",
            "litros_entera": "4000.00",
            "litros_descremada": "6000.00",
        }
        datos.update(extra)
        return datos

    def test_la_creacion_directa_asigna_el_codigo_e_ignora_el_del_cliente(self):
        respuesta = self.cliente.post(
            "/api/estandarizacion/vales/", self.cuerpo(codigo="jkjfd"), format="json"
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.json())
        self.assertEqual(respuesta.json()["codigo"], "VE6266-01")

    def test_la_respuesta_ya_no_trae_codigo_propuesto(self):
        respuesta = self.cliente.post(
            "/api/estandarizacion/vales/", self.cuerpo(), format="json"
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.json())
        self.assertNotIn("codigo_propuesto", respuesta.json())

    def test_un_patch_no_cambia_el_codigo(self):
        vale = self.crear_vale(codigo="", fecha=DIA)

        self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.id}/", {"codigo": "jkjfd"}, format="json"
        )

        vale.refresh_from_db()
        self.assertEqual(vale.codigo, "VE6266-01")

    def test_la_creacion_directa_sin_codigo_libre_responde_400_con_motivo(self):
        self.crear_vale(codigo="", fecha=DIA)  # ocupa VE6266-01

        with patch.object(
            ValeEstandarizacion, "_siguiente_correlativo", lambda vale, prefijo: 1
        ):
            respuesta = self.cliente.post(
                "/api/estandarizacion/vales/", self.cuerpo(), format="json"
            )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("vuelve a confirmar", str(respuesta.json()))
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test estandarizacion.tests_codigo_vale.CodigoValeApiTests --noinput`
Expected: FAIL — la creación directa responde 400 `{"codigo": "Este campo es obligatorio."}` o `KeyError: 'codigo'`; la respuesta todavía trae `codigo_propuesto`.

- [ ] **Step 3: Borrar el campo del modelo**

En `backend/estandarizacion/models.py`, borrar:

```python
    codigo_propuesto = models.CharField(
        "Código definitivo propuesto", max_length=40, blank=True
    )
```

- [ ] **Step 4: Serializer**

En `backend/estandarizacion/serializers.py`:

En `fields`, reemplazar `"id", "codigo", "codigo_propuesto", "fecha",` por `"id", "codigo", "fecha",`.

En `read_only_fields`, reemplazar:

```python
        read_only_fields = [
            "estado", "agitacion_desde", "muestreado_en",
```

por:

```python
        # El código lo asigna el sistema al confirmar (`models.asignar_codigo`).
        # Escribible, era por donde entraban códigos como «jkjfd».
        read_only_fields = [
            "codigo",
            "estado", "agitacion_desde", "muestreado_en",
```

En `validate`, reemplazar:

```python
            obligatorios = (
                "codigo", "fecha", "producto", "rc_objetivo", "volumen",
```

por:

```python
            obligatorios = (
                "fecha", "producto", "rc_objetivo", "volumen",
```

- [ ] **Step 5: Vista de creación directa**

En `backend/estandarizacion/views.py`, reemplazar:

```python
from rest_framework import status, viewsets
```

por:

```python
from rest_framework import serializers, status, viewsets
```

Agregar `CodigoValeNoAsignado` dentro del bloque `from .models import (...)`.

Reemplazar `perform_create`:

```python
    def perform_create(self, serializer):
        serializer.save(
            responsable=self.request.user,
            estado=ValeEstandarizacion.Estado.CALCULADO,
            codigo_propuesto=serializer.validated_data["codigo"],
        )
```

por:

```python
    def perform_create(self, serializer):
        # El código lo asigna el `save()` del vale; el cliente ya no lo manda.
        try:
            serializer.save(
                responsable=self.request.user,
                estado=ValeEstandarizacion.Estado.CALCULADO,
            )
        except CodigoValeNoAsignado as error:
            raise serializers.ValidationError({"codigo": [str(error)]})
```

- [ ] **Step 6: Admin**

En `backend/estandarizacion/admin.py`, reemplazar:

```python
    readonly_fields = (
        "estado", "agitacion_desde", "muestreado_en", "grasa_real", "sng_real",
        "creado_en",
    )
```

por:

```python
    # El código tampoco: lo asigna el sistema al confirmar. Editable aquí sería
    # una tercera puerta para teclearlo.
    readonly_fields = (
        "codigo", "estado", "agitacion_desde", "muestreado_en", "grasa_real",
        "sng_real", "creado_en",
    )
```

- [ ] **Step 7: Siembra de demostración**

En `backend/usuarios/management/commands/sembrar_flujo_demo.py`, en el `ValeEstandarizacion.objects.create(...)` (~línea 304), borrar la línea:

```python
            codigo=f"VE-{self.fecha:%Y%m%d}-01",
```

(El vale se crea `calculado` sin código; el modelo le asigna el suyo. De esta línea salió `VE-20260901-01`.)

- [ ] **Step 8: Pruebas existentes que usaban `codigo_propuesto`**

`backend/estandarizacion/tests_borrador.py`:
- en `datos_completos`, borrar `"codigo_propuesto": "VE-BORRADOR-1",`;
- `self.crear_borrador(codigo_propuesto="VE-PENDIENTE", observaciones="A medio completar")` → `self.crear_borrador(observaciones="A medio completar")`;
- `self.crear_borrador(codigo_propuesto="VE-INCOMPLETO")` → `self.crear_borrador()`;
- en `test_confirma_mezcla_solo_entera_sin_exigir_tanque_descremada`, borrar `"codigo_propuesto": "VE-SOLO-ENTERA",`.

`backend/produccion/tests_borrador.py`: borrar la línea `codigo_propuesto="VE-BOR-LOTE",`.

Verificar que no queda ninguna:

Run: `cd backend && grep -rn "codigo_propuesto" --include="*.py" . | grep -v "\.venv" | grep -v migrations`
Expected: sin salida.

- [ ] **Step 9: Generar y revisar la migración**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py makemigrations estandarizacion -n remove_valeestandarizacion_codigo_propuesto`
Expected: crea `estandarizacion/migrations/0008_remove_valeestandarizacion_codigo_propuesto.py` con **una sola** operación `RemoveField(model_name="valeestandarizacion", name="codigo_propuesto")`. Si genera cualquier otra operación, detenerse y revisar.

Run: `cd backend && ./.venv/Scripts/python.exe manage.py makemigrations --check --dry-run`
Expected: `No changes detected`

- [ ] **Step 10: Decisión en CLAUDE.md**

En `CLAUDE.md`, sección «Decisiones vigentes», justo después del bloque que empieza con `- **Código de lote** (vigente desde 2026-08-20)`, agregar:

```markdown
- **Código de vale** (vigente desde 2026-09-23): lo **asigna el sistema** al confirmar —`VE` + último dígito del año + día juliano (3) + `-` + correlativo del día, p. ej. `VE6266-01`— y **no es editable** en ninguna capa (formulario, serializer, admin). A diferencia del lote, que se *sugiere* y queda editable para poder registrar el histórico del POE anterior, el vale no arrastra histórico: el sistema parte en blanco. Un campo libre era por donde entraban códigos como `jkjfd`. El día sale de `vale.fecha`, no del reloj; el correlativo es el máximo existente más uno, así que un número nunca se reutiliza, y un borrador descartado no consume número. La asignación vive en el `save()` del vale y reintenta ante colisión dentro de un savepoint (`asignar_codigo`). Detalle en `docs/superpowers/specs/2026-09-23-codigo-vale-automatico-design.md`.
```

- [ ] **Step 11: Correr las pruebas y verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test estandarizacion produccion --noinput`
Expected: `OK`

- [ ] **Step 12: Commit**

```bash
git add backend/estandarizacion backend/produccion/tests_borrador.py backend/usuarios/management/commands/sembrar_flujo_demo.py CLAUDE.md
git commit -m "feat(estandarizacion): el código de vale deja de ser escribible"
```

---

### Task 4: Formulario — sin campo de código

**Files:**
- Modify: `frontend/src/pages/Estandarizacion/FormularioVale.tsx` (~35, ~96, ~137, ~326-331)
- Modify: `frontend/src/services/estandarizacion.service.ts` (~27, ~173)

**Interfaces:**
- Consumes: API sin `codigo_propuesto` (Task 3)

- [ ] **Step 1: Quitar `codigo_propuesto` de los tipos**

En `frontend/src/services/estandarizacion.service.ts`, borrar la línea `  codigo_propuesto: string;` de `interface ValeEstandarizacion` y de `interface DatosBorradorVale`.

- [ ] **Step 2: Comprobar que el compilador señala los usos**

Run: `cd frontend && npx tsc -b --pretty false`
Expected: FAIL con errores en `FormularioVale.tsx` (líneas ~96 y ~137) que usan `codigo_propuesto`.

- [ ] **Step 3: Formulario**

En `frontend/src/pages/Estandarizacion/FormularioVale.tsx`:

En `const inicial = {`, borrar `  codigo: "",`.

En `const datosBorrador: DatosBorradorVale = {`, borrar `    codigo_propuesto: datos.codigo,`.

En el `setDatos({ ...inicial, ...` que recupera el borrador, borrar `        codigo: guardado.codigo_propuesto,`.

Reemplazar el campo:

```tsx
          <Campo label="Código de vale">
            <input
              required value={datos.codigo}
              onChange={(e) => cambiar("codigo", e.target.value)}
              className="control"
            />
          </Campo>
```

por:

```tsx
          {/* El código lo asigna el sistema al confirmar (VE + año + día
              juliano + correlativo). Al confirmar, la pantalla abre el vale
              creado, que ya muestra el suyo. */}
          <div className="text-sm text-slate-600">
            Código de vale
            <p className="mt-1 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3 py-2.5 text-slate-600">
              Se asignará al confirmar
            </p>
          </div>
```

(Un `div` y no `Campo`: `Campo` es un `<label>`, y un label sin control asociado es un hallazgo de accesibilidad.)

- [ ] **Step 4: Verificar**

Run: `cd frontend && npx tsc -b --pretty false && npx eslint src/pages/Estandarizacion/FormularioVale.tsx src/services/estandarizacion.service.ts && npm test`
Expected: `tsc` sin errores, `eslint` sin salida, `node --test` todo en verde.

Run: `cd frontend && grep -rn "codigo_propuesto" src`
Expected: sin salida.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Estandarizacion/FormularioVale.tsx frontend/src/services/estandarizacion.service.ts
git commit -m "feat(estandarizacion): el formulario del vale deja de pedir el código"
```

---

### Task 5: E2E — prueba de aceptación de punta a punta

**Files:**
- Modify: `frontend/e2e/circuito-polvo.spec.ts` (constante `VALE` ~79-83; paso 4 ~335 y ~411-413; paso 5 ~415)

**Interfaces:**
- Consumes: formulario sin «Código de vale» (Task 4); respuesta de `confirmar-borrador` con `codigo` (Task 3)

- [ ] **Step 1: Leer el código de la respuesta, no teclearlo**

En `frontend/e2e/circuito-polvo.spec.ts`:

En `const VALE = {`, borrar `  codigo: \`VE-${SELLO}\`,`. `SELLO` se queda: lo siguen usando las guías de los camiones (`GR-ENT-${SELLO}`, `GR-DES-${SELLO}`).

Justo antes de `await test.step("4 · se compone el vale de estandarización", ...`, agregar:

```ts
  /* El código lo asigna el sistema al confirmar; se lee de la respuesta. */
  let codigoVale = "";
```

En el paso 4, borrar:

```ts
    await campo(page, "Código de vale").fill(VALE.codigo);
```

Y reemplazar:

```ts
    await trasGuardar(page, "confirmar-borrador", async () => {
      await page.getByRole("button", { name: "Crear vale" }).click();
    });
```

por:

```ts
    const confirmado = await trasGuardar(page, "confirmar-borrador", async () => {
      await page.getByRole("button", { name: "Crear vale" }).click();
    });
    codigoVale = (await confirmado.json()).codigo;
    expect(codigoVale, "El vale confirmado no trae el código del sistema.").toMatch(
      /^VE\d{4}-\d{2,}$/,
    );
```

En el paso 5, reemplazar:

```ts
    await page.getByRole("button", { name: new RegExp(VALE.codigo) }).first().click();
```

por:

```ts
    await page.getByRole("button", { name: new RegExp(codigoVale) }).first().click();
```

- [ ] **Step 2: Lint**

Run: `cd frontend && npx eslint e2e/circuito-polvo.spec.ts`
Expected: sin salida.

- [ ] **Step 3: Poner el backend en el código nuevo**

El backend corre con `--noreload`: tras los cambios sigue sirviendo el código viejo. Detener el proceso que escucha en el 8000 y levantarlo de nuevo:

Run: `cd backend && ./.venv/Scripts/python.exe manage.py migrate`
Expected: `Applying estandarizacion.0008_remove_valeestandarizacion_codigo_propuesto... OK`

Run (en segundo plano): `cd backend && ./.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --noreload`
Verificar: `curl -s http://127.0.0.1:8000/api/salud/` → `{"estado": "ok"}`

- [ ] **Step 4: Preparar la planta**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py preparar_circuito_polvo --aplicar`
Expected: termina con `Circuito preparado.`

Comprobar que hay al menos un evaporador libre (cada corrida fallida deja uno ocupado y no hay API para cancelar; ver memoria `e2e-cadena-polvo`). Si no hay ninguno, detenerse y avisar: no cancelar ejecuciones que no hayan creado corridas propias.

- [ ] **Step 5: Correr la cadena completa**

Run: `cd frontend && E2E_USUARIO=e2e_auditoria E2E_CLAVE=auditoria-e2e-ccaa E2E_CLAVE_AREAS=flujo-e2e-ccaa npx playwright test --project=circuito --project=flujo-polvo`
Expected: `4 passed` (sesion, circuito, evaporacion, flujo-polvo).

Verificar en la base que el último vale tiene código del sistema:

Run: `cd backend && ./.venv/Scripts/python.exe manage.py shell -c "from estandarizacion.models import ValeEstandarizacion as V; print(V.objects.exclude(estado='borrador').order_by('-id').first().codigo)"`
Expected: un código con forma `VE6266-NN` (el día de la corrida).

- [ ] **Step 6: Commit**

```bash
git add frontend/e2e/circuito-polvo.spec.ts
git commit -m "test(e2e): el circuito lee el código de vale asignado por el sistema"
```

---

### Task 6: Verificación final

- [ ] **Step 1: Suite completa del backend**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test --noinput`
Expected: todo en verde salvo el error preexistente `usuarios.tests_comando_e2e.SinDimensionFuncionalDeEmpresa` (conocido desde `e01db42`, ajeno a esta tarea). Cualquier otro fallo es de esta tarea.

- [ ] **Step 2: Sin rastros del campo**

Run: `cd .. && grep -rn "codigo_propuesto" backend frontend/src frontend/e2e --include="*.py" --include="*.ts" --include="*.tsx" | grep -v migrations`
Expected: sin salida.
