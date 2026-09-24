# Puestos de Bodega y Despacho — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar `/inventario` —un panel de consulta con formularios al final— por dos puestos de trabajo (`/bodega`, `/despacho`) y una consulta de solo lectura (`/inventario`), y devolver Abastecimiento como sección de compras.

**Architecture:** Primero el backend que los puestos necesitan (número de despacho automático, un pallet en una sola hoja activa, cancelar, filtros, pendientes de bodega). Después las bases compartidas del frontend (formato de cantidades, listas que recorren páginas, permisos por capacidades, tres componentes). Por último los puestos, que ya nacen con esas bases; la pantalla vieja no se parchea, se reemplaza.

**Tech Stack:** Django 6 + DRF + PostgreSQL; React 19 + TypeScript + Vite + Tailwind; `node --test` para unitarias del frontend; Playwright para E2E.

**Spec:** `docs/superpowers/specs/2026-09-24-puestos-bodega-despacho-design.md`

## Global Constraints

- Español en código, comentarios, mensajes y UI. Fechas ISO `YYYY-MM-DD`.
- Número de despacho: `DE` + último dígito del año + día juliano (3 cifras) + `-` + correlativo del día (mínimo 2 cifras), sobre la **fecha local** de creación (`timezone.localdate()`), p. ej. `DE6267-01` el 2026-09-24. Máximo existente con ese prefijo **en la planta**, más uno; reintento ante colisión dentro de un savepoint, **hasta 5 intentos**. `numero` es de solo lectura en el serializer: **un cliente que lo mande se ignora, no se rechaza**.
- Un pallet no puede estar en dos despachos `borrador`/`autorizado` a la vez; el rechazo **nombra el despacho** que lo tiene.
- `POST despachos/{id}/cancelar/` exige `motivo`; solo desde `borrador` o `autorizado`; mismo permiso que autorizar (`despacho_autorizar` o superusuario). Un despacho **no se borra**.
- Filtros `q`, `estado`, `ubicacion`, `desde`, `hasta` en `get_queryset`, sin dependencias nuevas.
- En el frontend, **ninguna cantidad cruda en pantalla**: toda cantidad pasa por `cantidad(valor, unidad)` de `services/formato.ts`.
- `puedeDespachar` / `puedeAutorizarDespacho` deciden **solo** con `usuario.capacidades`; nunca con rol ni área.
- Toda operación irreversible pasa por `ConfirmarAccion` (resumen + confirmar).
- Django 6: `Model.save()` solo acepta argumentos por nombre.
- Pruebas del backend: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test <etiqueta> --noinput`, **en serie** (nunca `--parallel`). Si queda una base `test_*` colgada de una corrida anterior, bórrala antes de reintentar.
- Frontend: `npx tsc -b --pretty false` (no `tsc --noEmit`, que no comprueba nada aquí), `npx eslint <archivos>`, `npm test`.
- Después de `makemigrations` hay que correr `migrate` sobre la base de desarrollo (el runner de pruebas migra solo la suya).
- Nunca commitear `frontend/e2e/.auth/estado.json`. Commits sin líneas de atribución.
- No reescribir archivos con acentos usando `Get-Content | Set-Content` de PowerShell: usa Edit.

## Mapa de archivos

| Archivo | Cambio | Tarea |
|---|---|---|
| `backend/inventario/dominio.py` | nuevo: prefijo, número y correlativo de despacho | 1 |
| `backend/inventario/models.py` | `Despacho.asignar_numero()`; campos de cancelación | 1, 2 |
| `backend/inventario/migrations/0030_despacho_cancelacion.py` | generada | 2 |
| `backend/inventario/serializers.py` | `numero` solo lectura; regla de hoja activa; campos legibles | 1, 2, 3 |
| `backend/inventario/servicios.py` | `cancelar_despacho` | 2 |
| `backend/inventario/views.py` | acción `cancelar`, `?vigentes=1`, `FiltraConsultaMixin`, `pendientes_bodega` | 2, 3, 4 |
| `backend/inventario/urls.py` | ruta `pendientes-bodega/` | 4 |
| `backend/inventario/pruebas_base.py` | nuevo: escenario compartido de producto terminado | 1 |
| `backend/inventario/tests_producto_terminado.py` | hereda el escenario | 1 |
| `backend/inventario/tests_despacho_numero.py` | nuevo | 1 |
| `backend/inventario/tests_despacho_hoja.py` | nuevo | 2 |
| `backend/inventario/tests_filtros_inventario.py` | nuevo | 3 |
| `backend/inventario/tests_pendientes_bodega.py` | nuevo | 4 |
| `frontend/src/services/formato.ts` | nuevo: `cantidad()` | 5 |
| `frontend/src/services/paginacion.ts` | nuevo: recorrer páginas, filtros | 5 |
| `frontend/src/services/permisos-despacho.ts` | nuevo | 5 |
| `frontend/src/components/operacion/{ConfirmarAccion,CampoEtiquetado,BuscadorCodigo}.tsx` | nuevos | 5 |
| `frontend/src/services/inventario.service.ts` | `lista()` recorre páginas; búsquedas paginadas; cancelar; pendientes; tipos | 5, 6 |
| `frontend/src/services/access-control.ts` | módulos `bodega`, `despacho`, `abastecimiento`; destinos iniciales | 6, 7, 8 |
| `frontend/src/services/navegacion-operacional.ts` | entradas de menú | 6, 7, 8, 9 |
| `frontend/src/app/routes.tsx` | rutas nuevas y Abastecimiento restaurado | 6, 7, 8, 9 |
| `frontend/src/pages/Abastecimiento/Abastecimiento.tsx` | pestañas de compras | 6 |
| `frontend/src/services/bodega-reglas.ts` | nuevo: conteo y destinos válidos | 7 |
| `frontend/src/pages/Bodega/*` | nuevo puesto | 7 |
| `frontend/src/services/despacho-reglas.ts` | nuevo: grupos y totales | 8 |
| `frontend/src/pages/Despacho/*` | nuevo puesto | 8 |
| `frontend/src/pages/Inventario/Inventario.tsx` | consulta de solo lectura | 9 |
| `frontend/src/pages/Inventario/OperacionesBodega.tsx` | se elimina | 9 |
| `frontend/e2e/flujo-polvo-continuacion.spec.ts` y demás specs que usan `/inventario` | selectores | 9 |
| `CLAUDE.md` | decisiones nuevas | 2, 9 |

---

### Task 1: Número de despacho automático

**Files:**
- Create: `backend/inventario/dominio.py`
- Create: `backend/inventario/pruebas_base.py`
- Create: `backend/inventario/tests_despacho_numero.py`
- Modify: `backend/inventario/models.py` (clase `Despacho`, ~línea 1030; imports)
- Modify: `backend/inventario/serializers.py` (`DespachoSerializer`, ~línea 861)
- Modify: `backend/inventario/tests_producto_terminado.py` (hereda el escenario)

**Interfaces:**
- Produces: `inventario.dominio.prefijo_numero_despacho(fecha: date) -> str`, `generar_numero_despacho(fecha: date, correlativo: int) -> str`, `correlativo_de_numero(numero: str, prefijo: str) -> int | None`; `Despacho.asignar_numero()` (guarda el despacho con el siguiente número libre); `Despacho._siguiente_correlativo(prefijo) -> int`; `inventario.pruebas_base.EscenarioProductoTerminado` (TestCase con `empresa`, `planta`, `usuario`, `producto`, `lote`, `pallet`, `ubicacion`, `cliente`, `api`, `liberar()`, `dar_permiso(codename, usuario=None)`, `crear_pallet(codigo)`).

- [ ] **Step 1: Extraer el escenario compartido**

Crea `backend/inventario/pruebas_base.py` moviendo **tal cual** el `setUp` y `liberar()` de `FlujoProductoTerminadoTests` (`tests_producto_terminado.py:26-61`), y agrega dos ayudantes:

```python
"""
Escenario compartido de las pruebas de producto terminado y despacho.

Vive aparte para que las pruebas de despacho no copien el mismo `setUp` de
treinta líneas: dos copias divergen, y lo primero que divergen son los estados
del pallet —que es justo lo que esas pruebas miden—.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import Liberacion
from maestros.models import Equipo, Mandante, Producto
from produccion.models import Lote, PalletProducto, RegistroEnvase
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Bodega, ClienteDespacho, Ubicacion


class EscenarioProductoTerminado(TestCase):
    def setUp(self):
        # ← aquí va, sin cambios, el cuerpo del setUp de FlujoProductoTerminadoTests
        # (empresa PT-1, planta PT, usuario bodega-pt, producto, lote L-PT,
        #  equipo ENV-PT, envase, pallet PAL-PT, bodega BPT, ubicación A-01,
        #  cliente CLI, APIClient autenticado).
        # Guarda además el envase en self.envase para crear_pallet().
        ...

    def liberar(self):
        # ← cuerpo actual de liberar(), sin cambios
        ...

    def dar_permiso(self, codename, usuario=None):
        (usuario or self.usuario).user_permissions.add(
            Permission.objects.get(codename=codename)
        )

    def crear_pallet(self, codigo, *, estado=PalletProducto.Estado.LIBERADO):
        """Otro pallet del mismo lote, ya liberado salvo que se pida otro estado."""
        return PalletProducto.objects.create(
            envase=self.envase, codigo=codigo, unidades=20, kg_neto=500, estado=estado,
        )
```

Los `...` son el código que mueves, no código nuevo: copia literal. En el `setUp`, cambia la variable local `envase = RegistroEnvase.objects.create(...)` por `self.envase = ...` y usa `self.envase` al crear `self.pallet`. Quita de ese archivo los imports que no uses.

Luego, en `tests_producto_terminado.py`, cambia `class FlujoProductoTerminadoTests(TestCase):` por `class FlujoProductoTerminadoTests(EscenarioProductoTerminado):`, borra su `setUp` y su `liberar`, agrega `from .pruebas_base import EscenarioProductoTerminado` y elimina los imports que queden sin uso.

- [ ] **Step 2: Correr las pruebas existentes (deben seguir verdes)**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test inventario.tests_producto_terminado --noinput`
Expected: OK, mismo número de pruebas que antes.

- [ ] **Step 3: Escribir las pruebas que fallan**

`backend/inventario/tests_despacho_numero.py`:

```python
from datetime import date
from unittest import mock

from django.test import SimpleTestCase

from . import dominio
from .models import Despacho
from .pruebas_base import EscenarioProductoTerminado
from .servicios import ingresar_pallet

DIA = date(2026, 9, 24)  # día juliano 267


class DominioNumeroDespachoTests(SimpleTestCase):
    def test_prefijo_es_de_mas_ultimo_digito_del_anio_y_dia_juliano(self):
        self.assertEqual(dominio.prefijo_numero_despacho(DIA), "DE6267-")
        self.assertEqual(dominio.prefijo_numero_despacho(date(2026, 1, 5)), "DE6005-")

    def test_el_correlativo_va_siempre_con_dos_cifras_minimo(self):
        self.assertEqual(dominio.generar_numero_despacho(DIA, 1), "DE6267-01")
        self.assertEqual(dominio.generar_numero_despacho(DIA, 123), "DE6267-123")

    def test_correlativo_de_numero_ignora_lo_que_no_tiene_la_forma(self):
        self.assertEqual(dominio.correlativo_de_numero("DE6267-07", "DE6267-"), 7)
        self.assertIsNone(dominio.correlativo_de_numero("D-1", "DE6267-"))
        self.assertIsNone(dominio.correlativo_de_numero("DE6267-xx", "DE6267-"))
        self.assertIsNone(dominio.correlativo_de_numero("", "DE6267-"))


class NumeroDespachoApiTests(EscenarioProductoTerminado):
    def setUp(self):
        super().setUp()
        reloj = mock.patch("inventario.models.timezone.localdate", return_value=DIA)
        reloj.start()
        self.addCleanup(reloj.stop)
        self.dar_permiso("despacho_crear")
        self.liberar()
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)

    def crear(self, **extra):
        return self.api.post("/api/inventario/despachos/", {
            "cliente": self.cliente.pk, "pallet_ids": [self.pallet.pk], **extra,
        }, format="json")

    def previo(self, numero):
        return Despacho.objects.create(
            sucursal=self.planta, numero=numero, cliente=self.cliente, creado_por=self.usuario,
            estado=Despacho.Estado.CANCELADO,
        )

    def test_el_sistema_asigna_el_primer_numero_del_dia(self):
        respuesta = self.crear()
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["numero"], "DE6267-01")

    def test_el_correlativo_sigue_desde_el_maximo_existente(self):
        self.previo("DE6267-07")
        self.assertEqual(self.crear().data["numero"], "DE6267-08")

    def test_el_numero_que_manda_el_cliente_se_ignora(self):
        respuesta = self.crear(numero="MIO-1")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["numero"], "DE6267-01")

    def test_numeros_antiguos_sin_la_forma_no_rompen_el_calculo(self):
        self.previo("D-1")
        self.previo("DE6267-xx")
        self.assertEqual(self.crear().data["numero"], "DE6267-01")

    def test_una_colision_reintenta_con_el_siguiente(self):
        self.previo("DE6267-01")
        with mock.patch.object(Despacho, "_siguiente_correlativo", side_effect=[1, 2]):
            respuesta = self.crear()
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["numero"], "DE6267-02")
```

(`previo` crea despachos **cancelados** a propósito: así no chocan con la regla de la Task 2 cuando esta corra después.)

- [ ] **Step 4: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test inventario.tests_despacho_numero --noinput`
Expected: ERROR `ImportError: cannot import name 'dominio'` (o `AttributeError` por `prefijo_numero_despacho`).

- [ ] **Step 5: Dominio puro**

`backend/inventario/dominio.py`:

```python
"""Reglas puras de inventario: sin ORM, testeables sin base."""
from datetime import date


def prefijo_numero_despacho(fecha: date) -> str:
    """
    Lo que comparten todos los despachos de un día: `DE6267-`.

    DE + último dígito del año + día juliano con tres cifras, igual que el vale
    (`VE…`) y el lote (`CCAA…`): quien ya lee uno lee los tres.
    """
    return f"DE{fecha.year % 10}{fecha.timetuple().tm_yday:03d}-"


def generar_numero_despacho(fecha: date, correlativo: int) -> str:
    """
    El número de una hoja de carga: `DE6267-01`.

    El correlativo va siempre, desde `-01`. Función pura: arma el texto y
    **no garantiza unicidad**; la garantiza la base (`despacho_numero_sucursal`).
    """
    return f"{prefijo_numero_despacho(fecha)}{correlativo:02d}"


def correlativo_de_numero(numero: str, prefijo: str) -> int | None:
    """
    El correlativo de un número con ese prefijo, o `None` si no tiene esa forma.

    `None` y no una excepción: hay despachos con números tecleados antes de esta
    regla (`D-1`), y ninguno debe romper el cálculo del siguiente.
    """
    if not numero or not numero.startswith(prefijo):
        return None
    resto = numero[len(prefijo):]
    return int(resto) if resto.isdigit() else None
```

- [ ] **Step 6: Asignación en el modelo**

En `backend/inventario/models.py`: cambia `from django.db import models` por `from django.db import IntegrityError, models, transaction` y agrega `from . import dominio` junto a los demás imports locales (verifica que `from django.utils import timezone` ya está; lo está en la línea 8). Agrega, sobre `class Despacho`:

```python
INTENTOS_NUMERO_DESPACHO = 5
```

y dentro de `Despacho`, después de `delete()`:

```python
    def asignar_numero(self):
        """
        Guarda el despacho con el siguiente número libre del día.

        Nadie lo teclea: un número tecleado se repite o se salta, y el de la
        guía del SII es otro dato (`guia_despacho`). La unicidad la garantiza la
        base; si dos hojas calculan el mismo número, `despacho_numero_sucursal`
        rechaza a la segunda y se reintenta con el siguiente. Cada intento va en
        su propio savepoint: sin él, el `IntegrityError` deja inutilizable la
        transacción que está creando la hoja con sus detalles.
        """
        prefijo = dominio.prefijo_numero_despacho(timezone.localdate())

        for _ in range(INTENTOS_NUMERO_DESPACHO):
            self.numero = dominio.generar_numero_despacho(
                timezone.localdate(), self._siguiente_correlativo(prefijo)
            )
            try:
                with transaction.atomic():
                    self.save()
                return
            except IntegrityError:
                ocupado = type(self).objects.filter(
                    sucursal_id=self.sucursal_id, numero=self.numero
                ).exists()
                if not ocupado:
                    # No fue el número: otra restricción. No se enmascara.
                    self.numero = ""
                    raise

        self.numero = ""
        raise ValidationError("No se pudo asignar un número de despacho; vuelve a intentarlo.")

    def _siguiente_correlativo(self, prefijo):
        """El máximo correlativo con ese prefijo en la planta, más uno. Nunca reutiliza."""
        usados = type(self).objects.filter(
            sucursal_id=self.sucursal_id, numero__startswith=prefijo
        ).values_list("numero", flat=True)
        correlativos = (dominio.correlativo_de_numero(n, prefijo) for n in usados)
        return max((n for n in correlativos if n is not None), default=0) + 1
```

(`ValidationError` ya está importado en `models.py`: lo usa `Despacho.delete`.)

- [ ] **Step 7: El serializer deja de pedir el número**

En `DespachoSerializer` (`backend/inventario/serializers.py`):

- agrega `"numero"` al principio de `Meta.read_only_fields`;
- en `create()`, reemplaza `despacho = super().create(validated_data)` por:

```python
        despacho = Despacho(**validated_data)
        despacho.asignar_numero()
```

- [ ] **Step 8: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test inventario --noinput`
Expected: OK (incluye las 8 nuevas y las existentes de despacho).

- [ ] **Step 9: Commit**

```bash
git add backend/inventario/dominio.py backend/inventario/pruebas_base.py backend/inventario/tests_despacho_numero.py backend/inventario/models.py backend/inventario/serializers.py backend/inventario/tests_producto_terminado.py
git commit -m "feat(inventario): número de despacho automático DE+año+juliano"
```

---

### Task 2: Una hoja de carga activa por pallet, cancelar y hojas vigentes

**Files:**
- Create: `backend/inventario/tests_despacho_hoja.py`
- Create (generada): `backend/inventario/migrations/0030_despacho_cancelacion.py`
- Modify: `backend/inventario/models.py` (`Despacho`: tres campos)
- Modify: `backend/inventario/serializers.py` (`DespachoSerializer.validate`, `read_only_fields`; `DetalleDespachoSerializer`)
- Modify: `backend/inventario/servicios.py` (nuevo `cancelar_despacho`)
- Modify: `backend/inventario/views.py` (`DespachoViewSet`: `get_queryset`, acción `cancelar`, prefetch)
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `EscenarioProductoTerminado` (Task 1), `Despacho.asignar_numero()`.
- Produces: `POST /api/inventario/despachos/{id}/cancelar/` con `{"motivo": str}` → 200 con el despacho, 400 `{"detail": str}`, 403 sin permiso. `GET /api/inventario/despachos/?vigentes=1` → borradores, autorizados y despachados hoy. Campos nuevos del despacho: `motivo_cancelacion`, `cancelado_en`, `cancelado_por`. `detalles[].ubicacion_codigo` (str | null) y `detalles[].lote_codigo` correcto. `servicios.cancelar_despacho(despacho, usuario, motivo)`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`backend/inventario/tests_despacho_hoja.py`:

```python
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from usuarios.models import PerfilUsuario, Rol

from .models import Despacho
from .pruebas_base import EscenarioProductoTerminado
from .servicios import autorizar_despacho, ejecutar_despacho, ingresar_pallet


class HojaDeCargaTests(EscenarioProductoTerminado):
    def setUp(self):
        super().setUp()
        self.dar_permiso("despacho_crear")
        self.dar_permiso("despacho_autorizar")
        self.liberar()
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)

    def crear(self, pallets=None):
        return self.api.post("/api/inventario/despachos/", {
            "cliente": self.cliente.pk, "pallet_ids": pallets or [self.pallet.pk],
        }, format="json")

    def cancelar(self, despacho_id, motivo="Cliente reprogramó"):
        return self.api.post(
            f"/api/inventario/despachos/{despacho_id}/cancelar/", {"motivo": motivo}, format="json",
        )

    # ---- un pallet, una hoja activa

    def test_un_pallet_en_otra_hoja_en_borrador_se_rechaza_nombrandola(self):
        primera = self.crear()
        self.assertEqual(primera.status_code, 201, primera.data)
        segunda = self.crear()
        self.assertEqual(segunda.status_code, 400)
        self.assertIn("PAL-PT", str(segunda.data))
        self.assertIn(primera.data["numero"], str(segunda.data))

    def test_un_pallet_en_una_hoja_autorizada_tambien_se_rechaza(self):
        primera = self.crear()
        autorizar_despacho(Despacho.objects.get(pk=primera.data["id"]), self.usuario)
        self.assertEqual(self.crear().status_code, 400)

    def test_tras_cancelar_el_pallet_vuelve_a_poder_cargarse(self):
        primera = self.crear()
        self.assertEqual(self.cancelar(primera.data["id"]).status_code, 200)
        self.assertEqual(self.crear().status_code, 201)

    # ---- cancelar

    def test_cancelar_deja_motivo_quien_y_cuando(self):
        creado = self.crear().data
        respuesta = self.cancelar(creado["id"], "  Camión no llegó  ")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        despacho = Despacho.objects.get(pk=creado["id"])
        self.assertEqual(despacho.estado, Despacho.Estado.CANCELADO)
        self.assertEqual(despacho.motivo_cancelacion, "Camión no llegó")
        self.assertEqual(despacho.cancelado_por, self.usuario)
        self.assertIsNotNone(despacho.cancelado_en)

    def test_cancelar_sin_motivo_se_rechaza(self):
        creado = self.crear().data
        respuesta = self.cancelar(creado["id"], "   ")
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(Despacho.objects.get(pk=creado["id"]).estado, Despacho.Estado.BORRADOR)

    def test_un_despacho_despachado_no_se_cancela(self):
        despacho = Despacho.objects.get(pk=self.crear().data["id"])
        autorizar_despacho(despacho, self.usuario)
        ejecutar_despacho(despacho, self.usuario)
        respuesta = self.cancelar(despacho.pk)
        self.assertEqual(respuesta.status_code, 400)
        despacho.refresh_from_db()
        self.assertEqual(despacho.estado, Despacho.Estado.DESPACHADO)

    def test_cancelar_exige_el_permiso_de_autorizar(self):
        creado = self.crear().data
        solo_crea = User.objects.create_user("despacho-solo-crea")
        PerfilUsuario.objects.create(
            usuario=solo_crea, empresa=self.empresa, sucursal=self.planta,
            rol=Rol.OPERARIO, area=PerfilUsuario.Area.DESPACHO,
        )
        self.dar_permiso("despacho_crear", solo_crea)
        self.api.force_authenticate(solo_crea)
        self.assertEqual(self.cancelar(creado["id"]).status_code, 403)

    # ---- hojas vigentes y detalle legible

    def test_vigentes_trae_borradores_autorizados_y_despachados_hoy(self):
        borrador = self.crear().data
        otro = self.crear_pallet("PAL-PT-2")
        ingresar_pallet(otro, self.ubicacion, self.usuario)
        despachado = Despacho.objects.get(pk=self.crear([otro.pk]).data["id"])
        autorizar_despacho(despachado, self.usuario)
        ejecutar_despacho(despachado, self.usuario)
        ayer = Despacho.objects.create(
            sucursal=self.planta, numero="VIEJO-1", cliente=self.cliente,
            creado_por=self.usuario, estado=Despacho.Estado.DESPACHADO,
            despachado_en=timezone.now() - timedelta(days=2),
        )
        respuesta = self.api.get("/api/inventario/despachos/?vigentes=1")
        filas = respuesta.data["results"] if isinstance(respuesta.data, dict) else respuesta.data
        ids = {fila["id"] for fila in filas}
        self.assertIn(borrador["id"], ids)
        self.assertIn(despachado.pk, ids)
        self.assertNotIn(ayer.pk, ids)

    def test_el_detalle_dice_lote_y_ubicacion_del_pallet(self):
        detalle = self.crear().data["detalles"][0]
        self.assertEqual(detalle["lote_codigo"], "L-PT")
        self.assertEqual(detalle["ubicacion_codigo"], "A-01")
```

- [ ] **Step 2: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test inventario.tests_despacho_hoja --noinput`
Expected: FAIL/ERROR — la segunda hoja se crea con 201, `cancelar/` responde 404, `vigentes` no filtra, `lote_codigo` falta en el detalle (hoy su `source` apunta a `lote.codigo`, que no existe, y DRF omite el campo en silencio).

- [ ] **Step 3: Campos de cancelación y migración**

En `Despacho` (`models.py`), después de `despachado_en`:

```python
    motivo_cancelacion = models.TextField(blank=True)
    cancelado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="despachos_cancelados",
    )
    cancelado_en = models.DateTimeField(null=True, blank=True)
```

Run: `cd backend && ./.venv/Scripts/python.exe manage.py makemigrations inventario --name despacho_cancelacion`
Expected: crea `inventario/migrations/0030_despacho_cancelacion.py` con tres `AddField`.

- [ ] **Step 4: Servicio de cancelación**

En `backend/inventario/servicios.py`, junto a `autorizar_despacho`:

```python
@transaction.atomic
def cancelar_despacho(despacho, usuario, motivo):
    """
    Cancela una hoja de carga que todavía no salió.

    No se borra: `Despacho.delete` lo impide, y la hoja cancelada conserva quién
    la armó, quién la canceló y por qué. Sus pallets quedan libres para otra
    hoja por la regla de una hoja activa por pallet, sin tocar nada más.
    """
    from django.utils import timezone

    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError("Indica el motivo de la cancelación.")
    despacho = Despacho.objects.select_for_update().get(pk=despacho.pk)
    if despacho.estado not in (Despacho.Estado.BORRADOR, Despacho.Estado.AUTORIZADO):
        raise ValidationError(
            f"Un despacho {despacho.get_estado_display().lower()} no se puede cancelar."
        )
    despacho.estado = Despacho.Estado.CANCELADO
    despacho.motivo_cancelacion = motivo
    despacho.cancelado_por = usuario
    despacho.cancelado_en = timezone.now()
    despacho.save(update_fields=["estado", "motivo_cancelacion", "cancelado_por", "cancelado_en"])
    return despacho
```

(Verifica que `Despacho`, `ValidationError` y `transaction` ya están importados en `servicios.py`; `autorizar_despacho` usa los tres.)

- [ ] **Step 5: Serializer**

En `DespachoSerializer`:

- agrega `"motivo_cancelacion", "cancelado_por", "cancelado_en"` a `Meta.read_only_fields`;
- en `validate()`, antes de `return attrs`:

```python
        if pallets:
            ocupados = DetalleDespacho.objects.filter(
                pallet__in=pallets,
                despacho__estado__in=[Despacho.Estado.BORRADOR, Despacho.Estado.AUTORIZADO],
            ).select_related("pallet", "despacho").order_by("pallet__codigo")
            if ocupados:
                # Sin esto el segundo despacho recién fallaba al ejecutarse, con
                # el camión ya cargado.
                raise serializers.ValidationError({"pallet_ids": [
                    f"El pallet {d.pallet.codigo} ya está en el despacho {d.despacho.numero} "
                    f"({d.despacho.get_estado_display().lower()})."
                    for d in ocupados
                ]})
```

En `DetalleDespachoSerializer`: cambia el `source` de `lote_codigo` a `"pallet.envase.lote.codigo_lote"` y agrega:

```python
    ubicacion_codigo = serializers.SerializerMethodField()

    def get_ubicacion_codigo(self, detalle):
        existencia = getattr(detalle.pallet, "existencia_producto", None)
        return existencia.ubicacion.codigo if existencia and existencia.activo else None
```

Si `DetalleDespachoSerializer.Meta.fields` es una lista explícita, agrega `"ubicacion_codigo"`.

`getattr(..., None)` sobre un `OneToOne` inverso inexistente lanza `RelatedObjectDoesNotExist`, que hereda de `AttributeError`, así que `getattr` con valor por defecto sí lo atrapa.

- [ ] **Step 6: Vista**

En `DespachoViewSet`:

- agrega `"detalles__pallet__existencia_producto__ubicacion"` al `prefetch_related`;
- agrega:

```python
    def get_queryset(self):
        consulta = super().get_queryset()
        if self.request.query_params.get("vigentes") == "1":
            # Lo que el puesto de Despacho tiene que ver: lo que falta sacar y
            # lo que salió hoy. Sin el filtro, las hojas activas de hace una
            # semana quedarían fuera de la primera página.
            consulta = consulta.filter(
                Q(estado__in=[Despacho.Estado.BORRADOR, Despacho.Estado.AUTORIZADO])
                | Q(estado=Despacho.Estado.DESPACHADO, despachado_en__date=timezone.localdate())
            )
        return consulta

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        if not (request.user.is_superuser or request.user.has_perm("usuarios.despacho_autorizar")):
            raise PermissionDenied("No tienes permiso para cancelar despachos.")
        try:
            despacho = cancelar_despacho(self.get_object(), request.user, request.data.get("motivo", ""))
            return Response(self.get_serializer(despacho).data)
        except DjangoValidationError as error:
            return Response({"detail": error.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
```

y agrega `cancelar_despacho` al import desde `.servicios`.

- [ ] **Step 7: Migrar y verificar**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py migrate inventario`
Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test inventario --noinput`
Expected: OK.

- [ ] **Step 8: Documentar en `CLAUDE.md`**

En «Decisiones vigentes», después del bullet del código de lote, agrega:

```markdown
- **Número de despacho** (desde 2026-09-24): `DE` + último dígito del año + día juliano + `-` + correlativo del día (`DE6267-01`), asignado al crear la hoja con reintento ante colisión, como el vale. **Nadie lo teclea**: el serializer lo ignora si llega. La guía del SII es otro dato, opcional (`guia_despacho`).
- **Un pallet, una hoja de carga activa.** Un pallet que ya está en un despacho `borrador` o `autorizado` no entra en otro; el rechazo nombra la hoja que lo tiene. Antes el segundo despacho recién fallaba al ejecutarse, con el camión cargado. **Cancelar** (`despachos/{id}/cancelar/`, motivo obligatorio, permiso de autorizar) lo libera; un despacho nunca se borra.
```

- [ ] **Step 9: Commit**

```bash
git add backend/inventario/models.py backend/inventario/migrations/0030_despacho_cancelacion.py backend/inventario/serializers.py backend/inventario/servicios.py backend/inventario/views.py backend/inventario/tests_despacho_hoja.py CLAUDE.md
git commit -m "feat(inventario): un pallet en una sola hoja activa, cancelar despacho y hojas vigentes"
```

---

### Task 3: Búsqueda y filtros en existencias y movimientos

**Files:**
- Create: `backend/inventario/tests_filtros_inventario.py`
- Modify: `backend/inventario/views.py` (`FiltraConsultaMixin` nuevo; `ExistenciaViewSet`, `MovimientoViewSet`, `ExistenciaProductoTerminadoViewSet`, `MovimientoProductoTerminadoViewSet`)
- Modify: `backend/inventario/serializers.py` (`ExistenciaSerializer`, `MovimientoSerializer`, `ExistenciaProductoTerminadoSerializer`, `MovimientoProductoTerminadoSerializer`)

**Interfaces:**
- Consumes: `EscenarioProductoTerminado` (Task 1); regla de hoja activa (Task 2).
- Produces: `inventario/catalogos/` gana `estado_calidad`, `tipo_movimiento`, `tipo_movimiento_pallet`, `estado_pallet` (cada uno `[{valor, etiqueta}]`). Query params: `existencias/?q=&estado=<estado_calidad>&ubicacion=<id>&con_saldo=1`; `producto-terminado/?q=&estado=disponible|cuarentena|bloqueado&ubicacion=<id>&cargable=1`; `movimientos/?q=&estado=<tipo>&ubicacion=<id>&desde=AAAA-MM-DD&hasta=AAAA-MM-DD`; `movimientos-producto-terminado/?` mismos. Fecha inválida → 400. Campos nuevos: existencia `unidad`, `insumo_codigo`, `bodega_nombre` (una sola `ubicacion_tipo`); movimiento `tipo_etiqueta`, `unidad`, `usuario_nombre`; pallet `ubicacion_tipo`; movimiento de pallet `tipo_etiqueta`, `origen_codigo`, `destino_codigo`, `registrado_por_nombre`, `lote_codigo`, `kg_neto`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`backend/inventario/tests_filtros_inventario.py`:

```python
from datetime import timedelta

from django.utils import timezone

from usuarios.models import PerfilUsuario

from .models import Despacho, DetalleDespacho, Existencia, Insumo, LoteInventario, MovimientoInventario, Ubicacion
from .pruebas_base import EscenarioProductoTerminado
from .servicios import ingresar_pallet


def filas(respuesta):
    return respuesta.data["results"] if isinstance(respuesta.data, dict) else respuesta.data


class FiltrosInventarioTests(EscenarioProductoTerminado):
    def setUp(self):
        super().setUp()
        self.otra = Ubicacion.objects.create(bodega=self.ubicacion.bodega, codigo="B-02")
        self.saco = self.material("SACO-25", "Saco 25 kg")
        self.etiqueta = self.material("ETQ-1", "Etiqueta frontal")
        self.ingresar(self.saco, "PROV-SACO-1", self.ubicacion)
        self.ingresar(self.etiqueta, "PROV-ETQ-1", self.otra)

    def material(self, codigo, nombre):
        return Insumo.objects.create(
            empresa=self.empresa, codigo=codigo, nombre=nombre,
            categoria=Insumo.Categoria.EMPAQUE, area=PerfilUsuario.Area.BODEGA,
            unidad=Insumo.Unidad.UN, requiere_calidad=False,
        )

    def ingresar(self, insumo, codigo_lote, ubicacion):
        respuesta = self.api.post("/api/inventario/movimientos/ingresar-material/", {
            "insumo": insumo.pk, "codigo_lote": codigo_lote,
            "ubicacion": ubicacion.pk, "cantidad": "20",
        }, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def nombres(self, ruta):
        respuesta = self.api.get(ruta)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return [fila["insumo_nombre"] for fila in filas(respuesta)]

    # ---- existencias de material

    def test_q_busca_por_nombre_codigo_de_material_y_lote(self):
        self.assertEqual(self.nombres("/api/inventario/existencias/?q=saco"), ["Saco 25 kg"])
        self.assertEqual(self.nombres("/api/inventario/existencias/?q=ETQ-1"), ["Etiqueta frontal"])
        self.assertEqual(self.nombres("/api/inventario/existencias/?q=prov-saco"), ["Saco 25 kg"])

    def test_ubicacion_acota_las_existencias(self):
        self.assertEqual(
            self.nombres(f"/api/inventario/existencias/?ubicacion={self.otra.pk}"), ["Etiqueta frontal"]
        )

    def test_estado_filtra_por_estado_de_calidad_del_lote(self):
        estado = LoteInventario.objects.get(codigo="PROV-SACO-1").estado_calidad
        self.assertEqual(len(self.nombres(f"/api/inventario/existencias/?estado={estado}")), 2)
        self.assertEqual(self.nombres("/api/inventario/existencias/?estado=rechazado"), [])

    def test_con_saldo_esconde_las_existencias_en_cero(self):
        Existencia.objects.filter(lote__codigo="PROV-ETQ-1").update(cantidad_fisica=0)
        self.assertEqual(self.nombres("/api/inventario/existencias/?con_saldo=1"), ["Saco 25 kg"])

    def test_la_existencia_trae_su_unidad(self):
        fila = filas(self.api.get("/api/inventario/existencias/?q=saco"))[0]
        self.assertEqual(fila["unidad"], "un")
        self.assertEqual(fila["insumo_codigo"], "SACO-25")
        self.assertEqual(fila["bodega_nombre"], "Bodega PT")

    # ---- movimientos de material

    def test_movimientos_filtran_por_q_tipo_ubicacion_y_fechas(self):
        tipo = MovimientoInventario.objects.first().tipo
        hoy = timezone.localdate()
        base = "/api/inventario/movimientos/"
        self.assertEqual(self.nombres(f"{base}?q=etiqueta"), ["Etiqueta frontal"])
        self.assertEqual(len(self.nombres(f"{base}?estado={tipo}")), 2)
        self.assertEqual(self.nombres(f"{base}?ubicacion={self.otra.pk}"), ["Etiqueta frontal"])
        self.assertEqual(len(self.nombres(f"{base}?desde={hoy}")), 2)
        self.assertEqual(self.nombres(f"{base}?hasta={hoy - timedelta(days=1)}"), [])

    def test_una_fecha_mal_escrita_es_un_400(self):
        respuesta = self.api.get("/api/inventario/movimientos/?desde=24-09-2026")
        self.assertEqual(respuesta.status_code, 400)

    def test_el_movimiento_se_lee_sin_traducir(self):
        fila = filas(self.api.get("/api/inventario/movimientos/?q=saco"))[0]
        self.assertTrue(fila["tipo_etiqueta"])
        self.assertNotEqual(fila["tipo_etiqueta"], fila["tipo"])
        self.assertEqual(fila["unidad"], "un")
        self.assertEqual(fila["usuario_nombre"], "bodega-pt")

    # ---- producto terminado

    def codigos(self, ruta):
        respuesta = self.api.get(ruta)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return sorted(fila["pallet_codigo"] for fila in filas(respuesta))

    def test_pallets_por_q_estado_y_cargable(self):
        self.liberar()
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)
        otro = self.crear_pallet("PAL-PT-2")
        ingresar_pallet(otro, self.ubicacion, self.usuario)
        despacho = Despacho.objects.create(
            sucursal=self.planta, numero="D-X", cliente=self.cliente, creado_por=self.usuario,
        )
        DetalleDespacho.objects.create(despacho=despacho, pallet=otro)
        base = "/api/inventario/producto-terminado/"
        self.assertEqual(self.codigos(f"{base}?q=pt-2"), ["PAL-PT-2"])
        self.assertEqual(self.codigos(f"{base}?estado=disponible"), ["PAL-PT", "PAL-PT-2"])
        self.assertEqual(self.codigos(f"{base}?estado=bloqueado"), [])
        self.assertEqual(self.codigos(f"{base}?cargable=1"), ["PAL-PT"])
        fila = filas(self.api.get(f"{base}?q=PAL-PT-2"))[0]
        self.assertEqual(fila["ubicacion_tipo"], "disponible")

    def test_movimientos_de_pallet_filtran_y_se_leen(self):
        self.liberar()
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)
        respuesta = self.api.get("/api/inventario/movimientos-producto-terminado/?q=PAL-PT&estado=ingreso")
        fila = filas(respuesta)[0]
        self.assertEqual(fila["pallet_codigo"], "PAL-PT")
        self.assertEqual(fila["lote_codigo"], "L-PT")
        self.assertEqual(fila["destino_codigo"], "A-01")
        self.assertEqual(fila["registrado_por_nombre"], "bodega-pt")
        self.assertTrue(fila["tipo_etiqueta"])
        self.assertEqual(
            filas(self.api.get("/api/inventario/movimientos-producto-terminado/?estado=despacho")), []
        )
```

- [ ] **Step 2: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test inventario.tests_filtros_inventario --noinput`
Expected: FAIL — los filtros se ignoran (devuelven todo) y faltan los campos nuevos.

- [ ] **Step 3: El mixin**

En `backend/inventario/views.py`, junto a `FiltraPorLoteMixin`, agrega (y `from django.utils.dateparse import parse_date` a los imports):

```python
class FiltraConsultaMixin:
    """
    `?q=`, `?estado=`, `?ubicacion=`, `?desde=`, `?hasta=` sobre un listado.

    En el servidor y no en el cliente: los listados están paginados, así que
    filtrar lo que llegó es filtrar la primera página y dar por inexistente lo
    que venía en la segunda. Cada vista declara **sobre qué campos** actúa cada
    filtro; un filtro que la vista no declara se ignora.
    """

    busqueda_en: tuple[str, ...] = ()
    filtro_estado: str | None = None
    filtro_ubicacion: tuple[str, ...] = ()
    filtro_fecha: str | None = None

    def condicion_estado(self, estado):
        return Q(**{self.filtro_estado: estado})

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        texto = parametros.get("q", "").strip()
        if texto and self.busqueda_en:
            condicion = Q()
            for campo in self.busqueda_en:
                condicion |= Q(**{f"{campo}__icontains": texto})
            consulta = consulta.filter(condicion)

        estado = parametros.get("estado", "").strip()
        if estado and self.filtro_estado:
            consulta = consulta.filter(self.condicion_estado(estado))

        ubicacion = parametros.get("ubicacion", "").strip()
        if ubicacion and self.filtro_ubicacion:
            if not ubicacion.isdigit():
                raise ValidationError({"ubicacion": "Debe ser el identificador de una ubicación."})
            condicion = Q()
            for campo in self.filtro_ubicacion:
                condicion |= Q(**{campo: int(ubicacion)})
            consulta = consulta.filter(condicion)

        for nombre, comparacion in (("desde", "gte"), ("hasta", "lte")):
            valor = parametros.get(nombre, "").strip()
            if valor and self.filtro_fecha:
                fecha = parse_date(valor)
                if fecha is None:
                    raise ValidationError({nombre: "Usa el formato AAAA-MM-DD."})
                consulta = consulta.filter(**{f"{self.filtro_fecha}__date__{comparacion}": fecha})

        return consulta
```

(`ValidationError` en `views.py` es el de DRF — ya importado — y responde 400.)

- [ ] **Step 4: Declarar los filtros en cada vista**

```python
class ExistenciaViewSet(FiltraConsultaMixin, FiltraPorLoteMixin, QuerysetTenantMixin, viewsets.ReadOnlyModelViewSet):
    # … lo que ya tiene …
    busqueda_en = ("lote__codigo", "lote__insumo__nombre", "lote__insumo__codigo", "ubicacion__codigo")
    filtro_estado = "lote__estado_calidad"
    filtro_ubicacion = ("ubicacion_id",)

    def get_queryset(self):
        consulta = super().get_queryset()
        if self.request.query_params.get("con_saldo") == "1":
            consulta = consulta.filter(cantidad_fisica__gt=0)
        return consulta


class MovimientoViewSet(FiltraConsultaMixin, FiltraPorLoteMixin, QuerysetTenantMixin, viewsets.ReadOnlyModelViewSet):
    # … lo que ya tiene …
    busqueda_en = ("lote__codigo", "lote__insumo__nombre", "lote__insumo__codigo")
    filtro_estado = "tipo"
    filtro_ubicacion = ("origen_id", "destino_id")
    filtro_fecha = "fecha"
```

Para `ExistenciaProductoTerminadoViewSet` (agrega `FiltraConsultaMixin` primero en las bases):

```python
    busqueda_en = (
        "pallet__codigo", "pallet__envase__lote__codigo_lote",
        "pallet__envase__lote__producto__nombre", "ubicacion__codigo",
    )
    filtro_estado = "pallet__estado"
    filtro_ubicacion = ("ubicacion_id",)

    def condicion_estado(self, estado):
        # El estado que ve Bodega (`estado_inventario` del serializer) agrupa
        # estados del pallet; se filtra con la misma tabla que sirve el catálogo.
        grupos = {valor: estados for valor, _, estados in estados_inventario_pallet()}
        return Q(pallet__estado__in=grupos.get(estado, [estado]))

    def get_queryset(self):
        consulta = super().get_queryset()
        if self.request.query_params.get("cargable") == "1":
            from produccion.models import PalletProducto
            # Lo que se puede subir a una hoja de carga: liberado, en una
            # ubicación disponible y sin otra hoja activa (Task 2).
            consulta = consulta.filter(
                ubicacion__tipo=Ubicacion.Tipo.DISPONIBLE,
                pallet__estado__in=[PalletProducto.Estado.LIBERADO, PalletProducto.Estado.EN_INVENTARIO],
            ).exclude(
                pallet__detalles_despacho__despacho__estado__in=[
                    Despacho.Estado.BORRADOR, Despacho.Estado.AUTORIZADO,
                ]
            )
        return consulta
```

Para `MovimientoProductoTerminadoViewSet` (agrega `FiltraConsultaMixin` primero en las bases):

```python
    queryset = MovimientoProductoTerminado.objects.select_related(
        "pallet__envase__lote", "origen", "destino", "despacho", "registrado_por",
    )
    busqueda_en = ("pallet__codigo", "pallet__envase__lote__codigo_lote")
    filtro_estado = "tipo"
    filtro_ubicacion = ("origen_id", "destino_id")
    filtro_fecha = "registrado_en"
```

Y, a nivel de módulo en `views.py` (junto a `FiltraConsultaMixin`):

```python
def estados_inventario_pallet():
    """
    Los estados de un pallet tal como los ve Bodega: (valor, etiqueta, estados del pallet).

    Una sola tabla para el filtro y para el catálogo del desplegable; con dos,
    el desplegable ofrecería un estado que el filtro no entiende.
    """
    from produccion.models import PalletProducto
    return [
        ("disponible", "Disponible", [PalletProducto.Estado.LIBERADO, PalletProducto.Estado.EN_INVENTARIO]),
        ("cuarentena", "Cuarentena", [PalletProducto.Estado.PENDIENTE_CALIDAD]),
        ("bloqueado", "Bloqueado", [PalletProducto.Estado.BLOQUEADO]),
    ]
```

- [ ] **Step 4b: Catálogo de los filtros**

Los desplegables de estado de la consulta **no se escriben en el frontend** (regla de `CLAUDE.md`: los catálogos se sirven desde el backend). En la función `catalogos` de `views.py` (~línea 1291, la que responde `inventario/catalogos/`), agrega al diccionario de la respuesta:

```python
            "estado_calidad": opciones(LoteInventario.EstadoCalidad.choices),
            "tipo_movimiento": opciones(MovimientoInventario.Tipo.choices),
            "tipo_movimiento_pallet": opciones(MovimientoProductoTerminado.Tipo.choices),
            "estado_pallet": [{"valor": v, "etiqueta": e} for v, e, _ in estados_inventario_pallet()],
```

y agrega esta prueba a `FiltrosInventarioTests`:

```python
    def test_el_catalogo_sirve_los_estados_que_entienden_los_filtros(self):
        datos = self.api.get("/api/inventario/catalogos/").data
        self.assertIn({"valor": "aprobado", "etiqueta": "Aprobado"}, datos["estado_calidad"])
        self.assertIn("ingreso", [o["valor"] for o in datos["tipo_movimiento_pallet"]])
        self.assertEqual([o["valor"] for o in datos["estado_pallet"]], ["disponible", "cuarentena", "bloqueado"])
        self.assertTrue(datos["tipo_movimiento"])
```

- [ ] **Step 5: Serializers legibles**

En `ExistenciaSerializer`: borra las **dos** líneas `ubicacion_tipo` repetidas (queda una) y agrega:

```python
    insumo_codigo = serializers.CharField(source="lote.insumo.codigo", read_only=True)
    unidad = serializers.CharField(source="lote.insumo.unidad", read_only=True)
    bodega_nombre = serializers.CharField(source="ubicacion.bodega.nombre", read_only=True)
```

En `MovimientoSerializer`:

```python
    tipo_etiqueta = serializers.CharField(source="get_tipo_display", read_only=True)
    unidad = serializers.CharField(source="lote.insumo.unidad", read_only=True)
    usuario_nombre = serializers.SerializerMethodField()

    def get_usuario_nombre(self, movimiento):
        usuario = movimiento.usuario
        return usuario.get_full_name() or usuario.username
```

En `ExistenciaProductoTerminadoSerializer`:

```python
    ubicacion_tipo = serializers.CharField(source="ubicacion.tipo", read_only=True)
```

En `MovimientoProductoTerminadoSerializer`:

```python
    tipo_etiqueta = serializers.CharField(source="get_tipo_display", read_only=True)
    origen_codigo = serializers.CharField(source="origen.codigo", read_only=True, allow_null=True, default=None)
    destino_codigo = serializers.CharField(source="destino.codigo", read_only=True, allow_null=True, default=None)
    lote_codigo = serializers.CharField(source="pallet.envase.lote.codigo_lote", read_only=True)
    kg_neto = serializers.DecimalField(source="pallet.kg_neto", max_digits=14, decimal_places=3, read_only=True)
    registrado_por_nombre = serializers.SerializerMethodField()

    def get_registrado_por_nombre(self, movimiento):
        usuario = movimiento.registrado_por
        return usuario.get_full_name() or usuario.username
```

Si DRF rechaza `default` junto a `read_only` en tu versión, quita `default=None` y deja `allow_null=True` (como en `MovimientoSerializer.origen_codigo`); la prueba dice si el campo sale.

- [ ] **Step 6: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test inventario --noinput`
Expected: OK.

- [ ] **Step 7: Commit**

```bash
git add backend/inventario/views.py backend/inventario/serializers.py backend/inventario/tests_filtros_inventario.py
git commit -m "feat(inventario): búsqueda y filtros en existencias y movimientos"
```

---

### Task 4: Pendientes de bodega

**Files:**
- Create: `backend/inventario/tests_pendientes_bodega.py`
- Modify: `backend/inventario/views.py` (extraer `_resumen_materiales`; nueva vista `pendientes_bodega`)
- Modify: `backend/inventario/urls.py`

**Interfaces:**
- Consumes: `EscenarioProductoTerminado`.
- Produces: `GET /api/inventario/pendientes-bodega/` →

```json
{
  "pallets_por_ubicar": [{"existencia_id": 1, "pallet_id": 2, "pallet_codigo": "PAL-PT", "lote_codigo": "L-PT", "producto_nombre": "Polvo PT", "kg_neto": "500.000", "ubicacion_codigo": "PT-CUAR"}],
  "material_en_cuarentena": [{"existencia_id": 3, "lote_codigo": "PROV-1", "insumo_nombre": "Saco", "cantidad": "20.000", "unidad": "un", "ubicacion_codigo": "Q-01"}],
  "bajo_minimo": [{"insumo_id": 4, "codigo": "SACO", "nombre": "Saco", "unidad": "un", "disponible": "5.000", "stock_minimo": "10.000"}],
  "ajustes_pendientes": [{"id": 5, "existencia_id": 3, "insumo_nombre": "Saco", "lote_codigo": "PROV-1", "ubicacion_codigo": "A-01", "tipo": "negativo", "tipo_etiqueta": "Ajuste negativo", "cantidad": "2.000", "unidad": "un", "motivo": "Conteo", "solicitante_id": 7, "solicitante_nombre": "bodega-pt", "creado_en": "…"}],
  "total": 4
}
```

- [ ] **Step 1: Escribir las pruebas que fallan**

`backend/inventario/tests_pendientes_bodega.py`:

```python
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone

from maestros.models import Equipo, Mandante, Producto
from produccion.models import Lote, PalletProducto, RegistroEnvase
from usuarios.models import Empresa, PerfilUsuario, Sucursal

from .models import Bodega, Existencia, ExistenciaProductoTerminado, Insumo, Ubicacion
from .pruebas_base import EscenarioProductoTerminado
from .servicios import crear_ajuste


class PendientesBodegaTests(EscenarioProductoTerminado):
    def setUp(self):
        super().setUp()
        self.cuarentena = Ubicacion.objects.create(
            bodega=self.ubicacion.bodega, codigo="PT-CUAR", tipo=Ubicacion.Tipo.CUARENTENA,
        )

    def pendientes(self):
        respuesta = self.api.get("/api/inventario/pendientes-bodega/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return respuesta.data

    def material(self, codigo, *, requiere_calidad=False, stock_minimo=Decimal("0")):
        return Insumo.objects.create(
            empresa=self.empresa, codigo=codigo, nombre=f"Material {codigo}",
            categoria=Insumo.Categoria.EMPAQUE, area=PerfilUsuario.Area.BODEGA,
            unidad=Insumo.Unidad.UN, requiere_calidad=requiere_calidad, stock_minimo=stock_minimo,
        )

    def ingresar(self, insumo, lote, ubicacion, cantidad="20"):
        respuesta = self.api.post("/api/inventario/movimientos/ingresar-material/", {
            "insumo": insumo.pk, "codigo_lote": lote, "ubicacion": ubicacion.pk, "cantidad": cantidad,
        }, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def test_pallet_liberado_en_cuarentena_espera_ubicacion(self):
        ExistenciaProductoTerminado.objects.create(pallet=self.pallet, ubicacion=self.cuarentena)
        self.assertEqual(self.pendientes()["pallets_por_ubicar"], [])  # aún sin liberar
        self.liberar()
        fila = self.pendientes()["pallets_por_ubicar"][0]
        self.assertEqual(fila["pallet_codigo"], "PAL-PT")
        self.assertEqual(fila["ubicacion_codigo"], "PT-CUAR")
        self.assertEqual(fila["lote_codigo"], "L-PT")

    def test_material_en_cuarentena_aparece_con_su_unidad(self):
        insumo = self.material("CAL-1", requiere_calidad=True)
        self.ingresar(insumo, "PROV-CAL-1", self.cuarentena)
        fila = self.pendientes()["material_en_cuarentena"][0]
        self.assertEqual(fila["lote_codigo"], "PROV-CAL-1")
        self.assertEqual(fila["unidad"], "un")
        self.assertEqual(Decimal(str(fila["cantidad"])), Decimal("20"))

    def test_bajo_minimo_cuando_el_disponible_no_alcanza(self):
        corto = self.material("CORTO", stock_minimo=Decimal("50"))
        holgado = self.material("HOLGADO", stock_minimo=Decimal("5"))
        sin_minimo = self.material("SIN-MIN")
        for insumo in (corto, holgado, sin_minimo):
            self.ingresar(insumo, f"L-{insumo.codigo}", self.ubicacion)
        codigos = [fila["codigo"] for fila in self.pendientes()["bajo_minimo"]]
        self.assertEqual(codigos, ["CORTO"])

    def test_ajuste_pendiente_trae_quien_lo_pidio(self):
        insumo = self.material("AJ-1")
        self.ingresar(insumo, "L-AJ-1", self.ubicacion)
        existencia = Existencia.objects.get(lote__codigo="L-AJ-1")
        crear_ajuste(existencia=existencia, tipo="negativo", cantidad="2", motivo="Conteo", solicitante=self.usuario)
        datos = self.pendientes()
        fila = datos["ajustes_pendientes"][0]
        self.assertEqual(fila["solicitante_id"], self.usuario.pk)
        self.assertEqual(fila["unidad"], "un")
        self.assertEqual(fila["existencia_id"], existencia.pk)
        self.assertEqual(datos["total"], 1)

    def test_no_muestra_lo_de_otra_empresa(self):
        otra = Empresa.objects.create(rut="PT-2", nombre="Otra")
        planta = Sucursal.objects.create(empresa=otra, codigo="PT2", nombre="Planta 2")
        mandante = Mandante.objects.create(empresa=otra, nombre="Mandante 2", codigo_cliente="p2")
        producto = Producto.objects.create(mandante=mandante, nombre="Polvo 2", unidad_base="kg")
        lote = Lote.objects.create(
            sucursal=planta, codigo_lote="L-OTRA", producto=producto, fecha=date(2026, 8, 17),
            estado=Lote.Estado.PRODUCIDO, kg_producidos=Decimal("500"),
        )
        equipo = Equipo.objects.create(sucursal=planta, codigo="ENV-2", nombre="Env 2", tipo=Equipo.Tipo.ENVASADORA)
        operador = User.objects.create_user("otra-empresa")
        envase = RegistroEnvase.objects.create(
            lote=lote, equipo=equipo, formato_kg=25, unidades=20, kg_envasados=500,
            operador=operador, inicio=timezone.now() - timedelta(hours=1), termino=timezone.now(),
        )
        pallet = PalletProducto.objects.create(
            envase=envase, codigo="PAL-OTRA", unidades=20, kg_neto=500, estado=PalletProducto.Estado.LIBERADO,
        )
        bodega = Bodega.objects.create(sucursal=planta, codigo="B2", nombre="Bodega 2")
        cuarentena = Ubicacion.objects.create(bodega=bodega, codigo="Q-2", tipo=Ubicacion.Tipo.CUARENTENA)
        ExistenciaProductoTerminado.objects.create(pallet=pallet, ubicacion=cuarentena)
        codigos = [fila["pallet_codigo"] for fila in self.pendientes()["pallets_por_ubicar"]]
        self.assertNotIn("PAL-OTRA", codigos)
```

Si el `ingresar-material` a una ubicación de cuarentena con `requiere_calidad=True` responde distinto de 201, lee el motivo en `respuesta.data` y ajusta **el escenario** (no la aserción): la regla es de `registrar_entrada`, no de este endpoint.

- [ ] **Step 2: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test inventario.tests_pendientes_bodega --noinput`
Expected: FAIL con 404 en `/api/inventario/pendientes-bodega/`.

- [ ] **Step 3: Extraer el resumen de materiales**

En `views.py`, mueve el bloque de `estado_operacional` que va desde `existencias_material = filtrar_por_scope(` hasta el final de la comprensión `materiales = [...]` a una función de módulo, **sin cambiar lo que calcula**:

```python
def _resumen_materiales(usuario):
    """Stock de material agrupado por insumo: físico, disponible, cuarentena, bloqueado."""
    decimal = DecimalField(max_digits=18, decimal_places=3)
    # ← el bloque movido, con request.user → usuario
    return materiales
```

y en `estado_operacional` deja `materiales = _resumen_materiales(request.user)`. Corre `inventario.tests_producto_terminado` para confirmar que el resumen sigue igual.

- [ ] **Step 4: La vista**

```python
@api_view(["GET"])
@permission_classes([PuedeVerInventario])
def pendientes_bodega(request):
    """
    Lo que Bodega tiene que resolver, cada cosa con lo necesario para actuar.

    Es la portada del puesto: el operador no busca qué hacer entre tablas de
    stock, lo ve. Material en cuarentena y bajo mínimo son informativos —los
    decide Calidad y Compras—; pallets por ubicar y ajustes tienen acción.
    """
    from produccion.models import PalletProducto

    alcance = {
        "campo_sucursal": "ubicacion__bodega__sucursal_id",
        "campo_empresa": "ubicacion__bodega__sucursal__empresa_id",
    }
    pallets = filtrar_por_scope(
        ExistenciaProductoTerminado.objects.filter(
            activo=True, ubicacion__tipo=Ubicacion.Tipo.CUARENTENA,
            pallet__estado=PalletProducto.Estado.LIBERADO,
        ).select_related("pallet__envase__lote__producto", "ubicacion").order_by("pallet__codigo"),
        request.user, **alcance,
    )
    cuarentena = filtrar_por_scope(
        Existencia.objects.filter(
            cantidad_fisica__gt=0, ubicacion__tipo=Ubicacion.Tipo.CUARENTENA,
        ).select_related("lote__insumo", "ubicacion").order_by("lote__insumo__nombre", "lote__codigo"),
        request.user, **alcance,
    )
    ajustes = filtrar_por_scope(
        AjusteInventario.objects.filter(estado=AjusteInventario.Estado.PENDIENTE).select_related(
            "existencia__lote__insumo", "existencia__ubicacion", "solicitante",
        ).order_by("creado_en"),
        request.user,
        campo_sucursal="existencia__ubicacion__bodega__sucursal_id",
        campo_empresa="existencia__ubicacion__bodega__sucursal__empresa_id",
    )

    respuesta = {
        "pallets_por_ubicar": [{
            "existencia_id": e.pk, "pallet_id": e.pallet_id, "pallet_codigo": e.pallet.codigo,
            "lote_codigo": e.pallet.envase.lote.codigo_lote,
            "producto_nombre": e.pallet.envase.lote.producto.nombre,
            "kg_neto": e.pallet.kg_neto, "ubicacion_codigo": e.ubicacion.codigo,
        } for e in pallets],
        "material_en_cuarentena": [{
            "existencia_id": e.pk, "lote_codigo": e.lote.codigo, "insumo_nombre": e.lote.insumo.nombre,
            "cantidad": e.cantidad_fisica, "unidad": e.lote.insumo.unidad,
            "ubicacion_codigo": e.ubicacion.codigo,
        } for e in cuarentena],
        "bajo_minimo": [{
            "insumo_id": m["insumo_id"], "codigo": m["codigo"], "nombre": m["nombre"],
            "unidad": m["unidad"], "disponible": m["disponible"], "stock_minimo": m["stock_minimo"],
        } for m in _resumen_materiales(request.user)
            if m["stock_minimo"] > 0 and m["disponible"] <= m["stock_minimo"]],
        "ajustes_pendientes": [{
            "id": a.pk, "existencia_id": a.existencia_id,
            "insumo_nombre": a.existencia.lote.insumo.nombre,
            "lote_codigo": a.existencia.lote.codigo, "ubicacion_codigo": a.existencia.ubicacion.codigo,
            "tipo": a.tipo, "tipo_etiqueta": a.get_tipo_display(), "cantidad": a.cantidad,
            "unidad": a.existencia.lote.insumo.unidad, "motivo": a.motivo,
            "solicitante_id": a.solicitante_id,
            "solicitante_nombre": a.solicitante.get_full_name() or a.solicitante.username,
            "creado_en": a.creado_en,
        } for a in ajustes],
    }
    respuesta["total"] = sum(len(v) for v in respuesta.values())
    return Response(respuesta)
```

`_resumen_materiales` solo cuenta insumos **con alguna existencia**; un material sin ninguna existencia no aparece bajo mínimo. Es una limitación consciente: el resumen actual tiene la misma. Déjalo anotado en el docstring de la vista.

En `urls.py`, junto a `path("estado-operacional/", estado_operacional)`: `path("pendientes-bodega/", pendientes_bodega),` y agrega `pendientes_bodega` al import.

- [ ] **Step 5: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test inventario --noinput`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add backend/inventario/views.py backend/inventario/urls.py backend/inventario/tests_pendientes_bodega.py
git commit -m "feat(inventario): pendientes de bodega en un solo endpoint"
```

---

### Task 5: Bases compartidas del frontend

**Files:**
- Create: `frontend/src/services/formato.ts`, `frontend/tests/formato.test.ts`
- Create: `frontend/src/services/paginacion.ts`, `frontend/tests/paginacion.test.ts`
- Create: `frontend/src/services/permisos-despacho.ts`, `frontend/tests/permisos-despacho.test.ts`
- Create: `frontend/src/components/operacion/ConfirmarAccion.tsx`, `CampoEtiquetado.tsx`, `BuscadorCodigo.tsx`
- Modify: `frontend/src/services/inventario.service.ts` (`lista()`, líneas 296-299; nueva `pagina()`)

**Interfaces:**
- Produces:
  - `cantidad(valor: string | number | null | undefined, unidad?: string): string`
  - `interface Pagina<T> { count: number; next: string | null; previous: string | null; results: T[] }`, `type RespuestaLista<T> = T[] | Pagina<T>`, `type Filtros = Record<string, string | number | boolean | null | undefined>`, `rutaDePagina(ruta, siguiente): string`, `recorrerPaginas<T>(pedir, ruta, maximo?): Promise<T[]>`, `conFiltros(ruta, filtros): string`
  - `puedeDespachar(usuario): boolean`, `puedeAutorizarDespacho(usuario): boolean` (reciben `Pick<Usuario, "capacidades"> | null | undefined`)
  - `<ConfirmarAccion titulo filas advertencia? textoConfirmar peligro? ocupado? error? onConfirmar onVolver />`, `interface FilaResumen { etiqueta: string; valor: string }`
  - `<CampoEtiquetado etiqueta ayuda?>{control}</CampoEtiquetado>`
  - `<BuscadorCodigo etiqueta ayuda? ocupado? onBuscar={(texto) => void} />`
  - En `inventario.service.ts`: `pagina<T>(ruta: string, filtros: Filtros): Promise<Pagina<T>>` exportada.

- [ ] **Step 1: Pruebas que fallan**

`frontend/tests/formato.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

import { cantidad } from "../src/services/formato.ts";

test("trece unidades se leen trece, no trece mil", () => {
  assert.equal(cantidad("13.000", "un"), "13 un");
});

test("miles con punto y decimales con coma, como en Chile", () => {
  assert.equal(cantidad("1234.5", "kg"), "1.234,5 kg");
  assert.equal(cantidad(25000, "L"), "25.000 L");
  assert.equal(cantidad("0.125"), "0,125");
});

test("hasta tres decimales, que es lo que guarda el modelo", () => {
  assert.equal(cantidad("2.34567", "kg"), "2,346 kg");
});

test("lo que no es un número se muestra como raya", () => {
  assert.equal(cantidad(null, "kg"), "—");
  assert.equal(cantidad(undefined), "—");
  assert.equal(cantidad("", "un"), "—");
  assert.equal(cantidad("abc", "un"), "—");
});
```

`frontend/tests/paginacion.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

import { conFiltros, recorrerPaginas, rutaDePagina, type RespuestaLista } from "../src/services/paginacion.ts";

test("la página siguiente se pide por la ruta relativa, no por la URL absoluta del backend", () => {
  assert.equal(
    rutaDePagina("inventario/movimientos/?q=saco", "http://127.0.0.1:8000/api/inventario/movimientos/?page=3&q=saco"),
    "inventario/movimientos/?q=saco&page=3",
  );
  assert.equal(rutaDePagina("inventario/ajustes/", "/api/inventario/ajustes/?page=2"), "inventario/ajustes/?page=2");
});

test("recorre todas las páginas y junta las filas", async () => {
  const pedidas: string[] = [];
  const paginas: Record<string, RespuestaLista<number>> = {
    "x/": { count: 3, next: "http://b/api/x/?page=2", previous: null, results: [1, 2] },
    "x/?page=2": { count: 3, next: null, previous: "http://b/api/x/", results: [3] },
  };
  const filas = await recorrerPaginas<number>(async (ruta) => { pedidas.push(ruta); return paginas[ruta]; }, "x/");
  assert.deepEqual(filas, [1, 2, 3]);
  assert.deepEqual(pedidas, ["x/", "x/?page=2"]);
});

test("una respuesta sin paginar se devuelve tal cual", async () => {
  assert.deepEqual(await recorrerPaginas<number>(async () => [7, 8], "y/"), [7, 8]);
});

test("una lista sin fin avisa en vez de colgar la pantalla", async () => {
  const infinita = async (): Promise<RespuestaLista<number>> =>
    ({ count: 999, next: "http://b/api/z/?page=2", previous: null, results: [1] });
  await assert.rejects(recorrerPaginas(infinita, "z/", 2), /más de 2 páginas/);
});

test("los filtros vacíos no viajan y los booleanos van como 1", () => {
  assert.equal(
    conFiltros("inventario/producto-terminado/", { q: "pal", estado: "", ubicacion: null, cargable: true, con_saldo: false, page: 2 }),
    "inventario/producto-terminado/?q=pal&cargable=1&page=2",
  );
  assert.equal(conFiltros("inventario/despachos/?vigentes=1", { q: "de6" }), "inventario/despachos/?vigentes=1&q=de6");
  assert.equal(conFiltros("a/", {}), "a/");
});
```

`frontend/tests/permisos-despacho.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

import { puedeAutorizarDespacho, puedeDespachar } from "../src/services/permisos-despacho.ts";

test("sin sesión no se despacha", () => {
  assert.equal(puedeDespachar(null), false);
  assert.equal(puedeAutorizarDespacho(undefined), false);
});

test("crear despachos no alcanza para autorizarlos", () => {
  const usuario = { capacidades: ["despacho_crear"] };
  assert.equal(puedeDespachar(usuario), true);
  assert.equal(puedeAutorizarDespacho(usuario), false);
});

test("quien autoriza también arma hojas, como decide el servidor", () => {
  const usuario = { capacidades: ["despacho_autorizar"] };
  assert.equal(puedeDespachar(usuario), true);
  assert.equal(puedeAutorizarDespacho(usuario), true);
});

test("el área o el rol no dan permiso: solo las capacidades", () => {
  assert.equal(puedeDespachar({ capacidades: [] }), false);
  assert.equal(puedeDespachar({ capacidades: ["inventario_transferir", "inventario_ajustar"] }), false);
});
```

- [ ] **Step 2: Verificar que fallan**

Run: `cd frontend && npm test`
Expected: FAIL — `Cannot find module '../src/services/formato.ts'` (y los otros dos).

- [ ] **Step 3: Implementar los tres servicios**

`frontend/src/services/formato.ts`:

```ts
/*
  Cantidades en pantalla.

  El backend manda decimales con tres cifras («13.000»), y en Chile el punto
  separa miles: sin formatear, trece unidades se leen trece mil. Toda cantidad
  del módulo pasa por aquí, con su unidad al lado.
*/
const NUMERO = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 3 });

export function cantidad(valor: string | number | null | undefined, unidad?: string): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const numero = Number(valor);
  if (!Number.isFinite(numero)) return "—";
  const texto = NUMERO.format(numero);
  return unidad ? `${texto} ${unidad}` : texto;
}
```

`frontend/src/services/paginacion.ts`:

```ts
/*
  Listas paginadas del backend (PageNumberPagination, 50 por página).

  `lista()` se quedaba con la primera página y la pantalla mostraba 50 filas
  como si fueran todas. Aquí se recorre `next` hasta el final —para conjuntos
  acotados, como ubicaciones o clientes— y se arma la ruta de una página con
  sus filtros —para las listas largas, que se paginan en el servidor—.
*/
export interface Pagina<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type RespuestaLista<T> = T[] | Pagina<T>;

export type Filtros = Record<string, string | number | boolean | null | undefined>;

export const MAXIMO_PAGINAS = 40;

/* `next` viene absoluto con el host del backend; pedirlo tal cual se saltaría
   el proxy de Vite. Se toma solo el número de página y se aplica a la ruta. */
export function rutaDePagina(ruta: string, siguiente: string): string {
  const pagina = new URL(siguiente, "http://relativa").searchParams.get("page");
  if (!pagina) throw new Error("La respuesta paginada no dice qué página sigue.");
  const [base, consulta = ""] = ruta.split("?");
  const parametros = new URLSearchParams(consulta);
  parametros.set("page", pagina);
  return `${base}?${parametros.toString()}`;
}

export async function recorrerPaginas<T>(
  pedir: (ruta: string) => Promise<RespuestaLista<T>>,
  ruta: string,
  maximo = MAXIMO_PAGINAS,
): Promise<T[]> {
  const filas: T[] = [];
  let actual: string | null = ruta;
  for (let vuelta = 0; actual !== null; vuelta += 1) {
    if (vuelta === maximo) {
      throw new Error(`La lista ${ruta} tiene más de ${maximo} páginas: búscala con filtros.`);
    }
    const datos: RespuestaLista<T> = await pedir(actual);
    if (Array.isArray(datos)) return filas.concat(datos);
    filas.push(...datos.results);
    actual = datos.next ? rutaDePagina(ruta, datos.next) : null;
  }
  return filas;
}

export function conFiltros(ruta: string, filtros: Filtros): string {
  const parametros = new URLSearchParams();
  for (const [clave, valor] of Object.entries(filtros)) {
    if (valor === undefined || valor === null || valor === "" || valor === false) continue;
    parametros.set(clave, valor === true ? "1" : String(valor));
  }
  const consulta = parametros.toString();
  if (!consulta) return ruta;
  return `${ruta}${ruta.includes("?") ? "&" : "?"}${consulta}`;
}
```

Nota: en `rutaDePagina`, si `ruta` ya trae `page`, `set` lo reemplaza; es lo que se quiere.

`frontend/src/services/permisos-despacho.ts`:

```ts
import type { Usuario } from "./sesion.ts";

/*
  Quién despacha. Refleja `PuedeCrearDespacho` y las acciones `autorizar`,
  `ejecutar` y `cancelar` de `inventario/views.py`, que miran **solo** permisos
  (`despacho_crear`, `despacho_autorizar`). La pantalla anterior decidía con el
  área y el rol, y ofrecía botones que el servidor rechazaba con 403.

  El superusuario queda cubierto: `capacidades_de()` le devuelve todas.
*/
type ConCapacidades = Pick<Usuario, "capacidades"> | null | undefined;

export function puedeAutorizarDespacho(usuario: ConCapacidades): boolean {
  return Boolean(usuario?.capacidades?.includes("despacho_autorizar"));
}

export function puedeDespachar(usuario: ConCapacidades): boolean {
  return Boolean(usuario?.capacidades?.includes("despacho_crear")) || puedeAutorizarDespacho(usuario);
}
```

- [ ] **Step 4: Verificar**

Run: `cd frontend && npm test`
Expected: PASS (las nuevas y las existentes).

- [ ] **Step 5: `lista()` recorre páginas; `pagina()` para listas largas**

En `inventario.service.ts`, agrega el import y reemplaza `lista`:

```ts
import { conFiltros, recorrerPaginas, type Filtros, type Pagina, type RespuestaLista } from "./paginacion";

/* Conjunto completo. Solo para listas acotadas: para las largas, `pagina()`. */
async function lista<T>(ruta: string): Promise<T[]> {
  return recorrerPaginas<T>(async (actual) => (await api.get<RespuestaLista<T>>(actual)).data, ruta);
}

/* Una página, con sus filtros aplicados en el servidor. */
export async function pagina<T>(ruta: string, filtros: Filtros = {}): Promise<Pagina<T>> {
  const { data } = await api.get<RespuestaLista<T>>(conFiltros(ruta, filtros));
  return Array.isArray(data) ? { count: data.length, next: null, previous: null, results: data } : data;
}
```

- [ ] **Step 6: Componentes**

`frontend/src/components/operacion/CampoEtiquetado.tsx`:

```tsx
import type { ReactNode } from "react";

/* Un campo con su etiqueta visible. Un `placeholder` no es una etiqueta:
   desaparece al escribir y el lector de pantalla no siempre lo anuncia. */
export default function CampoEtiquetado({ etiqueta, ayuda, children }: {
  etiqueta: string;
  ayuda?: string;
  children: ReactNode;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1.5 text-sm">
      <span className="font-medium text-slate-700">{etiqueta}</span>
      {children}
      {ayuda && <span className="text-xs text-slate-600">{ayuda}</span>}
    </label>
  );
}
```

`frontend/src/components/operacion/BuscadorCodigo.tsx`:

```tsx
import { useEffect, useRef, useState, type FormEvent } from "react";

import { claseBoton, claseCampo } from "../seccion/utilidades";

/*
  Campo de búsqueda por código con el foco puesto.

  Un lector de código de barras en modo teclado escribe el código y manda
  Enter: con el foco aquí, escanear ya es buscar. Después de cada búsqueda el
  texto queda seleccionado para que el siguiente escaneo lo reemplace.
*/
export default function BuscadorCodigo({ etiqueta, ayuda, ocupado = false, onBuscar }: {
  etiqueta: string;
  ayuda?: string;
  ocupado?: boolean;
  onBuscar: (texto: string) => void;
}) {
  const [texto, setTexto] = useState("");
  const campo = useRef<HTMLInputElement>(null);

  useEffect(() => {
    campo.current?.focus();
  }, []);

  const enviar = (evento: FormEvent) => {
    evento.preventDefault();
    const limpio = texto.trim();
    if (limpio) onBuscar(limpio);
    campo.current?.select();
  };

  return (
    <form role="search" onSubmit={enviar} className="flex flex-wrap items-end gap-3">
      <label className="flex min-w-0 flex-1 flex-col gap-1.5 text-sm">
        <span className="font-medium text-slate-700">{etiqueta}</span>
        <input
          ref={campo}
          type="search"
          value={texto}
          onChange={(evento) => setTexto(evento.target.value)}
          autoComplete="off"
          spellCheck={false}
          placeholder="Escanea o escribe el código"
          className={`${claseCampo} text-base`}
        />
        {ayuda && <span className="text-xs text-slate-600">{ayuda}</span>}
      </label>
      <button type="submit" disabled={ocupado || !texto.trim()} className={claseBoton}>
        {ocupado ? "Buscando…" : "Buscar"}
      </button>
    </form>
  );
}
```

`frontend/src/components/operacion/ConfirmarAccion.tsx`:

```tsx
import { Fragment, useEffect, useId, useRef } from "react";

export interface FilaResumen {
  etiqueta: string;
  valor: string;
}

/*
  Resumen y confirmación de una operación irreversible.

  El foco va al panel y no al botón de confirmar: un lector de código manda
  Enter al final de cada escaneo, y con el foco en «Confirmar» un escaneo de
  más ejecutaría la operación.
*/
export default function ConfirmarAccion({
  titulo, filas, advertencia, textoConfirmar, peligro = false, ocupado = false, error = "",
  onConfirmar, onVolver,
}: {
  titulo: string;
  filas: FilaResumen[];
  advertencia?: string;
  textoConfirmar: string;
  peligro?: boolean;
  ocupado?: boolean;
  error?: string;
  onConfirmar: () => void;
  onVolver: () => void;
}) {
  const id = useId();
  const panel = useRef<HTMLElement>(null);

  useEffect(() => {
    panel.current?.focus();
  }, []);

  return (
    <section
      ref={panel}
      tabIndex={-1}
      role="alertdialog"
      aria-labelledby={`${id}-titulo`}
      className="rounded-2xl border-2 border-slate-300 bg-slate-50 p-5 outline-none focus:border-slate-500"
    >
      <h3 id={`${id}-titulo`} className="text-base font-semibold text-slate-900">{titulo}</h3>
      <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
        {filas.map((fila) => (
          <Fragment key={fila.etiqueta}>
            <dt className="text-slate-600">{fila.etiqueta}</dt>
            <dd className="font-medium tabular-nums text-slate-900">{fila.valor}</dd>
          </Fragment>
        ))}
      </dl>
      {advertencia && <p className="mt-3 rounded-xl bg-amber-50 px-4 py-2 text-sm text-amber-900">{advertencia}</p>}
      {error && <p role="alert" className="mt-3 rounded-xl bg-red-50 px-4 py-2 text-sm text-red-800">{error}</p>}
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          disabled={ocupado}
          onClick={onConfirmar}
          className={`rounded-xl px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40 ${
            peligro ? "bg-red-700 hover:bg-red-800" : "bg-green-700 hover:bg-green-800"
          }`}
        >
          {ocupado ? "Registrando…" : textoConfirmar}
        </button>
        <button
          type="button"
          disabled={ocupado}
          onClick={onVolver}
          className="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-40"
        >
          Volver y corregir
        </button>
      </div>
    </section>
  );
}
```

- [ ] **Step 7: Tipos, lint y pruebas**

Run: `cd frontend && npx tsc -b --pretty false && npx eslint src/services/formato.ts src/services/paginacion.ts src/services/permisos-despacho.ts src/services/inventario.service.ts src/components/operacion && npm test`
Expected: sin errores; pruebas PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/services/formato.ts frontend/src/services/paginacion.ts frontend/src/services/permisos-despacho.ts frontend/src/services/inventario.service.ts frontend/src/components/operacion frontend/tests/formato.test.ts frontend/tests/paginacion.test.ts frontend/tests/permisos-despacho.test.ts
git commit -m "feat(frontend): bases de inventario — cantidades, páginas completas, permisos de despacho y componentes de operación"
```

---

### Task 6: Servicios nuevos, accesos y Abastecimiento de vuelta

**Files:**
- Modify: `frontend/src/services/inventario.service.ts`
- Modify: `frontend/src/pages/Inventario/OperacionesBodega.tsx` (solo quitar el número tecleado)
- Modify: `frontend/src/services/access-control.ts`
- Modify: `frontend/src/services/navegacion-operacional.ts`
- Modify: `frontend/tests/navegacion-operacional.test.ts`
- Modify: `frontend/src/app/routes.tsx`
- Modify: `frontend/src/pages/Abastecimiento/Abastecimiento.tsx`
- Modify: `frontend/src/pages/Abastecimiento/DetalleLoteInventario.tsx` (enlace de vuelta)

**Interfaces:**
- Consumes: `pagina()` (Task 5), `puedeDespachar` (Task 5); endpoints de Tasks 2-4.
- Produces (en `inventario.service.ts`):
  - tipos ampliados: `Existencia` + `ubicacion: number; ubicacion_tipo: TipoUbicacion; unidad: string; insumo_codigo: string; bodega_nombre: string`; `MovimientoInventario` + `tipo_etiqueta: string; unidad: string; usuario_nombre: string`; `MovimientoProductoTerminado` + `tipo_etiqueta; origen_codigo: string | null; destino_codigo: string | null; registrado_por_nombre: string; lote_codigo: string; kg_neto: string`; `DetalleDespacho` + `ubicacion_codigo: string | null`; `Despacho` + `motivo_cancelacion: string; cancelado_en: string | null`.
  - `export type TipoUbicacion = "disponible" | "cuarentena" | "rechazado" | "produccion"` (y `UbicacionInventario.tipo` lo usa).
  - `CatalogosInventario` + `estado_calidad`, `tipo_movimiento`, `tipo_movimiento_pallet`, `estado_pallet`, todos `{ valor: string; etiqueta: string }[]`.
  - `buscarExistencias(filtros)`, `buscarProductoTerminado(filtros)`, `buscarMovimientos(filtros)`, `buscarMovimientosProductoTerminado(filtros)`: `Promise<Pagina<…>>`.
  - `obtenerPalletsCargables(): Promise<ExistenciaProductoTerminado[]>`, `obtenerHojasVigentes(): Promise<Despacho[]>`.
  - `crearDespacho(datos)` **sin** `numero`; `cancelarDespacho(id: number, motivo: string): Promise<Despacho>`.
  - `interface PendientesBodega` (forma de la Task 4) con `PalletPorUbicar`, `MaterialEnCuarentena`, `MaterialBajoMinimo`, `AjustePendiente`; `obtenerPendientesBodega(): Promise<PendientesBodega>`.
  - En `access-control.ts`: `ModuloSistema` + `"bodega" | "despacho" | "abastecimiento"`.

- [ ] **Step 1: Servicios**

En `inventario.service.ts`:

```ts
export type TipoUbicacion = "disponible" | "cuarentena" | "rechazado" | "produccion";
```

usa `TipoUbicacion` en `UbicacionInventario.tipo` y `ExistenciaProductoTerminado.ubicacion_tipo`; agrega a `CatalogosInventario` las cuatro claves nuevas de la Task 3; amplía las interfaces con los campos listados arriba (se escriben en la misma línea/estilo que las existentes). Luego agrega:

```ts
export type FiltrosInventario = {
  q?: string; estado?: string; ubicacion?: number | ""; desde?: string; hasta?: string;
  page?: number; con_saldo?: boolean; cargable?: boolean;
};

export const buscarExistencias = (filtros: FiltrosInventario = {}) =>
  pagina<Existencia>("inventario/existencias/", filtros);
export const buscarProductoTerminado = (filtros: FiltrosInventario = {}) =>
  pagina<ExistenciaProductoTerminado>("inventario/producto-terminado/", filtros);
export const buscarMovimientos = (filtros: FiltrosInventario = {}) =>
  pagina<MovimientoInventario>("inventario/movimientos/", filtros);
export const buscarMovimientosProductoTerminado = (filtros: FiltrosInventario = {}) =>
  pagina<MovimientoProductoTerminado>("inventario/movimientos-producto-terminado/", filtros);

/* Lo que se puede subir a una hoja de carga: el servidor ya excluye lo que está en otra. */
export const obtenerPalletsCargables = () =>
  lista<ExistenciaProductoTerminado>("inventario/producto-terminado/?cargable=1");
/* Borradores, autorizadas y despachadas hoy: lo que el puesto de Despacho mira. */
export const obtenerHojasVigentes = () => lista<Despacho>("inventario/despachos/?vigentes=1");

export async function cancelarDespacho(id: number, motivo: string) {
  const { data } = await api.post<Despacho>(`inventario/despachos/${id}/cancelar/`, { motivo });
  return data;
}

export interface PalletPorUbicar {
  existencia_id: number; pallet_id: number; pallet_codigo: string; lote_codigo: string;
  producto_nombre: string; kg_neto: string; ubicacion_codigo: string;
}
export interface MaterialEnCuarentena {
  existencia_id: number; lote_codigo: string; insumo_nombre: string;
  cantidad: string; unidad: string; ubicacion_codigo: string;
}
export interface MaterialBajoMinimo {
  insumo_id: number; codigo: string; nombre: string; unidad: string;
  disponible: string; stock_minimo: string;
}
export interface AjustePendiente {
  id: number; existencia_id: number; insumo_nombre: string; lote_codigo: string;
  ubicacion_codigo: string; tipo: "positivo" | "negativo" | "merma"; tipo_etiqueta: string;
  cantidad: string; unidad: string; motivo: string; solicitante_id: number;
  solicitante_nombre: string; creado_en: string;
}
export interface PendientesBodega {
  pallets_por_ubicar: PalletPorUbicar[];
  material_en_cuarentena: MaterialEnCuarentena[];
  bajo_minimo: MaterialBajoMinimo[];
  ajustes_pendientes: AjustePendiente[];
  total: number;
}

export async function obtenerPendientesBodega() {
  const { data } = await api.get<PendientesBodega>("inventario/pendientes-bodega/");
  return data;
}
```

En `crearDespacho`, quita `numero: string;` del tipo de `datos`. En `OperacionesBodega.tsx` quita el estado, el campo y el envío del número (el archivo se elimina en la Task 9; aquí solo se deja compilando).

- [ ] **Step 2: Accesos**

En `access-control.ts`:

```ts
import { puedeDespachar } from "./permisos-despacho.ts";
```

- `ModuloSistema`: agrega `| "bodega" | "despacho" | "abastecimiento"`.
- `AREAS`: `bodega: ["bodega"]`, `despacho: []`, `abastecimiento: ["compras", "bodega", "calidad"]`.
- En `puedeAccederModulo`, como **primera** línea después de `if (!usuario) return false;`:

```ts
  // Despacho se decide con capacidades, como en el servidor: ni el área ni ser
  // administrador bastan si falta el permiso (el superusuario los tiene todos).
  if (modulo === "despacho") return puedeDespachar(usuario);
```

(Los destinos iniciales de bodega y despacho cambian en las Tasks 7 y 8, cuando sus rutas existan; aquí solo `compras: "/abastecimiento"`.)

- [ ] **Step 3: Abastecimiento restaurado**

En `routes.tsx`, reemplaza `<Route path="/abastecimiento/*" element={<Navigate to="/inventario" replace />} />` por:

```tsx
                    {/* Compras vuelve a ser alcanzable (quedó huérfana en 2430350).
                        Lo de bodega —materiales, ubicaciones, recepción— vive en
                        /bodega; las rutas viejas redirigen para no romper enlaces. */}
                    <Route element={<RutaModulo modulo="abastecimiento" />}>
                        <Route path="/abastecimiento" element={diferido(<Abastecimiento />)}>
                            <Route index element={diferido(<AbastecimientoPanel />)} />
                            <Route path="compras" element={diferido(<AbastecimientoCompras />)} />
                            <Route path="proveedores" element={diferido(<AbastecimientoProveedores />)} />
                            <Route path="pedidos" element={diferido(<AbastecimientoPedidos />)} />
                            <Route path="mrp" element={diferido(<AbastecimientoMrp />)} />
                            <Route path="calidad" element={diferido(<AbastecimientoCalidad />)} />
                            <Route path="no-conformidades" element={diferido(<AbastecimientoNoConformidades />)} />
                            <Route path="stock" element={<Navigate to="/inventario" replace />} />
                            <Route path="producto-terminado" element={<Navigate to="/inventario" replace />} />
                            <Route path="*" element={<Navigate to="/abastecimiento" replace />} />
                        </Route>
                    </Route>
```

y dentro del bloque existente `<Route element={<RutaModulo modulo="inventario" />}>`, junto a `/inventario`:

```tsx
                        <Route path="/inventario/lotes/:id" element={diferido(<AbastecimientoDetalleLote />)} />
```

Agrega los `lazy` de `Abastecimiento`, `Panel`, `Compras`, `Proveedores`, `Pedidos`, `Mrp`, `Calidad`, `NoConformidades` y `DetalleLoteInventario`, con los mismos nombres que tenían antes de `2430350` (`git show 2430350^:frontend/src/app/routes.tsx`, líneas 64-77) más `AbastecimientoCalidad` y `AbastecimientoNoConformidades`. Las rutas `materiales`, `bodegas` y `recepcion` caen en el `*` hasta la Task 7, que las redirige a `/bodega/...`.

En `Abastecimiento.tsx`, `PESTANAS` queda:

```ts
const PESTANAS = [
  { a: "", texto: "Panel", exacta: true },
  { a: "compras", texto: "Compras" },
  { a: "proveedores", texto: "Proveedores" },
  { a: "pedidos", texto: "Pedidos" },
  { a: "mrp", texto: "MRP" },
  { a: "calidad", texto: "Calidad de materiales" },
  { a: "no-conformidades", texto: "No conformidades" },
];
```

En `DetalleLoteInventario.tsx:55` cambia `to="/abastecimiento/stock"` por `to="/inventario"`. Busca otros enlaces a `/abastecimiento/stock/lotes/` con `grep -rn "stock/lotes" frontend/src` y cámbialos a `/inventario/lotes/`.

- [ ] **Step 4: Menú**

En `navegacion-operacional.ts`, grupo «Envasado y logística», agrega después de «Inventario y despacho»:

```ts
      { etiqueta: "Compras y abastecimiento", ruta: "/abastecimiento", modulo: "abastecimiento", icono: "planificacion" },
```

En `tests/navegacion-operacional.test.ts`, agrega:

```ts
test("Compras vuelve a tener entrada en el menú y es su destino inicial", () => {
  const compras = usuarioDeArea("compras", "Compras", null);
  assert.ok(etiquetas(compras, "Envasado y logística").includes("Compras y abastecimiento"));
  assert.equal(puedeAccederModulo(compras, "abastecimiento"), true);
});

test("Despacho se abre con la capacidad, no con el área", () => {
  const sinPermiso = usuarioDeArea("despacho", "Despacho", null);
  assert.equal(puedeAccederModulo(sinPermiso, "despacho"), false);
  assert.equal(puedeAccederModulo({ ...sinPermiso, capacidades: ["despacho_crear"] }, "despacho"), true);
});
```

Si alguna prueba existente fija el orden o el contenido exacto del grupo, actualízala para incluir la entrada nueva sin cambiar lo que comprueba.

- [ ] **Step 5: Verificar**

Run: `cd frontend && npx tsc -b --pretty false && npx eslint src/services src/app/routes.tsx src/pages/Abastecimiento src/pages/Inventario && npm test`
Expected: sin errores; PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services frontend/src/app/routes.tsx frontend/src/pages/Abastecimiento frontend/src/pages/Inventario/OperacionesBodega.tsx frontend/tests/navegacion-operacional.test.ts
git commit -m "feat(frontend): servicios de puestos, acceso a despacho por capacidades y Abastecimiento de vuelta"
```

---

### Task 7: Puesto de Bodega

**Files:**
- Create: `frontend/src/services/bodega-reglas.ts`, `frontend/tests/bodega-reglas.test.ts`
- Create: `frontend/src/pages/Bodega/PuestoBodega.tsx` (layout con pestañas)
- Create: `frontend/src/pages/Bodega/OperarBodega.tsx` (buscador, fichas, acciones, pendientes)
- Create: `frontend/src/pages/Bodega/PanelMovimiento.tsx` (panel guiado)
- Create: `frontend/src/pages/Bodega/PendientesBodega.tsx`
- Create: `frontend/src/pages/Bodega/ConfiguracionBodega.tsx`
- Modify: `frontend/src/app/routes.tsx`, `frontend/src/services/access-control.ts`, `frontend/src/services/navegacion-operacional.ts`, `frontend/tests/navegacion-operacional.test.ts`

**Interfaces:**
- Consumes: `cantidad` (formato), `ConfirmarAccion`/`FilaResumen`, `CampoEtiquetado`, `BuscadorCodigo`, `buscarExistencias`, `buscarProductoTerminado`, `obtenerPendientesBodega`, `obtenerUbicaciones`, `obtenerInsumos`, `ingresarMaterial`, `trasladarExistencia`, `registrarSalida`, `crearAjuste`, `decidirAjuste`, `transferirPallet`, `ingresarPallet`, tipos de Task 6; `mensajeDe`, `useCarga`, `claseCampo`, `claseBoton` de `components/seccion/utilidades`; `Tarjeta`, `Vacio`, `Aviso` de `components/seccion/componentes`.
- Produces: `ajustePorConteo(enSistema: string | number, contado: string | number): { tipo: "positivo" | "negativo"; cantidad: number } | null`; `tiposDeDestino(accion: TipoAccionBodega, contexto: { origenTipo?: TipoUbicacion; requiereCalidad?: boolean }): TipoUbicacion[]`; `leerCantidad(texto: string): number | null`; `type TipoAccionBodega = "recibir" | "reubicar-material" | "consumir" | "contar" | "reubicar-pallet" | "ubicar-liberado"`.

- [ ] **Step 1: Pruebas de las reglas**

`frontend/tests/bodega-reglas.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

import { ajustePorConteo, leerCantidad, tiposDeDestino } from "../src/services/bodega-reglas.ts";

test("contar menos de lo que dice el sistema pide un ajuste negativo por la diferencia", () => {
  assert.deepEqual(ajustePorConteo("20.000", "18"), { tipo: "negativo", cantidad: 2 });
});

test("contar más pide un ajuste positivo, sin arrastrar error de coma flotante", () => {
  assert.deepEqual(ajustePorConteo("13.000", "13.1"), { tipo: "positivo", cantidad: 0.1 });
});

test("si el conteo coincide no hay nada que ajustar", () => {
  assert.equal(ajustePorConteo("20.000", 20), null);
});

test("la cantidad se lee con coma o punto decimal y rechaza lo que no es positivo", () => {
  assert.equal(leerCantidad("12,5"), 12.5);
  assert.equal(leerCantidad(" 3 "), 3);
  assert.equal(leerCantidad("0"), null);
  assert.equal(leerCantidad("-2"), null);
  assert.equal(leerCantidad("abc"), null);
  assert.equal(leerCantidad(""), null);
});

test("recibir va a cuarentena si el material pasa por Calidad, y a disponible si no", () => {
  assert.deepEqual(tiposDeDestino("recibir", { requiereCalidad: true }), ["cuarentena"]);
  assert.deepEqual(tiposDeDestino("recibir", { requiereCalidad: false }), ["disponible"]);
});

test("reubicar material no le cambia el estado: mismo tipo de ubicación", () => {
  assert.deepEqual(tiposDeDestino("reubicar-material", { origenTipo: "cuarentena" }), ["cuarentena"]);
});

test("los pallets se mueven a ubicaciones disponibles, y consumir o contar no tienen destino", () => {
  assert.deepEqual(tiposDeDestino("reubicar-pallet", {}), ["disponible"]);
  assert.deepEqual(tiposDeDestino("ubicar-liberado", {}), ["disponible"]);
  assert.deepEqual(tiposDeDestino("consumir", {}), []);
  assert.deepEqual(tiposDeDestino("contar", {}), []);
});
```

Run: `cd frontend && npm test` → Expected: FAIL (módulo inexistente).

- [ ] **Step 2: Reglas**

`frontend/src/services/bodega-reglas.ts`:

```ts
import type { TipoUbicacion } from "./inventario.service.ts";

export type TipoAccionBodega =
  | "recibir" | "reubicar-material" | "consumir" | "contar" | "reubicar-pallet" | "ubicar-liberado";

/* Cantidad tecleada: acepta coma decimal (es lo que se escribe en Chile). */
export function leerCantidad(texto: string): number | null {
  const limpio = texto.trim().replace(",", ".");
  if (!limpio) return null;
  const numero = Number(limpio);
  return Number.isFinite(numero) && numero > 0 ? numero : null;
}

/*
  El ajuste que corresponde a un conteo físico.

  El operador dice cuánto contó —no cuánto sobra o falta—, que es lo que ve en
  la estantería. La diferencia se redondea a milésimas porque así la guarda el
  modelo; sin redondear, 13,1 − 13 daría 0,0999…
*/
export function ajustePorConteo(
  enSistema: string | number, contado: string | number,
): { tipo: "positivo" | "negativo"; cantidad: number } | null {
  const diferencia = Math.round((Number(contado) - Number(enSistema)) * 1000) / 1000;
  if (!Number.isFinite(diferencia) || diferencia === 0) return null;
  return { tipo: diferencia > 0 ? "positivo" : "negativo", cantidad: Math.abs(diferencia) };
}

/*
  Qué tipo de ubicación acepta cada movimiento. Se ofrecen solo esas: ofrecer
  todas deja elegir un destino que el backend rechaza al final del formulario.
  Recibir sigue la regla de `registrar_entrada` (cuarentena si pasa por Calidad).
*/
export function tiposDeDestino(
  accion: TipoAccionBodega,
  contexto: { origenTipo?: TipoUbicacion; requiereCalidad?: boolean },
): TipoUbicacion[] {
  switch (accion) {
    case "recibir":
      return [contexto.requiereCalidad ? "cuarentena" : "disponible"];
    case "reubicar-material":
      return contexto.origenTipo ? [contexto.origenTipo] : [];
    case "reubicar-pallet":
    case "ubicar-liberado":
      return ["disponible"];
    default:
      return [];
  }
}
```

Nota: `import type` desde `inventario.service.ts` se borra al ejecutar con `node --test`, así que no arrastra `axios`.

Run: `cd frontend && npm test` → Expected: PASS.

- [ ] **Step 3: Panel guiado**

`frontend/src/pages/Bodega/PanelMovimiento.tsx`:

```tsx
import { useState, type FormEvent } from "react";
import { X } from "lucide-react";

import CampoEtiquetado from "../../components/operacion/CampoEtiquetado";
import ConfirmarAccion, { type FilaResumen } from "../../components/operacion/ConfirmarAccion";
import { claseBoton, claseCampo, mensajeDe } from "../../components/seccion/utilidades";
import { ajustePorConteo, leerCantidad, tiposDeDestino } from "../../services/bodega-reglas";
import { cantidad } from "../../services/formato";
import {
  crearAjuste, ingresarMaterial, ingresarPallet, registrarSalida, transferirPallet, trasladarExistencia,
  type Existencia, type ExistenciaProductoTerminado, type Insumo, type PalletPorUbicar, type UbicacionInventario,
} from "../../services/inventario.service";

export type AccionBodega =
  | { tipo: "recibir" }
  | { tipo: "reubicar-material" | "consumir" | "contar"; existencia: Existencia }
  | { tipo: "reubicar-pallet"; pallet: ExistenciaProductoTerminado }
  | { tipo: "ubicar-liberado"; pallet: PalletPorUbicar };

const TITULOS: Record<AccionBodega["tipo"], string> = {
  recibir: "Recibir material",
  "reubicar-material": "Reubicar material",
  consumir: "Consumir material",
  contar: "Ajustar por conteo",
  "reubicar-pallet": "Reubicar pallet",
  "ubicar-liberado": "Ubicar pallet liberado",
};

/*
  Un movimiento en tres pasos: qué (viene elegido desde la ficha o el
  pendiente), adónde y cuánto, y resumen antes de registrar. Al terminar
  entrega el mensaje del movimiento con el saldo que dejó.
*/
export default function PanelMovimiento({ accion, ubicaciones, insumos, onCerrar, onHecho }: {
  accion: AccionBodega;
  ubicaciones: UbicacionInventario[];
  insumos: Insumo[];
  onCerrar: () => void;
  onHecho: (mensaje: string) => void;
}) {
  const [paso, setPaso] = useState<"datos" | "resumen">("datos");
  const [destino, setDestino] = useState("");
  const [texto, setTexto] = useState("");
  const [motivo, setMotivo] = useState("");
  const [insumoId, setInsumoId] = useState("");
  const [codigoLote, setCodigoLote] = useState("");
  const [vencimiento, setVencimiento] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");

  const existencia = "existencia" in accion ? accion.existencia : null;
  const insumo = insumos.find((item) => String(item.id) === insumoId) ?? null;
  const unidad = existencia?.unidad ?? insumo?.unidad ?? "kg";
  const origenId =
    existencia?.ubicacion ?? (accion.tipo === "reubicar-pallet" ? accion.pallet.ubicacion : null);
  const tipos = tiposDeDestino(accion.tipo, {
    origenTipo: existencia?.ubicacion_tipo,
    requiereCalidad: insumo?.requiere_calidad,
  });
  const destinos = ubicaciones.filter((u) => u.activo && u.id !== origenId && tipos.includes(u.tipo));
  const pideDestino = tipos.length > 0;
  const pideCantidad = accion.tipo === "recibir" || accion.tipo === "reubicar-material" || accion.tipo === "consumir";
  const destinoElegido = ubicaciones.find((u) => String(u.id) === destino);
  const numero = leerCantidad(texto);
  const conteo = accion.tipo === "contar" && existencia ? ajustePorConteo(existencia.cantidad_fisica, texto.replace(",", ".")) : null;

  const validar = (): string => {
    if (accion.tipo === "recibir") {
      if (!insumo) return "Elige el material.";
      if (!codigoLote.trim()) return "Escribe el lote del proveedor.";
      if (insumo.requiere_vencimiento && !vencimiento) return "Este material exige fecha de vencimiento.";
    }
    if (pideDestino && !destinoElegido) return "Elige la ubicación de destino.";
    if (pideCantidad && numero === null) return "Escribe una cantidad mayor que cero.";
    if (pideCantidad && existencia && numero !== null && numero > Number(existencia.cantidad_disponible)) {
      return `Hay ${cantidad(existencia.cantidad_disponible, unidad)} disponibles en esa ubicación.`;
    }
    if (accion.tipo === "contar") {
      if (texto.trim() === "" || !Number.isFinite(Number(texto.replace(",", ".")))) return "Escribe cuánto contaste.";
      if (!conteo) return "Lo contado coincide con el sistema: no hay nada que ajustar.";
      if (!motivo.trim()) return "El ajuste necesita un motivo.";
    }
    return "";
  };

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    const problema = validar();
    setError(problema);
    if (!problema) setPaso("resumen");
  };

  const resumen = (): FilaResumen[] => {
    const hacia = destinoElegido ? `${destinoElegido.codigo} · ${destinoElegido.bodega_nombre}` : "—";
    switch (accion.tipo) {
      case "recibir":
        return [
          { etiqueta: "Material", valor: insumo ? `${insumo.codigo} · ${insumo.nombre}` : "—" },
          { etiqueta: "Lote del proveedor", valor: codigoLote.trim() },
          { etiqueta: "Cantidad", valor: cantidad(numero, unidad) },
          { etiqueta: "Destino", valor: hacia },
          ...(vencimiento ? [{ etiqueta: "Vencimiento", valor: vencimiento }] : []),
        ];
      case "reubicar-material":
      case "consumir":
        return [
          { etiqueta: "Material", valor: accion.existencia.insumo_nombre },
          { etiqueta: "Lote", valor: accion.existencia.lote_codigo },
          { etiqueta: "Desde", valor: accion.existencia.ubicacion_codigo },
          ...(accion.tipo === "reubicar-material" ? [{ etiqueta: "Hacia", valor: hacia }] : []),
          { etiqueta: "Cantidad", valor: cantidad(numero, unidad) },
          ...(motivo.trim() ? [{ etiqueta: "Motivo", valor: motivo.trim() }] : []),
        ];
      case "contar":
        return [
          { etiqueta: "Material", valor: accion.existencia.insumo_nombre },
          { etiqueta: "Lote", valor: accion.existencia.lote_codigo },
          { etiqueta: "Ubicación", valor: accion.existencia.ubicacion_codigo },
          { etiqueta: "En sistema", valor: cantidad(accion.existencia.cantidad_fisica, unidad) },
          { etiqueta: "Contado", valor: cantidad(texto.replace(",", "."), unidad) },
          { etiqueta: "Ajuste", valor: conteo ? `${conteo.tipo === "positivo" ? "+" : "−"}${cantidad(conteo.cantidad, unidad)}` : "—" },
          { etiqueta: "Motivo", valor: motivo.trim() },
        ];
      case "reubicar-pallet":
        return [
          { etiqueta: "Pallet", valor: accion.pallet.pallet_codigo },
          { etiqueta: "Producto", valor: `${accion.pallet.producto_nombre} · lote ${accion.pallet.lote_codigo}` },
          { etiqueta: "Desde", valor: accion.pallet.ubicacion_codigo },
          { etiqueta: "Hacia", valor: hacia },
          { etiqueta: "Peso", valor: cantidad(accion.pallet.kg_neto, "kg") },
        ];
      case "ubicar-liberado":
        return [
          { etiqueta: "Pallet", valor: accion.pallet.pallet_codigo },
          { etiqueta: "Producto", valor: `${accion.pallet.producto_nombre} · lote ${accion.pallet.lote_codigo}` },
          { etiqueta: "Desde", valor: `${accion.pallet.ubicacion_codigo} (cuarentena)` },
          { etiqueta: "Hacia", valor: hacia },
          { etiqueta: "Peso", valor: cantidad(accion.pallet.kg_neto, "kg") },
        ];
    }
  };

  const ejecutar = async (): Promise<string> => {
    const idDestino = Number(destino);
    switch (accion.tipo) {
      case "recibir": {
        const m = await ingresarMaterial({
          insumo: Number(insumoId), codigo_lote: codigoLote.trim(), ubicacion: idDestino,
          cantidad: numero ?? 0, vencimiento: vencimiento || undefined,
        });
        return `Ingreso registrado: ${cantidad(m.cantidad, unidad)} de ${m.insumo_nombre} en ${m.destino_codigo}. Saldo del lote ahí: ${cantidad(m.saldo_posterior, unidad)}.`;
      }
      case "reubicar-material": {
        const m = await trasladarExistencia({
          existencia: accion.existencia.id, destino: idDestino, cantidad: numero ?? 0, motivo: motivo.trim(),
        });
        return `Traslado registrado: ${cantidad(m.cantidad, unidad)} de ${m.insumo_nombre}, de ${m.origen_codigo} a ${m.destino_codigo}.`;
      }
      case "consumir": {
        const m = await registrarSalida({
          existencia: accion.existencia.id, cantidad: numero ?? 0, tipo: "consumo", motivo: motivo.trim(),
        });
        return `Consumo registrado: ${cantidad(m.cantidad, unidad)} de ${m.insumo_nombre}. Quedan ${cantidad(m.saldo_posterior, unidad)} en ${m.origen_codigo}.`;
      }
      case "contar": {
        const a = await crearAjuste({
          existencia: accion.existencia.id, tipo: conteo!.tipo, cantidad: conteo!.cantidad, motivo: motivo.trim(),
        });
        return `Ajuste ${a.tipo} de ${cantidad(a.cantidad, unidad)} enviado a aprobación. Lo aprueba otra persona.`;
      }
      case "reubicar-pallet": {
        const e = await transferirPallet(accion.pallet.id, idDestino, motivo.trim());
        return `Pallet ${e.pallet_codigo} movido a ${e.ubicacion_codigo}.`;
      }
      case "ubicar-liberado": {
        const e = await ingresarPallet(accion.pallet.pallet_id, idDestino);
        return `Pallet ${e.pallet_codigo} ubicado en ${e.ubicacion_codigo}. Ya está disponible para despacho.`;
      }
    }
  };

  const confirmar = async () => {
    setOcupado(true);
    setError("");
    try {
      onHecho(await ejecutar());
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo registrar el movimiento."));
    } finally {
      setOcupado(false);
    }
  };

  return (
    <section aria-labelledby="panel-movimiento-titulo" className="rounded-2xl border border-green-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-green-700">
            Paso {paso === "datos" ? "2" : "3"} de 3
          </p>
          <h2 id="panel-movimiento-titulo" className="text-lg font-semibold text-slate-900">{TITULOS[accion.tipo]}</h2>
        </div>
        <button type="button" onClick={onCerrar} aria-label="Cerrar sin registrar" className="rounded-lg p-2 text-slate-600 hover:bg-slate-100">
          <X className="h-5 w-5" />
        </button>
      </div>

      {paso === "resumen" ? (
        <ConfirmarAccion
          titulo="Revisa antes de registrar"
          filas={resumen()}
          advertencia={accion.tipo === "contar" ? "El ajuste queda pendiente hasta que otra persona lo apruebe." : undefined}
          textoConfirmar={accion.tipo === "contar" ? "Enviar ajuste" : "Registrar movimiento"}
          ocupado={ocupado}
          error={error}
          onConfirmar={() => void confirmar()}
          onVolver={() => { setPaso("datos"); setError(""); }}
        />
      ) : (
        <form onSubmit={revisar} className="grid gap-4 sm:grid-cols-2">
          {accion.tipo === "recibir" && (
            <>
              <CampoEtiquetado etiqueta="Material">
                <select value={insumoId} onChange={(e) => { setInsumoId(e.target.value); setDestino(""); }} className={claseCampo}>
                  <option value="">Elige el material…</option>
                  {insumos.map((i) => <option key={i.id} value={i.id}>{i.codigo} · {i.nombre} ({i.unidad})</option>)}
                </select>
              </CampoEtiquetado>
              <CampoEtiquetado etiqueta="Lote del proveedor">
                <input value={codigoLote} onChange={(e) => setCodigoLote(e.target.value)} className={claseCampo} autoComplete="off" />
              </CampoEtiquetado>
              {insumo?.requiere_vencimiento && (
                <CampoEtiquetado etiqueta="Vencimiento">
                  <input type="date" value={vencimiento} onChange={(e) => setVencimiento(e.target.value)} className={claseCampo} />
                </CampoEtiquetado>
              )}
            </>
          )}

          {existencia && (
            <p className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700 sm:col-span-2">
              {existencia.insumo_nombre} · lote {existencia.lote_codigo} · en {existencia.ubicacion_codigo}:{" "}
              <strong>{cantidad(existencia.cantidad_fisica, unidad)}</strong> físicas,{" "}
              {cantidad(existencia.cantidad_disponible, unidad)} disponibles
            </p>
          )}

          {pideDestino && (
            <CampoEtiquetado
              etiqueta="Destino"
              ayuda={destinos.length === 0 ? "No hay ubicaciones válidas para este movimiento; créalas en Configuración." : undefined}
            >
              <select value={destino} onChange={(e) => setDestino(e.target.value)} className={claseCampo}>
                <option value="">Elige la ubicación…</option>
                {destinos.map((u) => <option key={u.id} value={u.id}>{u.codigo} · {u.bodega_nombre} ({u.tipo_etiqueta})</option>)}
              </select>
            </CampoEtiquetado>
          )}

          {pideCantidad && (
            <CampoEtiquetado etiqueta={`Cantidad (${unidad})`}>
              <input inputMode="decimal" value={texto} onChange={(e) => setTexto(e.target.value)} className={claseCampo} autoComplete="off" />
            </CampoEtiquetado>
          )}

          {accion.tipo === "contar" && (
            <CampoEtiquetado etiqueta={`Cantidad contada (${unidad})`} ayuda="Lo que hay en la estantería, no la diferencia.">
              <input inputMode="decimal" value={texto} onChange={(e) => setTexto(e.target.value)} className={claseCampo} autoComplete="off" />
            </CampoEtiquetado>
          )}

          {accion.tipo !== "recibir" && accion.tipo !== "ubicar-liberado" && (
            <CampoEtiquetado etiqueta={accion.tipo === "contar" ? "Motivo" : "Motivo (opcional)"}>
              <input value={motivo} onChange={(e) => setMotivo(e.target.value)} className={claseCampo} />
            </CampoEtiquetado>
          )}

          {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-2 text-sm text-red-800 sm:col-span-2">{error}</p>}

          <div className="sm:col-span-2">
            <button type="submit" className={claseBoton}>Revisar</button>
          </div>
        </form>
      )}
    </section>
  );
}
```

Verifica que `UbicacionInventario` tenga `bodega_nombre` y `tipo_etiqueta` (sí, líneas 22-31 del servicio) y que `ExistenciaProductoTerminado` tenga `ubicacion` y `pallet_codigo` (sí). `MovimientoInventario` tiene `insumo_nombre`, `origen_codigo`, `destino_codigo`, `saldo_posterior`.

- [ ] **Step 4: Pendientes**

`frontend/src/pages/Bodega/PendientesBodega.tsx`:

```tsx
import { useState } from "react";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { Tarjeta, Vacio } from "../../components/seccion/componentes";
import { mensajeDe } from "../../components/seccion/utilidades";
import { cantidad } from "../../services/formato";
import {
  decidirAjuste, type AjustePendiente, type PalletPorUbicar, type PendientesBodega as Pendientes,
} from "../../services/inventario.service";

/*
  Lo que Bodega tiene que resolver. Cada fila lleva su acción; lo que decide
  otra área (Calidad, Compras) se muestra sin botón, para que se sepa que está
  y a quién le toca.
*/
export default function PendientesBodega({ datos, usuarioId, onUbicar, onCambio }: {
  datos: Pendientes;
  usuarioId: number | undefined;
  onUbicar: (pallet: PalletPorUbicar) => void;
  onCambio: (mensaje: string) => void;
}) {
  const [decision, setDecision] = useState<{ ajuste: AjustePendiente; aprobar: boolean } | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");

  const decidir = async () => {
    if (!decision) return;
    setOcupado(true);
    setError("");
    try {
      await decidirAjuste(decision.ajuste.id, decision.aprobar ? "aprobar" : "rechazar");
      onCambio(`Ajuste de ${decision.ajuste.insumo_nombre} ${decision.aprobar ? "aprobado y aplicado" : "rechazado"}.`);
      setDecision(null);
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo registrar la decisión."));
    } finally {
      setOcupado(false);
    }
  };

  if (datos.total === 0) {
    return <Tarjeta titulo="Pendientes"><Vacio>No hay nada pendiente en bodega.</Vacio></Tarjeta>;
  }

  return (
    <div className="space-y-4">
      {datos.pallets_por_ubicar.length > 0 && (
        <Tarjeta titulo={`Pallets liberados por ubicar (${datos.pallets_por_ubicar.length})`} descripcion="Calidad los liberó y siguen en cuarentena: muévelos a una ubicación disponible para poder despacharlos." sinRelleno>
          <ul className="divide-y divide-slate-100">
            {datos.pallets_por_ubicar.map((p) => (
              <li key={p.existencia_id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-sm">
                <span><strong className="font-mono">{p.pallet_codigo}</strong> · {p.producto_nombre} · lote {p.lote_codigo} · {cantidad(p.kg_neto, "kg")} · en {p.ubicacion_codigo}</span>
                <button type="button" onClick={() => onUbicar(p)} className="rounded-xl bg-green-700 px-4 py-2 text-sm font-semibold text-white hover:bg-green-800">Ubicar</button>
              </li>
            ))}
          </ul>
        </Tarjeta>
      )}

      {datos.ajustes_pendientes.length > 0 && (
        <Tarjeta titulo={`Ajustes por aprobar (${datos.ajustes_pendientes.length})`} descripcion="Un ajuste lo aprueba una persona distinta de quien lo pidió." sinRelleno>
          <ul className="divide-y divide-slate-100">
            {datos.ajustes_pendientes.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-sm">
                <span>
                  {a.tipo_etiqueta} de <strong>{cantidad(a.cantidad, a.unidad)}</strong> · {a.insumo_nombre} · lote {a.lote_codigo} · {a.ubicacion_codigo}
                  <span className="block text-slate-600">«{a.motivo}» — pidió {a.solicitante_nombre}</span>
                </span>
                {a.solicitante_id === usuarioId ? (
                  <span className="text-slate-600">Lo aprueba otra persona</span>
                ) : (
                  <span className="flex gap-2">
                    <button type="button" onClick={() => setDecision({ ajuste: a, aprobar: true })} className="rounded-xl bg-green-700 px-4 py-2 font-semibold text-white hover:bg-green-800">Aprobar</button>
                    <button type="button" onClick={() => setDecision({ ajuste: a, aprobar: false })} className="rounded-xl border border-slate-300 px-4 py-2 font-medium text-slate-700 hover:bg-slate-100">Rechazar</button>
                  </span>
                )}
              </li>
            ))}
          </ul>
          {decision && (
            <div className="border-t border-slate-200 p-5">
              <ConfirmarAccion
                titulo={decision.aprobar ? "Aprobar y aplicar el ajuste" : "Rechazar el ajuste"}
                filas={[
                  { etiqueta: "Material", valor: `${decision.ajuste.insumo_nombre} · lote ${decision.ajuste.lote_codigo}` },
                  { etiqueta: "Ubicación", valor: decision.ajuste.ubicacion_codigo },
                  { etiqueta: "Ajuste", valor: `${decision.ajuste.tipo_etiqueta}: ${cantidad(decision.ajuste.cantidad, decision.ajuste.unidad)}` },
                  { etiqueta: "Motivo", valor: decision.ajuste.motivo },
                ]}
                advertencia={decision.aprobar ? "Aprobar mueve el saldo de inmediato." : undefined}
                textoConfirmar={decision.aprobar ? "Aprobar" : "Rechazar"}
                peligro={!decision.aprobar}
                ocupado={ocupado}
                error={error}
                onConfirmar={() => void decidir()}
                onVolver={() => { setDecision(null); setError(""); }}
              />
            </div>
          )}
        </Tarjeta>
      )}

      {datos.material_en_cuarentena.length > 0 && (
        <Tarjeta titulo={`Material en cuarentena (${datos.material_en_cuarentena.length})`} descripcion="Lo decide Calidad. Aparece para que sepas qué no se puede usar todavía." sinRelleno>
          <ul className="divide-y divide-slate-100">
            {datos.material_en_cuarentena.map((m) => (
              <li key={m.existencia_id} className="px-5 py-3 text-sm">{m.insumo_nombre} · lote {m.lote_codigo} · {cantidad(m.cantidad, m.unidad)} · en {m.ubicacion_codigo}</li>
            ))}
          </ul>
        </Tarjeta>
      )}

      {datos.bajo_minimo.length > 0 && (
        <Tarjeta titulo={`Bajo el mínimo (${datos.bajo_minimo.length})`} descripcion="Disponible igual o menor que el stock mínimo. Avísale a Compras." sinRelleno>
          <ul className="divide-y divide-slate-100">
            {datos.bajo_minimo.map((m) => (
              <li key={m.insumo_id} className="px-5 py-3 text-sm">{m.codigo} · {m.nombre}: {cantidad(m.disponible, m.unidad)} disponibles, mínimo {cantidad(m.stock_minimo, m.unidad)}</li>
            ))}
          </ul>
        </Tarjeta>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Operar (buscador, fichas, acciones)**

`frontend/src/pages/Bodega/OperarBodega.tsx`:

```tsx
import { useState } from "react";
import { PackagePlus } from "lucide-react";

import BuscadorCodigo from "../../components/operacion/BuscadorCodigo";
import { Aviso, Tarjeta } from "../../components/seccion/componentes";
import { claseBoton, useCarga } from "../../components/seccion/utilidades";
import { cantidad } from "../../services/formato";
import {
  buscarExistencias, buscarProductoTerminado, obtenerInsumos, obtenerPendientesBodega, obtenerUbicaciones,
  type Existencia, type ExistenciaProductoTerminado,
} from "../../services/inventario.service";
import { obtenerSesion } from "../../services/sesion";
import PanelMovimiento, { type AccionBodega } from "./PanelMovimiento";
import PendientesBodega from "./PendientesBodega";

interface Resultado {
  texto: string;
  pallets: ExistenciaProductoTerminado[];
  materiales: Existencia[];
  errores: string[];
}

/* Paso 1 de cada movimiento: encontrar la cosa. Todo lo demás cuelga de aquí. */
export default function OperarBodega() {
  const usuarioId = obtenerSesion()?.usuario.id;
  const pendientes = useCarga(obtenerPendientesBodega);
  const ubicaciones = useCarga(obtenerUbicaciones);
  const insumos = useCarga(obtenerInsumos);
  const [buscando, setBuscando] = useState(false);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [accion, setAccion] = useState<AccionBodega | null>(null);
  const [hecho, setHecho] = useState("");

  const buscar = async (texto: string) => {
    setBuscando(true);
    setHecho("");
    // Por separado: si falla una búsqueda, la otra igual se muestra.
    const [pallets, materiales] = await Promise.allSettled([
      buscarProductoTerminado({ q: texto }),
      buscarExistencias({ q: texto, con_saldo: true }),
    ]);
    setResultado({
      texto,
      pallets: pallets.status === "fulfilled" ? pallets.value.results : [],
      materiales: materiales.status === "fulfilled" ? materiales.value.results : [],
      errores: [
        ...(pallets.status === "rejected" ? ["No se pudieron buscar pallets."] : []),
        ...(materiales.status === "rejected" ? ["No se pudo buscar material."] : []),
      ],
    });
    setBuscando(false);
  };

  const terminar = (mensaje: string) => {
    setAccion(null);
    setHecho(mensaje);
    setResultado(null);
    void pendientes.recargar();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-4 rounded-2xl border border-slate-200 bg-white p-5">
        <div className="min-w-0 flex-1">
          <BuscadorCodigo
            etiqueta="Pallet, lote o material"
            ayuda="Escanea la etiqueta o escribe parte del código o del nombre."
            ocupado={buscando}
            onBuscar={(texto) => void buscar(texto)}
          />
        </div>
        <button type="button" onClick={() => { setAccion({ tipo: "recibir" }); setHecho(""); }} className={`${claseBoton} inline-flex items-center gap-2`}>
          <PackagePlus className="h-4 w-4" /> Recibir material
        </button>
      </div>

      {hecho && <p role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">{hecho}</p>}

      {accion && (
        <PanelMovimiento
          accion={accion}
          ubicaciones={ubicaciones.datos ?? []}
          insumos={insumos.datos ?? []}
          onCerrar={() => setAccion(null)}
          onHecho={terminar}
        />
      )}
      {accion && ubicaciones.error && <Aviso>No se pudieron cargar las ubicaciones: {ubicaciones.error}</Aviso>}

      {resultado && !accion && (
        <Tarjeta titulo={`Resultados para «${resultado.texto}»`} sinRelleno>
          {resultado.errores.map((e) => <p key={e} role="alert" className="px-5 pt-3 text-sm text-red-800">{e}</p>)}
          {resultado.pallets.length === 0 && resultado.materiales.length === 0 && resultado.errores.length === 0 && (
            <p className="px-5 py-4 text-sm text-slate-600">No hay pallets ni material con «{resultado.texto}».</p>
          )}
          <ul className="divide-y divide-slate-100">
            {resultado.pallets.map((p) => (
              <li key={`p-${p.id}`} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 text-sm">
                <span>
                  <strong className="font-mono">{p.pallet_codigo}</strong> · {p.producto_nombre} · lote {p.lote_codigo}
                  <span className="block text-slate-600">{cantidad(p.kg_neto, "kg")} · en {p.ubicacion_codigo} · {p.estado_inventario}</span>
                </span>
                {p.estado_inventario === "disponible" && p.ubicacion_tipo === "disponible" && (
                  <button type="button" onClick={() => setAccion({ tipo: "reubicar-pallet", pallet: p })} className="rounded-xl border border-slate-300 px-4 py-2 font-medium text-slate-800 hover:bg-slate-100">Reubicar</button>
                )}
                {p.estado_inventario === "disponible" && p.ubicacion_tipo === "cuarentena" && (
                  <button
                    type="button"
                    onClick={() => setAccion({ tipo: "ubicar-liberado", pallet: {
                      existencia_id: p.id, pallet_id: p.pallet, pallet_codigo: p.pallet_codigo,
                      lote_codigo: p.lote_codigo, producto_nombre: p.producto_nombre,
                      kg_neto: p.kg_neto, ubicacion_codigo: p.ubicacion_codigo,
                    } })}
                    className="rounded-xl bg-green-700 px-4 py-2 font-semibold text-white hover:bg-green-800"
                  >Ubicar</button>
                )}
              </li>
            ))}
            {resultado.materiales.map((m) => (
              <li key={`m-${m.id}`} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 text-sm">
                <span>
                  {m.insumo_nombre} · lote <span className="font-mono">{m.lote_codigo}</span>
                  <span className="block text-slate-600">
                    {cantidad(m.cantidad_fisica, m.unidad)} en {m.ubicacion_codigo} ({m.bodega_nombre}) · {cantidad(m.cantidad_disponible, m.unidad)} disponibles · Calidad: {m.estado_calidad}
                  </span>
                </span>
                <span className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => setAccion({ tipo: "reubicar-material", existencia: m })} className="rounded-xl border border-slate-300 px-4 py-2 font-medium text-slate-800 hover:bg-slate-100">Reubicar</button>
                  <button type="button" onClick={() => setAccion({ tipo: "consumir", existencia: m })} className="rounded-xl border border-slate-300 px-4 py-2 font-medium text-slate-800 hover:bg-slate-100">Consumir</button>
                  <button type="button" onClick={() => setAccion({ tipo: "contar", existencia: m })} className="rounded-xl border border-slate-300 px-4 py-2 font-medium text-slate-800 hover:bg-slate-100">Ajustar por conteo</button>
                </span>
              </li>
            ))}
          </ul>
        </Tarjeta>
      )}

      <section aria-labelledby="pendientes-titulo" className="space-y-3">
        <h2 id="pendientes-titulo" className="text-lg font-semibold text-slate-900">
          Pendientes{pendientes.datos ? ` (${pendientes.datos.total})` : ""}
        </h2>
        {pendientes.error && <p role="alert" className="text-sm text-red-800">{pendientes.error}</p>}
        {pendientes.cargando && !pendientes.datos && <p className="text-sm text-slate-600">Cargando pendientes…</p>}
        {pendientes.datos && (
          <PendientesBodega
            datos={pendientes.datos}
            usuarioId={usuarioId}
            onUbicar={(pallet) => { setAccion({ tipo: "ubicar-liberado", pallet }); setHecho(""); }}
            onCambio={terminar}
          />
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 6: Layout y configuración**

`frontend/src/pages/Bodega/PuestoBodega.tsx`:

```tsx
import { NavLink, Outlet } from "react-router-dom";

const PESTANAS = [
  { a: "", texto: "Operar", exacta: true },
  { a: "recepcion", texto: "Recepción de compras" },
  { a: "configuracion", texto: "Configuración" },
];

/* El puesto abre en lo que hay que hacer, no en lo que hay guardado. */
export default function PuestoBodega() {
  return (
    <div className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl">
        <header className="mb-6">
          <p className="text-sm font-semibold uppercase tracking-wider text-green-700">Puesto de trabajo</p>
          <h1 className="mt-1 text-3xl font-bold text-slate-900">Bodega</h1>
          <p className="mt-2 max-w-2xl text-slate-600">Busca un pallet, lote o material y registra el movimiento. Lo pendiente del turno está debajo.</p>
        </header>
        <nav aria-label="Secciones de Bodega" className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200">
          {PESTANAS.map(({ a, texto, exacta }) => (
            <NavLink
              key={texto}
              to={a}
              end={exacta}
              className={({ isActive }) =>
                `whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                  isActive ? "border-green-700 text-green-800" : "border-transparent text-slate-600 hover:text-slate-800"
                }`
              }
            >
              {texto}
            </NavLink>
          ))}
        </nav>
        <Outlet />
      </div>
    </div>
  );
}
```

`frontend/src/pages/Bodega/ConfiguracionBodega.tsx`:

```tsx
import Bodegas from "../Abastecimiento/Bodegas";
import Materiales from "../Abastecimiento/Materiales";

/* Lo que se configura una vez y se consulta poco: detrás de una pestaña,
   no delante de los movimientos. */
export default function ConfiguracionBodega() {
  return (
    <div className="space-y-10">
      <Bodegas />
      <Materiales />
    </div>
  );
}
```

- [ ] **Step 7: Ruta, destino inicial y menú**

En `routes.tsx`:

```tsx
const PuestoBodega = lazy(() => import("../pages/Bodega/PuestoBodega"));
const OperarBodega = lazy(() => import("../pages/Bodega/OperarBodega"));
const ConfiguracionBodega = lazy(() => import("../pages/Bodega/ConfiguracionBodega"));
```

```tsx
                    <Route element={<RutaModulo modulo="bodega" />}>
                        <Route path="/bodega" element={diferido(<PuestoBodega />)}>
                            <Route index element={diferido(<OperarBodega />)} />
                            <Route path="recepcion" element={diferido(<AbastecimientoRecepcion />)} />
                            <Route path="configuracion" element={diferido(<ConfiguracionBodega />)} />
                        </Route>
                    </Route>
```

(agrega `const AbastecimientoRecepcion = lazy(() => import("../pages/Abastecimiento/Recepcion"));`). Dentro de `/abastecimiento`, antes del `*`:

```tsx
                            <Route path="materiales" element={<Navigate to="/bodega/configuracion" replace />} />
                            <Route path="bodegas" element={<Navigate to="/bodega/configuracion" replace />} />
                            <Route path="recepcion" element={<Navigate to="/bodega/recepcion" replace />} />
```

En `access-control.ts`, `destinoInicial` → `bodega: "/bodega"`. En `navegacion-operacional.ts`, antes de «Inventario y despacho»:

```ts
      { etiqueta: "Bodega", ruta: "/bodega", modulo: "bodega", icono: "inventario" },
```

En `tests/navegacion-operacional.test.ts`:

```ts
test("Bodega entra a su puesto", () => {
  const bodega = usuarioDeArea("bodega", "Bodega", null);
  assert.equal(puedeAccederModulo(bodega, "bodega"), true);
  assert.ok(etiquetas(bodega, "Envasado y logística").includes("Bodega"));
});
```

(y si el archivo ya prueba `destinoInicial` para bodega con `"/inventario"`, cámbialo a `"/bodega"`).

- [ ] **Step 8: Verificar**

Run: `cd frontend && npx tsc -b --pretty false && npx eslint src/pages/Bodega src/services src/app/routes.tsx && npm test`
Expected: sin errores; PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/Bodega frontend/src/services/bodega-reglas.ts frontend/tests/bodega-reglas.test.ts frontend/src/app/routes.tsx frontend/src/services/access-control.ts frontend/src/services/navegacion-operacional.ts frontend/tests/navegacion-operacional.test.ts
git commit -m "feat(bodega): puesto de Bodega con búsqueda, movimientos guiados y pendientes"
```

---

### Task 8: Puesto de Despacho

**Files:**
- Create: `frontend/src/services/despacho-reglas.ts`, `frontend/tests/despacho-reglas.test.ts`
- Create: `frontend/src/pages/Despacho/PuestoDespacho.tsx`
- Create: `frontend/src/pages/Despacho/NuevaHojaCarga.tsx`
- Create: `frontend/src/pages/Despacho/HojaDeCarga.tsx`
- Modify: `frontend/src/app/routes.tsx`, `frontend/src/services/access-control.ts`, `frontend/src/services/navegacion-operacional.ts`, `frontend/tests/navegacion-operacional.test.ts`

**Interfaces:**
- Consumes: `puedeDespachar`, `puedeAutorizarDespacho`, `cantidad`, `ConfirmarAccion`, `CampoEtiquetado`, `BuscadorCodigo`, `obtenerHojasVigentes`, `obtenerPalletsCargables`, `obtenerClientesDespacho`, `obtenerGranelDisponible`, `crearDespacho`, `autorizarDespacho`, `ejecutarDespacho`, `cancelarDespacho`, `fechaLocalISO` (de `services/fechas.ts`).
- Produces: `agruparHojas<T extends { estado: string; despachado_en: string | null }>(hojas: T[], hoy: string): { borrador: T[]; autorizada: T[]; despachadaHoy: T[] }`; `totalesCarga(pallets: { kg_neto: string | number }[], graneles: { cantidad: string | number; unidad: string }[]): { pallets: number; kg: number; litros: number }`; `buscarPalletPorCodigo<T extends { pallet_codigo: string }>(pallets: T[], codigo: string): T | null`.

- [ ] **Step 1: Pruebas de las reglas**

`frontend/tests/despacho-reglas.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

import { agruparHojas, buscarPalletPorCodigo, totalesCarga } from "../src/services/despacho-reglas.ts";

test("las hojas se agrupan por lo que falta hacer, y de las despachadas solo las de hoy", () => {
  const hojas = [
    { id: 1, estado: "borrador", despachado_en: null },
    { id: 2, estado: "autorizado", despachado_en: null },
    { id: 3, estado: "despachado", despachado_en: "2026-09-24T15:00:00-03:00" },
    { id: 4, estado: "despachado", despachado_en: "2026-09-22T15:00:00-03:00" },
    { id: 5, estado: "cancelado", despachado_en: null },
  ];
  const grupos = agruparHojas(hojas, "2026-09-24");
  assert.deepEqual(grupos.borrador.map((h) => h.id), [1]);
  assert.deepEqual(grupos.autorizada.map((h) => h.id), [2]);
  assert.deepEqual(grupos.despachadaHoy.map((h) => h.id), [3]);
});

test("los totales suman kilos de pallets y de graneles en kg, y los litros aparte", () => {
  assert.deepEqual(
    totalesCarga(
      [{ kg_neto: "500.000" }, { kg_neto: 487.5 }],
      [{ cantidad: "1200", unidad: "kg" }, { cantidad: 8000, unidad: "L" }],
    ),
    { pallets: 2, kg: 2187.5, litros: 8000 },
  );
});

test("el código escaneado se busca sin importar mayúsculas ni espacios", () => {
  const pallets = [{ pallet_codigo: "PAL-001" }, { pallet_codigo: "PAL-002" }];
  assert.equal(buscarPalletPorCodigo(pallets, " pal-002 ")?.pallet_codigo, "PAL-002");
  assert.equal(buscarPalletPorCodigo(pallets, "PAL-9"), null);
});
```

Run: `cd frontend && npm test` → FAIL (módulo inexistente).

- [ ] **Step 2: Reglas**

`frontend/src/services/despacho-reglas.ts`:

```ts
import { fechaLocalISO } from "./fechas.ts";

/*
  Cómo se ordena el puesto de Despacho: por lo que falta hacer con cada hoja.
  «Despachada hoy» usa el día local de Chile, no el UTC: un camión que sale a
  las 22:00 salió hoy.
*/
export function agruparHojas<T extends { estado: string; despachado_en: string | null }>(hojas: T[], hoy: string) {
  return {
    borrador: hojas.filter((h) => h.estado === "borrador"),
    autorizada: hojas.filter((h) => h.estado === "autorizado"),
    despachadaHoy: hojas.filter(
      (h) => h.estado === "despachado" && h.despachado_en !== null && fechaLocalISO(new Date(h.despachado_en)) === hoy,
    ),
  };
}

export function totalesCarga(
  pallets: { kg_neto: string | number }[],
  graneles: { cantidad: string | number; unidad: string }[],
) {
  const suma = (valores: number[]) => Math.round(valores.reduce((a, b) => a + b, 0) * 1000) / 1000;
  return {
    pallets: pallets.length,
    kg: suma([
      ...pallets.map((p) => Number(p.kg_neto)),
      ...graneles.filter((g) => g.unidad === "kg").map((g) => Number(g.cantidad)),
    ]),
    litros: suma(graneles.filter((g) => g.unidad === "L").map((g) => Number(g.cantidad))),
  };
}

export function buscarPalletPorCodigo<T extends { pallet_codigo: string }>(pallets: T[], codigo: string): T | null {
  const buscado = codigo.trim().toUpperCase();
  return pallets.find((p) => p.pallet_codigo.toUpperCase() === buscado) ?? null;
}
```

Si la prueba de agrupar falla por zona horaria del equipo que la corre (el `fechaLocalISO` usa la hora local de la máquina), revisa cómo lo resuelve `tests/fechas.test.ts` y usa el mismo recurso; no cambies el caso de prueba para que pase.

Run: `cd frontend && npm test` → PASS.

- [ ] **Step 3: Hoja de carga (tarjeta con acciones)**

`frontend/src/pages/Despacho/HojaDeCarga.tsx`:

```tsx
import { useState } from "react";

import CampoEtiquetado from "../../components/operacion/CampoEtiquetado";
import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { claseCampo, mensajeDe } from "../../components/seccion/utilidades";
import { totalesCarga } from "../../services/despacho-reglas";
import { cantidad } from "../../services/formato";
import { autorizarDespacho, cancelarDespacho, ejecutarDespacho, type Despacho } from "../../services/inventario.service";

type Paso = "nada" | "ejecutar" | "cancelar";

/*
  Autorizar y ejecutar son pasos distintos y se ven distintos: autorizar es un
  visto bueno que se puede deshacer cancelando; ejecutar saca el producto del
  inventario y no tiene vuelta. Por eso ejecutar y cancelar pasan por resumen.
*/
export default function HojaDeCarga({ hoja, autoriza, onCambio }: {
  hoja: Despacho;
  autoriza: boolean;
  onCambio: (mensaje: string) => void;
}) {
  const [paso, setPaso] = useState<Paso>("nada");
  const [motivo, setMotivo] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const totales = totalesCarga(hoja.detalles, hoja.detalles_granel);
  const activa = hoja.estado === "borrador" || hoja.estado === "autorizado";

  const correr = async (accion: () => Promise<Despacho>, mensaje: string) => {
    setOcupado(true);
    setError("");
    try {
      await accion();
      setPaso("nada");
      onCambio(mensaje);
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo registrar la operación."));
    } finally {
      setOcupado(false);
    }
  };

  const resumenCarga = [
    { etiqueta: "Cliente", valor: hoja.cliente_nombre },
    { etiqueta: "Transporte", valor: [hoja.transportista, hoja.patente].filter(Boolean).join(" · ") || "—" },
    { etiqueta: "Pallets", valor: hoja.detalles.map((d) => `${d.pallet_codigo} (${d.ubicacion_codigo ?? "sin ubicación"})`).join(", ") || "—" },
    { etiqueta: "Total", valor: `${totales.pallets} pallets · ${cantidad(totales.kg, "kg")}${totales.litros ? ` · ${cantidad(totales.litros, "L")}` : ""}` },
  ];

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-mono text-lg font-semibold text-slate-900">{hoja.numero}</h3>
          <p className="text-sm text-slate-700">{hoja.cliente_nombre}</p>
          <p className="text-sm text-slate-600">
            {[hoja.transportista, hoja.patente, hoja.guia_despacho && `Guía ${hoja.guia_despacho}`].filter(Boolean).join(" · ") || "Sin datos de transporte"}
          </p>
        </div>
        <p className="text-right text-sm font-semibold tabular-nums text-slate-900">
          {totales.pallets} pallets<br />{cantidad(totales.kg, "kg")}
          {totales.litros > 0 && <><br />{cantidad(totales.litros, "L")}</>}
        </p>
      </header>

      <ul className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-100 text-sm">
        {hoja.detalles.map((d) => (
          <li key={d.id} className="flex flex-wrap justify-between gap-2 px-3 py-2">
            <span><span className="font-mono">{d.pallet_codigo}</span> · lote {d.lote_codigo}</span>
            <span className="tabular-nums text-slate-700">{cantidad(d.kg_neto, "kg")}{d.ubicacion_codigo ? ` · ${d.ubicacion_codigo}` : ""}</span>
          </li>
        ))}
        {hoja.detalles_granel.map((g) => (
          <li key={`g-${g.id}`} className="flex flex-wrap justify-between gap-2 px-3 py-2">
            <span>Granel {g.producto_nombre} · {g.corrida_codigo}</span>
            <span className="tabular-nums text-slate-700">{cantidad(g.cantidad, g.unidad)}</span>
          </li>
        ))}
      </ul>

      {activa && !autoriza && (
        <p className="mt-3 text-sm text-slate-600">
          {hoja.estado === "borrador" ? "Espera la autorización de quien tiene permiso para autorizar despachos." : "Autorizada: la ejecuta quien tiene permiso para autorizar despachos."}
        </p>
      )}

      {activa && autoriza && paso === "nada" && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {hoja.estado === "borrador" && (
            <button type="button" disabled={ocupado} onClick={() => void correr(() => autorizarDespacho(hoja.id), `Hoja ${hoja.numero} autorizada.`)}
              className="rounded-xl border-2 border-blue-700 px-5 py-2.5 text-sm font-semibold text-blue-800 hover:bg-blue-50 disabled:opacity-40">
              Autorizar
            </button>
          )}
          {hoja.estado === "autorizado" && (
            <button type="button" onClick={() => setPaso("ejecutar")}
              className="rounded-xl bg-green-700 px-6 py-3 text-sm font-bold text-white hover:bg-green-800">
              Ejecutar salida
            </button>
          )}
          <button type="button" onClick={() => setPaso("cancelar")} className="ml-auto text-sm font-medium text-red-700 underline-offset-2 hover:underline">
            Cancelar hoja
          </button>
        </div>
      )}

      {paso === "ejecutar" && (
        <div className="mt-4">
          <ConfirmarAccion
            titulo={`Ejecutar la salida de ${hoja.numero}`}
            filas={resumenCarga}
            advertencia="Los pallets salen del inventario. No se puede deshacer."
            textoConfirmar="Confirmar salida"
            ocupado={ocupado}
            error={error}
            onConfirmar={() => void correr(() => ejecutarDespacho(hoja.id), `Salida de ${hoja.numero} registrada.`)}
            onVolver={() => { setPaso("nada"); setError(""); }}
          />
        </div>
      )}

      {paso === "cancelar" && (
        <div className="mt-4 space-y-3">
          <CampoEtiquetado etiqueta="Motivo de la cancelación">
            <input value={motivo} onChange={(e) => setMotivo(e.target.value)} className={claseCampo} />
          </CampoEtiquetado>
          <ConfirmarAccion
            titulo={`Cancelar ${hoja.numero}`}
            filas={[...resumenCarga, { etiqueta: "Motivo", valor: motivo.trim() || "— (obligatorio)" }]}
            advertencia="La hoja queda cancelada, no se borra. Sus pallets vuelven a poder cargarse."
            textoConfirmar="Cancelar hoja"
            peligro
            ocupado={ocupado}
            error={error}
            onConfirmar={() => {
              if (!motivo.trim()) { setError("Escribe el motivo de la cancelación."); return; }
              void correr(() => cancelarDespacho(hoja.id, motivo.trim()), `Hoja ${hoja.numero} cancelada.`);
            }}
            onVolver={() => { setPaso("nada"); setError(""); }}
          />
        </div>
      )}

      {paso === "nada" && error && <p role="alert" className="mt-3 rounded-xl bg-red-50 px-4 py-2 text-sm text-red-800">{error}</p>}
    </article>
  );
}
```

- [ ] **Step 4: Nueva hoja de carga**

`frontend/src/pages/Despacho/NuevaHojaCarga.tsx`:

```tsx
import { useState, type FormEvent } from "react";

import BuscadorCodigo from "../../components/operacion/BuscadorCodigo";
import CampoEtiquetado from "../../components/operacion/CampoEtiquetado";
import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { claseBoton, claseCampo, mensajeDe } from "../../components/seccion/utilidades";
import { buscarPalletPorCodigo, totalesCarga } from "../../services/despacho-reglas";
import { cantidad } from "../../services/formato";
import {
  crearDespacho, type ClienteDespacho, type ExistenciaProductoTerminado, type GranelDisponible,
} from "../../services/inventario.service";

/*
  Una hoja de carga es un camión: un cliente, un transporte y varios pallets.
  El número lo asigna el sistema al guardar; la guía del SII es opcional.
*/
export default function NuevaHojaCarga({ clientes, disponibles, graneles, onCreada, onCerrar }: {
  clientes: ClienteDespacho[];
  disponibles: ExistenciaProductoTerminado[];
  graneles: GranelDisponible[];
  onCreada: (mensaje: string) => void;
  onCerrar: () => void;
}) {
  const [cliente, setCliente] = useState("");
  const [transportista, setTransportista] = useState("");
  const [patente, setPatente] = useState("");
  const [guia, setGuia] = useState("");
  const [elegidos, setElegidos] = useState<number[]>([]);
  const [granel, setGranel] = useState<Record<number, string>>({});
  const [paso, setPaso] = useState<"datos" | "resumen">("datos");
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const pallets = disponibles.filter((p) => elegidos.includes(p.pallet));
  const granelElegido = graneles
    .filter((g) => granel[g.id] !== undefined)
    .map((g) => ({ salida: g, cantidad: Number(granel[g.id].replace(",", ".")) }));
  const totales = totalesCarga(pallets, granelElegido.map((g) => ({ cantidad: g.cantidad, unidad: g.salida.unidad })));
  const clienteElegido = clientes.find((c) => String(c.id) === cliente);

  const alternar = (pallet: number) =>
    setElegidos((actual) => (actual.includes(pallet) ? actual.filter((id) => id !== pallet) : [...actual, pallet]));

  const escanear = (codigo: string) => {
    const encontrado = buscarPalletPorCodigo(disponibles, codigo);
    if (!encontrado) {
      setAviso(`El pallet ${codigo} no está disponible para cargar: no existe, no está liberado en una ubicación disponible o ya está en otra hoja.`);
      return;
    }
    setAviso(elegidos.includes(encontrado.pallet) ? `${encontrado.pallet_codigo} ya estaba en la hoja.` : `${encontrado.pallet_codigo} agregado.`);
    if (!elegidos.includes(encontrado.pallet)) setElegidos((actual) => [...actual, encontrado.pallet]);
  };

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (!clienteElegido) return setError("Elige el cliente.");
    if (pallets.length === 0 && granelElegido.length === 0) return setError("Agrega al menos un pallet o un granel.");
    const malo = granelElegido.find((g) => !(g.cantidad > 0) || g.cantidad > Number(g.salida.cantidad_disponible));
    if (malo) return setError(`La cantidad de ${malo.salida.producto_nombre} debe ser mayor que cero y hasta ${cantidad(malo.salida.cantidad_disponible, malo.salida.unidad)}.`);
    setError("");
    setPaso("resumen");
  };

  const guardar = async () => {
    setOcupado(true);
    setError("");
    try {
      const hoja = await crearDespacho({
        cliente: Number(cliente),
        pallet_ids: pallets.map((p) => p.pallet),
        graneles: granelElegido.map((g) => ({ salida: g.salida.id, cantidad: g.cantidad })),
        transportista: transportista.trim(), patente: patente.trim().toUpperCase(), guia_despacho: guia.trim(),
      });
      onCreada(`Hoja ${hoja.numero} creada en borrador con ${totales.pallets} pallets.`);
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo crear la hoja de carga."));
    } finally {
      setOcupado(false);
    }
  };

  return (
    <section aria-labelledby="nueva-hoja-titulo" className="rounded-2xl border border-green-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-4">
        <h2 id="nueva-hoja-titulo" className="text-lg font-semibold text-slate-900">Nueva hoja de carga</h2>
        <button type="button" onClick={onCerrar} className="text-sm font-medium text-slate-600 hover:text-slate-900">Cerrar</button>
      </div>

      {paso === "resumen" ? (
        <ConfirmarAccion
          titulo="Revisa la hoja antes de guardarla"
          filas={[
            { etiqueta: "Cliente", valor: clienteElegido?.nombre ?? "—" },
            { etiqueta: "Transporte", valor: [transportista.trim(), patente.trim().toUpperCase()].filter(Boolean).join(" · ") || "—" },
            { etiqueta: "Guía de despacho", valor: guia.trim() || "Sin guía" },
            { etiqueta: "Pallets", valor: pallets.map((p) => p.pallet_codigo).join(", ") || "—" },
            { etiqueta: "Total", valor: `${totales.pallets} pallets · ${cantidad(totales.kg, "kg")}${totales.litros ? ` · ${cantidad(totales.litros, "L")}` : ""}` },
          ]}
          advertencia="Queda en borrador: la salida se ejecuta después de autorizarla."
          textoConfirmar="Guardar hoja"
          ocupado={ocupado}
          error={error}
          onConfirmar={() => void guardar()}
          onVolver={() => { setPaso("datos"); setError(""); }}
        />
      ) : (
        <form onSubmit={revisar} className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <CampoEtiquetado etiqueta="Cliente">
              <select value={cliente} onChange={(e) => setCliente(e.target.value)} className={claseCampo}>
                <option value="">Elige el cliente…</option>
                {clientes.filter((c) => c.activo).map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            </CampoEtiquetado>
            <CampoEtiquetado etiqueta="Transportista">
              <input value={transportista} onChange={(e) => setTransportista(e.target.value)} className={claseCampo} />
            </CampoEtiquetado>
            <CampoEtiquetado etiqueta="Patente">
              <input value={patente} onChange={(e) => setPatente(e.target.value)} className={claseCampo} autoComplete="off" />
            </CampoEtiquetado>
            <CampoEtiquetado etiqueta="Guía de despacho (opcional)" ayuda="La del SII, si ya está emitida.">
              <input value={guia} onChange={(e) => setGuia(e.target.value)} className={claseCampo} autoComplete="off" />
            </CampoEtiquetado>
          </div>

          <BuscadorCodigo etiqueta="Agregar pallet por código" onBuscar={escanear} />
          {aviso && <p role="status" className="text-sm text-slate-700">{aviso}</p>}

          <fieldset className="rounded-xl border border-slate-200">
            <legend className="px-2 text-sm font-medium text-slate-700">Pallets disponibles ({disponibles.length})</legend>
            {disponibles.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-600">No hay pallets liberados en ubicaciones disponibles sin otra hoja.</p>
            ) : (
              <ul className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
                {disponibles.map((p) => (
                  <li key={p.id}>
                    <label className="flex cursor-pointer flex-wrap items-center gap-3 px-4 py-2 text-sm hover:bg-slate-50">
                      <input type="checkbox" checked={elegidos.includes(p.pallet)} onChange={() => alternar(p.pallet)} className="h-4 w-4" />
                      <span className="font-mono">{p.pallet_codigo}</span>
                      <span className="text-slate-700">{p.producto_nombre} · lote {p.lote_codigo}</span>
                      <span className="ml-auto tabular-nums text-slate-700">{cantidad(p.kg_neto, "kg")} · {p.ubicacion_codigo}</span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </fieldset>

          {graneles.length > 0 && (
            <fieldset className="rounded-xl border border-slate-200">
              <legend className="px-2 text-sm font-medium text-slate-700">Graneles liberados</legend>
              <ul className="divide-y divide-slate-100">
                {graneles.map((g) => (
                  <li key={g.id} className="flex flex-wrap items-center gap-3 px-4 py-2 text-sm">
                    <label className="flex items-center gap-3">
                      <input type="checkbox" checked={granel[g.id] !== undefined} className="h-4 w-4"
                        onChange={() => setGranel((actual) => {
                          const copia = { ...actual };
                          if (copia[g.id] !== undefined) delete copia[g.id]; else copia[g.id] = String(g.cantidad_disponible);
                          return copia;
                        })} />
                      {g.producto_nombre} · {g.corrida_codigo} · hasta {cantidad(g.cantidad_disponible, g.unidad)}
                    </label>
                    {granel[g.id] !== undefined && (
                      <input aria-label={`Cantidad de ${g.producto_nombre} (${g.unidad})`} inputMode="decimal" value={granel[g.id]}
                        onChange={(e) => setGranel((actual) => ({ ...actual, [g.id]: e.target.value }))} className={`${claseCampo} ml-auto w-32`} />
                    )}
                  </li>
                ))}
              </ul>
            </fieldset>
          )}

          <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-900 px-5 py-3 text-white">
            <p className="text-sm font-semibold tabular-nums" aria-live="polite">
              {totales.pallets} pallets · {cantidad(totales.kg, "kg")}{totales.litros ? ` · ${cantidad(totales.litros, "L")}` : ""}
            </p>
            <button type="submit" className={claseBoton}>Revisar hoja</button>
          </div>
          {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-2 text-sm text-red-800">{error}</p>}
        </form>
      )}
    </section>
  );
}
```

- [ ] **Step 5: El puesto**

`frontend/src/pages/Despacho/PuestoDespacho.tsx`:

```tsx
import { useState } from "react";
import { Plus } from "lucide-react";

import { Vacio } from "../../components/seccion/componentes";
import { claseBoton, useCarga } from "../../components/seccion/utilidades";
import { agruparHojas } from "../../services/despacho-reglas";
import { fechaLocalISO } from "../../services/fechas";
import {
  obtenerClientesDespacho, obtenerGranelDisponible, obtenerHojasVigentes, obtenerPalletsCargables, type Despacho,
} from "../../services/inventario.service";
import { puedeAutorizarDespacho, puedeDespachar } from "../../services/permisos-despacho";
import { obtenerSesion } from "../../services/sesion";
import HojaDeCarga from "./HojaDeCarga";
import NuevaHojaCarga from "./NuevaHojaCarga";

function Grupo({ titulo, hojas, autoriza, vacio, onCambio }: {
  titulo: string; hojas: Despacho[]; autoriza: boolean; vacio: string; onCambio: (m: string) => void;
}) {
  return (
    <section aria-label={titulo} className="space-y-3">
      <h2 className="text-lg font-semibold text-slate-900">{titulo} ({hojas.length})</h2>
      {hojas.length === 0 ? <Vacio>{vacio}</Vacio> : hojas.map((h) => <HojaDeCarga key={h.id} hoja={h} autoriza={autoriza} onCambio={onCambio} />)}
    </section>
  );
}

/* Abre en las hojas que falta sacar: lo primero que se decide al llegar un camión. */
export default function PuestoDespacho() {
  const usuario = obtenerSesion()?.usuario;
  const crea = puedeDespachar(usuario);
  const autoriza = puedeAutorizarDespacho(usuario);
  const hojas = useCarga(obtenerHojasVigentes);
  const clientes = useCarga(obtenerClientesDespacho);
  const disponibles = useCarga(obtenerPalletsCargables);
  const graneles = useCarga(obtenerGranelDisponible);
  const [nueva, setNueva] = useState(false);
  const [mensaje, setMensaje] = useState("");

  const cambio = (texto: string) => {
    setMensaje(texto);
    setNueva(false);
    void hojas.recargar();
    void disponibles.recargar();
    void graneles.recargar();
  };

  const grupos = agruparHojas(hojas.datos ?? [], fechaLocalISO());

  return (
    <div className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-green-700">Puesto de trabajo</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-900">Despacho</h1>
            <p className="mt-2 max-w-2xl text-slate-600">Arma la hoja de carga del camión, autorízala y ejecuta la salida.</p>
          </div>
          {crea && !nueva && (
            <button type="button" onClick={() => { setNueva(true); setMensaje(""); }} className={`${claseBoton} inline-flex items-center gap-2`}>
              <Plus className="h-4 w-4" /> Nueva hoja de carga
            </button>
          )}
        </header>

        {mensaje && <p role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">{mensaje}</p>}

        {nueva && (
          <>
            {(clientes.error || disponibles.error || graneles.error) && (
              <p role="alert" className="text-sm text-red-800">
                {[clientes.error && "clientes", disponibles.error && "pallets disponibles", graneles.error && "graneles"].filter(Boolean).join(", ")}: no se pudo cargar.
              </p>
            )}
            <NuevaHojaCarga
              clientes={clientes.datos ?? []}
              disponibles={disponibles.datos ?? []}
              graneles={graneles.datos ?? []}
              onCreada={cambio}
              onCerrar={() => setNueva(false)}
            />
          </>
        )}

        {hojas.error && <p role="alert" className="text-sm text-red-800">{hojas.error}</p>}
        {hojas.cargando && !hojas.datos && <p className="text-sm text-slate-600">Cargando hojas de carga…</p>}

        <Grupo titulo="Autorizadas" hojas={grupos.autorizada} autoriza={autoriza} vacio="No hay hojas autorizadas esperando salida." onCambio={cambio} />
        <Grupo titulo="Borrador" hojas={grupos.borrador} autoriza={autoriza} vacio="No hay hojas en borrador." onCambio={cambio} />
        <Grupo titulo="Despachadas hoy" hojas={grupos.despachadaHoy} autoriza={false} vacio="Hoy no ha salido ninguna hoja." onCambio={cambio} />
      </div>
    </div>
  );
}
```

(Las autorizadas van primero: son las que tienen un camión esperando. Si `fechaLocalISO()` no acepta llamarse sin argumento, pásale `new Date()`.)

- [ ] **Step 6: Ruta, destino inicial y menú**

En `routes.tsx`: `const PuestoDespacho = lazy(() => import("../pages/Despacho/PuestoDespacho"));` y

```tsx
                    <Route element={<RutaModulo modulo="despacho" />}>
                        <Route path="/despacho" element={diferido(<PuestoDespacho />)} />
                    </Route>
```

En `access-control.ts`, `destinoInicial` → `despacho: "/despacho"`. En `navegacion-operacional.ts`, después de «Bodega»:

```ts
      { etiqueta: "Despacho", ruta: "/despacho", modulo: "despacho", icono: "despacho" },
```

En `tests/navegacion-operacional.test.ts`:

```ts
test("Despacho aparece en el menú solo con la capacidad", () => {
  const despacho = usuarioDeArea("despacho", "Despacho", null);
  assert.ok(!etiquetas(despacho, "Envasado y logística").includes("Despacho"));
  assert.ok(etiquetas({ ...despacho, capacidades: ["despacho_crear"] }, "Envasado y logística").includes("Despacho"));
});
```

- [ ] **Step 7: Verificar**

Run: `cd frontend && npx tsc -b --pretty false && npx eslint src/pages/Despacho src/services src/app/routes.tsx && npm test`
Expected: sin errores; PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/Despacho frontend/src/services/despacho-reglas.ts frontend/tests/despacho-reglas.test.ts frontend/src/app/routes.tsx frontend/src/services/access-control.ts frontend/src/services/navegacion-operacional.ts frontend/tests/navegacion-operacional.test.ts
git commit -m "feat(despacho): puesto de Despacho con hojas de carga de varios pallets"
```

---

### Task 9: Existencias de solo lectura y E2E al día

**Files:**
- Modify (reescritura): `frontend/src/pages/Inventario/Inventario.tsx`
- Create: `frontend/src/pages/Inventario/TablaConsulta.tsx`
- Delete: `frontend/src/pages/Inventario/OperacionesBodega.tsx`
- Modify: `frontend/src/services/navegacion-operacional.ts` (etiqueta «Existencias»), `frontend/tests/navegacion-operacional.test.ts` si fija la etiqueta vieja
- Modify: `frontend/e2e/flujo-polvo-continuacion.spec.ts` (paso 7) y los specs que despachan desde `/inventario`: `flujo-descremado.spec.ts`, `flujo-precondensado-despacho.spec.ts`, `flujo-mantequilla.spec.ts`, `flujo-suero.spec.ts`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `buscarExistencias`, `buscarProductoTerminado`, `buscarMovimientos`, `buscarMovimientosProductoTerminado`, `obtenerUbicaciones`, `obtenerCatalogosInventario` (con las claves de la Task 3), `cantidad`, `ReworkInventario` (existente), `Pagina`.
- Produces: `TablaConsulta<T>` genérica: `{ cargar: (filtros: FiltrosInventario) => Promise<Pagina<T>>; columnas: { titulo: string; celda: (fila: T) => ReactNode; numerica?: boolean }[]; clave: (fila: T) => string | number; estados: { valor: string; texto: string }[]; etiquetaEstado?: string; conFechas?: boolean; ubicaciones: UbicacionInventario[]; etiquetaBusqueda: string; vacio: string; filtrosFijos?: FiltrosInventario }`.

- [ ] **Step 1: Tabla de consulta genérica**

`frontend/src/pages/Inventario/TablaConsulta.tsx`:

```tsx
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";

import CampoEtiquetado from "../../components/operacion/CampoEtiquetado";
import { claseBoton, claseCampo, claseCelda, claseEncabezado } from "../../components/seccion/utilidades";
import type { Pagina } from "../../services/paginacion";
import type { FiltrosInventario, UbicacionInventario } from "../../services/inventario.service";

export interface Columna<T> {
  titulo: string;
  celda: (fila: T) => ReactNode;
  numerica?: boolean;
}

/*
  Una pestaña de consulta: filtros arriba, una página del servidor abajo, y
  su propio error. Los filtros viajan al servidor porque la lista está
  paginada: filtrar en el cliente sería filtrar solo la primera página.
*/
export default function TablaConsulta<T>({
  cargar, columnas, clave, estados, etiquetaEstado = "Estado", conFechas = false, ubicaciones, etiquetaBusqueda, vacio,
  filtrosFijos = {},
}: {
  cargar: (filtros: FiltrosInventario) => Promise<Pagina<T>>;
  columnas: Columna<T>[];
  clave: (fila: T) => string | number;
  estados: { valor: string; texto: string }[];
  etiquetaEstado?: string;
  conFechas?: boolean;
  ubicaciones: UbicacionInventario[];
  etiquetaBusqueda: string;
  vacio: string;
  filtrosFijos?: FiltrosInventario;
}) {
  const [borrador, setBorrador] = useState<FiltrosInventario>({});
  const [filtros, setFiltros] = useState<FiltrosInventario>({});
  const [pagina, setPagina] = useState(1);
  const [datos, setDatos] = useState<Pagina<T> | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const traer = useCallback(async () => {
    setCargando(true);
    try {
      setDatos(await cargar({ ...filtrosFijos, ...filtros, page: pagina }));
      setError("");
    } catch {
      setError("No se pudo cargar esta consulta.");
    } finally {
      setCargando(false);
    }
    // filtrosFijos se compara por contenido: un objeto literal cambia de identidad en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cargar, filtros, pagina, JSON.stringify(filtrosFijos)]);

  useEffect(() => {
    const t = setTimeout(() => void traer(), 0);
    return () => clearTimeout(t);
  }, [traer]);

  const aplicar = (evento: FormEvent) => {
    evento.preventDefault();
    setPagina(1);
    setFiltros(borrador);
  };

  const total = datos?.count ?? 0;
  const desde = total === 0 ? 0 : (pagina - 1) * 50 + 1;
  const hasta = Math.min(pagina * 50, total);

  return (
    <div className="space-y-4">
      <form onSubmit={aplicar} className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-6">
        <div className="lg:col-span-2">
          <CampoEtiquetado etiqueta={etiquetaBusqueda}>
            <input type="search" value={borrador.q ?? ""} onChange={(e) => setBorrador({ ...borrador, q: e.target.value })} className={claseCampo} />
          </CampoEtiquetado>
        </div>
        {estados.length > 0 && (
          <CampoEtiquetado etiqueta={etiquetaEstado}>
            <select value={borrador.estado ?? ""} onChange={(e) => setBorrador({ ...borrador, estado: e.target.value })} className={claseCampo}>
              <option value="">Todos</option>
              {estados.map((s) => <option key={s.valor} value={s.valor}>{s.texto}</option>)}
            </select>
          </CampoEtiquetado>
        )}
        <CampoEtiquetado etiqueta="Ubicación">
          <select value={borrador.ubicacion ?? ""} onChange={(e) => setBorrador({ ...borrador, ubicacion: e.target.value ? Number(e.target.value) : "" })} className={claseCampo}>
            <option value="">Todas</option>
            {ubicaciones.map((u) => <option key={u.id} value={u.id}>{u.codigo} · {u.bodega_nombre}</option>)}
          </select>
        </CampoEtiquetado>
        {conFechas && (
          <>
            <CampoEtiquetado etiqueta="Desde">
              <input type="date" value={borrador.desde ?? ""} onChange={(e) => setBorrador({ ...borrador, desde: e.target.value })} className={claseCampo} />
            </CampoEtiquetado>
            <CampoEtiquetado etiqueta="Hasta">
              <input type="date" value={borrador.hasta ?? ""} onChange={(e) => setBorrador({ ...borrador, hasta: e.target.value })} className={claseCampo} />
            </CampoEtiquetado>
          </>
        )}
        <div className="flex items-end">
          <button type="submit" className={claseBoton}>Filtrar</button>
        </div>
      </form>

      {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}

      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <table className="min-w-full">
          <thead className="bg-slate-50">
            <tr>{columnas.map((c) => <th key={c.titulo} scope="col" className={`${claseEncabezado} ${c.numerica ? "text-right" : ""}`}>{c.titulo}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {datos?.results.map((fila) => (
              <tr key={clave(fila)}>
                {columnas.map((c) => <td key={c.titulo} className={`${claseCelda} ${c.numerica ? "text-right tabular-nums" : ""}`}>{c.celda(fila)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {!cargando && datos && datos.results.length === 0 && <p className="px-5 py-4 text-sm text-slate-600">{vacio}</p>}
        {cargando && <p className="px-5 py-4 text-sm text-slate-600">Cargando…</p>}
      </div>

      <nav aria-label="Páginas" className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-700">
        <span>{total === 0 ? "Sin resultados" : `${desde}–${hasta} de ${total}`}</span>
        <span className="flex gap-2">
          <button type="button" disabled={!datos?.previous || cargando} onClick={() => setPagina((p) => p - 1)} className="rounded-xl border border-slate-300 px-4 py-2 disabled:opacity-40">Anterior</button>
          <button type="button" disabled={!datos?.next || cargando} onClick={() => setPagina((p) => p + 1)} className="rounded-xl border border-slate-300 px-4 py-2 disabled:opacity-40">Siguiente</button>
        </span>
      </nav>
    </div>
  );
}
```

(El tamaño de página 50 es `PAGE_SIZE` del backend; si el linter rechaza el `eslint-disable`, reemplaza la dependencia por un `useMemo` sobre `JSON.stringify(filtrosFijos)`.)

- [ ] **Step 2: Existencias**

Reemplaza **por completo** `frontend/src/pages/Inventario/Inventario.tsx`:

```tsx
import { useState } from "react";

import { useCarga } from "../../components/seccion/utilidades";
import { cantidad } from "../../services/formato";
import {
  buscarExistencias, buscarMovimientos, buscarMovimientosProductoTerminado, buscarProductoTerminado,
  obtenerCatalogosInventario, obtenerUbicaciones,
  type Existencia, type ExistenciaProductoTerminado, type FiltrosInventario, type MovimientoInventario, type MovimientoProductoTerminado,
} from "../../services/inventario.service";
import ReworkInventario from "./ReworkInventario";
import TablaConsulta from "./TablaConsulta";

type Pestana = "materiales" | "producto" | "movimientos" | "movimientos-pallets" | "rework";

const PESTANAS: { id: Pestana; texto: string }[] = [
  { id: "materiales", texto: "Materiales" },
  { id: "producto", texto: "Producto terminado" },
  { id: "movimientos", texto: "Movimientos de materiales" },
  { id: "movimientos-pallets", texto: "Movimientos de pallets" },
  { id: "rework", texto: "Rework" },
];

const fechaHora = (iso: string) =>
  new Date(iso).toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" });

const SOLO_CON_SALDO: FiltrosInventario = { con_saldo: true };

type Opcion = { valor: string; etiqueta: string };
const aEstados = (opciones: Opcion[] | undefined) =>
  (opciones ?? []).map((o) => ({ valor: o.valor, texto: o.etiqueta }));

/*
  Consulta de solo lectura. Los movimientos se registran en los puestos de
  Bodega y Despacho; aquí se mira qué hay, dónde y qué pasó.
*/
export default function Inventario() {
  const [pestana, setPestana] = useState<Pestana>("producto");
  const ubicaciones = useCarga(obtenerUbicaciones);
  // Auxiliares: si fallan, la consulta igual carga, sin esos desplegables.
  const catalogos = useCarga(obtenerCatalogosInventario);
  const lista = ubicaciones.datos ?? [];
  const opciones = catalogos.datos;

  return (
    <div className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <header>
          <p className="text-sm font-semibold uppercase tracking-wider text-green-700">Consulta</p>
          <h1 className="mt-1 text-3xl font-bold text-slate-900">Existencias</h1>
          <p className="mt-2 max-w-2xl text-slate-600">Qué hay, dónde está y qué se movió. Para registrar un movimiento, usa los puestos de Bodega o Despacho.</p>
        </header>

        <div role="tablist" aria-label="Consultas de inventario" className="flex gap-1 overflow-x-auto border-b border-slate-200">
          {PESTANAS.map((p) => (
            <button key={p.id} type="button" role="tab" aria-selected={pestana === p.id} onClick={() => setPestana(p.id)}
              className={`whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium ${pestana === p.id ? "border-green-700 text-green-800" : "border-transparent text-slate-600 hover:text-slate-800"}`}>
              {p.texto}
            </button>
          ))}
        </div>

        <div role="tabpanel">
          {pestana === "materiales" && (
            <TablaConsulta<Existencia>
              cargar={buscarExistencias}
              filtrosFijos={SOLO_CON_SALDO}
              clave={(f) => f.id}
              ubicaciones={lista}
              etiquetaBusqueda="Material o lote"
              vacio="No hay material con saldo que coincida."
              estados={aEstados(opciones?.estado_calidad)}
              columnas={[
                { titulo: "Material", celda: (f) => <>{f.insumo_nombre}<span className="block text-xs text-slate-600">{f.insumo_codigo}</span></> },
                { titulo: "Lote", celda: (f) => <span className="font-mono">{f.lote_codigo}</span> },
                { titulo: "Ubicación", celda: (f) => `${f.ubicacion_codigo} · ${f.bodega_nombre}` },
                { titulo: "Calidad", celda: (f) => f.estado_calidad },
                { titulo: "Físico", numerica: true, celda: (f) => cantidad(f.cantidad_fisica, f.unidad) },
                { titulo: "Disponible", numerica: true, celda: (f) => cantidad(f.cantidad_disponible, f.unidad) },
              ]}
            />
          )}
          {pestana === "producto" && (
            <TablaConsulta<ExistenciaProductoTerminado>
              cargar={buscarProductoTerminado}
              clave={(f) => f.id}
              ubicaciones={lista}
              etiquetaBusqueda="Pallet, lote o producto"
              vacio="No hay pallets que coincidan."
              estados={aEstados(opciones?.estado_pallet)}
              columnas={[
                { titulo: "Pallet", celda: (f) => <span className="font-mono">{f.pallet_codigo}</span> },
                { titulo: "Producto", celda: (f) => f.producto_nombre },
                { titulo: "Lote", celda: (f) => <span className="font-mono">{f.lote_codigo}</span> },
                { titulo: "Ubicación", celda: (f) => f.ubicacion_codigo },
                { titulo: "Estado", celda: (f) => f.estado_inventario },
                { titulo: "Peso", numerica: true, celda: (f) => cantidad(f.kg_neto, "kg") },
              ]}
            />
          )}
          {pestana === "movimientos" && (
            <TablaConsulta<MovimientoInventario>
              cargar={buscarMovimientos}
              clave={(f) => f.id}
              ubicaciones={lista}
              conFechas
              etiquetaBusqueda="Material o lote"
              vacio="No hay movimientos que coincidan."
              estados={aEstados(opciones?.tipo_movimiento)}
              etiquetaEstado="Tipo"
              columnas={[
                { titulo: "Fecha", celda: (f) => fechaHora(f.fecha) },
                { titulo: "Tipo", celda: (f) => f.tipo_etiqueta },
                { titulo: "Material", celda: (f) => <>{f.insumo_nombre}<span className="block font-mono text-xs text-slate-600">{f.lote_codigo}</span></> },
                { titulo: "Origen → destino", celda: (f) => `${f.origen_codigo ?? "—"} → ${f.destino_codigo ?? "—"}` },
                { titulo: "Cantidad", numerica: true, celda: (f) => cantidad(f.cantidad, f.unidad) },
                { titulo: "Usuario", celda: (f) => f.usuario_nombre },
              ]}
            />
          )}
          {pestana === "movimientos-pallets" && (
            <TablaConsulta<MovimientoProductoTerminado>
              cargar={buscarMovimientosProductoTerminado}
              clave={(f) => f.id}
              ubicaciones={lista}
              conFechas
              etiquetaBusqueda="Pallet o lote"
              vacio="No hay movimientos de pallets que coincidan."
              estados={aEstados(opciones?.tipo_movimiento_pallet)}
              etiquetaEstado="Tipo"
              columnas={[
                { titulo: "Fecha", celda: (f) => fechaHora(f.registrado_en) },
                { titulo: "Tipo", celda: (f) => f.tipo_etiqueta },
                { titulo: "Pallet", celda: (f) => <>{f.pallet_codigo}<span className="block font-mono text-xs text-slate-600">{f.lote_codigo}</span></> },
                { titulo: "Origen → destino", celda: (f) => `${f.origen_codigo ?? "—"} → ${f.destino_codigo ?? "—"}` },
                { titulo: "Peso", numerica: true, celda: (f) => cantidad(f.kg_neto, "kg") },
                { titulo: "Usuario", celda: (f) => f.registrado_por_nombre },
              ]}
            />
          )}
          {pestana === "rework" && <ReworkInventario />}
        </div>
      </div>
    </div>
  );
}
```

Los `estados` de cada pestaña vienen de `inventario/catalogos/` (Task 3), no se escriben aquí. Verifica también cómo `ReworkInventario` se montaba en el `Inventario.tsx` viejo (props que recibía) y pásale lo mismo.

Borra `frontend/src/pages/Inventario/OperacionesBodega.tsx` (`git rm`). Comprueba con `grep -rn "OperacionesBodega\|obtenerEstadoOperacionalInventario" frontend/src` que nada más lo usa; si `obtenerEstadoOperacionalInventario` queda sin uso, déjala (el endpoint sigue existiendo y otras pantallas pueden quererla) — solo borra el import muerto.

En `navegacion-operacional.ts`, la entrada `/inventario` pasa a `{ etiqueta: "Existencias", ruta: "/inventario", modulo: "inventario", icono: "documentos" }`. Actualiza las pruebas que fijen «Inventario y despacho».

- [ ] **Step 3: Verificar frontend**

Run: `cd frontend && npx tsc -b --pretty false && npx eslint src && npm test`
Expected: sin errores; PASS.

- [ ] **Step 4: E2E al día**

En `frontend/e2e/flujo-polvo-continuacion.spec.ts`, paso 7, reemplaza el cuerpo después de `irA(page, "/inventario")` por:

```ts
    await page.getByRole("tab", { name: "Producto terminado" }).click();
    await page.getByLabel("Pallet, lote o producto").fill(pallet);
    await page.getByRole("button", { name: "Filtrar" }).click();
    const fila = page.getByRole("row").filter({ hasText: pallet });
    await expect(fila).toBeVisible({ timeout: 20_000 });
    await expect(fila).toContainText(flujo.lote);
    await expect(fila).toContainText("500 kg");
    await expect(fila).toContainText("disponible");
    await expect(fila).toContainText("PT-DISP");
```

(`"Productos"` era el botón de la pestaña vieja; ahora es un `tab`.)

En los otros cuatro specs, cada paso que hacía `irA(page, "/inventario")` para **ingresar, transferir o despachar** pasa al puesto que corresponde: ingresar/transferir un pallet → `/bodega` (buscar el código con el campo «Pallet, lote o material», botón «Ubicar» o «Reubicar», elegir «Destino», «Revisar», «Registrar movimiento»); despachar → `/despacho` («Nueva hoja de carga», «Cliente», marcar el pallet o granel, «Revisar hoja», «Guardar hoja», luego «Autorizar», «Ejecutar salida», «Confirmar salida»). Los pasos que solo **miran** existencias se quedan en `/inventario` con el patrón de arriba. Donde un spec tecleaba el número de despacho, quita esa línea: ahora lo asigna el sistema. Mantén las esperas `trasGuardar(page, "/api/inventario/despachos/", …)` sobre las rutas que siguen existiendo. Tras editarlos, `npx tsc -p e2e` (o el `tsconfig` que los cubra) debe pasar.

- [ ] **Step 5: Documentar en `CLAUDE.md`**

En «Decisiones vigentes», agrega:

```markdown
- **Bodega y Despacho son puestos de trabajo, Existencias es consulta** (desde 2026-09-24, `docs/superpowers/specs/2026-09-24-puestos-bodega-despacho-design.md`). `/bodega` abre en un buscador por código y en los pendientes (`inventario/pendientes-bodega/`); cada movimiento es un panel guiado que termina en `ConfirmarAccion`. `/despacho` agrupa las hojas de carga por lo que falta hacer. `/inventario` ya no registra nada: filtra y pagina **en el servidor**, porque filtrar en el cliente es filtrar la primera página. Toda cantidad pasa por `cantidad(valor, unidad)`: «13.000» son trece unidades y en Chile se lee trece mil. Quién despacha lo deciden **solo las capacidades** (`permisos-despacho.ts`), igual que el servidor. Abastecimiento volvió como sección de compras; lo de bodega vive en el puesto.
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Inventario frontend/src/services/navegacion-operacional.ts frontend/tests/navegacion-operacional.test.ts frontend/e2e/*.spec.ts CLAUDE.md
git commit -m "feat(inventario): Existencias como consulta paginada; E2E en los puestos nuevos"
```

(Antes del commit, `git status` no debe listar `frontend/e2e/.auth/estado.json` como agregado.)

---

### Task 10: Aceptación (la corre el controlador)

No es tarea de un implementador: necesita los servidores levantados y escribe en la base de desarrollo.

- [ ] **Step 1: Backend completo**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test --noinput`
Expected: todo verde salvo el error preexistente `usuarios.tests_comando_e2e.SinDimensionFuncionalDeEmpresa` (contradicción anterior a este trabajo). Cualquier otro rojo se corrige antes de seguir.

- [ ] **Step 2: Frontend completo**

Run: `cd frontend && npx tsc -b --pretty false && npx eslint . && npm test`
Expected: limpio.

- [ ] **Step 3: Servidor al día**

Reiniciar el backend (`runserver 127.0.0.1:8000 --noreload`) y correr `manage.py migrate`. Vite recarga solo.

- [ ] **Step 4: Cadena E2E**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py preparar_circuito_polvo --aplicar`, comprobar que hay un evaporador libre (sin tocar `EJ-PROD-72`), y luego
`cd frontend && E2E_USUARIO=e2e_auditoria E2E_CLAVE=auditoria-e2e-ccaa E2E_CLAVE_AREAS=flujo-e2e-ccaa npx playwright test --project=circuito --project=flujo-polvo`
Expected: 4/4.

- [ ] **Step 5: Recorrido manual de los puestos**

Con Playwright (o a mano), como `e2e_bodega`/`e2e_despacho` o un superusuario: en `/bodega`, buscar el pallet del paso anterior, reubicarlo y ver el mensaje con el destino; registrar un conteo y comprobar que otra cuenta lo ve en «Ajustes por aprobar» y la propia no; en `/despacho`, armar una hoja con dos pallets, ver el número `DE…` asignado, cancelarla con motivo y comprobar que los pallets vuelven a la lista de disponibles.

- [ ] **Step 6: Accesibilidad**

Run: `cd frontend && npm run auditoria` (o el proyecto de accesibilidad que use `e2e/accesibilidad.spec.ts`), agregando `/bodega`, `/despacho` e `/inventario` a sus rutas si no están.
Expected: ninguna regla nueva respecto de la última corrida en las pantallas nuevas.
