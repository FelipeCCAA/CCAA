# Instrumentación y medición — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Poder responder con números —no con impresiones— qué endpoints se llaman de más, cuáles son lentos y cuáles disparan N+1, para que las optimizaciones posteriores se decidan y se comprueben con evidencia.

**Architecture:** Un middleware que mide cada request —latencia, número de consultas SQL y tiempo total en SQL— y escribe una línea JSON por request. Cuenta las consultas con `connection.execute_wrapper`, **no** con `connection.queries`, que solo se llena con `DEBUG=True` y en producción devolvería cero. Se activa por un ajuste y, cuando está apagado, Django lo descarta entero con `MiddlewareNotUsed`: cero costo. Un comando agrega ese registro en percentiles por ruta y en repeticiones por ventana de tiempo. Los cálculos son puros y viven en `dominio.py`.

**Tech Stack:** Django 6.0.7 + DRF, PostgreSQL, Nginx. Sin dependencias nuevas.

## Por qué esta tanda va primera

El prompt de optimización exige, para cada cambio: *«2. Mostrar evidencia … 5. Medir antes/después»*. **Hoy eso es imposible**: el backend no tiene Silk, ni Debug Toolbar, ni Prometheus, ni Sentry. Sin esta tanda, cualquier optimización posterior es a ciegas — que es exactamente lo que el prompt dice no querer.

Esta tanda **no optimiza nada**. Mide, y de paso arregla dos cosas baratas y seguras que no necesitan medición previa para justificarse.

## Global Constraints

- **No introducir dependencias nuevas.** `requirements.txt` no cambia.
- **Apagado por omisión.** Con `METRICAS_ACTIVAS = False` el middleware no debe existir en la cadena.
- **No tocar reglas de negocio, permisos, auditoría ni el camino de la firma.** Esta tanda es observación.
- **Español** en UI, datos y comentarios. Fechas ISO.
- Reglas puras en `dominio.py`, sin ORM, cubiertas en `tests_dominio.py`.
- Después de `makemigrations`, correr `migrate`.
- Comandos desde `backend/`: `.venv\Scripts\python.exe manage.py ...`

## Lista de intocables

Vale para esta tanda y para todas las siguientes de optimización. Un agente que optimice CPU va a tropezar con estas si no se le dicen:

| No tocar | Por qué |
|---|---|
| Cachear el **veredicto de calidad** o el **avance del checklist** | No se persisten a propósito: se recalculan. Cachearlos es cómo se libera un lote contra un veredicto viejo |
| `select_for_update` del camino de la firma | `DECISIONES.md` §001. Es la garantía de que dos firmas no se pisan |
| Las **señales** de `auditoria` | Capturan todo lo que escribe en la base, no solo la API. Saltarlas por rendimiento deja cambios sin rastro |
| Recortar serializers «que el frontend no usa» | Las decisiones devuelven **motivos**; quitar campos puede borrar en silencio un motivo de bloqueo |
| `.only()` / `.values()` sobre modelos con propiedades calculadas | `Recepcion.permanencia_horas`, `crioscopia_pool`, `AnalisisSilo.vigencia` leen campos fuera de `fields`. Diferir columnas dispara **más** consultas |
| Unificar los catálogos en un `Promise.all` con el resto | Decisión vigente: los datos auxiliares van aparte y **degradan solos**, para que un endpoint caído no vacíe la pantalla |

---

### Task 1: Los cálculos, puros

**Files:**
- Create: `backend/observabilidad/__init__.py`
- Create: `backend/observabilidad/apps.py`
- Create: `backend/observabilidad/dominio.py`
- Create: `backend/observabilidad/tests_dominio.py`

**Interfaces:**
- Produces:
  - `percentil(valores, p) -> float | None`
  - `Resumen` — dataclass con `ruta`, `llamadas`, `p50`, `p95`, `p99`, `ms_total`, `consultas_media`, `ms_sql_media`
  - `resumir(muestras) -> list[Resumen]`, ordenado por `ms_total` descendente
  - `repeticiones(muestras, ventana_seg) -> list[tuple[str, int]]`

- [ ] **Step 1: Crear la app y escribir las pruebas que fallan**

Crear `backend/observabilidad/__init__.py` vacío y `backend/observabilidad/apps.py`:

```python
from django.apps import AppConfig


class ObservabilidadConfig(AppConfig):
    name = "observabilidad"
    verbose_name = "Observabilidad"
```

Crear `backend/observabilidad/tests_dominio.py`:

```python
"""
Los cálculos de la medición, sin ORM ni middleware.

Se prueban solos porque son lo que va a sostener decisiones: si el p95 está
mal calculado, la optimización se decide contra un número inventado.
"""

from django.test import TestCase

from observabilidad import dominio


def _muestra(ruta, ms, consultas=1, ms_sql=1.0, t=0.0, usuario="op"):
    return dominio.Muestra(
        ruta=ruta, metodo="GET", estado=200, ms=ms,
        consultas=consultas, ms_sql=ms_sql, t=t, usuario=usuario,
    )


class PercentilTests(TestCase):
    def test_sin_valores_no_hay_percentil(self):
        """
        `None` y no cero: cero es un percentil bajísimo, y leerlo como tal
        haría pasar por rapidísimo a un endpoint que nadie llamó.
        """
        self.assertIsNone(dominio.percentil([], 95))

    def test_con_un_valor_todos_los_percentiles_son_ese(self):
        self.assertEqual(dominio.percentil([7.0], 50), 7.0)
        self.assertEqual(dominio.percentil([7.0], 99), 7.0)

    def test_usa_rango_mas_cercano(self):
        valores = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]

        self.assertEqual(dominio.percentil(valores, 50), 5.0)
        self.assertEqual(dominio.percentil(valores, 90), 9.0)
        self.assertEqual(dominio.percentil(valores, 100), 10.0)

    def test_no_le_importa_el_orden_de_entrada(self):
        self.assertEqual(dominio.percentil([9.0, 1.0, 5.0], 50), 5.0)


class ResumirTests(TestCase):
    def test_agrupa_por_ruta_y_ordena_por_tiempo_total(self):
        """
        Por tiempo **total**, no por el más lento: un endpoint de 20 ms
        llamado 300 veces cuesta más que uno de 900 ms llamado una vez, y es
        el que hay que mirar primero.
        """
        muestras = (
            [_muestra("/api/maestros/productos/", 20.0) for _ in range(300)]
            + [_muestra("/api/calidad/expedientes/", 900.0)]
        )

        resumen = dominio.resumir(muestras)

        self.assertEqual(resumen[0].ruta, "/api/maestros/productos/")
        self.assertEqual(resumen[0].llamadas, 300)
        self.assertEqual(resumen[0].ms_total, 6000.0)

    def test_promedia_consultas_y_tiempo_de_sql(self):
        muestras = [
            _muestra("/api/produccion/lotes/", 10.0, consultas=2, ms_sql=4.0),
            _muestra("/api/produccion/lotes/", 10.0, consultas=8, ms_sql=6.0),
        ]

        resumen = dominio.resumir(muestras)

        self.assertEqual(resumen[0].consultas_media, 5.0)
        self.assertEqual(resumen[0].ms_sql_media, 5.0)


class RepeticionesTests(TestCase):
    def test_cuenta_la_misma_ruta_repetida_dentro_de_la_ventana(self):
        """
        Es el síntoma reportado: `productos/` varias veces en segundos al
        navegar entre módulos.
        """
        muestras = [
            _muestra("/api/maestros/productos/", 5.0, t=0.0),
            _muestra("/api/maestros/productos/", 5.0, t=1.0),
            _muestra("/api/maestros/productos/", 5.0, t=2.0),
        ]

        self.assertEqual(
            dominio.repeticiones(muestras, ventana_seg=5.0),
            [("/api/maestros/productos/", 3)],
        )

    def test_fuera_de_la_ventana_no_es_repeticion(self):
        muestras = [
            _muestra("/api/maestros/productos/", 5.0, t=0.0),
            _muestra("/api/maestros/productos/", 5.0, t=60.0),
        ]

        self.assertEqual(dominio.repeticiones(muestras, ventana_seg=5.0), [])

    def test_dos_usuarios_pidiendo_lo_mismo_no_es_una_repeticion(self):
        """
        Dos operadores abriendo la misma pantalla es uso normal. Lo que se
        busca es una pantalla pidiendo lo mismo dos veces.
        """
        muestras = [
            _muestra("/api/maestros/productos/", 5.0, t=0.0, usuario="ana"),
            _muestra("/api/maestros/productos/", 5.0, t=1.0, usuario="luis"),
        ]

        self.assertEqual(dominio.repeticiones(muestras, ventana_seg=5.0), [])
```

- [ ] **Step 2: Correr y verificar que falla**

```
cd backend
.venv\Scripts\python.exe manage.py test observabilidad --noinput -v 2
```

Esperado: FAIL — `ModuleNotFoundError: No module named 'observabilidad.dominio'`.
Si la app todavía no está en `INSTALLED_APPS`, el runner igual descubre el módulo
por ruta; si no lo hiciera, agregarla ahora (Task 4 lo formaliza).

- [ ] **Step 3: Escribir el dominio**

Crear `backend/observabilidad/dominio.py`:

```python
"""
Los cálculos de la medición. Sin ORM, sin Django, sin reloj.

El tiempo entra como número en la muestra en vez de leerse aquí: una función
que consulta el reloj no se puede probar dos veces con el mismo resultado.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Muestra:
    ruta: str
    metodo: str
    estado: int
    ms: float
    consultas: int
    ms_sql: float
    t: float
    usuario: str


@dataclass(frozen=True)
class Resumen:
    ruta: str
    llamadas: int
    p50: float | None
    p95: float | None
    p99: float | None
    ms_total: float
    consultas_media: float
    ms_sql_media: float


def percentil(valores, p: float) -> float | None:
    """
    Percentil por rango más cercano.

    Devuelve `None` sin valores, y no cero: cero es un percentil bajísimo, y
    leerlo como tal haría pasar por rapidísimo a un endpoint que nadie llamó.
    """
    if not valores:
        return None

    ordenados = sorted(valores)

    if p <= 0:
        return ordenados[0]

    indice = math.ceil(p / 100 * len(ordenados)) - 1

    return ordenados[max(0, min(indice, len(ordenados) - 1))]


def resumir(muestras) -> list[Resumen]:
    """
    Una fila por ruta, ordenadas por **tiempo total** descendente.

    Por total y no por el más lento: un endpoint de 20 ms llamado 300 veces
    cuesta más que uno de 900 ms llamado una vez, y es el que hay que mirar
    primero.
    """
    por_ruta = defaultdict(list)

    for muestra in muestras:
        por_ruta[muestra.ruta].append(muestra)

    filas = []

    for ruta, grupo in por_ruta.items():
        tiempos = [m.ms for m in grupo]
        filas.append(
            Resumen(
                ruta=ruta,
                llamadas=len(grupo),
                p50=percentil(tiempos, 50),
                p95=percentil(tiempos, 95),
                p99=percentil(tiempos, 99),
                ms_total=sum(tiempos),
                consultas_media=sum(m.consultas for m in grupo) / len(grupo),
                ms_sql_media=sum(m.ms_sql for m in grupo) / len(grupo),
            )
        )

    return sorted(filas, key=lambda f: f.ms_total, reverse=True)


def repeticiones(muestras, ventana_seg: float) -> list[tuple[str, int]]:
    """
    Rutas que el **mismo usuario** pidió más de una vez dentro de la ventana.

    Se agrupa por usuario porque dos operadores abriendo la misma pantalla es
    uso normal; lo que se busca es una pantalla pidiendo lo mismo dos veces.
    """
    por_clave = defaultdict(list)

    for muestra in muestras:
        por_clave[(muestra.usuario, muestra.ruta)].append(muestra.t)

    encontradas = defaultdict(int)

    for (_, ruta), tiempos in por_clave.items():
        tiempos.sort()
        inicio = 0
        for fin in range(len(tiempos)):
            while tiempos[fin] - tiempos[inicio] > ventana_seg:
                inicio += 1
            racha = fin - inicio + 1
            if racha > 1:
                encontradas[ruta] = max(encontradas[ruta], racha)

    return sorted(encontradas.items(), key=lambda par: par[1], reverse=True)
```

- [ ] **Step 4: Correr y verificar que pasa**

```
cd backend
.venv\Scripts\python.exe manage.py test observabilidad --noinput -v 2
```

Esperado: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/observabilidad/
git commit -m "Observabilidad: percentiles, resumen por ruta y repeticiones, sin ORM"
```

---

### Task 2: El middleware que mide

**Files:**
- Create: `backend/observabilidad/middleware.py`
- Create: `backend/observabilidad/tests_middleware.py`

**Interfaces:**
- Consumes: `django.db.connection.execute_wrapper`
- Produces: `observabilidad.middleware.MetricasMiddleware`, que emite una línea JSON por request al logger `metricas` con las claves `ruta`, `metodo`, `estado`, `ms`, `consultas`, `ms_sql`, `t`, `usuario`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `backend/observabilidad/tests_middleware.py`:

```python
"""
El middleware mide sin estorbar.

Dos propiedades que hay que fijar: que cuente las consultas **con
`DEBUG=False`** —que es como corre en producción— y que apagado no exista.
"""

import json

from django.core.exceptions import MiddlewareNotUsed
from django.test import TestCase, override_settings

from observabilidad.middleware import MetricasMiddleware


@override_settings(METRICAS_ACTIVAS=True, DEBUG=False)
class MetricasMiddlewareTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from rest_framework.authtoken.models import Token
        from rest_framework.test import APIClient
        from usuarios.models import PerfilUsuario, Rol

        usuario = User.objects.create_user("medido", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=Rol.RECEPCION)
        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )

    def test_registra_una_linea_por_request_con_consultas_contadas(self):
        with self.assertLogs("metricas", level="INFO") as registro:
            respuesta = self.cliente.get("/api/recepcion/analisis-silo/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(registro.output), 1)

        datos = json.loads(registro.output[0].split(":", 2)[2])
        self.assertEqual(datos["metodo"], "GET")
        self.assertEqual(datos["estado"], 200)
        self.assertEqual(datos["usuario"], "medido")
        self.assertGreater(datos["ms"], 0)
        self.assertGreater(
            datos["consultas"], 0,
            "Con DEBUG=False, `connection.queries` está vacío: hay que contar "
            "con execute_wrapper o esto sale en cero y la medición miente.",
        )

    def test_la_ruta_agrupa_los_detalles_por_su_patron(self):
        """
        Sin esto, cada id sería un endpoint distinto y el resumen tendría
        una fila por lote en vez de una por endpoint.
        """
        from maestros.models import Silo
        from recepcion.models import AnalisisSilo
        from datetime import datetime, timezone as tz
        from decimal import Decimal

        silo = Silo.objects.create(
            codigo="SILO 7", tipo=Silo.Tipo.SILO, capacidad_l=Decimal("1000")
        )
        analisis = AnalisisSilo.objects.create(
            silo=silo, tomado_en=datetime(2026, 8, 20, 9, 0, tzinfo=tz.utc)
        )

        with self.assertLogs("metricas", level="INFO") as registro:
            self.cliente.get(f"/api/recepcion/analisis-silo/{analisis.id}/")

        datos = json.loads(registro.output[0].split(":", 2)[2])
        self.assertNotIn(str(analisis.id), datos["ruta"])


class MiddlewareApagadoTests(TestCase):
    @override_settings(METRICAS_ACTIVAS=False)
    def test_apagado_django_lo_descarta(self):
        """
        `MiddlewareNotUsed` hace que Django lo saque de la cadena: apagado no
        cuesta una llamada por request, cuesta cero.
        """
        with self.assertRaises(MiddlewareNotUsed):
            MetricasMiddleware(lambda peticion: None)
```

- [ ] **Step 2: Correr y verificar que falla**

```
cd backend
.venv\Scripts\python.exe manage.py test observabilidad.tests_middleware --noinput -v 2
```

Esperado: FAIL — `ModuleNotFoundError: No module named 'observabilidad.middleware'`

- [ ] **Step 3: Escribir el middleware**

Crear `backend/observabilidad/middleware.py`:

```python
"""
Mide cada request: latencia, consultas SQL y tiempo en SQL.

**Cuenta con `connection.execute_wrapper` y no con `connection.queries`.**
`connection.queries` solo se llena con `DEBUG=True`; en producción devolvería
cero consultas por request y la medición diría que no hay N+1 en ninguna
parte.

Escribe una línea JSON por request a un logger y no a la base: guardar la
medición en PostgreSQL agregaría escrituras a cada request y distorsionaría
justamente lo que se está midiendo.
"""

import json
import logging
import time

from django.core.exceptions import MiddlewareNotUsed
from django.conf import settings
from django.db import connection

registro = logging.getLogger("metricas")


class _Contador:
    """Cuenta consultas y su tiempo, sin depender de DEBUG."""

    def __init__(self):
        self.consultas = 0
        self.segundos = 0.0

    def __call__(self, ejecutar, sql, parametros, muchos, contexto):
        inicio = time.perf_counter()
        try:
            return ejecutar(sql, parametros, muchos, contexto)
        finally:
            self.consultas += 1
            self.segundos += time.perf_counter() - inicio


class MetricasMiddleware:
    def __init__(self, obtener_respuesta):
        if not getattr(settings, "METRICAS_ACTIVAS", False):
            # Django lo saca de la cadena: apagado cuesta cero, no una
            # llamada por request.
            raise MiddlewareNotUsed

        self.obtener_respuesta = obtener_respuesta

    def __call__(self, peticion):
        contador = _Contador()
        inicio = time.perf_counter()

        with connection.execute_wrapper(contador):
            respuesta = self.obtener_respuesta(peticion)

        transcurrido = (time.perf_counter() - inicio) * 1000

        # El patrón de la ruta y no la URL: sin esto cada id sería un
        # endpoint distinto y el resumen tendría una fila por lote.
        coincidencia = getattr(peticion, "resolver_match", None)
        ruta = f"/{coincidencia.route}" if coincidencia else peticion.path

        usuario = getattr(peticion, "user", None)
        registro.info(
            json.dumps(
                {
                    "ruta": ruta,
                    "metodo": peticion.method,
                    "estado": respuesta.status_code,
                    "ms": round(transcurrido, 2),
                    "consultas": contador.consultas,
                    "ms_sql": round(contador.segundos * 1000, 2),
                    "t": round(time.time(), 3),
                    "usuario": (
                        usuario.username
                        if usuario is not None and usuario.is_authenticated
                        else ""
                    ),
                }
            )
        )

        return respuesta
```

- [ ] **Step 4: Correr y verificar que pasa**

```
cd backend
.venv\Scripts\python.exe manage.py test observabilidad --noinput -v 2
```

Esperado: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/observabilidad/middleware.py backend/observabilidad/tests_middleware.py
git commit -m "Observabilidad: middleware que mide latencia y consultas por request"
```

---

### Task 3: El comando que resume

**Files:**
- Create: `backend/observabilidad/management/__init__.py`
- Create: `backend/observabilidad/management/commands/__init__.py`
- Create: `backend/observabilidad/management/commands/resumen_metricas.py`
- Create: `backend/observabilidad/tests_comando.py`

**Interfaces:**
- Consumes: `dominio.Muestra`, `dominio.resumir`, `dominio.repeticiones`
- Produces: `manage.py resumen_metricas <archivo.jsonl> [--ventana 5]`

- [ ] **Step 1: Escribir la prueba que falla**

Crear `backend/observabilidad/tests_comando.py`:

```python
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase


class ResumenMetricasTests(TestCase):
    def _archivo(self, filas):
        ruta = Path(tempfile.mkdtemp()) / "metricas.jsonl"
        ruta.write_text(
            "\n".join(json.dumps(f) for f in filas), encoding="utf-8"
        )
        return str(ruta)

    def _fila(self, ruta, ms, t, consultas=1):
        return {
            "ruta": ruta, "metodo": "GET", "estado": 200, "ms": ms,
            "consultas": consultas, "ms_sql": 1.0, "t": t, "usuario": "op",
        }

    def test_informa_llamadas_percentiles_y_repeticiones(self):
        archivo = self._archivo([
            self._fila("/api/maestros/productos/", 10.0, 0.0),
            self._fila("/api/maestros/productos/", 30.0, 1.0),
            self._fila("/api/maestros/productos/", 20.0, 2.0),
        ])
        salida = StringIO()

        call_command("resumen_metricas", archivo, stdout=salida)
        texto = salida.getvalue()

        self.assertIn("/api/maestros/productos/", texto)
        self.assertIn("3", texto)
        self.assertIn("repeticion", texto.lower())

    def test_una_linea_corrupta_no_tumba_el_informe(self):
        """
        El registro se escribe en producción y puede quedar cortado a mitad
        de línea. Perder el informe entero por eso sería perder la medición.
        """
        ruta = Path(tempfile.mkdtemp()) / "metricas.jsonl"
        ruta.write_text(
            json.dumps(self._fila("/api/produccion/lotes/", 5.0, 0.0))
            + "\n{ esto no es json\n",
            encoding="utf-8",
        )
        salida = StringIO()

        call_command("resumen_metricas", str(ruta), stdout=salida)

        self.assertIn("/api/produccion/lotes/", salida.getvalue())
        self.assertIn("1 línea ilegible", salida.getvalue())
```

- [ ] **Step 2: Correr y verificar que falla**

```
cd backend
.venv\Scripts\python.exe manage.py test observabilidad.tests_comando --noinput -v 2
```

Esperado: FAIL — `CommandError: Unknown command: 'resumen_metricas'`

- [ ] **Step 3: Escribir el comando**

Crear los dos `__init__.py` vacíos y
`backend/observabilidad/management/commands/resumen_metricas.py`:

```python
"""
Convierte el registro de métricas en las respuestas que se necesitan.

Las dos preguntas que contesta son las del síntoma reportado: qué endpoints
cuestan más en total, y cuáles pide la misma pantalla varias veces seguidas.
"""

import json

from django.core.management.base import BaseCommand

from observabilidad import dominio


class Command(BaseCommand):
    help = "Resume un registro de métricas: percentiles por ruta y repeticiones."

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Ruta al .jsonl que escribió el middleware")
        parser.add_argument(
            "--ventana", type=float, default=5.0,
            help="Segundos dentro de los cuales dos llamadas iguales son repetición",
        )

    def handle(self, *args, **opciones):
        muestras, ilegibles = self._leer(opciones["archivo"])

        if not muestras:
            self.stdout.write(self.style.WARNING("El registro no trae muestras."))
            return

        self.stdout.write(f"\n{len(muestras)} requests medidos\n")

        self.stdout.write(
            f"\n{'ruta':<52}{'n':>6}{'p50':>8}{'p95':>8}{'p99':>8}"
            f"{'total':>10}{'SQL':>7}{'msSQL':>8}"
        )
        for fila in dominio.resumir(muestras):
            self.stdout.write(
                f"{fila.ruta[:50]:<52}{fila.llamadas:>6}"
                f"{fila.p50:>8.0f}{fila.p95:>8.0f}{fila.p99:>8.0f}"
                f"{fila.ms_total:>10.0f}{fila.consultas_media:>7.1f}"
                f"{fila.ms_sql_media:>8.1f}"
            )

        repetidas = dominio.repeticiones(muestras, opciones["ventana"])
        self.stdout.write(
            f"\nRepeticiones dentro de {opciones['ventana']:.0f} s "
            f"(mismo usuario, misma ruta):"
        )
        if not repetidas:
            self.stdout.write("  ninguna")
        for ruta, veces in repetidas:
            self.stdout.write(f"  {veces:>3}x  {ruta}")

        if ilegibles:
            self.stdout.write(
                self.style.WARNING(f"\n{ilegibles} línea ilegible(s) omitida(s).")
            )

    def _leer(self, archivo):
        muestras, ilegibles = [], 0

        with open(archivo, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    muestras.append(dominio.Muestra(**json.loads(linea)))
                except (ValueError, TypeError):
                    # El registro se escribe en producción y puede quedar
                    # cortado. Perder el informe entero por una línea rota
                    # sería perder la medición.
                    ilegibles += 1

        return muestras, ilegibles
```

- [ ] **Step 4: Correr y verificar que pasa**

```
cd backend
.venv\Scripts\python.exe manage.py test observabilidad --noinput -v 2
```

Esperado: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/observabilidad/management/ backend/observabilidad/tests_comando.py
git commit -m "Observabilidad: comando que resume el registro en percentiles y repeticiones"
```

---

### Task 4: Conectarlo y tomar la línea base

**Files:**
- Modify: `backend/config/settings.py`

**Interfaces:**
- Produces: `METRICAS_ACTIVAS` (por variable de entorno, apagado por omisión), el middleware al final de `MIDDLEWARE`, y el logger `metricas` escribiendo a `METRICAS_ARCHIVO`.

- [ ] **Step 1: Agregar la app, el ajuste y el logger**

En `backend/config/settings.py`:

```python
INSTALLED_APPS = [
    # ... sin cambios ...
    "observabilidad",
]
```

Después de la definición de `MIDDLEWARE`, agregar:

```python
# Medición de rendimiento. Apagada por omisión: se enciende para medir y se
# apaga después. `MetricasMiddleware` va **después** de AuditoriaMiddleware
# para medir el request completo, incluida la auditoría.
METRICAS_ACTIVAS = os.getenv("METRICAS_ACTIVAS", "").lower() in {"1", "true"}
METRICAS_ARCHIVO = os.getenv("METRICAS_ARCHIVO", "/tmp/metricas.jsonl")

if METRICAS_ACTIVAS:
    MIDDLEWARE = MIDDLEWARE + ["observabilidad.middleware.MetricasMiddleware"]

    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "metricas": {
                "class": "logging.FileHandler",
                "filename": METRICAS_ARCHIVO,
                "encoding": "utf-8",
                "formatter": "crudo",
            }
        },
        "formatters": {"crudo": {"format": "%(message)s"}},
        "loggers": {
            "metricas": {
                "handlers": ["metricas"],
                "level": "INFO",
                "propagate": False,
            }
        },
    }
```

Verificar que `os` esté importado en `settings.py` (lo está).

- [ ] **Step 2: Comprobar que apagado no cambia nada**

```
cd backend
.venv\Scripts\python.exe manage.py test
```

Esperado: PASS, sin cambios en el conteo respecto de la línea base.

- [ ] **Step 3: Comprobar que encendido mide**

```
cd backend
METRICAS_ACTIVAS=1 METRICAS_ARCHIVO=/tmp/base.jsonl .venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

En otra terminal, levantar el frontend y **navegar rápido entre módulos durante
dos minutos**, que es el escenario reportado. Luego:

```
cd backend
.venv\Scripts\python.exe manage.py resumen_metricas /tmp/base.jsonl
```

Esperado: una tabla con los endpoints ordenados por tiempo total y una lista de
repeticiones. **Esta salida es la línea base**: guardarla.

- [ ] **Step 4: Commit**

```bash
git add backend/config/settings.py
git commit -m "Conecta la medición, apagada por omisión"
```

---

### Task 5: Paginación con orden estable

**Files:**
- Modify: `backend/inventario/models.py`
- Create: `backend/inventario/tests_orden_estable.py`

**Interfaces:**
- Produces: `ordering = ["-id"]` en `Existencia`, `InspeccionMaterial`, `AjusteInventario` y `SolicitudMaterial`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `backend/inventario/tests_orden_estable.py`:

```python
"""
Paginar sin orden es devolver resultados inconsistentes.

`UnorderedObjectListWarning` no es un problema de rendimiento: sin `ORDER BY`,
PostgreSQL puede devolver las filas en cualquier orden entre una consulta y la
siguiente, así que un registro puede aparecer en la página 1 y en la 2, o en
ninguna. Es corrección, no velocidad.
"""

from django.test import TestCase

from inventario.models import (
    AjusteInventario, Existencia, InspeccionMaterial, SolicitudMaterial,
)


class OrdenEstableTests(TestCase):
    def test_los_modelos_paginados_declaran_su_orden(self):
        for modelo in (
            Existencia, InspeccionMaterial, AjusteInventario, SolicitudMaterial,
        ):
            with self.subTest(modelo=modelo.__name__):
                self.assertTrue(
                    modelo._meta.ordering,
                    f"{modelo.__name__} se pagina sin orden: sus páginas no "
                    f"son reproducibles.",
                )
```

- [ ] **Step 2: Correr y verificar que falla**

```
cd backend
.venv\Scripts\python.exe manage.py test inventario.tests_orden_estable --noinput -v 2
```

Esperado: FAIL en los cuatro subtests.

- [ ] **Step 3: Declarar el orden**

En `backend/inventario/models.py`, en la `class Meta` de cada uno de los cuatro
modelos, agregar:

```python
        # Sin orden, la paginación no es reproducible: una fila puede salir en
        # dos páginas o en ninguna. `-id` es estable, está indexado por ser la
        # clave primaria, y deja lo más reciente primero.
        ordering = ["-id"]
```

`SolicitudMaterial` y `AjusteInventario` ya tienen `class Meta`; `Existencia` e
`InspeccionMaterial` puede que no — crearla si falta.

- [ ] **Step 4: Correr y verificar**

```
cd backend
.venv\Scripts\python.exe manage.py test inventario --noinput -v 2
```

Esperado: PASS. `ordering` no genera migración de esquema, pero correr
`makemigrations --check --dry-run` para confirmarlo.

- [ ] **Step 5: Commit**

```bash
git add backend/inventario/models.py backend/inventario/tests_orden_estable.py
git commit -m "Paginación con orden estable en los cuatro modelos que avisaba DRF"
```

---

### Task 6: El healthcheck de Nginx deja de cruzar a Django

**Files:**
- Modify: `infra/nginx/nginx.conf`
- Modify: `infra/nginx/nginx.production.conf`
- Modify: `compose.yml`

**Interfaces:**
- Produces: `GET /salud/nginx` servido por Nginx sin tocar el backend.

- [ ] **Step 1: Agregar la ruta propia**

En **los dos** archivos de configuración, antes de `location ~ ^/(api|admin)(/|$)`:

```nginx
        # El healthcheck de Nginx comprueba **Nginx**. Antes pedía
        # /api/salud/listo/, o sea que cada 10 s cruzaba a Django y sumaba un
        # request a Gunicorn que ya se comprueba a sí mismo por dentro. Que
        # Django esté caído no significa que Nginx lo esté.
        location = /salud/nginx {
            access_log off;
            add_header Content-Type text/plain;
            return 200 "ok\n";
        }
```

- [ ] **Step 2: Apuntar el healthcheck a la ruta nueva**

En `compose.yml`, en el servicio `nginx`, reemplazar:

```yaml
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1:8080/api/salud/listo/"]
```

por:

```yaml
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1:8080/salud/nginx"]
```

Dejar `interval: 10s` como está: la comprobación ya no cuesta nada.

- [ ] **Step 3: Comprobar**

```bash
docker compose up -d nginx
docker compose exec nginx wget -qO- http://127.0.0.1:8080/salud/nginx
docker compose ps nginx
```

Esperado: devuelve `ok` y el servicio queda `healthy`. Confirmar en los logs de
Django que **dejaron de aparecer** las peticiones de Wget a `/api/salud/listo/`.

- [ ] **Step 4: Commit**

```bash
git add infra/nginx/nginx.conf infra/nginx/nginx.production.conf compose.yml
git commit -m "El healthcheck de Nginx comprueba Nginx, no Django"
```

---

### Task 7: Dejar escrito cómo se mide

**Files:**
- Create: `docs/MEDICION_DE_RENDIMIENTO.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Escribir el instructivo**

Crear `docs/MEDICION_DE_RENDIMIENTO.md` con: cómo encender la medición
(`METRICAS_ACTIVAS=1`), el guion de la sesión de navegación de dos minutos,
cómo leer el resumen, **la línea base capturada en la Task 4 pegada entera**, y
la lista de intocables de este plan.

- [ ] **Step 2: Anotar la decisión en `CLAUDE.md`**

Agregar a «Decisiones vigentes»:

```markdown
- **La medición se cuenta con `execute_wrapper`, no con `connection.queries`** (desde
  2026-08-20, app `observabilidad`). `connection.queries` solo se llena con `DEBUG=True`:
  en producción devolvería cero consultas por request y la medición diría que no hay N+1
  en ninguna parte. El middleware está **apagado por omisión** y Django lo descarta con
  `MiddlewareNotUsed`, así que apagado cuesta cero.

  Escribe a un archivo y **no a la base**: guardar la medición en PostgreSQL agregaría
  escrituras a cada request y distorsionaría justo lo que se mide.

  Ninguna optimización se aplica sin una medición antes y otra después. La línea base y el
  procedimiento están en `docs/MEDICION_DE_RENDIMIENTO.md`.
```

- [ ] **Step 3: Suite completa**

```
cd backend
.venv\Scripts\python.exe manage.py test
```

Esperado: PASS sin regresiones.

- [ ] **Step 4: Commit**

```bash
git add docs/MEDICION_DE_RENDIMIENTO.md CLAUDE.md
git commit -m "Documenta cómo se mide el rendimiento y la línea base"
```

---

## Qué queda fuera, y por qué

| Fuera | Motivo |
|---|---|
| Cualquier optimización de consultas, caché o frontend | **Es el punto**: se deciden con la medición de la Task 4 en la mano, no antes |
| TanStack Query | No está instalado. Agregarlo es una decisión de arquitectura, no una optimización; se evalúa cuando se sepa cuánto del problema es deduplicación |
| `pg_stat_statements` | Va en la tanda de base de datos, junto con `EXPLAIN ANALYZE` de las consultas que esta medición señale |
| Tuning de Gunicorn | El propio prompt dice medir primero. Sin la línea base no hay con qué decidir |
| Intervalos de los healthchecks de PostgreSQL y Redis | `pg_isready` y `redis-cli ping` no consultan datos; su costo es despreciable frente a los picos reportados. Tocarlos sin medir sería justo la microoptimización sin evidencia que el prompt pone en prioridad BAJA |

## Después de esta tanda

Con la línea base, escribir un plan por tanda **en este orden**, cada uno citando
la evidencia que lo justifica:

1. **N+1 y consultas lentas** — sobre los endpoints que el resumen ponga arriba por
   `consultas_media`. Ya hay uno conocido: `AnalisisSiloViewSet` con `?vigentes=1` evalúa
   la vigencia por fila, y cada evaluación consulta `MovimientoSilo`.
2. **Deduplicación en el frontend** — sobre las rutas que aparezcan en «repeticiones».
3. **Índices** — solo sobre lo que `EXPLAIN ANALYZE` muestre, nunca por intuición.
