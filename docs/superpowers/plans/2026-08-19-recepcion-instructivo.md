# Recepción — parámetros del Instructivo diario · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que `recepcion` capture los parámetros del formato `CCAA.REC.FORM.002.02` —una fila por camión, con la crioscopía por módulo— y derive lo que la planilla calcula, corrigiendo el defecto de sobreestadía que mide contra un cero.

**Architecture:** `Recepcion` pasa de ser un registro por módulo a un registro por camión; la crioscopía baja a un hijo `ModuloRecepcion`. Los cálculos nuevos (pesajes, sólidos, permanencia, horas a pagar, pool) viven en `recepcion/dominio.py` como funciones puras, sin ORM, cubiertas en `recepcion/tests_dominio.py`. Lo derivable no se guarda: `kg_guia`, la diferencia de pesaje, los sólidos totales y las horas a pagar se calculan al leer, igual que el veredicto de calidad.

**Tech Stack:** Django REST + PostgreSQL (backend), React + TypeScript + Vite (frontend).

**Spec:** [`docs/superpowers/specs/2026-08-19-recepcion-instructivo-design.md`](../specs/2026-08-19-recepcion-instructivo-design.md)

## Global Constraints

- **Español** en UI, datos, nombres de campo y comentarios. Fechas ISO `YYYY-MM-DD`.
- **Las reglas puras van a `dominio.py`**, sin ORM ni DOM, y se cubren en `tests_dominio.py`. Ninguna regla nueva se escribe dentro de una vista.
- **Lo derivable no se persiste.** Si se puede calcular desde lo capturado, es una propiedad o una función de dominio, no una columna.
- **Después de `makemigrations` hay que correr `migrate`.** El runner migra solo la base de pruebas: una migración generada y no aplicada deja la suite verde y revienta en el navegador.
- **Comandos** (desde `backend/`):
  - pruebas: `.venv/Scripts/python.exe manage.py test recepcion -v 2`
  - migraciones: `.venv/Scripts/python.exe manage.py makemigrations recepcion` y luego `.venv/Scripts/python.exe manage.py migrate`
  - frontend (desde `frontend/`): `npx tsc -b` — **no** `npx tsc --noEmit`, que con este `tsconfig.json` de tipo solución no comprueba nada y sale con 0.
- **Cada commit termina con** `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.
- **Constantes declaradas una sola vez**, en `recepcion/dominio.py`: `FACTOR_LITROS_A_KILOS = Decimal("1.03")`, `LIMITE_PERMANENCIA_HORAS = 2.0`, y los límites de `ph_camion` dentro de `LIMITES`.
- **No colapsar filas históricas.** La migración de datos convierte cada `Recepcion` existente en sí misma más un `ModuloRecepcion`; nunca suma litros de filas hermanas.

## Estructura de archivos

| Archivo | Responsabilidad | Tarea |
|---|---|---|
| `backend/recepcion/dominio.py` | Todo el cálculo puro: pesajes, sólidos, tiempos, pool, evaluación, bloqueos de cierre | 1, 2, 4, 6 |
| `backend/recepcion/tests_dominio.py` | **Nuevo.** Pruebas de las funciones puras nuevas | 1, 2, 4, 6 |
| `backend/recepcion/models.py` | `Recepcion` (cabecera), `ModuloRecepcion`, `ControlInhibidores`, `BusquedaProveedor`, catálogos de `controles` | 3, 4, 5, 6 |
| `backend/recepcion/migrations/0011…0014` | Creación del hijo, traslado de datos, retiro de campos, campos nuevos | 3, 5, 6 |
| `backend/recepcion/serializers.py` | Módulos anidados, derivados de solo lectura, validación de `controles` | 7 |
| `backend/recepcion/views.py` | `registrar-llegada/` con el contrato nuevo, `cerrar/`, `catalogos-flujo/`, `resumen-diario/` | 6, 7 |
| `backend/recepcion/admin.py` | Inlines de módulos y de inhibidores | 7 |
| `backend/recepcion/tests_hermanos.py` | Se reescribe: lo que fijaba deja de existir | 3 |
| `frontend/src/services/recepcion.service.ts` | Tipos y llamadas | 8 |
| `frontend/src/pages/Leche/FormularioRecepcion.tsx` | Formulario por bloques del formato | 8 |
| `frontend/src/pages/Leche/TablaRecepciones.tsx` | Columnas nuevas | 8 |
| `CLAUDE.md`, `docs/REGLAS_DE_PLANTA.md` | Decisiones vigentes y estado de las reglas | 9 |

---

## Task 1: Dominio — pesajes y sólidos

**Files:**
- Modify: `backend/recepcion/dominio.py`
- Create: `backend/recepcion/tests_dominio.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `FACTOR_LITROS_A_KILOS: Decimal`
  - `kilos_desde_litros(litros) -> Decimal | None`
  - `diferencia_pesaje(kg_guia, kg_romana) -> Decimal | None`
  - `solidos_totales(grasa, sng) -> float | None`
  - `solidos_totales_kg(kilos, ts) -> float | None`

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `backend/recepcion/tests_dominio.py`:

```python
"""
Cálculos puros de recepción, sin ORM.

Los números de referencia salen de una fila real del formato
`CCAA.REC.FORM.002.02` (31-07-2026, camión JLKD92): 5.321 L de guía, 5.430 kg
de romana, grasa 4,5 y SNG 9,06.
"""

from datetime import time
from decimal import Decimal

from django.test import TestCase

from . import dominio


class PesajesTests(TestCase):
    def test_kilos_de_guia_desde_litros(self):
        self.assertEqual(dominio.kilos_desde_litros(5321), Decimal("5480.63"))

    def test_sin_litros_no_hay_kilos(self):
        """None no es cero: cero diría que el camión llegó vacío."""
        self.assertIsNone(dominio.kilos_desde_litros(None))

    def test_diferencia_es_romana_menos_guia(self):
        self.assertEqual(
            dominio.diferencia_pesaje(Decimal("5480.63"), Decimal("5430")),
            Decimal("-50.63"),
        )

    def test_sin_romana_no_hay_diferencia(self):
        """Falta el pesaje, no es que coincidan."""
        self.assertIsNone(dominio.diferencia_pesaje(Decimal("5480.63"), None))


class SolidosTests(TestCase):
    def test_totales_son_la_suma_de_grasa_y_sng(self):
        self.assertAlmostEqual(dominio.solidos_totales(4.5, 9.06), 13.56, places=2)

    def test_sin_una_de_las_dos_no_hay_total(self):
        self.assertIsNone(dominio.solidos_totales(4.5, None))

    def test_kilos_de_solidos_sobre_el_pesaje_real(self):
        self.assertAlmostEqual(
            dominio.solidos_totales_kg(5430, 13.56), 736.308, places=3
        )

    def test_sin_pesaje_no_hay_kilos_de_solidos(self):
        self.assertIsNone(dominio.solidos_totales_kg(None, 13.56))
```

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

Run: `.venv/Scripts/python.exe manage.py test recepcion.tests_dominio -v 2`
Expected: FAIL — `AttributeError: module 'recepcion.dominio' has no attribute 'kilos_desde_litros'`

- [ ] **Step 3: Implementar en `dominio.py`**

Agregar después del bloque `LIMITES`:

```python
# Factor de conversión de litros a kilos del formato CCAA.REC.FORM.002.02
# (columna I = H × 1,03).
#
# La hoja `Litros-kilos` (0082.MAN.FORM.000112) del mismo libro usa `/0,97`,
# que es 1,030928: no es el mismo número. Manda el de la hoja operativa,
# porque es el que produjo las cifras que la planta reportó. Si Calidad
# resuelve la discrepancia, se cambia aquí y en ningún otro lugar.
FACTOR_LITROS_A_KILOS = Decimal("1.03")


def kilos_desde_litros(litros) -> Decimal | None:
    """Kilos de la guía. Sin litros devuelve None, que no es cero."""
    if litros in (None, ""):
        return None

    return (Decimal(str(litros)) * FACTOR_LITROS_A_KILOS).quantize(Decimal("0.01"))


def diferencia_pesaje(kg_guia, kg_romana) -> Decimal | None:
    """
    Romana menos guía, con su signo (columna M del formato).

    Falta cualquiera de los dos y devuelve None: un cero diría que
    coincidieron, y nadie las comparó.
    """
    if kg_guia in (None, "") or kg_romana in (None, ""):
        return None

    return Decimal(str(kg_romana)) - Decimal(str(kg_guia))


def solidos_totales(grasa, sng) -> float | None:
    """Sólidos totales = grasa + SNG (columna S)."""
    valor_grasa = _numero(grasa)
    valor_sng = _numero(sng)

    if valor_grasa is None or valor_sng is None:
        return None

    return round(valor_grasa + valor_sng, 2)


def solidos_totales_kg(kilos, ts) -> float | None:
    """Kilos de sólidos totales sobre el pesaje real (columna BF)."""
    valor_kilos = _numero(kilos)
    valor_ts = _numero(ts)

    if valor_kilos is None or valor_ts is None:
        return None

    return round(valor_kilos * valor_ts / 100, 3)
```

- [ ] **Step 4: Correr las pruebas y verificar que pasan**

Run: `.venv/Scripts/python.exe manage.py test recepcion.tests_dominio -v 2`
Expected: PASS — 8 pruebas.

- [ ] **Step 5: Commit**

```bash
git add backend/recepcion/dominio.py backend/recepcion/tests_dominio.py
git commit -m "Recepción: pesajes y sólidos totales como cálculo puro"
```

---

## Task 2: Dominio — tiempos, permanencia y horas a pagar

Aquí se corrige el defecto que se midió sobre los 26 archivos: la planilla calcula horas a pagar contra una hora programa vacía, y el resultado son 254 horas fantasma en un día.

**Files:**
- Modify: `backend/recepcion/dominio.py`
- Modify: `backend/recepcion/tests_dominio.py`

**Interfaces:**
- Consumes: nada de la Task 1.
- Produces:
  - `LIMITE_PERMANENCIA_HORAS: float`
  - `Permanencia` (dataclass: `horas: float | None`, `horas_en_planta: float | None`, `motivo: str`)
  - `permanencia(arribo, termino_cip, limite_horas=LIMITE_PERMANENCIA_HORAS) -> Permanencia`
  - `horas_a_pagar(horas) -> int | None`
  - `horas_entre(inicio, fin) -> float | None`

- [ ] **Step 1: Escribir las pruebas que fallan**

Agregar a `backend/recepcion/tests_dominio.py`:

```python
class PermanenciaTests(TestCase):
    def test_descuenta_las_dos_horas_libres(self):
        """Arriba 08:00, termina CIP 11:30: 3,5 h en planta, 1,5 a contar."""
        resultado = dominio.permanencia(time(8, 0), time(11, 30))

        self.assertEqual(resultado.horas_en_planta, 3.5)
        self.assertEqual(resultado.horas, 1.5)
        self.assertEqual(resultado.motivo, "")

    def test_dentro_del_limite_no_acumula(self):
        resultado = dominio.permanencia(time(8, 0), time(9, 30))

        self.assertEqual(resultado.horas, 0.0)

    def test_sin_arribo_no_devuelve_cero_sino_nada(self):
        """
        El defecto de la planilla: la hora programa estaba vacía en 602 de 603
        filas y el cálculo la trataba como cero, así que cada camión 'pagaba'
        la hora del reloj menos dos. Un dato que falta no es un dato que vale
        cero.
        """
        resultado = dominio.permanencia(None, time(11, 30))

        self.assertIsNone(resultado.horas)
        self.assertIsNone(resultado.horas_en_planta)
        self.assertIn("arribo", resultado.motivo.lower())

    def test_sin_termino_de_cip_tampoco(self):
        resultado = dominio.permanencia(time(8, 0), None)

        self.assertIsNone(resultado.horas)
        self.assertIn("cip", resultado.motivo.lower())

    def test_cruzar_la_medianoche_no_da_negativo(self):
        """Turno C: arriba 23:30, termina CIP 01:00. Son 1,5 h, no -22,5."""
        resultado = dominio.permanencia(time(23, 30), time(1, 0))

        self.assertEqual(resultado.horas_en_planta, 1.5)
        self.assertEqual(resultado.horas, 0.0)


class HorasAPagarTests(TestCase):
    def test_redondeo_comercial_sube_sobre_la_media_hora(self):
        self.assertEqual(dominio.horas_a_pagar(7.25), 7)
        self.assertEqual(dominio.horas_a_pagar(8.42), 8)
        self.assertEqual(dominio.horas_a_pagar(16.67), 17)

    def test_la_media_hora_exacta_no_sube(self):
        """El formato usa `>0,5`, no `>=`. Se respeta."""
        self.assertEqual(dominio.horas_a_pagar(9.5), 9)

    def test_sin_permanencia_no_hay_horas_que_pagar(self):
        self.assertIsNone(dominio.horas_a_pagar(None))


class HorasEntreTests(TestCase):
    def test_diferencia_simple(self):
        self.assertEqual(dominio.horas_entre(time(8, 30), time(10, 0)), 1.5)

    def test_falta_un_extremo(self):
        self.assertIsNone(dominio.horas_entre(time(8, 30), None))
```

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

Run: `.venv/Scripts/python.exe manage.py test recepcion.tests_dominio -v 2`
Expected: FAIL — `module 'recepcion.dominio' has no attribute 'permanencia'`

- [ ] **Step 3: Implementar en `dominio.py`**

Agregar al final del archivo:

```python
# Horas de permanencia libres antes de que empiece a contar la sobreestadía.
# Es el valor de la celda AI14 del formato (0,0833 de día = 2 h).
LIMITE_PERMANENCIA_HORAS = 2.0


@dataclass(frozen=True)
class Permanencia:
    # Horas por sobre el límite libre. None cuando falta una marca horaria:
    # nunca cero, porque un cero se suma y una ausencia no.
    horas: float | None
    horas_en_planta: float | None
    motivo: str = ""


def horas_entre(inicio, fin) -> float | None:
    """
    Horas entre dos marcas del reloj.

    Si el fin es anterior al inicio, cruzó la medianoche y se suman 24 h: el
    turno C existe, y un camión que arriba 23:30 y termina 01:00 estuvo hora y
    media, no menos veintidós.
    """
    if inicio is None or fin is None:
        return None

    minutos = (fin.hour * 60 + fin.minute) - (inicio.hour * 60 + inicio.minute)

    if minutos < 0:
        minutos += 24 * 60

    return minutos / 60


def permanencia(
    arribo, termino_cip, limite_horas: float = LIMITE_PERMANENCIA_HORAS
) -> Permanencia:
    """
    Horas de permanencia por sobre el límite libre.

    Se cuenta desde el **arribo a portería** hasta el término del lavado CIP.
    El formato la cuenta desde la «hora programa», que en los 26 libros de
    julio está llena en 1 de 603 filas: restaba contra cero y devolvía la hora
    del reloj menos dos. Por eso aquí un dato ausente devuelve None con su
    motivo, y no un número que alguien va a sumar.
    """
    if arribo is None:
        return Permanencia(None, None, "Falta la hora de arribo a portería.")

    if termino_cip is None:
        return Permanencia(None, None, "Falta la hora de término del lavado CIP.")

    en_planta = horas_entre(arribo, termino_cip)

    return Permanencia(
        horas=round(max(0.0, en_planta - limite_horas), 2),
        horas_en_planta=round(en_planta, 2),
    )


def horas_a_pagar(horas) -> int | None:
    """
    Redondeo comercial del formato (columna AT): sube solo si la fracción
    **supera** la media hora. Exactamente 0,5 no sube.
    """
    if horas is None:
        return None

    entero = int(horas)

    return entero + (1 if horas - entero > 0.5 else 0)
```

- [ ] **Step 4: Correr las pruebas y verificar que pasan**

Run: `.venv/Scripts/python.exe manage.py test recepcion.tests_dominio -v 2`
Expected: PASS — 18 pruebas.

- [ ] **Step 5: Commit**

```bash
git add backend/recepcion/dominio.py backend/recepcion/tests_dominio.py
git commit -m "Recepción: permanencia y horas a pagar, sin tratar la ausencia como cero"
```

---

## Task 3: `ModuloRecepcion` — la crioscopía baja al módulo

**Files:**
- Modify: `backend/recepcion/models.py`
- Create: `backend/recepcion/migrations/0011_modulorecepcion.py` (generada)
- Create: `backend/recepcion/migrations/0012_modulos_desde_recepcion.py` (a mano)
- Create: `backend/recepcion/migrations/0013_recepcion_sin_modulo.py` (generada)
- Create: `backend/recepcion/tests_modulos.py`
- Rewrite: `backend/recepcion/tests_hermanos.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `ModuloRecepcion` con campos `recepcion` (FK, `related_name="modulos"`), `numero` (`PositiveSmallIntegerField`), `crioscopia` (`DecimalField(6,3)`, nulable), `carga_recoleccion` (FK a `recoleccion.CargaModulo`, nulable).
  - `Recepcion` pierde `modulo`, `llegada_id` y `carga_recoleccion`.
  - `Recepcion.diferencia_recoleccion_litros` pasa a comparar contra la suma de las cargas de sus módulos.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `backend/recepcion/tests_modulos.py`:

```python
"""
Un camión, un registro. Solo la crioscopía se mide por compartimiento.

La planilla pone M1..M4 en una sola fila porque un camión trae hasta cuatro
módulos, pero los litros, el silo y el destino son del camión. Aquí se fija
esa forma.
"""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from usuarios.tenancy import sucursal_predeterminada_pruebas

from .models import ModuloRecepcion, Recepcion


class ModuloRecepcionTests(TestCase):
    def _recepcion(self):
        return Recepcion.objects.create(
            sucursal=sucursal_predeterminada_pruebas(),
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("19339"),
        )

    def test_un_camion_lleva_varios_modulos_con_su_crioscopia(self):
        recepcion = self._recepcion()

        for numero, valor in ((1, "-0.521"), (2, "-0.532"), (3, "-0.530"), (4, "-0.534")):
            ModuloRecepcion.objects.create(
                recepcion=recepcion, numero=numero, crioscopia=Decimal(valor)
            )

        self.assertEqual(recepcion.modulos.count(), 4)
        self.assertEqual(
            [m.numero for m in recepcion.modulos.order_by("numero")], [1, 2, 3, 4]
        )

    def test_no_se_repite_el_numero_de_modulo_en_el_mismo_camion(self):
        recepcion = self._recepcion()
        ModuloRecepcion.objects.create(recepcion=recepcion, numero=1)

        with self.assertRaises(Exception):
            ModuloRecepcion.objects.create(recepcion=recepcion, numero=1)

    def test_el_modulo_no_lleva_litros(self):
        """Los litros son del camión: que el módulo no los tenga es la regla."""
        self.assertFalse(
            any(campo.name == "litros" for campo in ModuloRecepcion._meta.get_fields())
        )

    def test_la_recepcion_ya_no_tiene_modulo_ni_llegada(self):
        nombres = {campo.name for campo in Recepcion._meta.get_fields()}

        self.assertNotIn("modulo", nombres)
        self.assertNotIn("llegada_id", nombres)
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `.venv/Scripts/python.exe manage.py test recepcion.tests_modulos -v 2`
Expected: FAIL — `ImportError: cannot import name 'ModuloRecepcion'`

- [ ] **Step 3: Crear el modelo en `models.py`**

Agregar después de la clase `Recepcion`:

```python
class ModuloRecepcion(models.Model):
    """
    Un compartimiento del camión.

    Lo único que se mide por módulo es la crioscopía: el formato la anota en
    las columnas M1 a M4 de la misma fila. Los litros, el silo y el destino
    son del camión, así que no están aquí — ponerlos abriría la puerta a que
    dos módulos del mismo camión declararan silos distintos.
    """

    recepcion = models.ForeignKey(
        Recepcion,
        on_delete=models.CASCADE,
        related_name="modulos",
        verbose_name="Recepción",
    )
    numero = models.PositiveSmallIntegerField(
        "Módulo",
        help_text="1 a 4, como las columnas M1-M4 del formato",
    )
    crioscopia = models.DecimalField(
        "Crioscopía",
        max_digits=6,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Un valor MENOS negativo que el límite sugiere agua añadida",
    )
    carga_recoleccion = models.ForeignKey(
        "recoleccion.CargaModulo",
        on_delete=models.PROTECT,
        related_name="modulos_recepcion",
        null=True,
        blank=True,
        verbose_name="Carga esperada de Recolección",
    )

    class Meta:
        verbose_name = "Módulo de la recepción"
        verbose_name_plural = "Módulos de la recepción"
        ordering = ["recepcion", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["recepcion", "numero"], name="modulo_unico_por_recepcion"
            ),
            models.CheckConstraint(
                condition=models.Q(numero__gte=1), name="modulo_numero_positivo"
            ),
        ]

    def __str__(self):
        return f"{self.recepcion_id} · M{self.numero}"
```

- [ ] **Step 4: Generar y aplicar la migración de creación**

```bash
cd backend
.venv/Scripts/python.exe manage.py makemigrations recepcion --name modulorecepcion
.venv/Scripts/python.exe manage.py migrate
```

- [ ] **Step 5: Escribir la migración de datos**

Crear `backend/recepcion/migrations/0012_modulos_desde_recepcion.py`:

```python
"""
Traslada el módulo y la crioscopía de cada recepción a su hijo.

NO colapsa filas hermanas. Sumar los litros de dos recepciones del mismo
camión exigiría decidir qué silo, qué estado y qué veredicto quedan, y
produciría un registro que nadie hizo. Las filas viejas quedan como están; la
forma nueva —un camión, un registro— rige desde la captura siguiente.

A una recepción sin módulo ni crioscopía se le crea igual un módulo vacío:
que la relación sea siempre no vacía evita que cada consumidor tenga que
distinguir el caso.
"""

from django.db import migrations


def _numero_de_modulo(texto):
    """`Módulo 2`, `M2`, `2` → 2. Cualquier otra cosa → 1."""
    digitos = "".join(caracter for caracter in (texto or "") if caracter.isdigit())

    if not digitos:
        return 1

    numero = int(digitos)

    return numero if 1 <= numero <= 4 else 1


def poblar(apps, schema_editor):
    Recepcion = apps.get_model("recepcion", "Recepcion")
    ModuloRecepcion = apps.get_model("recepcion", "ModuloRecepcion")

    for recepcion in Recepcion.objects.all().iterator():
        controles = recepcion.controles or {}
        crioscopia = controles.pop("crioscopia", None)

        ModuloRecepcion.objects.create(
            recepcion=recepcion,
            numero=_numero_de_modulo(recepcion.modulo),
            crioscopia=crioscopia if crioscopia not in (None, "") else None,
            carga_recoleccion_id=recepcion.carga_recoleccion_id,
        )

        # La clave sale de `controles` porque deja de estar declarada: dejarla
        # haría fallar el `clean()` de la fila la próxima vez que se guarde.
        recepcion.controles = controles
        recepcion.save(update_fields=["controles"])


def revertir(apps, schema_editor):
    ModuloRecepcion = apps.get_model("recepcion", "ModuloRecepcion")
    ModuloRecepcion.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [("recepcion", "0011_modulorecepcion")]

    operations = [migrations.RunPython(poblar, revertir)]
```

- [ ] **Step 6: Retirar los campos viejos de `Recepcion`**

En `backend/recepcion/models.py`:

1. Borrar los campos `llegada_id`, `carga_recoleccion` y `modulo` de `Recepcion`.
2. Reemplazar la propiedad `diferencia_recoleccion_litros` por:

```python
    @property
    def diferencia_recoleccion_litros(self):
        """
        Litros del camión contra lo que Recolección esperaba.

        Compara contra la **suma** de las cargas de los módulos: la carga de
        recolección es por módulo y los litros son del camión. Sin ninguna
        carga vinculada devuelve None, que no es lo mismo que una diferencia
        de cero.
        """
        cargas = [
            modulo.carga_recoleccion
            for modulo in self.modulos.all()
            if modulo.carga_recoleccion_id
        ]

        if not cargas:
            return None

        return self.litros - sum(carga.litros for carga in cargas)
```

3. Quitar `crioscopia` de `CONTROLES_DECLARADOS` y de `CONTROLES_NUMERICOS`, y borrar por completo las constantes `CONTROLES_POR_MODULO` y `CONTROLES_POR_CAMION` (todo `controles` es del camión ahora).
4. Quitar de `dominio.evaluar_recepcion` el bloque que lee `c.get("crioscopia")` — vuelve en la Task 4 leyendo los módulos.

- [ ] **Step 7: Generar y aplicar la migración de retiro**

```bash
cd backend
.venv/Scripts/python.exe manage.py makemigrations recepcion --name recepcion_sin_modulo
.venv/Scripts/python.exe manage.py migrate
```

- [ ] **Step 8: Reescribir `tests_hermanos.py`**

Reemplazar el archivo completo por:

```python
"""
Lo que este archivo fijaba —que los módulos hermanos de un camión comparten
los controles de la carga— dejó de ser un problema: un camión es **un**
registro, así que no hay hermanos que sincronizar. La crioscopía, lo único que
se mide por compartimiento, vive en `ModuloRecepcion` (ver `tests_modulos`).

Lo que sigue vigente y por eso se conserva: **no se reescribe lo ya decidido.**
El veredicto se deriva de los controles en vez de guardarse, así que tocarlos
después de liberar cambiaría el veredicto de leche que ya está en el silo.
"""

from recepcion.models import Recepcion
from recepcion.tests import BaseAPIRecepcion


CARGA_LIMPIA = {
    "delvo": "Negativo",
    "inhibidores": "Negativo",
    "temperatura": 4.0,
    "acidez": 16.0,
    "ph": 6.7,
}


class NoSeReescribeLoDecididoTests(BaseAPIRecepcion):
    def test_una_recepcion_liberada_no_admite_cambio_de_controles(self):
        recepcion = Recepcion.objects.create(
            sucursal=self.sucursal,
            fecha="2026-07-20",
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=5000,
            controles=CARGA_LIMPIA,
            estado=Recepcion.Estado.LIBERADA,
        )

        respuesta = self.cliente.patch(
            f"/api/recepcion/recepciones/{recepcion.id}/",
            {"controles": {**CARGA_LIMPIA, "delvo": "Positivo"}},
            format="json",
        )

        recepcion.refresh_from_db()
        self.assertEqual(
            recepcion.controles["delvo"],
            "Negativo",
            "los controles de una recepción liberada no se reescriben",
        )
```

> Nota para quien ejecuta: `BaseAPIRecepcion` está en `recepcion/tests.py`. Si no expone `self.sucursal`, léelo y usa el atributo que sí crea la sucursal de pruebas; no inventes uno.

- [ ] **Step 9: Correr toda la suite de recepción**

Run: `.venv/Scripts/python.exe manage.py test recepcion -v 2`
Expected: fallan `tests.py`, `tests_consulta.py` y `views.py`/`serializers.py` por las referencias a `modulo`, `llegada_id`, `CONTROLES_POR_CAMION` y `CONTROLES_POR_MODULO`. **Se arreglan aquí mismo**: quitar esas referencias de `serializers.py` (campos `modulo`, `llegada_id`, `carga_recoleccion`, `controles_camion`, `controles_modulo` y sus `SerializerMethodField`, y el bloque de `validate` que compara `modulo` con la carga), de `views.py` (el import, `catalogos-flujo`, y el mensaje de `_notificar_recepcion` que dice `modulo`) y de los tests que los usan.

Run de nuevo hasta verde: `.venv/Scripts/python.exe manage.py test recepcion -v 2`

- [ ] **Step 10: Commit**

```bash
git add backend/recepcion
git commit -m "Recepción: un camión un registro, con la crioscopía en ModuloRecepcion"
```

---

## Task 4: `controles` ampliado y evaluación por módulos

**Files:**
- Modify: `backend/recepcion/models.py`
- Modify: `backend/recepcion/dominio.py`
- Modify: `backend/recepcion/tests_dominio.py`

**Interfaces:**
- Consumes: `ModuloRecepcion` (Task 3), `_numero` (ya existía).
- Produces:
  - `CONTROLES_DECLARADOS` incluye `grasa`, `sng`, `sangre`, `pus`, `materias_extranas`, `aroma`.
  - `crioscopia_pool(valores) -> float | None`
  - `evaluar_recepcion(controles, *, crioscopias=(), ph_camion=None, limites=None) -> EvaluacionRecepcion`
  - `LIMITES` gana `ph_camion_min = 5.5` y `ph_camion_max = 8.5`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Agregar a `backend/recepcion/tests_dominio.py`:

```python
class CrioscopiaPoolTests(TestCase):
    def test_promedio_de_los_modulos_medidos(self):
        self.assertEqual(dominio.crioscopia_pool([-0.521, -0.532, -0.53]), -0.528)

    def test_ignora_los_modulos_sin_lectura(self):
        self.assertEqual(dominio.crioscopia_pool([-0.52, None, None]), -0.52)

    def test_sin_ninguna_lectura_no_hay_pool(self):
        self.assertIsNone(dominio.crioscopia_pool([None, None]))
        self.assertIsNone(dominio.crioscopia_pool([]))


class EvaluacionAmpliadaTests(TestCase):
    def test_una_crioscopia_de_modulo_fuera_de_rango_retiene(self):
        """
        Basta con que UN compartimiento venga aguado: la leche del camión se
        mezcla en el silo, así que el promedio escondería el módulo malo.
        """
        evaluacion = dominio.evaluar_recepcion(
            {"delvo": "Negativo"}, crioscopias=[-0.52, -0.505]
        )

        self.assertEqual(evaluacion.estado, "retenida")
        self.assertTrue(any("M2" in motivo for motivo in evaluacion.motivos))

    def test_todas_las_crioscopias_en_rango_liberan(self):
        evaluacion = dominio.evaluar_recepcion(
            {"delvo": "Negativo"}, crioscopias=[-0.52, -0.53]
        )

        self.assertEqual(evaluacion.estado, "liberada")

    def test_un_item_organoleptico_no_conforme_retiene(self):
        evaluacion = dominio.evaluar_recepcion(
            {"delvo": "Negativo", "sangre": "No conforme"}
        )

        self.assertEqual(evaluacion.estado, "retenida")
        self.assertTrue(any("sangre" in motivo.lower() for motivo in evaluacion.motivos))

    def test_el_organoleptico_viejo_se_sigue_entendiendo(self):
        """Las filas históricas traen una sola clave; no se las deja de leer."""
        evaluacion = dominio.evaluar_recepcion(
            {"delvo": "Negativo", "organoleptico": "No conforme"}
        )

        self.assertEqual(evaluacion.estado, "retenida")

    def test_el_ph_del_camion_fuera_de_rango_retiene(self):
        evaluacion = dominio.evaluar_recepcion({"delvo": "Negativo"}, ph_camion=9.2)

        self.assertEqual(evaluacion.estado, "retenida")
        self.assertTrue(any("camión" in motivo for motivo in evaluacion.motivos))

    def test_el_ph_del_camion_no_es_el_de_la_leche(self):
        """
        7,0 es válido para el enjuague del camión (5,5-8,5) y estaría fuera del
        rango de la leche (6,5-6,9 lo admite, pero 8,0 no). Confundirlos haría
        que el agua retuviera leche conforme.
        """
        evaluacion = dominio.evaluar_recepcion(
            {"delvo": "Negativo", "ph": 6.7}, ph_camion=8.0
        )

        self.assertEqual(evaluacion.estado, "liberada")
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `.venv/Scripts/python.exe manage.py test recepcion.tests_dominio -v 2`
Expected: FAIL — `crioscopia_pool` no existe y `evaluar_recepcion` no acepta `crioscopias`.

- [ ] **Step 3: Ampliar los catálogos en `models.py`**

Reemplazar el bloque de constantes por:

```python
CONTROLES_DECLARADOS = {
    "temperatura",
    "acidez",
    "ph",
    "delvo",
    "inhibidores",
    "grasa",
    "sng",
    # Los cuatro ítems que el formato pide por separado (columnas AC-AF).
    "sangre",
    "pus",
    "materias_extranas",
    "aroma",
    # Clave histórica: dejó de escribirse pero se sigue leyendo, porque las
    # filas anteriores al formato ampliado la tienen y siguen valiendo.
    "organoleptico",
}

CONTROLES_NUMERICOS = {"temperatura", "acidez", "ph", "grasa", "sng"}

ITEMS_ORGANOLEPTICOS = ("sangre", "pus", "materias_extranas", "aroma")

VALORES_ADMITIDOS = {
    "delvo": {"Negativo", "Positivo"},
    "inhibidores": {"Negativo", "Positivo"},
    "organoleptico": {"Conforme", "No conforme"},
    **{item: {"Conforme", "No conforme"} for item in ITEMS_ORGANOLEPTICOS},
}
```

- [ ] **Step 4: Ampliar el dominio**

En `backend/recepcion/dominio.py`:

1. Agregar a `LIMITES`:

```python
    # pH del enjuague del CAMIÓN, no de la leche. El formato declara el rango
    # en el propio encabezado de la columna AO.
    "ph_camion_min": 5.5,
    "ph_camion_max": 8.5,
```

2. Agregar la función:

```python
def crioscopia_pool(valores) -> float | None:
    """
    Promedio de las crioscopías de los módulos que sí se midieron.

    Es lo que la hoja `Pool Crioscopia` calcula. Sirve para informar, no para
    decidir: el veredicto lo da cada módulo por separado, porque un promedio
    esconde el compartimiento aguado entre los que no lo están.
    """
    medidos = [numero for numero in (_numero(v) for v in valores or []) if numero is not None]

    if not medidos:
        return None

    return round(sum(medidos) / len(medidos), 3)
```

3. Cambiar la firma y el cuerpo de `evaluar_recepcion`:

```python
def evaluar_recepcion(
    controles: dict[str, Any],
    *,
    crioscopias: Iterable[Any] = (),
    ph_camion: Any = None,
    limites: dict | None = None,
) -> EvaluacionRecepcion:
```

Dentro, **después** del bloque de `inhibidores` y **en reemplazo** del antiguo `organoleptico`:

```python
    if c.get("organoleptico") == "No conforme":
        motivos.append("Evaluación organoléptica no conforme.")

    etiquetas = {
        "sangre": "sangre",
        "pus": "pus",
        "materias_extranas": "materias extrañas",
        "aroma": "aroma",
    }
    for clave, etiqueta in etiquetas.items():
        if c.get(clave) == "No conforme":
            motivos.append(f"Inspección visual no conforme: {etiqueta}.")
```

Y **en reemplazo** del bloque que leía `c.get("crioscopia")`:

```python
    for indice, valor in enumerate(crioscopias or [], start=1):
        medida = _numero(valor)
        if medida is not None and medida > lim["crioscopia_max"]:
            motivos.append(
                f"Crioscopía del módulo M{indice} ({medida}) indica posible aguado."
            )

    ph_del_camion = _numero(ph_camion)
    if ph_del_camion is not None and not (
        lim["ph_camion_min"] <= ph_del_camion <= lim["ph_camion_max"]
    ):
        motivos.append(
            f"pH del camión {ph_del_camion} fuera del rango "
            f"{lim['ph_camion_min']}–{lim['ph_camion_max']}."
        )
```

- [ ] **Step 5: Correr las pruebas y verificar que pasan**

Run: `.venv/Scripts/python.exe manage.py test recepcion -v 2`
Expected: PASS. Si `tests.py` falla por la clave `crioscopia` en algún diccionario de prueba, quitarla de ahí: ya no es un control del camión.

- [ ] **Step 6: Commit**

```bash
git add backend/recepcion
git commit -m "Recepción: sólidos, organoléptico en cuatro ítems y crioscopía por módulo"
```

---

## Task 5: Campos de cabecera — destino, pesaje, tiempos e higiene

**Files:**
- Modify: `backend/recepcion/models.py`
- Create: `backend/recepcion/migrations/0014_recepcion_instructivo.py` (generada)
- Create: `backend/recepcion/tests_cabecera.py`

**Interfaces:**
- Consumes: `dominio.kilos_desde_litros`, `dominio.diferencia_pesaje`, `dominio.solidos_totales`, `dominio.solidos_totales_kg`, `dominio.permanencia`, `dominio.horas_a_pagar`, `dominio.horas_entre`, `dominio.crioscopia_pool`.
- Produces, en `Recepcion`:
  - Campos: `certificada`, `uso`, `uso_numero`, `kg_romana`, `hora_programa`, `hora_arribo_porteria`, `hora_ingreso`, `hora_inicio_descarga`, `hora_termino_descarga`, `hora_inicio_cip`, `hora_termino_cip`, `hora_salida`, `lavado_ruedas`, `relavado`, `recambio_dilucion`, `ph_camion`.
  - Enums: `Recepcion.Uso`, `Recepcion.RecambioDilucion`, y `Procedencia` con `CCAA` y `COLUN`.
  - Propiedades: `kg_guia`, `diferencia_kg`, `solidos_totales`, `solidos_totales_kg`, `crioscopia_pool`, `permanencia_horas`, `horas_en_planta`, `horas_a_pagar`, `tiempo_en_fabrica_horas`, `tiempo_de_descarga_horas`, `evaluacion`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `backend/recepcion/tests_cabecera.py`:

```python
"""
Lo derivado no se guarda: se calcula al leer, como el veredicto de calidad.

Los números salen de la fila real del camión JLKD92 del 31-07-2026.
"""

from datetime import date, time
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from usuarios.tenancy import sucursal_predeterminada_pruebas

from .models import ModuloRecepcion, Recepcion


class DerivadosTests(TestCase):
    def setUp(self):
        self.recepcion = Recepcion.objects.create(
            sucursal=sucursal_predeterminada_pruebas(),
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5321"),
            kg_romana=Decimal("5430"),
            controles={"grasa": 4.5, "sng": 9.06},
            hora_arribo_porteria=time(7, 45),
            hora_inicio_descarga=time(8, 30),
            hora_termino_descarga=time(8, 45),
            hora_termino_cip=time(9, 15),
        )

    def test_kilos_de_guia_se_derivan_de_los_litros(self):
        self.assertEqual(self.recepcion.kg_guia, Decimal("5480.63"))

    def test_diferencia_de_pesaje(self):
        self.assertEqual(self.recepcion.diferencia_kg, Decimal("-50.63"))

    def test_solidos_totales(self):
        self.assertAlmostEqual(self.recepcion.solidos_totales, 13.56, places=2)
        self.assertAlmostEqual(self.recepcion.solidos_totales_kg, 736.308, places=3)

    def test_permanencia_descuenta_las_dos_horas_libres(self):
        self.assertEqual(self.recepcion.horas_en_planta, 1.5)
        self.assertEqual(self.recepcion.permanencia_horas, 0.0)
        self.assertEqual(self.recepcion.horas_a_pagar, 0)

    def test_sin_arribo_no_hay_horas_a_pagar(self):
        self.recepcion.hora_arribo_porteria = None
        self.assertIsNone(self.recepcion.permanencia_horas)
        self.assertIsNone(self.recepcion.horas_a_pagar)

    def test_tiempo_de_descarga(self):
        self.assertEqual(self.recepcion.tiempo_de_descarga_horas, 0.25)

    def test_pool_de_crioscopia_desde_los_modulos(self):
        ModuloRecepcion.objects.create(
            recepcion=self.recepcion, numero=1, crioscopia=Decimal("-0.521")
        )
        ModuloRecepcion.objects.create(
            recepcion=self.recepcion, numero=2, crioscopia=Decimal("-0.527")
        )

        self.assertEqual(self.recepcion.crioscopia_pool, -0.524)


class DestinoTests(TestCase):
    def _recepcion(self, **extra):
        return Recepcion(
            sucursal=sucursal_predeterminada_pruebas(),
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5000"),
            **extra,
        )

    def test_el_numero_de_destino_exige_su_familia(self):
        """`n° 2` a secas no dice de qué. Un número suelto no es trazabilidad."""
        with self.assertRaises(ValidationError):
            self._recepcion(uso_numero=2).full_clean()

    def test_semi_con_su_numero_es_valido(self):
        recepcion = self._recepcion(uso=Recepcion.Uso.SEMI, uso_numero=2)
        recepcion.full_clean()

    def test_despacho_no_lleva_numero(self):
        with self.assertRaises(ValidationError):
            self._recepcion(uso=Recepcion.Uso.DESPACHO, uso_numero=2).full_clean()

    def test_ccaa_y_colun_son_procedencias_validas(self):
        valores = {opcion.value for opcion in Recepcion.Procedencia}
        self.assertIn("CCAA", valores)
        self.assertIn("Colun", valores)
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `.venv/Scripts/python.exe manage.py test recepcion.tests_cabecera -v 2`
Expected: FAIL — `Recepcion() got unexpected keyword arguments: 'kg_romana'`

- [ ] **Step 3: Agregar los enums y campos a `Recepcion`**

Ampliar `Procedencia`:

```python
    class Procedencia(models.TextChoices):
        CCAA = "CCAA", "CCAA"
        NESTLE = "Nestlé", "Nestlé"
        COLUN = "Colun", "Colun"
        P_UNION = "P. Unión", "P. Unión"
```

Agregar los enums nuevos dentro de `Recepcion`:

```python
    class Uso(models.TextChoices):
        """
        A qué va la leche del camión. El comentario de la celda O15 del
        formato lo explica: «a qué n° de precondensado va ir esta leche, sirve
        para llevar trazabilidad y desviación de uso».

        Se guarda la familia aparte del número (`uso_numero`) porque la
        pregunta que motiva el campo —qué entró al Semi n°2— no se puede
        hacer contra un texto libre que además viene con variantes de tipeo.
        """

        DESPACHO = "despacho", "Despacho"
        STOCK = "stock", "Stock"
        SEMI = "semi", "Precondensado semidescremado"
        ENTERO = "entero", "Precondensado entero"
        LE = "le", "Leche entera"
        SUERO = "suero", "Suero"
        ANTIBIOTICO = "antibiotico", "Antibiótico"

    class RecambioDilucion(models.TextChoices):
        RECAMBIO = "recambio", "Recambio"
        OK = "ok", "OK"

    # Familias que numeran su destino. `Despacho` o `Stock` con un número
    # detrás no significaría nada.
    USOS_NUMERADOS = ("semi", "entero")
```

Agregar los campos después de `litros`:

```python
    kg_romana = models.DecimalField(
        "Kilos (romana)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="El pesaje real. Los kilos de guía se derivan de los litros.",
    )
    certificada = models.BooleanField(
        "Leche certificada",
        null=True,
        blank=True,
        help_text="Nulo = no se registró, que no es lo mismo que no certificada",
    )
    uso = models.CharField("Uso", max_length=20, choices=Uso.choices, blank=True)
    uso_numero = models.PositiveSmallIntegerField(
        "N° de destino", null=True, blank=True
    )

    # Las ocho marcas horarias del formato. Son fijas y una sola vez por
    # camión, así que van aquí y no en un modelo hijo.
    hora_programa = models.TimeField("Hora programa", null=True, blank=True)
    hora_arribo_porteria = models.TimeField("Arribo a portería", null=True, blank=True)
    hora_ingreso = models.TimeField("Hora de ingreso", null=True, blank=True)
    hora_inicio_descarga = models.TimeField("Inicio de descarga", null=True, blank=True)
    hora_termino_descarga = models.TimeField("Término de descarga", null=True, blank=True)
    hora_inicio_cip = models.TimeField("Inicio del lavado CIP", null=True, blank=True)
    hora_termino_cip = models.TimeField("Término del lavado CIP", null=True, blank=True)
    hora_salida = models.TimeField("Hora de salida", null=True, blank=True)

    # Higiene del camión.
    lavado_ruedas = models.BooleanField("Lavado de ruedas", null=True, blank=True)
    relavado = models.BooleanField(
        "Vuelve a lavarse e ingresa", null=True, blank=True
    )
    recambio_dilucion = models.CharField(
        "Cambio de dilución", max_length=20, choices=RecambioDilucion.choices, blank=True
    )
    ph_camion = models.DecimalField(
        "pH del camión",
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Del enjuague del camión (5,5 a 8,5), NO de la leche. Mezclarlo con "
            "el pH de la leche haría que el agua retuviera un camión conforme."
        ),
    )
```

- [ ] **Step 4: Agregar las propiedades derivadas y la regla de `uso_numero`**

Dentro de `Recepcion`, junto a `diferencia_recoleccion_litros`:

```python
    @property
    def kg_guia(self):
        return dominio.kilos_desde_litros(self.litros)

    @property
    def diferencia_kg(self):
        return dominio.diferencia_pesaje(self.kg_guia, self.kg_romana)

    @property
    def solidos_totales(self):
        controles = self.controles or {}
        return dominio.solidos_totales(controles.get("grasa"), controles.get("sng"))

    @property
    def solidos_totales_kg(self):
        return dominio.solidos_totales_kg(self.kg_romana, self.solidos_totales)

    @property
    def crioscopia_pool(self):
        return dominio.crioscopia_pool(
            [modulo.crioscopia for modulo in self.modulos.all()]
        )

    @property
    def _permanencia(self):
        return dominio.permanencia(self.hora_arribo_porteria, self.hora_termino_cip)

    @property
    def permanencia_horas(self):
        return self._permanencia.horas

    @property
    def horas_en_planta(self):
        return self._permanencia.horas_en_planta

    @property
    def horas_a_pagar(self):
        return dominio.horas_a_pagar(self.permanencia_horas)

    @property
    def tiempo_en_fabrica_horas(self):
        return dominio.horas_entre(self.hora_ingreso, self.hora_termino_cip)

    @property
    def tiempo_de_descarga_horas(self):
        return dominio.horas_entre(
            self.hora_inicio_descarga, self.hora_termino_descarga
        )
```

Y al final de `clean()`:

```python
        # Un número de destino sin familia no dice de qué es, y una familia sin
        # número que la admita convierte el número en ruido.
        if self.uso_numero is not None and self.uso not in self.USOS_NUMERADOS:
            raise ValidationError(
                {
                    "uso_numero": (
                        "Solo los precondensados llevan número de destino. "
                        f"«{self.get_uso_display() or 'sin uso'}» no."
                    )
                }
            )
```

Agregar el import al principio de `models.py`: `from . import dominio`.

> Cuidado con el ciclo: `dominio.py` no importa `models.py`. Si lo hiciera, este import lo rompería. Verificar antes de escribirlo.

- [ ] **Step 5: Generar y aplicar la migración**

```bash
cd backend
.venv/Scripts/python.exe manage.py makemigrations recepcion --name recepcion_instructivo
.venv/Scripts/python.exe manage.py migrate
```

- [ ] **Step 6: Correr las pruebas**

Run: `.venv/Scripts/python.exe manage.py test recepcion -v 2`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/recepcion
git commit -m "Recepción: destino, pesaje de romana, marcas horarias e higiene del camión"
```

---

## Task 6: PPRO N°1 — control de inhibidores y búsqueda a proveedor

Cierra el primer eslabón de la cadena que `docs/REGLAS_DE_PLANTA.md` §1.2 marca como faltante: hoy un positivo retiene y ahí termina todo.

**Files:**
- Modify: `backend/recepcion/models.py`
- Modify: `backend/recepcion/dominio.py`
- Modify: `backend/recepcion/tests_dominio.py`
- Modify: `backend/recepcion/views.py`
- Create: `backend/recepcion/migrations/0015_inhibidores.py` (generada)
- Create: `backend/recepcion/tests_inhibidores.py`

**Interfaces:**
- Consumes: `Recepcion` (Task 5).
- Produces:
  - `ControlInhibidores` (`related_name="controles_inhibidores"`), `BusquedaProveedor` (`related_name="busquedas"`).
  - `dominio.bloqueos_de_cierre(controles, *, busquedas_a_proveedor=0) -> list[str]`
  - Acción `POST /api/recepcion/recepciones/<id>/cerrar/`.

- [ ] **Step 1: Escribir la prueba de dominio que falla**

Agregar a `backend/recepcion/tests_dominio.py`:

```python
class BloqueosDeCierreTests(TestCase):
    def test_positivo_sin_busqueda_no_cierra(self):
        """
        Un positivo retiene, y ahí terminaba todo. El primer eslabón de la
        cadena de REGLAS_DE_PLANTA §1.2 es buscar al proveedor: sin eso, el
        registro dice que hubo antibióticos y no dice de quién.
        """
        bloqueos = dominio.bloqueos_de_cierre({"delvo": "Positivo"})

        self.assertEqual(len(bloqueos), 1)
        self.assertIn("proveedor", bloqueos[0].lower())

    def test_positivo_con_busqueda_cierra(self):
        self.assertEqual(
            dominio.bloqueos_de_cierre(
                {"delvo": "Positivo"}, busquedas_a_proveedor=1
            ),
            [],
        )

    def test_inhibidores_positivos_valen_igual_que_el_delvo(self):
        self.assertEqual(
            len(dominio.bloqueos_de_cierre({"inhibidores": "Positivo"})), 1
        )

    def test_sin_positivos_no_hay_bloqueo(self):
        self.assertEqual(dominio.bloqueos_de_cierre({"delvo": "Negativo"}), [])
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `.venv/Scripts/python.exe manage.py test recepcion.tests_dominio -v 2`
Expected: FAIL — `no attribute 'bloqueos_de_cierre'`

- [ ] **Step 3: Implementar la regla en `dominio.py`**

```python
def bloqueos_de_cierre(controles: dict[str, Any], *, busquedas_a_proveedor: int = 0) -> list[str]:
    """
    Qué impide cerrar la recepción.

    Devuelve motivos y no un booleano, igual que el resto de las decisiones
    del sistema: la pantalla tiene que poder decir por qué no se pudo.
    """
    c = controles or {}
    bloqueos: list[str] = []

    positivo = c.get("delvo") == "Positivo" or c.get("inhibidores") == "Positivo"

    if positivo and busquedas_a_proveedor == 0:
        bloqueos.append(
            "Inhibidores positivos: falta registrar la búsqueda a proveedores "
            "antes de cerrar la recepción."
        )

    return bloqueos
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `.venv/Scripts/python.exe manage.py test recepcion.tests_dominio -v 2`
Expected: PASS.

- [ ] **Step 5: Crear los modelos**

En `backend/recepcion/models.py`, al final:

```python
class ControlInhibidores(models.Model):
    """
    PPRO N°1 — control de inhibidores en leche fresca.

    Origen: hoja `Inhibidores` del Instructivo (`CCAA.REC.FORM.002.01`), que
    la rotula «PPRO N°1» en su encabezado.

    No usa `inocuidad.MonitoreoPPRO` porque ese modelo exige un lote, y esto
    cuelga de un camión y una fecha: la leche todavía no es un lote.
    """

    class Metodo(models.TextChoices):
        TRI_SENSOR = "tri_sensor", "Tri Sensor"
        CHARM = "charm", "Charm"
        DELVO_SP = "delvo_sp", "Delvo SP"

    class Resultado(models.TextChoices):
        NEGATIVO = "negativo", "Negativo"
        POSITIVO = "positivo", "Positivo"

    recepcion = models.ForeignKey(
        Recepcion,
        on_delete=models.CASCADE,
        related_name="controles_inhibidores",
        verbose_name="Recepción",
    )
    metodo = models.CharField(
        "Método", max_length=20, choices=Metodo.choices, default=Metodo.TRI_SENSOR
    )
    tiras_usadas = models.PositiveSmallIntegerField(
        "Tiras usadas",
        default=0,
        help_text="El formato las totaliza al pie: es control de consumo",
    )
    hora_lectura = models.TimeField("Hora de lectura", null=True, blank=True)
    resultado = models.CharField(
        "Resultado", max_length=20, choices=Resultado.choices
    )
    analista = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="controles_inhibidores",
        null=True,
        blank=True,
        verbose_name="Analista",
    )

    class Meta:
        verbose_name = "Control de inhibidores (PPRO N°1)"
        verbose_name_plural = "Controles de inhibidores (PPRO N°1)"
        ordering = ["recepcion", "hora_lectura"]

    def __str__(self):
        return f"{self.recepcion_id} · {self.get_metodo_display()} · {self.resultado}"


class BusquedaProveedor(models.Model):
    """
    Búsqueda del proveedor responsable tras un positivo.

    Es el paso siguiente al positivo, que hasta ahora no existía: la recepción
    quedaba retenida y el registro no decía de quién venía la leche.
    """

    control = models.ForeignKey(
        ControlInhibidores,
        on_delete=models.CASCADE,
        related_name="busquedas",
        verbose_name="Control de inhibidores",
    )
    proveedor = models.CharField("Proveedor", max_length=160)
    charm_bet = models.CharField(
        "Charm rosa Bet",
        max_length=20,
        choices=ControlInhibidores.Resultado.choices,
        blank=True,
    )
    charm_tetra = models.CharField(
        "Charm rosa Tetra",
        max_length=20,
        choices=ControlInhibidores.Resultado.choices,
        blank=True,
    )
    delvo_sp = models.CharField(
        "Delvo SP",
        max_length=20,
        choices=ControlInhibidores.Resultado.choices,
        blank=True,
    )
    hora_lectura = models.TimeField("Hora de lectura", null=True, blank=True)
    resultado = models.CharField(
        "Resultado", max_length=20, choices=ControlInhibidores.Resultado.choices
    )

    class Meta:
        verbose_name = "Búsqueda a proveedor"
        verbose_name_plural = "Búsquedas a proveedores"
        ordering = ["control", "proveedor"]

    def __str__(self):
        return f"{self.proveedor} · {self.resultado}"
```

- [ ] **Step 6: Generar y aplicar la migración**

```bash
cd backend
.venv/Scripts/python.exe manage.py makemigrations recepcion --name inhibidores
.venv/Scripts/python.exe manage.py migrate
```

- [ ] **Step 7: Escribir la prueba de API que falla**

Crear `backend/recepcion/tests_inhibidores.py`:

```python
"""
El positivo ya no termina en 'retenida y nada más'.
"""

from datetime import date, time
from decimal import Decimal

from recepcion.models import BusquedaProveedor, ControlInhibidores, Recepcion
from recepcion.tests import BaseAPIRecepcion


class CierreConInhibidoresTests(BaseAPIRecepcion):
    def _recepcion_positiva(self):
        return Recepcion.objects.create(
            sucursal=self.sucursal,
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5000"),
            controles={"delvo": "Positivo"},
            estado=Recepcion.Estado.RETENIDA,
            motivo="Delvo positivo",
        )

    def test_no_se_cierra_sin_buscar_al_proveedor(self):
        recepcion = self._recepcion_positiva()

        respuesta = self.cliente.post(
            f"/api/recepcion/recepciones/{recepcion.id}/cerrar/", {}, format="json"
        )

        self.assertEqual(respuesta.status_code, 400)
        recepcion.refresh_from_db()
        self.assertEqual(recepcion.estado, Recepcion.Estado.RETENIDA)

    def test_con_la_busqueda_registrada_cierra(self):
        recepcion = self._recepcion_positiva()
        control = ControlInhibidores.objects.create(
            recepcion=recepcion,
            resultado=ControlInhibidores.Resultado.POSITIVO,
            tiras_usadas=2,
            hora_lectura=time(9, 0),
        )
        BusquedaProveedor.objects.create(
            control=control,
            proveedor="Predio Los Álamos",
            resultado=ControlInhibidores.Resultado.POSITIVO,
        )

        respuesta = self.cliente.post(
            f"/api/recepcion/recepciones/{recepcion.id}/cerrar/", {}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200)
        recepcion.refresh_from_db()
        self.assertEqual(recepcion.estado, Recepcion.Estado.CERRADA)

    def test_una_recepcion_limpia_cierra_sin_tramite(self):
        recepcion = Recepcion.objects.create(
            sucursal=self.sucursal,
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5000"),
            controles={"delvo": "Negativo"},
            estado=Recepcion.Estado.DESCARGADA,
        )

        respuesta = self.cliente.post(
            f"/api/recepcion/recepciones/{recepcion.id}/cerrar/", {}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200)
```

- [ ] **Step 8: Correr y verificar que falla**

Run: `.venv/Scripts/python.exe manage.py test recepcion.tests_inhibidores -v 2`
Expected: FAIL — 404, la acción `cerrar` no existe.

- [ ] **Step 9: Agregar la acción `cerrar` en `views.py`**

Dentro de `RecepcionViewSet`, después de `descargar`:

```python
    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        """
        Cierra la recepción.

        Un positivo de inhibidores no basta con retener: antes de cerrar tiene
        que estar registrada la búsqueda al proveedor. Es el primer eslabón de
        la cadena de `REGLAS_DE_PLANTA.md` §1.2, que hasta ahora no existía.
        """
        recepcion = self.get_object()

        busquedas = BusquedaProveedor.objects.filter(
            control__recepcion=recepcion
        ).count()

        bloqueos = dominio.bloqueos_de_cierre(
            recepcion.controles, busquedas_a_proveedor=busquedas
        )

        if bloqueos:
            return Response({"bloqueos": bloqueos}, status=status.HTTP_400_BAD_REQUEST)

        if not recepcion.puede_pasar_a(Recepcion.Estado.CERRADA):
            return Response(
                {
                    "estado": (
                        f"Una recepción {recepcion.get_estado_display()} no puede "
                        "cerrarse."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        recepcion.estado = Recepcion.Estado.CERRADA
        recepcion.save(update_fields=["estado"])

        return Response(self.get_serializer(recepcion).data)
```

Agregar `BusquedaProveedor` al import de `.models` al principio de `views.py`.

- [ ] **Step 10: Correr y verificar que pasa**

Run: `.venv/Scripts/python.exe manage.py test recepcion -v 2`
Expected: PASS.

- [ ] **Step 11: Registrar los modelos en el admin**

En `backend/recepcion/admin.py`:

```python
class BusquedaProveedorInline(admin.TabularInline):
    model = BusquedaProveedor
    extra = 0


@admin.register(ControlInhibidores)
class ControlInhibidoresAdmin(admin.ModelAdmin):
    list_display = ("recepcion", "metodo", "resultado", "tiras_usadas", "hora_lectura")
    list_filter = ("metodo", "resultado")
    inlines = [BusquedaProveedorInline]


class ModuloRecepcionInline(admin.TabularInline):
    model = ModuloRecepcion
    extra = 0
```

Y agregar `inlines = [ModuloRecepcionInline]` al `ModelAdmin` de `Recepcion` que ya existe en el archivo, junto con los imports correspondientes.

- [ ] **Step 12: Commit**

```bash
git add backend/recepcion
git commit -m "Recepción: PPRO N°1 con búsqueda a proveedor obligatoria antes de cerrar"
```

---

## Task 7: API — serializers, `registrar-llegada/` y catálogos

**Files:**
- Modify: `backend/recepcion/serializers.py`
- Modify: `backend/recepcion/views.py`
- Create: `backend/recepcion/tests_api_instructivo.py`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces:
  - `ModuloRecepcionSerializer`, `ControlInhibidoresSerializer`, `BusquedaProveedorSerializer`.
  - `RecepcionSerializer` con `modulos` anidados y los derivados de solo lectura.
  - `POST /api/recepcion/recepciones/registrar-llegada/` con contrato nuevo.
  - `GET /api/recepcion/recepciones/catalogos-flujo/` con `usos`, `procedencias`, `recambios_dilucion`, `controles`.
  - `GET /api/recepcion/recepciones/resumen-diario/?fecha=YYYY-MM-DD`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `backend/recepcion/tests_api_instructivo.py`:

```python
from datetime import date
from decimal import Decimal

from maestros.models import Vehiculo
from recepcion.models import Recepcion
from recepcion.tests import BaseAPIRecepcion


class RegistrarLlegadaTests(BaseAPIRecepcion):
    def test_un_camion_crea_un_registro_con_sus_modulos(self):
        vehiculo = Vehiculo.objects.create(
            sucursal=self.sucursal, placa="JLKD92", numero="109"
        )

        respuesta = self.cliente.post(
            "/api/recepcion/recepciones/registrar-llegada/",
            {
                "fecha": "2026-07-31",
                "vehiculo": vehiculo.id,
                "tipo_leche": "Entera",
                "procedencia": "CCAA",
                "litros": "5321",
                "kg_romana": "5430",
                "uso": "semi",
                "uso_numero": 2,
                "certificada": True,
                "hora_arribo_porteria": "07:45",
                "hora_termino_cip": "09:15",
                "modulos": [
                    {"numero": 1, "crioscopia": "-0.521"},
                    {"numero": 2, "crioscopia": "-0.527"},
                ],
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(Recepcion.objects.count(), 1)

        recepcion = Recepcion.objects.get()
        self.assertEqual(recepcion.litros, Decimal("5321.00"))
        self.assertEqual(recepcion.modulos.count(), 2)

    def test_sin_modulos_no_se_registra(self):
        """La crioscopía se mide por compartimiento: sin módulos no hay dónde."""
        respuesta = self.cliente.post(
            "/api/recepcion/recepciones/registrar-llegada/",
            {
                "fecha": "2026-07-31",
                "tipo_leche": "Entera",
                "litros": "5321",
                "modulos": [],
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_no_se_repite_el_numero_de_modulo(self):
        respuesta = self.cliente.post(
            "/api/recepcion/recepciones/registrar-llegada/",
            {
                "fecha": "2026-07-31",
                "tipo_leche": "Entera",
                "litros": "5321",
                "modulos": [{"numero": 1}, {"numero": 1}],
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)


class DerivadosEnLaApiTests(BaseAPIRecepcion):
    def test_la_ficha_trae_los_calculos_del_formato(self):
        recepcion = Recepcion.objects.create(
            sucursal=self.sucursal,
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5321"),
            kg_romana=Decimal("5430"),
            controles={"grasa": 4.5, "sng": 9.06, "delvo": "Negativo"},
        )

        respuesta = self.cliente.get(
            f"/api/recepcion/recepciones/{recepcion.id}/"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["kg_guia"], "5480.63")
        self.assertEqual(respuesta.data["diferencia_kg"], "-50.63")
        self.assertAlmostEqual(respuesta.data["solidos_totales"], 13.56, places=2)

    def test_los_catalogos_vienen_del_backend(self):
        respuesta = self.cliente.get(
            "/api/recepcion/recepciones/catalogos-flujo/"
        )

        self.assertEqual(respuesta.status_code, 200)
        valores = [opcion["valor"] for opcion in respuesta.data["usos"]]
        self.assertIn("semi", valores)
        self.assertIn("despacho", valores)


class ResumenDiarioTests(BaseAPIRecepcion):
    def test_totaliza_el_dia_como_el_pie_de_la_planilla(self):
        for litros in ("5321", "8560"):
            Recepcion.objects.create(
                sucursal=self.sucursal,
                fecha=date(2026, 7, 31),
                tipo_leche=Recepcion.TipoLeche.ENTERA,
                procedencia=Recepcion.Procedencia.CCAA,
                litros=Decimal(litros),
            )

        respuesta = self.cliente.get(
            "/api/recepcion/recepciones/resumen-diario/?fecha=2026-07-31"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["litros"], "13881.00")
        self.assertEqual(respuesta.data["por_procedencia"]["CCAA"], "13881.00")
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `.venv/Scripts/python.exe manage.py test recepcion.tests_api_instructivo -v 2`
Expected: FAIL en las tres clases.

- [ ] **Step 3: Agregar los serializers hijos**

En `backend/recepcion/serializers.py`, antes de `RecepcionSerializer`:

```python
class ModuloRecepcionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuloRecepcion
        fields = ["id", "numero", "crioscopia", "carga_recoleccion"]


class BusquedaProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusquedaProveedor
        fields = [
            "id", "proveedor", "charm_bet", "charm_tetra",
            "delvo_sp", "hora_lectura", "resultado",
        ]


class ControlInhibidoresSerializer(serializers.ModelSerializer):
    busquedas = BusquedaProveedorSerializer(many=True, read_only=True)
    analista_nombre = serializers.CharField(
        source="analista.get_full_name", read_only=True
    )

    class Meta:
        model = ControlInhibidores
        fields = [
            "id", "recepcion", "metodo", "tiras_usadas", "hora_lectura",
            "resultado", "analista", "analista_nombre", "busquedas",
        ]
```

- [ ] **Step 4: Ampliar `RecepcionSerializer`**

1. Borrar `get_controles_camion` y `get_controles_modulo` y sus `SerializerMethodField` (ya no existe la división).
2. Agregar:

```python
    modulos = ModuloRecepcionSerializer(many=True, required=False)
    controles_inhibidores = ControlInhibidoresSerializer(many=True, read_only=True)

    kg_guia = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    diferencia_kg = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    solidos_totales = serializers.FloatField(read_only=True)
    solidos_totales_kg = serializers.FloatField(read_only=True)
    crioscopia_pool = serializers.FloatField(read_only=True)
    permanencia_horas = serializers.FloatField(read_only=True)
    horas_en_planta = serializers.FloatField(read_only=True)
    horas_a_pagar = serializers.IntegerField(read_only=True)
    tiempo_en_fabrica_horas = serializers.FloatField(read_only=True)
    tiempo_de_descarga_horas = serializers.FloatField(read_only=True)
```

3. En `Meta.fields`, quitar `modulo`, `llegada_id`, `carga_recoleccion`, `controles_camion`, `controles_modulo`; agregar los campos nuevos de la Task 5, `modulos`, `controles_inhibidores` y los diez derivados de arriba.
4. En `Meta.read_only_fields`, quitar `llegada_id`.
5. En `get_evaluacion`, pasar los módulos y el pH del camión:

```python
    def get_evaluacion(self, recepcion):
        evaluacion = dominio.evaluar_recepcion(
            recepcion.controles,
            crioscopias=[
                (modulo.numero, modulo.crioscopia)
                for modulo in recepcion.modulos.all()
            ],
            ph_camion=recepcion.ph_camion,
        )
```

6. En `validate`, borrar el bloque que compara `modulo` con `carga.modulo` (ese campo ya no está en `Recepcion`).

- [ ] **Step 5: Reescribir `registrar_llegada` en `views.py`**

Reemplazar el cuerpo completo de la acción por:

```python
    @action(detail=False, methods=["post"], url_path="registrar-llegada")
    def registrar_llegada(self, request):
        """
        Registra un camión: **un** registro, con sus módulos.

        Los litros, el silo y el destino son del camión. Lo único que baja al
        módulo es la crioscopía, que es lo único que el formato mide por
        compartimiento.
        """
        modulos = request.data.get("modulos")

        if not isinstance(modulos, list) or not modulos:
            return Response(
                {"modulos": "Declara al menos un compartimiento del camión."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        numeros = [item.get("numero") for item in modulos if isinstance(item, dict)]

        if len(numeros) != len(modulos) or any(
            not isinstance(numero, int) or numero < 1 for numero in numeros
        ):
            return Response(
                {"modulos": "Cada módulo necesita su número (1 a 4)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(set(numeros)) != len(numeros):
            return Response(
                {"modulos": "No repitas el mismo número de módulo en el camión."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sucursal = sucursal_para_escritura(request.user, {})

        datos = {
            clave: valor
            for clave, valor in request.data.items()
            if clave != "modulos" and valor not in (None, "")
        }
        datos["sucursal"] = sucursal.id

        serializer = self.get_serializer(data=datos)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            recepcion = serializer.save(
                sucursal=sucursal,
                operador=request.user,
                estado=Recepcion.Estado.REGISTRADA,
            )

            for item in modulos:
                ModuloRecepcion.objects.create(
                    recepcion=recepcion,
                    numero=item["numero"],
                    crioscopia=item.get("crioscopia") or None,
                    carga_recoleccion_id=item.get("carga_recoleccion") or None,
                )

            _notificar_recepcion(
                recepcion,
                tipo="leche_recepcionada",
                titulo="Camion de leche recepcionado",
                mensaje=(
                    f"Se recibieron {recepcion.litros} L del camión "
                    f"{recepcion.vehiculo.placa if recepcion.vehiculo else 'sin patente'} "
                    f"en {len(modulos)} compartimiento(s)."
                ),
                areas=[PerfilUsuario.Area.RECEPCION],
            )

        return Response(
            self.get_serializer(recepcion).data, status=status.HTTP_201_CREATED
        )
```

> El `RecepcionSerializer` declara `modulos` anidado. Como aquí los módulos se crean a mano, hay que asegurarse de que `modulos` no llegue al `serializer.save()`: por eso se excluye de `datos`. Si DRF se queja por el campo anidado escribible, marcarlo `read_only=True` y dejar la creación donde está — un solo camino para crear módulos es mejor que dos.

Agregar `ModuloRecepcion` al import de `.models` en `views.py` y borrar `import uuid` si quedó sin uso.

- [ ] **Step 6: Ampliar `catalogos-flujo` y agregar `resumen-diario`**

Reemplazar el `return` de `catalogos_flujo` por:

```python
        def opciones(choices):
            return [{"valor": valor, "etiqueta": etiqueta} for valor, etiqueta in choices]

        return Response({
            "responsables_recepcion": [
                {
                    "id": usuario.id,
                    "nombre": usuario.get_full_name().strip() or usuario.username,
                    "turno": usuario.perfil.turno,
                }
                for usuario in usuarios.select_related("perfil")
            ],
            # Los catálogos se sirven desde aquí y no se escriben en el
            # frontend: una copia ofrece tarde o temprano un valor que el
            # backend rechaza.
            "usos": opciones(Recepcion.Uso.choices),
            "usos_numerados": list(Recepcion.USOS_NUMERADOS),
            "procedencias": opciones(Recepcion.Procedencia.choices),
            "recambios_dilucion": opciones(Recepcion.RecambioDilucion.choices),
            "controles": sorted(CONTROLES_DECLARADOS),
        })
```

Agregar `CONTROLES_DECLARADOS` al import de `.models`.

Y agregar la acción nueva:

```python
    @action(detail=False, methods=["get"], url_path="resumen-diario")
    def resumen_diario(self, request):
        """
        Los totales que la planilla pone al pie: litros y kilos del día,
        reparto por silo y por procedencia, promedios de grasa y SNG, y las
        horas de sobreestadía.

        Las horas se suman en Python y no en SQL porque `permanencia` devuelve
        `None` cuando falta una marca horaria, y esa distinción —no medido
        contra cero— es justamente la que la planilla perdía.
        """
        fecha = request.query_params.get("fecha")

        if not fecha:
            return Response(
                {"fecha": "Indica la fecha del resumen (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base = filtrar_por_scope(
            Recepcion.objects.filter(fecha=fecha).prefetch_related("modulos"),
            request.user,
            campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )

        recepciones = list(base)

        litros = sum((r.litros or Decimal("0") for r in recepciones), Decimal("0"))
        kg_guia = sum(
            (r.kg_guia or Decimal("0") for r in recepciones), Decimal("0")
        )
        kg_romana = sum(
            (r.kg_romana or Decimal("0") for r in recepciones), Decimal("0")
        )

        por_silo = {}
        por_procedencia = {}
        for recepcion in recepciones:
            if recepcion.silo_id:
                clave = recepcion.silo.codigo
                por_silo[clave] = por_silo.get(clave, Decimal("0")) + recepcion.litros
            if recepcion.procedencia:
                por_procedencia[recepcion.procedencia] = (
                    por_procedencia.get(recepcion.procedencia, Decimal("0"))
                    + recepcion.litros
                )

        grasas = [
            r.controles.get("grasa") for r in recepciones
            if (r.controles or {}).get("grasa") is not None
        ]
        sngs = [
            r.controles.get("sng") for r in recepciones
            if (r.controles or {}).get("sng") is not None
        ]

        horas = [r.horas_a_pagar for r in recepciones]
        medidas = [h for h in horas if h is not None]

        return Response({
            "fecha": fecha,
            "camiones": len(recepciones),
            "litros": str(litros),
            "kg_guia": str(kg_guia),
            "kg_romana": str(kg_romana),
            "diferencia_kg": str(kg_romana - kg_guia),
            "por_silo": {clave: str(valor) for clave, valor in por_silo.items()},
            "por_procedencia": {
                clave: str(valor) for clave, valor in por_procedencia.items()
            },
            "grasa_promedio": round(sum(grasas) / len(grasas), 2) if grasas else None,
            "sng_promedio": round(sum(sngs) / len(sngs), 2) if sngs else None,
            "horas_a_pagar": sum(medidas),
            # Cuántos camiones no se pudieron calcular. Sin esto el total
            # parecería completo aunque le falte la mitad de las marcas.
            "camiones_sin_marcas_horarias": len(horas) - len(medidas),
        })
```

Agregar `from decimal import Decimal` al principio de `views.py`.

- [ ] **Step 7: Correr y verificar que pasa**

Run: `.venv/Scripts/python.exe manage.py test recepcion -v 2`
Expected: PASS.

- [ ] **Step 8: Correr la suite completa del backend**

Run: `.venv/Scripts/python.exe manage.py test -v 1`
Expected: PASS. Prestar atención a `calidad`, `estandarizacion` e `inventario`, que consultan recepciones. Arreglar aquí lo que se rompa.

- [ ] **Step 9: Commit**

```bash
git add backend/recepcion
git commit -m "Recepción: API con módulos anidados, derivados del formato y resumen diario"
```

---

## Task 8: Frontend — tipos, servicio y formulario por bloques

**Files:**
- Modify: `frontend/src/services/recepcion.service.ts`
- Modify: `frontend/src/pages/Leche/FormularioRecepcion.tsx`
- Modify: `frontend/src/pages/Leche/TablaRecepciones.tsx`

**Interfaces:**
- Consumes: el contrato de la Task 7.
- Produces: `Recepcion` sin `modulo`/`llegada_id`/`controles_camion`/`controles_modulo` y con los campos y derivados nuevos; `LlegadaCamionNueva` con litros en la cabecera y `modulos: Array<{numero, crioscopia?, carga_recoleccion?}>`.

- [ ] **Step 1: Actualizar los tipos del servicio**

En `frontend/src/services/recepcion.service.ts`:

```ts
export interface ModuloRecepcion {
  id: number;
  numero: number;
  crioscopia: string | null;
  carga_recoleccion: number | null;
}

export interface Recepcion {
  id: number;
  fecha: string;
  hora: string | null;
  guia: string;
  vehiculo: number | null;
  vehiculo_placa: string | null;
  procedencia: string;
  tipo_leche: string;
  litros: string;
  kg_romana: string | null;
  certificada: boolean | null;
  uso: string;
  uso_numero: number | null;
  silo: number | null;
  silo_codigo: string | null;
  operador_nombre: string;
  turno: string;
  controles: Record<string, number | string>;
  modulos: ModuloRecepcion[];

  /* Marcas horarias del formato CCAA.REC.FORM.002.02 */
  hora_programa: string | null;
  hora_arribo_porteria: string | null;
  hora_ingreso: string | null;
  hora_inicio_descarga: string | null;
  hora_termino_descarga: string | null;
  hora_inicio_cip: string | null;
  hora_termino_cip: string | null;
  hora_salida: string | null;

  /* Higiene del camión */
  lavado_ruedas: boolean | null;
  relavado: boolean | null;
  recambio_dilucion: string;
  ph_camion: string | null;

  /* Derivados: los calcula el backend, no se envían */
  kg_guia: string | null;
  diferencia_kg: string | null;
  solidos_totales: number | null;
  solidos_totales_kg: number | null;
  crioscopia_pool: number | null;
  permanencia_horas: number | null;
  horas_en_planta: number | null;
  horas_a_pagar: number | null;
  tiempo_en_fabrica_horas: number | null;
  tiempo_de_descarga_horas: number | null;

  estado: string;
  estado_etiqueta: string;
  motivo: string;
  observacion: string;
  codigo_muestra: string;
  muestreado_por: number | null;
  muestreado_por_nombre: string;
  muestreado_en: string | null;
  calidad_por: number | null;
  calidad_por_nombre: string;
  calidad_en: string | null;
  silo_asignado_por: number | null;
  silo_asignado_por_nombre: string;
  silo_asignado_en: string | null;
  evaluacion: EvaluacionRecepcion;
}

export interface OpcionCatalogo {
  valor: string;
  etiqueta: string;
}

export interface CatalogosFlujoRecepcion {
  responsables_recepcion: ResponsableRecepcion[];
  usos: OpcionCatalogo[];
  usos_numerados: string[];
  procedencias: OpcionCatalogo[];
  recambios_dilucion: OpcionCatalogo[];
  controles: string[];
}

export interface LlegadaCamionNueva {
  fecha: string;
  hora?: string;
  guia?: string;
  vehiculo: number;
  procedencia?: string;
  tipo_leche: string;
  turno?: string;
  litros: string;
  kg_romana?: string;
  certificada?: boolean;
  uso?: string;
  uso_numero?: number;
  hora_programa?: string;
  hora_arribo_porteria?: string;
  hora_ingreso?: string;
  hora_inicio_descarga?: string;
  hora_termino_descarga?: string;
  hora_inicio_cip?: string;
  hora_termino_cip?: string;
  hora_salida?: string;
  lavado_ruedas?: boolean;
  relavado?: boolean;
  recambio_dilucion?: string;
  ph_camion?: string;
  observacion?: string;
  modulos: Array<{
    numero: number;
    crioscopia?: string;
    carga_recoleccion?: number;
  }>;
}

export interface ResumenDiarioRecepcion {
  fecha: string;
  camiones: number;
  litros: string;
  kg_guia: string;
  kg_romana: string;
  diferencia_kg: string;
  por_silo: Record<string, string>;
  por_procedencia: Record<string, string>;
  grasa_promedio: number | null;
  sng_promedio: number | null;
  horas_a_pagar: number;
  camiones_sin_marcas_horarias: number;
}
```

Quitar `modulo` de `RecepcionNueva` y agregar la llamada:

```ts
export async function resumenDiarioRecepcion(
  fecha: string,
): Promise<ResumenDiarioRecepcion> {
  const { data } = await api.get<ResumenDiarioRecepcion>(
    `recepcion/recepciones/resumen-diario/?fecha=${fecha}`,
  );
  return data;
}
```

> Usar el mismo cliente HTTP y el mismo estilo de las funciones que ya están en el archivo; léelo antes de escribir esta función y copia su forma en vez de introducir otra.

- [ ] **Step 2: Compilar y ver los errores de tipo**

Run (desde `frontend/`): `npx tsc -b`
Expected: FAIL — errores en `FormularioRecepcion.tsx`, `TablaRecepciones.tsx`, `Panel.tsx` y donde se lea `modulo`, `controles_camion` o `controles_modulo`.

- [ ] **Step 3: Rehacer `FormularioRecepcion.tsx`**

Reestructurar el formulario en los bloques del formato. Los cambios concretos:

1. `ModuloFormulario` pasa de `{ modulo: string; litros: string }` a:

```ts
interface ModuloFormulario {
  clave: number;
  numero: number;
  crioscopia: string;
  carga_recoleccion?: number;
}

const nuevoModulo = (clave: number, numero: number): ModuloFormulario => ({
  clave,
  numero,
  crioscopia: "",
});
```

2. Los litros salen del bloque de módulos y suben a la cabecera, junto a `kg_romana`. Se elimina `litrosTotales`: ya no se suman, se escriben. El envío queda:

```ts
await registrarLlegada({
  ...cabecera,
  litros,
  modulos: modulos.map(({ numero, crioscopia, carga_recoleccion }) => ({
    numero,
    crioscopia: crioscopia || undefined,
    carga_recoleccion,
  })),
});
```
3. Se agregan secciones, cada una con su encabezado, en este orden: **Identificación** (fecha, hora, guía, camión, procedencia, turno), **Destino** (tipo de leche, certificada, uso, n° de destino, silo), **Cantidades** (litros, kg romana — con los kg de guía mostrados como cálculo, no como campo), **Analítica** (grasa, SNG, acidez, T°, pH, delvo, inhibidores, y los cuatro ítems visuales), **Módulos** (número + crioscopía), **Tiempos** (las ocho marcas), **Higiene del camión** (lavado de ruedas, relavado, recambio de dilución, pH del camión).
4. El desplegable de `uso` se llena desde `catalogos.usos`, y el campo `uso_numero` solo se muestra si `catalogos.usos_numerados.includes(uso)`.
5. El envío pasa `litros` en la cabecera y `modulos: modulos.map(({ numero, crioscopia, carga_recoleccion }) => ({ numero, crioscopia: crioscopia || undefined, carga_recoleccion }))`.

> Mantener las clases de Tailwind y los componentes que el archivo ya usa (`campo`, `etiqueta`, los iconos de `lucide-react`). No introducir una biblioteca de formularios nueva.

- [ ] **Step 4: Actualizar `TablaRecepciones.tsx`**

Quitar la columna `modulo` y agregar, en este orden después de litros: **kg romana**, **diferencia**, **TS**, **uso** (familia + número), **horas a pagar**. Los tres primeros son strings o `null`; los nulos se muestran como `—`, nunca como `0`.

- [ ] **Step 5: Compilar hasta verde**

Run: `npx tsc -b`
Expected: PASS, sin errores.

- [ ] **Step 6: Probar contra el backend corriendo**

Levantar backend y frontend (ver `COMANDOS_PARA_CORRER.txt`), entrar a `/leche`, registrar un camión con dos módulos y verificar que la ficha muestre los kg de guía, la diferencia y los sólidos totales calculados.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "Leche: formulario por bloques del formato, con los módulos solo para crioscopía"
```

---

## Task 9: Documentación

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/REGLAS_DE_PLANTA.md`

- [ ] **Step 1: Agregar la decisión a `CLAUDE.md`**

En la sección **Decisiones vigentes**, agregar:

```markdown
- **Una recepción es un camión, no un módulo** (desde 2026-08-19,
  `docs/superpowers/specs/2026-08-19-recepcion-instructivo-design.md`). El formato
  `CCAA.REC.FORM.002.02` pone una fila por camión con las crioscopías M1 a M4, porque un
  camión trae hasta cuatro compartimientos pero **un** silo, **unos** litros y **un**
  destino. `ModuloRecepcion` guarda lo único que se mide por compartimiento —la
  crioscopía— y nada más: darle litros abriría la puerta a que dos módulos del mismo
  camión declararan silos distintos. La migración `0012` **no colapsó** las filas
  hermanas existentes: sumar litros de filas con silo, estado o veredicto distintos
  habría producido un registro que nadie hizo.
- **Una marca horaria que falta no vale cero.** `recepcion.dominio.permanencia` devuelve
  `None` con su motivo si falta el arribo a portería o el término del CIP. En los 26
  libros de julio de 2026 la hora programa estaba llena en **1 de 603 filas** y la
  planilla calculaba igual: restaba contra cero, así que cada camión «pagaba» la hora del
  reloj a la que terminó el CIP menos dos. El 31-07 el total del día fue de 254 horas que
  no eran sobreestadía. Por eso la permanencia se cuenta desde el **arribo a portería**, y
  `resumen-diario/` informa `camiones_sin_marcas_horarias` en vez de dejar que el total
  parezca completo.
- **El pH del camión no es el pH de la leche.** `ph_camion` (5,5–8,5) es del enjuague y
  vive en su propia columna; `controles["ph"]` (6,5–6,9) es de la leche. Con una sola
  clave, el pH del agua retendría un camión conforme.
```

En **Trampas conocidas**, agregar:

```markdown
- Los archivos del Instructivo (`Fabricación/2026/Instructivo/`) están **abiertos por
  OneDrive**: leerlos con `ZipFile::OpenRead` falla con «está siendo utilizado en otro
  proceso». Hay que copiarlos a un directorio temporal primero.
```

- [ ] **Step 2: Actualizar `docs/REGLAS_DE_PLANTA.md`**

1. En §1.1, agregar filas a la tabla de umbrales:

```markdown
| pH del camión | 5,5 – 8,5 | Retiene | **Implementado** — `recepcion.dominio.LIMITES["ph_camion_min"/"ph_camion_max"]`, columna AO del formato |
| Permanencia libre | 2 h desde el arribo a portería | Sobre eso, sobreestadía | **Implementado** — `recepcion.dominio.LIMITE_PERMANENCIA_HORAS` |
```

2. En §1.2, reemplazar el párrafo «**Lo que falta:**» por:

```markdown
**Lo que ya existe además** (desde 2026-08-19): `ControlInhibidores` registra el PPRO N°1
—método, tiras usadas, hora de lectura, resultado, analista— y `BusquedaProveedor` el
primer eslabón del escalamiento. Una recepción con inhibidores positivos **no se puede
cerrar** sin al menos una búsqueda registrada (`dominio.bloqueos_de_cierre`).

**Lo que sigue faltando:** la repetición del análisis y su confirmación, el bloqueo del
camión, la apertura de la no conformidad y los avisos a Operaciones y a Calidad.
```

3. En §1.4, agregar bajo el diagrama de estados:

```markdown
La transición a `CERRADA` pasa ahora por la acción `cerrar/`, que consulta
`dominio.bloqueos_de_cierre`. Antes ningún camino del API llevaba a ese estado.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md docs/REGLAS_DE_PLANTA.md
git commit -m "Documentar la recepción por camión y la regla de la marca horaria ausente"
```

---

## Cobertura del spec

| Sección del spec | Tarea |
|---|---|
| §4.1 Forma del registro, migración sin colapsar | 3 |
| §4.2 Destino y procedencia | 5 |
| §4.2 Pesajes (`kg_romana`, derivados) | 1, 5 |
| §4.2 Analítica (`grasa`, `sng`, cuatro ítems) | 4 |
| §4.2 Tiempos (ocho marcas) | 5 |
| §4.2 Higiene (`ph_camion` aparte) | 4, 5 |
| §4.3 `ControlInhibidores`, `BusquedaProveedor`, regla de cierre | 6 |
| §4.4 Dominio: pesajes, sólidos, pool, permanencia, horas a pagar | 1, 2, 4 |
| §4.4 Regla de la marca ausente y del cruce de medianoche | 2 |
| §4.4 Constantes declaradas una vez | 1, 2, 4 |
| §4.5 Serializer, `registrar-llegada/`, catálogos, `resumen-diario/` | 7 |
| §4.5 Pantalla por bloques | 8 |
| §4.6 Pruebas | 1–7 |
| §6 Riesgos 1 y 2 (contrato y `llegada_id`) | 3, 7, 8 |
| §6 Riesgo 4 (`una_descarga_por_recepcion`) | 7 step 8 |
| §6 Riesgo 5 (`hora` sin migrar) | 9 — se documenta, no se decide |
