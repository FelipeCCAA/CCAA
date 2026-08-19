# Análisis de silo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Registrar el análisis de la leche que hay en un silo como dato propio, y que el vale de estandarización lo consuma en vez de que el operador teclee grasa y SNG sin dejar rastro de su origen.

**Architecture:** Un modelo nuevo `AnalisisSilo` en la app `recepcion` —la que ya es dueña del libro mayor del silo—, con la regla de vigencia en `dominio.py` (pura, sin ORM): un análisis deja de servir para componer un vale cuando entró un camión después de la muestra. El vale de estandarización **no cambia su forma**: sigue congelando la composición en sus propias columnas, y solo gana dos claves foráneas de **procedencia** que dicen de qué análisis salieron esos números.

**Tech Stack:** Django REST + PostgreSQL (backend), TypeScript + React (frontend). Pruebas con el runner de Django (`manage.py test`) y `npx tsc -b` para el frontend.

**Origen del requisito:** `docs/LEVANTAMIENTO_REGISTROS_FABRICACION_2026.md` §4.G y §7 (fase 1). El formato de planta es `CCAA.REC.FORM.005.01`, carpeta `Fabricación/2026/Trazabilidad de leche/`.

## Global Constraints

- **PostgreSQL** es el motor. No introducir nada que dependa de SQLite (`DECISIONES.md` §001).
- **Español** en UI, datos, nombres de campo y comentarios. Fechas ISO `YYYY-MM-DD`.
- Las **reglas puras van en `dominio.py`**, sin ORM ni DOM, y se cubren en `tests_dominio*.py`.
- Las **decisiones devuelven motivos, no booleanos** (patrón `Permanencia`, `EvaluacionRecepcion`).
- **Después de `makemigrations` hay que correr `migrate`**: el runner migra solo la base de pruebas, así que una migración sin aplicar deja la suite en verde y revienta en el navegador.
- **Nada de inocuidad ni de operación se decide comparando sucursales** (CLAUDE.md). El aislamiento lo dan los mixins de tenancy existentes.
- Un **`default` de campo que lanza excepción rompe la página «Añadir» del admin**. Los campos nuevos no llevan `default` calculado.
- **No reescribir archivos con acentos usando `Get-Content | ... | Set-Content`** en PowerShell 5.1: usar la herramienta de edición.
- Comprobar el frontend con **`npx tsc -b`** (`tsconfig.json` es de tipo solución; `npx tsc --noEmit` no comprueba nada).
- Comandos del backend desde `backend/`, con el intérprete del entorno virtual: `.venv\Scripts\python.exe manage.py ...`

---

### Task 1: El modelo `AnalisisSilo`

**Files:**
- Modify: `backend/recepcion/models.py` (agregar al final, después de `BusquedaProveedor`)
- Create: `backend/recepcion/migrations/0018_analisis_silo.py` (la genera `makemigrations`)
- Create: `backend/recepcion/tests_analisis_silo.py`

**Interfaces:**
- Consumes: `maestros.Silo`, `recepcion.Recepcion.Procedencia`
- Produces: `recepcion.models.AnalisisSilo` con los campos `silo`, `tomado_en`, `hora_inicio_llenado`, `ph`, `acidez`, `grasa`, `sng`, `proteina`, `temperatura`, `densidad`, `certificada`, `procedencia`, `analista`, `observacion`, `creado_en`. Constraint `analisis_silo_unico_por_momento`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `backend/recepcion/tests_analisis_silo.py`:

```python
"""
El análisis del silo — CCAA.REC.FORM.005.01.

El vale de trazabilidad de planta trae pH, acidez, grasa, SNG, proteína,
temperatura y densidad **del silo**, y es la fuente de los números que la
Hoja RC usa. Hasta ahora solo existían los controles del camión.
"""

from datetime import date, datetime, time, timezone as tz
from decimal import Decimal

from django.db.utils import IntegrityError
from django.test import TestCase

from maestros.models import Silo
from recepcion.models import AnalisisSilo


class AnalisisSiloModeloTests(TestCase):
    def setUp(self):
        self.silo = Silo.objects.create(
            codigo="SILO 6", tipo=Silo.Tipo.SILO, capacidad_l=Decimal("100000")
        )

    def test_guarda_los_siete_parametros_del_formato(self):
        analisis = AnalisisSilo.objects.create(
            silo=self.silo,
            tomado_en=datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc),
            hora_inicio_llenado=time(6, 0),
            ph=Decimal("6.77"),
            acidez=Decimal("15.60"),
            grasa=Decimal("4.35"),
            sng=Decimal("8.90"),
            proteina=Decimal("3.44"),
            temperatura=Decimal("6.00"),
            densidad=Decimal("1032"),
            certificada=True,
        )

        analisis.refresh_from_db()
        self.assertEqual(analisis.grasa, Decimal("4.35"))
        self.assertEqual(analisis.proteina, Decimal("3.44"))
        self.assertEqual(analisis.densidad, Decimal("1032"))
        self.assertIs(analisis.certificada, True)

    def test_dos_analisis_del_mismo_silo_en_el_mismo_instante_no_conviven(self):
        """
        Sería el mismo muestreo cargado dos veces. Dejar pasar el duplicado
        deja al vale eligiendo entre dos análisis que dicen cosas distintas
        de la misma leche.
        """
        momento = datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc)
        AnalisisSilo.objects.create(silo=self.silo, tomado_en=momento, grasa=Decimal("4.35"))

        with self.assertRaises(IntegrityError):
            AnalisisSilo.objects.create(
                silo=self.silo, tomado_en=momento, grasa=Decimal("4.20")
            )

    def test_certificada_nula_no_es_lo_mismo_que_no_certificada(self):
        analisis = AnalisisSilo.objects.create(
            silo=self.silo, tomado_en=datetime(2026, 7, 15, 10, 0, tzinfo=tz.utc)
        )

        self.assertIsNone(analisis.certificada)
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

```
cd backend
.venv\Scripts\python.exe manage.py test recepcion.tests_analisis_silo -v 2
```

Esperado: FAIL — `ImportError: cannot import name 'AnalisisSilo' from 'recepcion.models'`

- [ ] **Step 3: Escribir el modelo**

Agregar al final de `backend/recepcion/models.py`:

```python
class AnalisisSilo(models.Model):
    """
    El análisis de la leche que hay en un silo.

    Origen: el vale `CCAA.REC.FORM.005.01` («Trazabilidad de leche en silos»),
    que trae pH, acidez, grasa, SNG, proteína, temperatura y densidad por silo.

    No se confunde con `Recepcion.controles`, que son los del **camión**: el
    silo mezcla varios camiones, y es esta mezcla —no cada camión— la que
    alimenta el cálculo del RC. Con un solo registro para los dos, un vale
    compuesto desde el análisis de un camión describiría una leche que no
    está en ninguna parte.

    Los siete parámetros son nulables porque el formato se llena por partes:
    la temperatura y el pH se miden al llenar, la grasa y el SNG cuando el
    laboratorio devuelve la muestra. Qué falta para componer un vale lo
    responde `dominio.parametros_faltantes`, no el esquema.
    """

    silo = models.ForeignKey(
        Silo, on_delete=models.PROTECT, related_name="analisis", verbose_name="Silo"
    )
    tomado_en = models.DateTimeField(
        "Hora de toma de muestra",
        help_text="Fecha y hora en que se muestreó el silo. Fija la vigencia del análisis.",
    )
    hora_inicio_llenado = models.TimeField(
        "Hora de inicio de llenado", null=True, blank=True
    )

    ph = models.DecimalField("pH", max_digits=4, decimal_places=2, null=True, blank=True)
    acidez = models.DecimalField(
        "Acidez (°Th)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    grasa = models.DecimalField(
        "Grasa (%)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    sng = models.DecimalField(
        "SNG (%)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    proteina = models.DecimalField(
        "Proteína (%)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    temperatura = models.DecimalField(
        "Temperatura (°C)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    densidad = models.DecimalField(
        "Densidad (kg/m³)", max_digits=7, decimal_places=2, null=True, blank=True
    )

    certificada = models.BooleanField(
        "Leche certificada",
        null=True,
        blank=True,
        help_text="Nulo = no se registró, que no es lo mismo que no certificada",
    )
    procedencia = models.CharField(
        "Procedencia", max_length=20, choices=Recepcion.Procedencia.choices, blank=True
    )
    analista = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="analisis_silo",
        null=True,
        blank=True,
        verbose_name="Analista",
    )
    observacion = models.TextField("Observación", blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Análisis de silo"
        verbose_name_plural = "Análisis de silo"
        ordering = ["-tomado_en"]
        indexes = [models.Index(fields=["silo", "-tomado_en"])]
        constraints = [
            models.UniqueConstraint(
                fields=["silo", "tomado_en"], name="analisis_silo_unico_por_momento"
            ),
        ]

    def __str__(self):
        return f"{self.silo} · {self.tomado_en:%Y-%m-%d %H:%M}"
```

- [ ] **Step 4: Generar y aplicar la migración**

```
cd backend
.venv\Scripts\python.exe manage.py makemigrations recepcion --name analisis_silo
.venv\Scripts\python.exe manage.py migrate
```

Esperado: crea `recepcion/migrations/0018_analisis_silo.py` y la aplica sin errores.

- [ ] **Step 5: Correr las pruebas y verificar que pasan**

```
cd backend
.venv\Scripts\python.exe manage.py test recepcion -v 2
```

Esperado: PASS, incluidas las pruebas de recepción que ya existían.

- [ ] **Step 6: Commit**

```bash
git add backend/recepcion/models.py backend/recepcion/migrations/0018_analisis_silo.py backend/recepcion/tests_analisis_silo.py
git commit -m "Análisis de silo: el modelo del vale CCAA.REC.FORM.005.01"
```

---

### Task 2: La regla de vigencia, pura

**Files:**
- Modify: `backend/recepcion/dominio.py` (agregar al final)
- Modify: `backend/recepcion/tests_dominio.py` (agregar clases al final)

**Interfaces:**
- Consumes: nada del ORM. Recibe valores ya extraídos.
- Produces:
  - `recepcion.dominio.Vigencia` — dataclass congelada con `vigente: bool` y `motivo: str`
  - `recepcion.dominio.analisis_vigente(tomado_en, ingresos) -> Vigencia`, donde `ingresos` es un iterable de pares `(fecha_hora, litros)`
  - `recepcion.dominio.PARAMETROS_ANALISIS_SILO` — tupla de los siete nombres
  - `recepcion.dominio.parametros_faltantes(valores: dict, requeridos) -> list[str]`

- [ ] **Step 1: Escribir las pruebas que fallan**

Agregar al final de `backend/recepcion/tests_dominio.py`:

```python
class VigenciaDelAnalisisDeSiloTests(TestCase):
    """
    Un análisis describe la leche que había cuando se tomó la muestra. Si
    después entró un camión, el silo ya no es el que se midió.
    """

    MOMENTO = datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc)

    def test_sin_ingresos_posteriores_esta_vigente(self):
        resultado = dominio.analisis_vigente(self.MOMENTO, [])

        self.assertTrue(resultado.vigente)
        self.assertEqual(resultado.motivo, "")

    def test_un_ingreso_anterior_no_lo_invalida(self):
        antes = datetime(2026, 7, 15, 8, 0, tzinfo=tz.utc)

        resultado = dominio.analisis_vigente(self.MOMENTO, [(antes, Decimal("21140"))])

        self.assertTrue(resultado.vigente)

    def test_un_ingreso_posterior_lo_invalida_y_dice_cuanto_entro(self):
        despues = datetime(2026, 7, 15, 11, 0, tzinfo=tz.utc)

        resultado = dominio.analisis_vigente(self.MOMENTO, [(despues, Decimal("21140"))])

        self.assertFalse(resultado.vigente)
        self.assertIn("21140", resultado.motivo)
        self.assertIn("1 ingreso", resultado.motivo)

    def test_varios_ingresos_posteriores_se_suman(self):
        resultado = dominio.analisis_vigente(
            self.MOMENTO,
            [
                (datetime(2026, 7, 15, 11, 0, tzinfo=tz.utc), Decimal("10000")),
                (datetime(2026, 7, 15, 13, 0, tzinfo=tz.utc), Decimal("5000")),
                (datetime(2026, 7, 15, 8, 0, tzinfo=tz.utc), Decimal("9999")),
            ],
        )

        self.assertFalse(resultado.vigente)
        self.assertIn("15000", resultado.motivo)
        self.assertIn("2 ingresos", resultado.motivo)

    def test_sin_hora_de_muestreo_no_esta_vigente_y_lo_dice(self):
        """
        Sin la hora no hay contra qué comparar. Devolver `True` aquí haría
        pasar por vigente a un análisis del que no se sabe cuándo se tomó.
        """
        resultado = dominio.analisis_vigente(None, [])

        self.assertFalse(resultado.vigente)
        self.assertIn("hora", resultado.motivo.lower())


class ParametrosFaltantesTests(TestCase):
    def test_devuelve_los_que_faltan_en_el_orden_pedido(self):
        faltan = dominio.parametros_faltantes(
            {"grasa": Decimal("4.35"), "sng": None}, ("grasa", "sng")
        )

        self.assertEqual(faltan, ["sng"])

    def test_sin_faltantes_devuelve_lista_vacia(self):
        faltan = dominio.parametros_faltantes(
            {"grasa": Decimal("4.35"), "sng": Decimal("8.90")}, ("grasa", "sng")
        )

        self.assertEqual(faltan, [])

    def test_una_clave_ausente_cuenta_como_faltante(self):
        faltan = dominio.parametros_faltantes({}, ("grasa",))

        self.assertEqual(faltan, ["grasa"])
```

`tests_dominio.py` importa hoy `from datetime import time`. Cambiar esa línea por:

```python
from datetime import datetime, time, timezone as tz
```

`Decimal`, `TestCase` y `from . import dominio` ya están en la cabecera del archivo.

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

```
cd backend
.venv\Scripts\python.exe manage.py test recepcion.tests_dominio -v 2
```

Esperado: FAIL — `AttributeError: module 'recepcion.dominio' has no attribute 'analisis_vigente'`

- [ ] **Step 3: Escribir el dominio**

Agregar al final de `backend/recepcion/dominio.py`:

```python
#: Los siete parámetros que el vale de trazabilidad pide por silo.
PARAMETROS_ANALISIS_SILO = (
    "ph", "acidez", "grasa", "sng", "proteina", "temperatura", "densidad",
)


@dataclass(frozen=True)
class Vigencia:
    """Si un análisis todavía describe lo que hay en el silo, y por qué no."""

    vigente: bool
    motivo: str


def analisis_vigente(tomado_en, ingresos) -> Vigencia:
    """
    Un análisis vale mientras nadie haya agregado leche después de la muestra.

    `ingresos` son pares `(fecha_hora, litros)` de los ingresos del silo, ya
    filtrados por quien llama: esta función no consulta la base.

    Devuelve motivo y no solo un booleano porque quien lo lee necesita saber
    qué hacer — y lo que hay que hacer es volver a muestrear.
    """
    if tomado_en is None:
        return Vigencia(False, "El análisis no tiene hora de muestreo.")

    posteriores = [
        (cuando, litros) for cuando, litros in ingresos if cuando > tomado_en
    ]

    if not posteriores:
        return Vigencia(True, "")

    total = sum(litros for _, litros in posteriores)
    palabra = "ingreso" if len(posteriores) == 1 else "ingresos"

    return Vigencia(
        False,
        f"Entraron {total:g} L al silo después de la muestra "
        f"({len(posteriores)} {palabra}); vuelve a muestrear.",
    )


def parametros_faltantes(valores, requeridos) -> list[str]:
    """
    Cuáles de `requeridos` no están cargados en `valores`.

    Un parámetro ausente y uno en `None` son lo mismo: no se midió.
    """
    return [nombre for nombre in requeridos if valores.get(nombre) is None]
```

Verificar que `dataclass` ya esté importado en la cabecera del archivo (lo está: `EvaluacionRecepcion`, `Ocupacion` y `Permanencia` lo usan).

- [ ] **Step 4: Correr las pruebas y verificar que pasan**

```
cd backend
.venv\Scripts\python.exe manage.py test recepcion.tests_dominio -v 2
```

Esperado: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/recepcion/dominio.py backend/recepcion/tests_dominio.py
git commit -m "Análisis de silo: un camión después de la muestra invalida el análisis"
```

---

### Task 3: Vigencia sobre el libro mayor

**Files:**
- Modify: `backend/recepcion/models.py` (propiedades en `AnalisisSilo`)
- Modify: `backend/recepcion/tests_analisis_silo.py` (agregar clase)

**Interfaces:**
- Consumes: `dominio.analisis_vigente`, `dominio.parametros_faltantes`, `MovimientoSilo`
- Produces: `AnalisisSilo.vigencia -> dominio.Vigencia`, `AnalisisSilo.vigente -> bool`, `AnalisisSilo.motivo_vigencia -> str`, `AnalisisSilo.faltantes_para_vale -> list[str]`

- [ ] **Step 1: Escribir la prueba que falla**

Agregar a `backend/recepcion/tests_analisis_silo.py`:

```python
from recepcion.models import MovimientoSilo


class VigenciaContraElLibroTests(TestCase):
    def setUp(self):
        self.silo = Silo.objects.create(
            codigo="SILO 4", tipo=Silo.Tipo.SILO, capacidad_l=Decimal("100000")
        )
        self.analisis = AnalisisSilo.objects.create(
            silo=self.silo,
            tomado_en=datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc),
            grasa=Decimal("4.24"),
            sng=Decimal("8.69"),
        )

    def test_recien_tomado_esta_vigente(self):
        self.assertTrue(self.analisis.vigente)
        self.assertEqual(self.analisis.motivo_vigencia, "")

    def test_un_ingreso_posterior_lo_deja_fuera_de_vigencia(self):
        MovimientoSilo.objects.create(
            silo=self.silo,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("74834"),
            fecha_hora=datetime(2026, 7, 15, 14, 0, tzinfo=tz.utc),
        )

        self.assertFalse(self.analisis.vigente)
        self.assertIn("74834", self.analisis.motivo_vigencia)

    def test_una_salida_posterior_no_lo_invalida(self):
        """
        Sacar leche no cambia la composición de la que queda: el análisis
        sigue describiéndola. Invalidarlo obligaría a re-muestrear cada vez
        que una línea consume, que es todo el día.
        """
        MovimientoSilo.objects.create(
            silo=self.silo,
            tipo=MovimientoSilo.Tipo.SALIDA,
            litros=Decimal("20000"),
            fecha_hora=datetime(2026, 7, 15, 14, 0, tzinfo=tz.utc),
        )

        self.assertTrue(self.analisis.vigente)

    def test_un_ingreso_a_otro_silo_no_lo_invalida(self):
        otro = Silo.objects.create(
            codigo="SILO 5", tipo=Silo.Tipo.SILO, capacidad_l=Decimal("100000")
        )
        MovimientoSilo.objects.create(
            silo=otro,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("9337"),
            fecha_hora=datetime(2026, 7, 15, 14, 0, tzinfo=tz.utc),
        )

        self.assertTrue(self.analisis.vigente)

    def test_dice_que_falta_para_componer_un_vale(self):
        sin_sng = AnalisisSilo.objects.create(
            silo=self.silo,
            tomado_en=datetime(2026, 7, 15, 18, 0, tzinfo=tz.utc),
            grasa=Decimal("4.24"),
        )

        self.assertEqual(sin_sng.faltantes_para_vale, ["sng"])
        self.assertEqual(self.analisis.faltantes_para_vale, [])
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

```
cd backend
.venv\Scripts\python.exe manage.py test recepcion.tests_analisis_silo -v 2
```

Esperado: FAIL — `AttributeError: 'AnalisisSilo' object has no attribute 'vigente'`

- [ ] **Step 3: Escribir las propiedades**

Agregar dentro de la clase `AnalisisSilo`, después de `__str__`:

```python
    #: Lo mínimo que un vale de estandarización necesita del silo.
    REQUERIDOS_PARA_VALE = ("grasa", "sng")

    @property
    def vigencia(self):
        """
        Si el análisis todavía describe lo que hay en el silo.

        Solo los **ingresos** cuentan: una salida no cambia la composición de
        la leche que queda, y invalidar por salida obligaría a re-muestrear
        cada vez que una línea consume.
        """
        ingresos = MovimientoSilo.objects.filter(
            silo_id=self.silo_id,
            tipo=MovimientoSilo.Tipo.INGRESO,
            fecha_hora__gt=self.tomado_en,
        ).values_list("fecha_hora", "litros")

        return dominio.analisis_vigente(self.tomado_en, ingresos)

    @property
    def vigente(self):
        return self.vigencia.vigente

    @property
    def motivo_vigencia(self):
        return self.vigencia.motivo

    @property
    def faltantes_para_vale(self):
        valores = {nombre: getattr(self, nombre) for nombre in dominio.PARAMETROS_ANALISIS_SILO}
        return dominio.parametros_faltantes(valores, self.REQUERIDOS_PARA_VALE)
```

`AnalisisSilo` queda definida **después** de `MovimientoSilo` en el archivo, así que la referencia directa a la clase funciona sin import diferido. `dominio` ya está importado en `models.py`.

- [ ] **Step 4: Correr las pruebas y verificar que pasan**

```
cd backend
.venv\Scripts\python.exe manage.py test recepcion -v 2
```

Esperado: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/recepcion/models.py backend/recepcion/tests_analisis_silo.py
git commit -m "Análisis de silo: la vigencia se lee del libro mayor, no de un campo"
```

---

### Task 4: API y admin

**Files:**
- Modify: `backend/recepcion/serializers.py`
- Modify: `backend/recepcion/views.py`
- Modify: `backend/recepcion/urls.py`
- Modify: `backend/recepcion/admin.py`
- Modify: `backend/recepcion/tests_analisis_silo.py`

**Interfaces:**
- Consumes: `AnalisisSilo`, `EscribeRecepcion`, `QuerysetTenantMixin`, `RelacionesTenantMixin`
- Produces: endpoint `/api/recepcion/analisis-silo/` (CRUD) con filtros `?silo=<id>` y `?vigentes=1`, y `AnalisisSiloSerializer` que expone además `silo_codigo`, `vigente`, `motivo_vigencia`, `faltantes_para_vale`, `analista_nombre`

- [ ] **Step 1: Escribir las pruebas que fallan**

Agregar a `backend/recepcion/tests_analisis_silo.py`:

```python
from recepcion.tests import BaseAPIRecepcion


class AnalisisSiloAPITests(BaseAPIRecepcion):
    def test_registra_un_analisis_y_devuelve_su_vigencia(self):
        respuesta = self.cliente.post(
            "/api/recepcion/analisis-silo/",
            {
                "silo": self.silo.id,
                "tomado_en": "2026-07-15T09:40:00Z",
                "ph": "6.77",
                "acidez": "15.60",
                "grasa": "4.35",
                "sng": "8.90",
                "proteina": "3.44",
                "temperatura": "6.00",
                "densidad": "1032.00",
                "certificada": True,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertIs(respuesta.data["vigente"], True)
        self.assertEqual(respuesta.data["faltantes_para_vale"], [])
        self.assertEqual(respuesta.data["silo_codigo"], "SILO 1")

    def test_el_analista_es_quien_lo_registra(self):
        respuesta = self.cliente.post(
            "/api/recepcion/analisis-silo/",
            {"silo": self.silo.id, "tomado_en": "2026-07-15T09:40:00Z"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["analista_nombre"], "op")

    def test_filtra_por_silo(self):
        otro = Silo.objects.create(
            codigo="SILO 9", tipo=Silo.Tipo.SILO, capacidad_l=Decimal("50000")
        )
        AnalisisSilo.objects.create(
            silo=self.silo, tomado_en=datetime(2026, 7, 15, 9, 0, tzinfo=tz.utc)
        )
        AnalisisSilo.objects.create(
            silo=otro, tomado_en=datetime(2026, 7, 15, 9, 0, tzinfo=tz.utc)
        )

        respuesta = self.cliente.get(f"/api/recepcion/analisis-silo/?silo={otro.id}")

        self.assertEqual(respuesta.status_code, 200)
        resultados = respuesta.data["results"] if "results" in respuesta.data else respuesta.data
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["silo_codigo"], "SILO 9")

    def test_vigentes_deja_fuera_al_que_recibio_leche_despues(self):
        viejo = AnalisisSilo.objects.create(
            silo=self.silo, tomado_en=datetime(2026, 7, 15, 9, 0, tzinfo=tz.utc)
        )
        MovimientoSilo.objects.create(
            silo=self.silo,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("10000"),
            fecha_hora=datetime(2026, 7, 15, 12, 0, tzinfo=tz.utc),
        )
        nuevo = AnalisisSilo.objects.create(
            silo=self.silo, tomado_en=datetime(2026, 7, 15, 13, 0, tzinfo=tz.utc)
        )

        respuesta = self.cliente.get("/api/recepcion/analisis-silo/?vigentes=1")

        self.assertEqual(respuesta.status_code, 200)
        resultados = respuesta.data["results"] if "results" in respuesta.data else respuesta.data
        devueltos = {fila["id"] for fila in resultados}
        self.assertIn(nuevo.id, devueltos)
        self.assertNotIn(viejo.id, devueltos)
```

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

```
cd backend
.venv\Scripts\python.exe manage.py test recepcion.tests_analisis_silo -v 2
```

Esperado: FAIL con 404 en `/api/recepcion/analisis-silo/`

- [ ] **Step 3: Escribir el serializer**

Agregar a `backend/recepcion/serializers.py` (y sumar `AnalisisSilo` al import de `.models`):

```python
class AnalisisSiloSerializer(serializers.ModelSerializer):
    silo_codigo = serializers.CharField(source="silo.codigo", read_only=True)
    # Método y no `source="analista.username"`: el analista es nulable, y una
    # travesía sobre `None` en DRF revienta en vez de devolver el vacío.
    analista_nombre = serializers.SerializerMethodField()
    vigente = serializers.BooleanField(read_only=True)
    motivo_vigencia = serializers.CharField(read_only=True)
    faltantes_para_vale = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )

    class Meta:
        model = AnalisisSilo
        fields = [
            "id", "silo", "silo_codigo", "tomado_en", "hora_inicio_llenado",
            "ph", "acidez", "grasa", "sng", "proteina", "temperatura", "densidad",
            "certificada", "procedencia", "analista", "analista_nombre",
            "observacion", "creado_en",
            "vigente", "motivo_vigencia", "faltantes_para_vale",
        ]
        read_only_fields = ["analista", "creado_en"]

    def get_analista_nombre(self, obj):
        return obj.analista.username if obj.analista_id else ""
```

- [ ] **Step 4: Escribir el viewset**

Agregar a `backend/recepcion/views.py` (y sumar `AnalisisSilo` al import de `.models` y `AnalisisSiloSerializer` al de `.serializers`):

```python
class AnalisisSiloViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    """
    El análisis del silo — `CCAA.REC.FORM.005.01`.

    `?vigentes=1` filtra en Python y no en la base: la vigencia se decide
    contra el libro de movimientos, y expresarla como consulta duplicaría en
    SQL una regla que ya está en el dominio. Con ocho silos el costo es nulo
    y la regla sigue teniendo una sola implementación.
    """

    tenant_lookup_sucursal = "silo__sucursal_id"
    tenant_lookup_empresa = "silo__sucursal__empresa_id"
    tenant_relation_fields = {"silo": ("sucursal_id", "sucursal__empresa_id")}
    queryset = AnalisisSilo.objects.select_related("silo", "analista")
    serializer_class = AnalisisSiloSerializer
    permission_classes = [EscribeRecepcion]

    def get_queryset(self):
        consulta = super().get_queryset()

        silo = self.request.query_params.get("silo")
        if silo:
            consulta = consulta.filter(silo_id=silo)

        if self.request.query_params.get("vigentes") in {"1", "true"}:
            vigentes = [fila.id for fila in consulta if fila.vigente]
            consulta = consulta.filter(id__in=vigentes)

        return consulta

    def perform_create(self, serializer):
        serializer.save(analista=self.request.user)
```

- [ ] **Step 5: Registrar la ruta**

Reemplazar el contenido de `backend/recepcion/urls.py`:

```python
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnalisisSiloViewSet, MovimientoSiloViewSet, RecepcionViewSet, ocupacion,
)

router = DefaultRouter()
router.register("recepciones", RecepcionViewSet)
router.register("movimientos", MovimientoSiloViewSet)
router.register("analisis-silo", AnalisisSiloViewSet)

urlpatterns = [
    path("ocupacion/", ocupacion, name="ocupacion"),
    path("", include(router.urls)),
]
```

- [ ] **Step 6: Registrar en el admin**

Agregar a `backend/recepcion/admin.py` (y sumar `AnalisisSilo` a su import de `.models`):

```python
@admin.register(AnalisisSilo)
class AnalisisSiloAdmin(admin.ModelAdmin):
    list_display = ("silo", "tomado_en", "grasa", "sng", "ph", "acidez", "analista")
    list_filter = ("silo", "certificada", "procedencia")
    date_hierarchy = "tomado_en"
    search_fields = ("silo__codigo", "observacion")
    autocomplete_fields = ("silo",)
```

Si `SiloAdmin` de `maestros` no declara `search_fields`, `autocomplete_fields` falla al arrancar. En ese caso, quitar la línea `autocomplete_fields` en vez de tocar el admin de maestros.

- [ ] **Step 7: Correr las pruebas y verificar que pasan**

```
cd backend
.venv\Scripts\python.exe manage.py test recepcion usuarios -v 2
```

Esperado: PASS. `usuarios` entra porque `tests_admin_alta` recorre el registro completo del admin y el modelo nuevo cae ahí.

- [ ] **Step 8: Commit**

```bash
git add backend/recepcion/serializers.py backend/recepcion/views.py backend/recepcion/urls.py backend/recepcion/admin.py backend/recepcion/tests_analisis_silo.py
git commit -m "Análisis de silo: API y admin"
```

---

### Task 5: El vale de estandarización declara de dónde salieron sus números

**Files:**
- Modify: `backend/estandarizacion/models.py` (dos campos en `ValeEstandarizacion`)
- Create: `backend/estandarizacion/migrations/0003_procedencia_del_analisis.py` (la genera `makemigrations`)
- Modify: `backend/estandarizacion/serializers.py`
- Modify: `backend/estandarizacion/views.py`
- Create: `backend/estandarizacion/tests_composicion.py`

**Interfaces:**
- Consumes: `recepcion.models.AnalisisSilo`, `recepcion.dominio.Vigencia`
- Produces:
  - `ValeEstandarizacion.analisis_entera` y `.analisis_descremada` (FK nulables a `recepcion.AnalisisSilo`, `on_delete=PROTECT`, `related_name="vales_como_entera"` / `"vales_como_descremada"`)
  - endpoint `GET /api/estandarizacion/vales/composicion-silos/?entera=<id>&descremada=<id>` que devuelve `{"entera": {...}, "descremada": {...}}`, cada uno con `analisis`, `grasa`, `sng`, `tomado_en`, `vigente`, `motivo`, `faltantes`

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `backend/estandarizacion/tests_composicion.py`:

```python
"""
De dónde salen la grasa y el SNG del vale.

Hasta ahora el operador los tecleaba y no quedaba de dónde. El vale sigue
**congelando** la composición en sus columnas —esa decisión no cambia—, pero
ahora además dice contra qué análisis se compuso.
"""

from datetime import datetime, timezone as tz
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import Silo
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import PerfilUsuario, Rol


class ComposicionDeSilosTests(TestCase):
    def setUp(self):
        usuario = User.objects.create_user(username="est", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=Rol.RECEPCION)
        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )

        self.entera = Silo.objects.create(
            codigo="SILO 6", tipo=Silo.Tipo.SILO, capacidad_l=Decimal("100000")
        )
        self.descremada = Silo.objects.create(
            codigo="TK LD 1", tipo=Silo.Tipo.TK_LD, capacidad_l=Decimal("50000")
        )

    def test_devuelve_el_ultimo_analisis_de_cada_silo(self):
        AnalisisSilo.objects.create(
            silo=self.entera,
            tomado_en=datetime(2026, 7, 15, 6, 0, tzinfo=tz.utc),
            grasa=Decimal("4.10"),
            sng=Decimal("8.80"),
        )
        AnalisisSilo.objects.create(
            silo=self.entera,
            tomado_en=datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc),
            grasa=Decimal("4.35"),
            sng=Decimal("8.90"),
        )
        AnalisisSilo.objects.create(
            silo=self.descremada,
            tomado_en=datetime(2026, 7, 15, 9, 0, tzinfo=tz.utc),
            grasa=Decimal("0.09"),
            sng=Decimal("9.20"),
        )

        respuesta = self.cliente.get(
            "/api/estandarizacion/vales/composicion-silos/"
            f"?entera={self.entera.id}&descremada={self.descremada.id}"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["entera"]["grasa"], "4.35")
        self.assertEqual(respuesta.data["entera"]["sng"], "8.90")
        self.assertIs(respuesta.data["entera"]["vigente"], True)
        self.assertEqual(respuesta.data["descremada"]["grasa"], "0.09")

    def test_avisa_cuando_el_analisis_quedo_fuera_de_vigencia(self):
        AnalisisSilo.objects.create(
            silo=self.entera,
            tomado_en=datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc),
            grasa=Decimal("4.35"),
            sng=Decimal("8.90"),
        )
        MovimientoSilo.objects.create(
            silo=self.entera,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("21140"),
            fecha_hora=datetime(2026, 7, 15, 12, 0, tzinfo=tz.utc),
        )

        respuesta = self.cliente.get(
            f"/api/estandarizacion/vales/composicion-silos/?entera={self.entera.id}"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIs(respuesta.data["entera"]["vigente"], False)
        self.assertIn("21140", respuesta.data["entera"]["motivo"])

    def test_un_silo_sin_analisis_no_es_un_error_pero_lo_dice(self):
        respuesta = self.cliente.get(
            f"/api/estandarizacion/vales/composicion-silos/?entera={self.entera.id}"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.data["entera"]["analisis"])
        self.assertIn("sin análisis", respuesta.data["entera"]["motivo"].lower())

    def test_dice_que_parametro_falta(self):
        AnalisisSilo.objects.create(
            silo=self.entera,
            tomado_en=datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc),
            grasa=Decimal("4.35"),
        )

        respuesta = self.cliente.get(
            f"/api/estandarizacion/vales/composicion-silos/?entera={self.entera.id}"
        )

        self.assertEqual(respuesta.data["entera"]["faltantes"], ["sng"])
```

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

```
cd backend
.venv\Scripts\python.exe manage.py test estandarizacion.tests_composicion -v 2
```

Esperado: FAIL con 404 en `composicion-silos/`

- [ ] **Step 3: Agregar la procedencia al modelo**

Agregar a `ValeEstandarizacion` en `backend/estandarizacion/models.py`, justo después de `descremada_sng`:

```python
    # De dónde salieron los cuatro números de arriba. Es **procedencia**, no
    # fuente de verdad: la composición sigue congelada en las columnas del
    # vale, porque el análisis se puede corregir y un vale de mayo tiene que
    # seguir auditándose contra lo que se usó en mayo. Sin estas dos claves,
    # «4,35» era un número tecleado sin origen.
    analisis_entera = models.ForeignKey(
        "recepcion.AnalisisSilo", on_delete=models.PROTECT,
        related_name="vales_con_esta_entera", null=True, blank=True,
        verbose_name="Análisis de la entera",
    )
    analisis_descremada = models.ForeignKey(
        "recepcion.AnalisisSilo", on_delete=models.PROTECT,
        related_name="vales_con_esta_descremada", null=True, blank=True,
        verbose_name="Análisis de la descremada",
    )
```

Los `related_name` **no** son `vales_como_entera` / `vales_como_descremada`: esos ya los
usan `silo_entera` y `silo_descremada` sobre `maestros.Silo`. Django lo permitiría —el
modelo de destino es otro— pero `silo.vales_como_entera` y `analisis.vales_como_entera`
devolverían cosas distintas con el mismo nombre, y quien lea el código a los seis meses
no tiene cómo saber cuál está mirando.

- [ ] **Step 4: Generar y aplicar la migración**

```
cd backend
.venv\Scripts\python.exe manage.py makemigrations estandarizacion --name procedencia_del_analisis
.venv\Scripts\python.exe manage.py migrate
```

Esperado: crea `estandarizacion/migrations/0003_procedencia_del_analisis.py` y la aplica.

- [ ] **Step 5: Exponer los dos campos en el serializer**

En `backend/estandarizacion/serializers.py`, agregar `"analisis_entera"` y `"analisis_descremada"` a la lista `fields` de `ValeEstandarizacionSerializer`.

- [ ] **Step 6: Escribir la acción**

Agregar a `ValeEstandarizacionViewSet` en `backend/estandarizacion/views.py`, después de `calcular`:

```python
    @action(detail=False, methods=["get"], url_path="composicion-silos")
    def composicion_silos(self, request):
        """
        La composición de cada silo según su **último** análisis.

        Es lo que el operador copiaba a mano del vale de trazabilidad. No
        crea nada ni decide nada: devuelve el dato con su vigencia y con lo
        que falte, y quien compone el vale sigue siendo quien decide.

        Un silo sin análisis o con uno vencido **no es un error**: devuelve
        el motivo. Rechazar con 400 dejaría a la pantalla sin poder mostrar
        por qué no hay número que ofrecer.
        """
        respuesta = {}

        for rol in ("entera", "descremada"):
            silo_id = request.query_params.get(rol)

            if not silo_id:
                respuesta[rol] = self._sin_analisis("No se indicó el silo.")
                continue

            analisis = (
                AnalisisSilo.objects.filter(silo_id=silo_id)
                .select_related("silo")
                .order_by("-tomado_en")
                .first()
            )

            if analisis is None:
                respuesta[rol] = self._sin_analisis(
                    "El silo está sin análisis registrado."
                )
                continue

            vigencia = analisis.vigencia
            respuesta[rol] = {
                "analisis": analisis.id,
                "silo": analisis.silo_id,
                "silo_codigo": analisis.silo.codigo,
                "tomado_en": analisis.tomado_en,
                "grasa": str(analisis.grasa) if analisis.grasa is not None else None,
                "sng": str(analisis.sng) if analisis.sng is not None else None,
                "vigente": vigencia.vigente,
                "motivo": vigencia.motivo,
                "faltantes": analisis.faltantes_para_vale,
            }

        return Response(respuesta)

    @staticmethod
    def _sin_analisis(motivo):
        return {
            "analisis": None,
            "silo": None,
            "silo_codigo": "",
            "tomado_en": None,
            "grasa": None,
            "sng": None,
            "vigente": False,
            "motivo": motivo,
            "faltantes": ["grasa", "sng"],
        }
```

Agregar el import al comienzo del archivo:

```python
from recepcion.models import AnalisisSilo
```

- [ ] **Step 7: Correr las pruebas y verificar que pasan**

```
cd backend
.venv\Scripts\python.exe manage.py test estandarizacion recepcion -v 2
```

Esperado: PASS, incluidas las pruebas del vale que ya existían (`tests_vale.py`).

- [ ] **Step 8: Commit**

```bash
git add backend/estandarizacion/models.py backend/estandarizacion/migrations/0003_procedencia_del_analisis.py backend/estandarizacion/serializers.py backend/estandarizacion/views.py backend/estandarizacion/tests_composicion.py
git commit -m "El vale declara de qué análisis de silo salieron su grasa y su SNG"
```

---

### Task 6: Captura en la pantalla de silos

**Files:**
- Modify: `frontend/src/services/recepcion.service.ts`
- Modify: `frontend/src/services/estandarizacion.service.ts`
- Create: `frontend/src/pages/Leche/AnalisisSilo.tsx`
- Modify: `frontend/src/pages/Leche/Silos.tsx`

**Interfaces:**
- Consumes: `/api/recepcion/analisis-silo/`, `/api/estandarizacion/vales/composicion-silos/`
- Produces: tipo `AnalisisSilo`, funciones `listarAnalisisSilo(siloId)`, `crearAnalisisSilo(datos)` y `composicionSilos(enteraId, descremadaId)`

- [ ] **Step 1: Agregar el tipo y las llamadas al servicio de recepción**

Agregar a `frontend/src/services/recepcion.service.ts`:

```ts
export interface AnalisisSilo {
  id: number;
  silo: number;
  silo_codigo: string;
  tomado_en: string;
  hora_inicio_llenado: string | null;
  ph: string | null;
  acidez: string | null;
  grasa: string | null;
  sng: string | null;
  proteina: string | null;
  temperatura: string | null;
  densidad: string | null;
  certificada: boolean | null;
  procedencia: string;
  analista_nombre: string;
  observacion: string;
  vigente: boolean;
  motivo_vigencia: string;
  faltantes_para_vale: string[];
}

export type AnalisisSiloNuevo = Omit<
  AnalisisSilo,
  "id" | "silo_codigo" | "analista_nombre" | "vigente" | "motivo_vigencia" | "faltantes_para_vale"
>;

export async function listarAnalisisSilo(siloId: number): Promise<AnalisisSilo[]> {
  const { data } = await api.get("/recepcion/analisis-silo/", { params: { silo: siloId } });
  return Array.isArray(data) ? data : data.results;
}

export async function crearAnalisisSilo(datos: Partial<AnalisisSiloNuevo>): Promise<AnalisisSilo> {
  const { data } = await api.post("/recepcion/analisis-silo/", datos);
  return data;
}
```

- [ ] **Step 2: Agregar la consulta de composición al servicio de estandarización**

Agregar a `frontend/src/services/estandarizacion.service.ts`:

```ts
export interface ComposicionDeSilo {
  analisis: number | null;
  silo: number | null;
  silo_codigo: string;
  tomado_en: string | null;
  grasa: string | null;
  sng: string | null;
  vigente: boolean;
  motivo: string;
  faltantes: string[];
}

export interface ComposicionSilos {
  entera: ComposicionDeSilo;
  descremada: ComposicionDeSilo;
}

export async function composicionSilos(
  enteraId?: number,
  descremadaId?: number,
): Promise<ComposicionSilos> {
  const { data } = await api.get("/estandarizacion/vales/composicion-silos/", {
    params: { entera: enteraId, descremada: descremadaId },
  });
  return data;
}
```

- [ ] **Step 3: Escribir el panel de captura**

Crear `frontend/src/pages/Leche/AnalisisSilo.tsx`:

```tsx
import { useEffect, useState } from "react";

import {
  crearAnalisisSilo,
  listarAnalisisSilo,
  type AnalisisSilo as Analisis,
} from "../../services/recepcion.service";

const PARAMETROS = [
  { clave: "ph", etiqueta: "pH" },
  { clave: "acidez", etiqueta: "Acidez (°Th)" },
  { clave: "grasa", etiqueta: "Grasa (%)" },
  { clave: "sng", etiqueta: "SNG (%)" },
  { clave: "proteina", etiqueta: "Proteína (%)" },
  { clave: "temperatura", etiqueta: "Temperatura (°C)" },
  { clave: "densidad", etiqueta: "Densidad (kg/m³)" },
] as const;

interface Props {
  siloId: number;
  siloCodigo: string;
}

export default function AnalisisSiloPanel({ siloId, siloCodigo }: Props) {
  const [historial, setHistorial] = useState<Analisis[]>([]);
  const [valores, setValores] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function recargar() {
    try {
      setHistorial(await listarAnalisisSilo(siloId));
    } catch {
      setError("No se pudo leer el historial de análisis.");
    }
  }

  useEffect(() => {
    void recargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [siloId]);

  async function guardar() {
    setGuardando(true);
    setError("");
    try {
      const datos: Record<string, unknown> = { silo: siloId, tomado_en: new Date().toISOString() };
      for (const { clave } of PARAMETROS) {
        if (valores[clave]) datos[clave] = valores[clave];
      }
      await crearAnalisisSilo(datos);
      setValores({});
      await recargar();
    } catch {
      setError("No se pudo guardar el análisis.");
    } finally {
      setGuardando(false);
    }
  }

  const ultimo = historial[0];

  return (
    <section>
      <h3>Análisis de {siloCodigo}</h3>

      {ultimo && !ultimo.vigente && (
        <p role="status">{ultimo.motivo_vigencia}</p>
      )}

      {PARAMETROS.map(({ clave, etiqueta }) => (
        <label key={clave}>
          {etiqueta}
          <input
            type="number"
            step="0.01"
            value={valores[clave] ?? ""}
            onChange={(e) => setValores({ ...valores, [clave]: e.target.value })}
          />
        </label>
      ))}

      <button type="button" onClick={() => void guardar()} disabled={guardando}>
        {guardando ? "Guardando…" : "Registrar análisis"}
      </button>

      {error && <p role="alert">{error}</p>}

      <table>
        <thead>
          <tr>
            <th>Muestra</th>
            <th>Grasa</th>
            <th>SNG</th>
            <th>Vigente</th>
            <th>Analista</th>
          </tr>
        </thead>
        <tbody>
          {historial.map((fila) => (
            <tr key={fila.id}>
              <td>{new Date(fila.tomado_en).toLocaleString("es-CL")}</td>
              <td>{fila.grasa ?? "—"}</td>
              <td>{fila.sng ?? "—"}</td>
              <td>{fila.vigente ? "Sí" : fila.motivo_vigencia}</td>
              <td>{fila.analista_nombre || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
```

- [ ] **Step 4: Enganchar el panel en la pantalla de silos**

En `frontend/src/pages/Leche/Silos.tsx`, importar el panel y renderizarlo para el silo seleccionado:

```tsx
import AnalisisSiloPanel from "./AnalisisSilo";
```

Y en el lugar donde la pantalla ya muestra el detalle de un silo seleccionado, agregar:

```tsx
{siloSeleccionado && (
  <AnalisisSiloPanel
    siloId={siloSeleccionado.id}
    siloCodigo={siloSeleccionado.codigo}
  />
)}
```

Si `Silos.tsx` todavía no tiene un silo seleccionado, agregar el estado `const [siloSeleccionado, setSiloSeleccionado] = useState<Silo | null>(null);` y un `onClick={() => setSiloSeleccionado(silo)}` en la fila de la tabla. No cambiar la carga de datos existente: los análisis se piden aparte, para que un endpoint caído no vacíe la pantalla de silos.

- [ ] **Step 5: Comprobar tipos y build**

```
cd frontend
npx tsc -b
```

Esperado: sin errores. Si `npx tsc -b` deja artefactos `*.tsbuildinfo`, verificar que estén ignorados en `.gitignore` antes de commitear.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services/recepcion.service.ts frontend/src/services/estandarizacion.service.ts frontend/src/pages/Leche/AnalisisSilo.tsx frontend/src/pages/Leche/Silos.tsx
git commit -m "Captura del análisis de silo en la pantalla de silos"
```

---

### Task 7: Dejar la decisión escrita

**Files:**
- Modify: `CLAUDE.md` (sección «Decisiones vigentes»)
- Modify: `docs/REGLAS_DE_PLANTA.md` (§3, antes de §3.1)
- Modify: `docs/LEVANTAMIENTO_REGISTROS_FABRICACION_2026.md` (§7, marcar la fase 1)

**Interfaces:**
- Consumes: nada.
- Produces: nada de código. Es el paso que impide que la próxima sesión reinvente la regla.

- [ ] **Step 1: Anotar la decisión en `CLAUDE.md`**

Agregar como viñeta al final de «Decisiones vigentes»:

```markdown
- **El análisis del silo es un registro propio** (desde 2026-08-19, `recepcion.AnalisisSilo`,
  formato `CCAA.REC.FORM.005.01`). No se confunde con `Recepcion.controles`, que son los del
  **camión**: el silo mezcla varios camiones, y es la mezcla —no cada camión— la que alimenta el
  cálculo del RC. Trae los siete parámetros del vale de trazabilidad, incluidas **proteína y
  densidad**, que no existían en ninguna parte del sistema.

  **La vigencia no se guarda: se decide contra el libro de movimientos.** Un análisis deja de
  servir para componer un vale cuando entró un camión después de la muestra —una salida no, porque
  sacar leche no cambia la composición de la que queda, e invalidar por salida obligaría a
  re-muestrear cada vez que una línea consume—. Un campo `vigente` almacenado se desincronizaría al
  corregir la hora de un movimiento, y un vale quedaría compuesto contra leche que ya no está.

  El vale de estandarización **sigue congelando** la composición en sus columnas y solo gana dos
  claves foráneas de **procedencia** (`analisis_entera`, `analisis_descremada`): el análisis se
  puede corregir, y un vale de mayo tiene que auditarse contra lo que se usó en mayo.
```

- [ ] **Step 2: Anotar la regla en `docs/REGLAS_DE_PLANTA.md`**

Insertar al final de §3, antes de «### 3.1»:

```markdown
**De dónde salen la grasa y el SNG** (desde 2026-08-19): del último `AnalisisSilo`
vigente del silo, no de un número tecleado. `GET /api/estandarizacion/vales/composicion-silos/`
los ofrece con su vigencia y con lo que falte; el operador sigue decidiendo. Un silo
sin análisis, o con uno invalidado por un ingreso posterior, **no es un error**:
devuelve el motivo, porque una pantalla que solo dice «no» no le dice a nadie qué hacer.
```

- [ ] **Step 3: Marcar la fase como hecha**

En `docs/LEVANTAMIENTO_REGISTROS_FABRICACION_2026.md` §7, cambiar la fila de la fase 1 para que empiece con `~~Análisis de silo~~ — hecho (2026-08-19)`, y agregar bajo «Planes escritos» que la fase 2 es la siguiente.

- [ ] **Step 4: Correr la suite completa**

```
cd backend
.venv\Scripts\python.exe manage.py test -v 1
```

Esperado: PASS, sin regresiones.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/REGLAS_DE_PLANTA.md docs/LEVANTAMIENTO_REGISTROS_FABRICACION_2026.md
git commit -m "Documenta el análisis de silo y su regla de vigencia"
```

---

## Qué queda fuera de esta fase, y por qué

| Fuera | Motivo |
|---|---|
| Que un análisis vencido **impida** crear el vale | Es decisión de Calidad (§6 del levantamiento). El sistema avisa; endurecerlo es cambiar una función, no el modelo |
| Caducidad por tiempo del análisis (re-muestreo de un silo en reposo) | Sin regla de planta que la fije. Un número inventado aquí retendría leche conforme |
| Delvo por silo y control de permanencia > 48 h | Fase 3. Cuelgan de este modelo pero son registros distintos |
| `LECHE CERT. DESCREMADA` y N° de parte del vale de trazabilidad | Pertenecen al documento impreso, no al dato que consume el RC |
| Importar los 184 vales de trazabilidad de 2026 | No se pidió. El modelo queda listo para recibirlos |
| Emisión del formato `CCAA.REC.FORM.005.01` impreso | Mismo criterio que la spec de recepción: capturar y calcular ahora, emitir después |
