# Borrador P0 — para revisar con Claude Code

> Código de arranque para las tareas **P0** del backlog, escrito siguiendo las convenciones del
> repo (funciones de dominio puras, `TextChoices`, `JSONField` para lo dinámico, modelo hijo con FK
> para el detalle repetitivo, `clean()` de validación, docstrings que citan `MODELO_DATOS.md`).
> **No está aplicado**: es un borrador para que Claude Code lo revise contigo, lo ubique en la app
> definitiva (ver decisión `produccion` vs. app `inocuidad`) y genere las migraciones.
> **Fecha:** 2026-07-30.

Contenido:
1. Autogeneración y validación de `codigo_lote` → `produccion/dominio.py` (+ tests).
2. `ControlProceso` + `ControlProcesoLectura` (PCC 1 uperización) → `produccion/models.py`.
3. `MonitoreoPPRO` + `PproLectura` (PCC detector de metales / PPRO) → `produccion/` o app `inocuidad`.
4. Campo `area` en `DocumentoLiberacion` → `maestros/models.py`.
5. Data migration que siembra los 19 registros del Dossier → `maestros/migrations/`.

Orden de aplicación sugerido: (4) → makemigrations maestros → (5) migrate · (1)+tests · (2)+(3) → makemigrations → migrate. Correr `python manage.py test` tras cada bloque.

---

## 1. `produccion/dominio.py` — código de lote (POE.009.02)

Función pura, sin ORM, como el resto del archivo. Reproduce la codificación real:
`CCAA + <último dígito del año> + <día juliano 3 dígitos> + sufijo`.
Verificado contra los ejemplos del POE (16-07-2025): crema `CCAA5197`, precondensado nacional
`CCAA5197N`, LEP Egron 1 `CCAA51971`, Egron 2 `CCAA51972`, 2ª producción del día `…A`.

```python
# --- añadir a produccion/dominio.py ---

import re
from datetime import date

# Tipos de producto a efectos de la codificación de lote (POE.009.02).
TIPO_PRECONDENSADO = "precondensado"
TIPO_CREMA = "crema"
TIPO_LEP = "lep"  # leche entera/descremada en polvo

_SUFIJO_LINEA = {"E1": "1", "E2": "2"}
_PATRON_CODIGO = re.compile(r"^CCAA\d{4}(N|[12])?A?$")


def generar_codigo_lote(
    fecha: date,
    tipo: str,
    *,
    linea: str | None = None,
    nacional: bool = False,
    segunda_produccion: bool = False,
) -> str:
    """
    Genera el código de lote según CCAA.Calidad.POE.009.02.

    Base: 'CCAA' + último dígito del año + día juliano (3 dígitos).
    Sufijo:
      - precondensado: 'N' si es de uso nacional, nada si no.
      - crema: sin sufijo.
      - LEP: '1' si sale de Egron 1 (E1), '2' si sale de Egron 2 (E2).
    Si es la segunda producción del mismo día, se agrega 'A' al final para
    evitar duplicidad (POE.009.02, "Consideraciones").

    No garantiza unicidad por sí solo: la clave natural del lote sigue siendo
    `codigo_lote + producto + fecha` (ver Lote.Meta), que es lo que la base
    controla. Esta función solo arma el código que el operador vería en papel.
    """
    base = f"CCAA{fecha.year % 10}{fecha.timetuple().tm_yday:03d}"

    if tipo == TIPO_PRECONDENSADO:
        sufijo = "N" if nacional else ""
    elif tipo == TIPO_CREMA:
        sufijo = ""
    elif tipo == TIPO_LEP:
        sufijo = _SUFIJO_LINEA.get(linea or "", "")
    else:
        raise ValueError(f"Tipo de producto desconocido para codificación: {tipo!r}")

    if segunda_produccion:
        sufijo += "A"

    return base + sufijo


def codigo_lote_valido(codigo: str) -> bool:
    """Comprueba que un código respeta la forma de POE.009.02."""
    return bool(_PATRON_CODIGO.match(codigo or ""))
```

Tests (nuevo archivo `produccion/tests_dominio_codigo_lote.py`, o añadir a `tests_dominio.py`):

```python
from datetime import date

from django.test import SimpleTestCase

from produccion.dominio import (
    generar_codigo_lote,
    codigo_lote_valido,
    TIPO_PRECONDENSADO,
    TIPO_CREMA,
    TIPO_LEP,
)


class GenerarCodigoLote(SimpleTestCase):
    """Ejemplos tomados literalmente del POE.009.02 (elaboración 16-07-2025)."""

    fecha = date(2025, 7, 16)  # día juliano 197

    def test_crema_sin_sufijo(self):
        self.assertEqual(generar_codigo_lote(self.fecha, TIPO_CREMA), "CCAA5197")

    def test_precondensado_nacional_lleva_N(self):
        self.assertEqual(
            generar_codigo_lote(self.fecha, TIPO_PRECONDENSADO, nacional=True),
            "CCAA5197N",
        )

    def test_precondensado_no_nacional_sin_sufijo(self):
        self.assertEqual(
            generar_codigo_lote(self.fecha, TIPO_PRECONDENSADO), "CCAA5197"
        )

    def test_lep_por_linea(self):
        self.assertEqual(generar_codigo_lote(self.fecha, TIPO_LEP, linea="E1"), "CCAA51971")
        self.assertEqual(generar_codigo_lote(self.fecha, TIPO_LEP, linea="E2"), "CCAA51972")

    def test_segunda_produccion_agrega_A(self):
        self.assertEqual(
            generar_codigo_lote(self.fecha, TIPO_LEP, linea="E1", segunda_produccion=True),
            "CCAA51971A",
        )

    def test_tipo_desconocido_falla(self):
        with self.assertRaises(ValueError):
            generar_codigo_lote(self.fecha, "queso")

    def test_validador(self):
        self.assertTrue(codigo_lote_valido("CCAA51971"))
        self.assertTrue(codigo_lote_valido("CCAA5197N"))
        self.assertTrue(codigo_lote_valido("CCAA51971A"))
        self.assertFalse(codigo_lote_valido("6134"))
        self.assertFalse(codigo_lote_valido(""))
```

> Integración en la UI/serializer (fase siguiente): al dar de alta un lote, proponer el código con
> `generar_codigo_lote(...)` a partir de fecha + producto (tipo) + línea + destino, dejándolo editable.

---

## 2. `produccion/models.py` — Control de proceso (PCC 1)

Cabecera por lote/equipo/turno + una fila hija por lectura horaria. Los parámetros medidos varían
por equipo (VEB, Scheffers 2/3, E1/E2), por eso la lectura los guarda como `JSONField`, igual que
`Analisis.valores`. El PCC 1 (temperatura mínima y caudal máximo de uperización) va en la cabecera
como límite y en la lectura como valor; la evaluación de cumplimiento se hará en `dominio.py`.

```python
# --- añadir a produccion/models.py ---

class Equipo(models.TextChoices):
    """Equipos que registran control de proceso. Provisional como choices;
    puede migrar a un maestro `maestros.Equipo` con sus límites críticos."""
    VEB = "VEB", "Evaporador VEB"
    SCH2 = "SCH2", "Evaporador Scheffers 2"
    SCH3 = "SCH3", "Evaporador Scheffers 3"
    E1 = "E1", "Torre de secado Egron 1"
    E2 = "E2", "Torre de secado Egron 2"


class ControlProceso(models.Model):
    """
    Registro de control de proceso de un equipo para un lote (condensación o
    secado). Reúne el PCC 1 de uperización (CCAA.Cond.FORM.001/006/010–012 y
    CCAA.Sec.FORM.002/025/026).

    Origen: formatos de control de proceso de planta. El detalle horario vive en
    `ControlProcesoLectura`; aquí van la cabecera y el límite crítico del PCC 1.
    """

    lote = models.ForeignKey(
        "produccion.Lote",
        on_delete=models.CASCADE,
        related_name="controles_proceso",
        verbose_name="Lote",
    )
    equipo = models.CharField("Equipo", max_length=10, choices=Equipo.choices)
    turno = models.CharField(
        "Turno", max_length=5, choices=Lote.Turno.choices, blank=True
    )
    fecha = models.DateField("Fecha")
    hora_arranque = models.TimeField("Hora de arranque", null=True, blank=True)
    hora_inicio_produccion = models.TimeField("Inicio de producción", null=True, blank=True)
    hora_termino_produccion = models.TimeField("Término de producción", null=True, blank=True)

    # PCC 1 — Uperización. Límites del formato (VEB: 80,0 °C / 14.175 kg·h;
    # Sch2: 81,2 °C / 17.100 kg·h). Se guardan por registro porque cambian por
    # equipo/producto; el cumplimiento se recalcula en dominio.py, no se guarda.
    pcc1_temp_min = models.DecimalField(
        "PCC1 · Temperatura mínima (°C)", max_digits=5, decimal_places=1,
        null=True, blank=True,
    )
    pcc1_caudal_max = models.DecimalField(
        "PCC1 · Caudal máximo (kg/h)", max_digits=10, decimal_places=1,
        null=True, blank=True,
    )

    operador = models.ForeignKey(
        "auth.User", on_delete=models.PROTECT,
        related_name="controles_proceso", null=True, blank=True,
        verbose_name="Operador",
    )
    observacion = models.TextField("Observación", blank=True)

    class Meta:
        verbose_name = "Control de proceso"
        verbose_name_plural = "Controles de proceso"
        ordering = ["-fecha", "equipo"]

    def __str__(self):
        return f"Control {self.equipo} · {self.lote.codigo_lote} · {self.fecha}"


class ControlProcesoLectura(models.Model):
    """Una lectura horaria de un ControlProceso. Los parámetros medidos varían
    por equipo, así que se guardan como JSON (igual que Analisis.valores)."""

    control = models.ForeignKey(
        ControlProceso, on_delete=models.CASCADE,
        related_name="lecturas", verbose_name="Control de proceso",
    )
    hora = models.TimeField("Hora")
    valores = models.JSONField(
        "Valores medidos", default=dict,
        help_text='{"flujo_entrada": 13500, "densidad": 1020, "t_dsi": 82.1, ...}',
    )

    class Meta:
        verbose_name = "Lectura de control de proceso"
        verbose_name_plural = "Lecturas de control de proceso"
        ordering = ["hora"]

    def __str__(self):
        return f"{self.control.equipo} · {self.hora}"

    def clean(self):
        if not isinstance(self.valores, dict):
            raise ValidationError({"valores": "Debe ser un objeto de valores medidos."})
```

Regla de bloqueo asociada (a escribir en `calidad/dominio.py` / `puede_liberar`, con test):
una `ControlProcesoLectura` cuyo `t_dsi < control.pcc1_temp_min` o cuyo caudal supere
`pcc1_caudal_max` marca el lote y **bloquea la liberación**.

---

## 3. `MonitoreoPPRO` + `PproLectura` (PPRO / PCC detector de metales)

Chequeos OK / No-OK por hora y turno. Ubicación a decidir: `produccion` o una app nueva
`inocuidad` (recomendada si se quiere separar la capa FSSC). Origen: CCAA.Sec.FORM.022/007 y
CCAA.ENV.FORM.001/003.

```python
# --- ControlProceso vive en produccion; este bloque puede ir junto o en app `inocuidad` ---

class MonitoreoPPRO(models.Model):
    """Monitoreo de un PPRO/PCC para un lote y turno (p. ej. presión de aire,
    roce de válvulas, cuerpos extraños, detector de metales)."""

    class Tipo(models.TextChoices):
        AIRE_TRANSPORTE = "aire_transporte", "Presión aire transporte fluidizado"
        AIRE_SECUNDARIO = "aire_secundario", "Presión aire secundario"
        ROCE_VALVULAS = "roce_valvulas", "Roce válvulas fluidificadoras"
        CUERPOS_EXTRANOS = "cuerpos_extranos", "Cuerpos extraños"
        DETECTOR_METALES = "detector_metales", "Detector de metales (PCC)"

    lote = models.ForeignKey(
        "produccion.Lote", on_delete=models.CASCADE,
        related_name="monitoreos_ppro", verbose_name="Lote",
    )
    tipo = models.CharField("Tipo de PPRO", max_length=30, choices=Tipo.choices)
    equipo = models.CharField("Equipo", max_length=20, blank=True,
                              help_text="E1/E2, Rovema 3/4, etc.")
    turno = models.CharField("Turno", max_length=5, choices=Lote.Turno.choices, blank=True)
    fecha = models.DateField("Fecha")
    accion_correctiva = models.TextField(
        "Acción correctiva", blank=True,
        help_text="Obligatoria si hubo alguna lectura No-OK",
    )
    operador = models.ForeignKey(
        "auth.User", on_delete=models.PROTECT, related_name="monitoreos_ppro",
        null=True, blank=True, verbose_name="Operador",
    )

    class Meta:
        verbose_name = "Monitoreo PPRO"
        verbose_name_plural = "Monitoreos PPRO"
        ordering = ["-fecha", "tipo"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.lote.codigo_lote} · {self.fecha}"


class PproLectura(models.Model):
    """Lectura horaria de un MonitoreoPPRO."""

    class Resultado(models.TextChoices):
        OK = "ok", "OK"
        NO_OK = "no_ok", "No OK"

    monitoreo = models.ForeignKey(
        MonitoreoPPRO, on_delete=models.CASCADE,
        related_name="lecturas", verbose_name="Monitoreo",
    )
    hora = models.TimeField("Hora")
    resultado = models.CharField("Resultado", max_length=6, choices=Resultado.choices)
    # Para el detector de metales: rechazos y alarmas del período.
    detalle = models.JSONField("Detalle", default=dict, blank=True,
                               help_text='{"rechazos": 2, "alarmas": 1} (opcional)')

    class Meta:
        verbose_name = "Lectura PPRO"
        verbose_name_plural = "Lecturas PPRO"
        ordering = ["hora"]

    def __str__(self):
        return f"{self.hora} · {self.get_resultado_display()}"
```

Regla de bloqueo: un `MonitoreoPPRO` con alguna `PproLectura` `no_ok` y `accion_correctiva`
vacía **bloquea la liberación** del lote (en `calidad/dominio.py`, con test).

---

## 4. `maestros/models.py` — campo `area` en `DocumentoLiberacion`

Permite reproducir el flujo del Dossier (Recepción → Condensación → Secado → Envase) y saber qué
área tiene el registro pendiente. Añadir la clase `Area` y el campo dentro de `DocumentoLiberacion`:

```python
# --- dentro de class DocumentoLiberacion, junto a TIPOS_CAMPO ---

    class Area(models.TextChoices):
        RECEPCION = "recepcion", "Recepción"
        CONDENSACION = "condensacion", "Condensación"
        SECADO = "secado", "Secado"
        ENVASE = "envase", "Envase"
        CALIDAD = "calidad", "Calidad"

    # ... campos existentes ...
    area = models.CharField(
        "Área de origen", max_length=20, choices=Area.choices, blank=True,
        help_text="Etapa del flujo que genera el registro",
    )
```

Luego: `python manage.py makemigrations maestros`.

---

## 5. Data migration — sembrar los 19 registros del Dossier

`maestros/migrations/XXXX_seed_dossier.py` (ajustar el número al siguiente de la app). Idempotente:
usa `update_or_create` por `codigo`. `aplica_a` queda en `["polvo"]` por defecto — **confirmar con
Calidad** qué documentos aplican también a crema/mantequilla.

```python
from django.db import migrations

# Los 19 registros del Dossier CCAA.Calidad.FORM.023, en orden de flujo.
DOSSIER = [
    (1,  "recepcion",    "Trazabilidad de Leche fresca",                  "CCAA.REC.FORM.005"),
    (2,  "condensacion", "PCC 1 - Formulario de Control de Proceso",       "CCAA.Cond.FORM.010"),
    (3,  "condensacion", "Checklist de Cuerpos Extraños Evaporadores",     "CCAA.Cond.FORM.005"),
    (4,  "condensacion", "Disco de Uperización",                           ""),
    (5,  "secado",       "Hoja de Pulverización E1-E2",                    "CCAA.Sec.FORM.025"),
    (6,  "secado",       "Inspección Pre-operativa E1-E2",                 "CCAA.Sec.FORM.003"),
    (7,  "secado",       "Conexión a Tierra E1-E2",                        "CCAA.Sec.FORM.016"),
    (8,  "secado",       "Formulario de Análisis Fisicoquímico E1-E2",     "CCAA.Sec.FORM.001"),
    (9,  "secado",       "Formulario de Filtros de Limpieza de producto",  "CCAA.Sec.FORM.020"),
    (10, "secado",       "Dosificación de Lecitina en Leche en Polvo",     "CCAA.Sec.FORM.021"),
    (11, "secado",       "Checklist de Cuerpos Extraños E1-E2",            "CCAA.Sec.FORM.012"),
    (12, "secado",       "PPRO 3 - Monitoreo de PPRO E1-E2",               "CCAA.Sec.FORM.022"),
    (13, "envase",       "PPRO 4 - Monitoreo PPRO Rovemas 3 y 4",          "CCAA.Sec.FORM.005"),
    (14, "envase",       "Checklist de Cuerpos Extraños Rovema 3 y 4",     "CCAA.Sec.FORM.007"),
    (15, "envase",       "Inspección en Operación Rovema 3-4",             "CCAA.Sec.FORM.024"),
    (16, "envase",       "Seguimiento FEFO",                               "CCAA.Sec.FORM.023"),
    (17, "envase",       "PPRO 5 - Monitoreo PPRO Detector de Metales",    "CCAA.ENV.FORM.001"),
    (18, "envase",       "Control de Consumo de Materiales",               "CCAA.Sec.FORM.011"),
    (19, "envase",       "Control de Hermeticidad y Peso Neto",            "CCAA.ENV.FORM.004"),
]


def sembrar_dossier(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")
    for orden, area, nombre, codigo in DOSSIER:
        defaults = {
            "nombre": nombre,
            "area": area,
            "orden": orden,
            "aplica_a": ["polvo"],          # TODO confirmar crema/mantequilla con Calidad
            "plantilla": [],                # atestación; se detalla por documento después
            "fuente": "Dossier CCAA.Calidad.FORM.023 (levantamiento 2026-07)",
            "activo": True,
        }
        if codigo:
            Documento.objects.update_or_create(codigo=codigo, defaults=defaults)
        else:
            # El disco de uperización no tiene código: buscar por nombre.
            Documento.objects.update_or_create(
                codigo="", nombre=nombre, defaults=defaults
            )


def borrar_dossier(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")
    codigos = [c for _, _, _, c in DOSSIER if c]
    Documento.objects.filter(codigo__in=codigos).delete()


class Migration(migrations.Migration):

    dependencies = [
        # ("maestros", "XXXX_documentoliberacion_area"),  # la migración del campo `area`
    ]

    operations = [
        migrations.RunPython(sembrar_dossier, borrar_dossier),
    ]
```

> Nota: el PCC 1 (registro 2) referencia varios formatos según equipo
> (CCAA.Cond.FORM.001/006/009/010–012/007/013/015). Aquí se siembra un documento con el código
> representativo; si Calidad prefiere un registro por equipo, se expande la lista.

---

## Qué queda para las siguientes tareas P0/P1 (no en este borrador)

- Escribir las dos reglas de bloqueo (PCC1 y PPRO) en `calidad/dominio.py` y sus pruebas de
  regresión (que un lote con PCC1 fuera de límite o PPRO No-OK sin acción **no** pueda liberarse).
- Serializers, urls y admin de los modelos nuevos, y las pantallas de captura en el frontend.
- Definir la `plantilla` de cada uno de los 19 documentos (hoy van como atestación).
