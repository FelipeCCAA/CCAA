# Puesto de Evaporación — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un solo puesto, `/produccion/evaporacion`, donde se abre el lote, se prepara, se inicia y se cierra la evaporación, en vez de 5 pasos en 3 pantallas.

**Architecture:** El backend funde abrir lote y preparar corrida en `confirmar-borrador` (todo o nada), extrae los motivos que impiden iniciar a una función compartida por `iniciar_condensacion` y por un endpoint de estado del puesto, y filtra los destinos que el cierre aceptará. El frontend agrega la página del puesto (tarjetas por evaporador que pintan lo que manda el servidor + el formulario de lote en modo evaporación) y retira la evaporación de `/produccion` y `/procesos`, con redirecciones.

**Tech Stack:** Django 6 + DRF + PostgreSQL; React 19 + TypeScript + react-router (HashRouter); `node --test`; Playwright.

**Spec:** `docs/superpowers/specs/2026-10-05-puesto-evaporacion-design.md` (con el ajuste de ruta de la Task 3).

## Global Constraints

- Abrir y preparar es **todo o nada**: si cualquiera de los dos falla, no queda lote, ni movimiento de silo, ni corrida, ni evaporador ocupado.
- Sobre un **evaporador**, `silo_destino` es **obligatorio** al confirmar: sin él → 400 `{"silo_destino": "Elige el silo de destino del concentrado."}`. Para otras máquinas se ignora.
- Destino válido = silo activo con estado **`disponible`** y capacidad libre ≥ litros; es la misma condición que el cierre/inicio exigen.
- `motivos_para_iniciar_condensacion(corrida)` es **la única implementación** de las reglas de inicio: `iniciar_condensacion` la usa y el endpoint del puesto también.
- La tarjeta del evaporador **pinta lo que manda el servidor**; no recalcula estado ni motivos.
- Un estado por evaporador, derivado de una sola corrida: `en_proceso` manda sobre `borrador`.
- Trampa de `CLAUDE.md`: dentro de `transaction.atomic()` un `return Response(...)` **confirma**; solo una excepción revierte.
- Toda cantidad en pantalla pasa por `cantidad(valor, unidad)` (`frontend/src/services/formato.ts`); toda operación irreversible por `ConfirmarAccion`.
- Español en código, comentarios, mensajes y UI. Django 6: `save()` solo por nombre.
- Pruebas backend: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test <etiquetas> --noinput`, **en serie, nunca `--parallel`**. Frontend: `npx tsc -b --pretty false`, `npx eslint <archivos>`, `npm test`.
- No reescribir archivos con acentos con PowerShell `Get-Content | Set-Content`. Commits sin líneas de atribución; nunca `frontend/e2e/.auth/estado.json`.

## Mapa de archivos

| Archivo | Cambio | Tarea |
|---|---|---|
| `backend/procesos/servicios.py` | `motivos_para_iniciar_condensacion`; `iniciar_condensacion` la usa; `crear_condensacion_guiada` valida destino; `estado_puesto_evaporacion` | 1, 2, 3 |
| `backend/procesos/tests_condensacion.py` | pruebas de motivos y destino | 1, 2 |
| `backend/produccion/views.py` | `confirmar_borrador` con `silo_destino` | 2 |
| `backend/produccion/tests_borrador_evaporacion.py` | nuevo | 2 |
| `backend/procesos/views.py` | acción `puesto` en `CorridaCondensacionViewSet` | 3 |
| `backend/procesos/tests_puesto_evaporacion.py` | nuevo | 3 |
| `backend/procesos/dominio.py` | `ruta_de_etapa` → puesto | 5 |
| `frontend/src/services/procesos.service.ts` | tipos y llamadas del puesto | 4 |
| `frontend/src/services/produccion.service.ts` | `confirmarBorradorLote(id, siloDestino?)` | 4 |
| `frontend/src/services/puesto-evaporacion.ts` | nuevo: acción de la tarjeta (pura) | 4 |
| `frontend/tests/puesto-evaporacion.test.ts` | nuevo | 4 |
| `frontend/src/pages/Produccion/FormularioLote.tsx` | modo evaporación y modo resto | 4 |
| `frontend/src/pages/Evaporacion/PuestoEvaporacion.tsx`, `TarjetaEvaporador.tsx` | nuevos | 5 |
| `frontend/src/app/routes.tsx`, `services/navegacion-operacional.ts`, `services/planta-ahora.ts` | ruta, menú, destinos | 5 |
| `frontend/src/pages/Produccion/Produccion.tsx`, `pages/Procesos/Procesos.tsx` | retirar evaporación | 5 |
| `frontend/src/pages/Produccion/EvaporadoresProduccion.tsx`, `services/estado-evaporador.ts`, `tests/estado-evaporador.test.ts`, `pages/Procesos/NuevaCondensacion.tsx` | eliminar si quedan sin uso | 5 |
| `frontend/e2e/evaporacion.spec.ts`, `e2e/rutas.ts` y specs que usen la evaporación de `/procesos` | E2E | 6 |
| `CLAUDE.md` | decisión nueva | 5 |

---

### Task 1: Motivos para iniciar, una sola implementación

**Files:**
- Modify: `backend/procesos/servicios.py` (`iniciar_condensacion`, ~1323)
- Test: `backend/procesos/tests_condensacion.py` (clase `FlujoCondensacionTests`)

**Interfaces:**
- Produces: `motivos_para_iniciar_condensacion(corrida, *, origen=None, destino=None) -> list[str]` en `procesos/servicios.py`. Lista vacía = se puede iniciar. Lee la corrida con `orden`, `ejecucion.equipo`, `silo_origen`, `silo_destino`; si se pasan `origen`/`destino` (los objetos bloqueados), usa esos.

- [ ] **Step 1: Pruebas que fallan** — agrega a `FlujoCondensacionTests`:

```python
    def test_motivos_para_iniciar_vacios_cuando_todo_esta_listo(self):
        from .servicios import motivos_para_iniciar_condensacion

        self.assertEqual(motivos_para_iniciar_condensacion(self.corrida), [])

    def test_motivos_para_iniciar_nombran_el_silo_de_origen_sin_analisis(self):
        from .servicios import motivos_para_iniciar_condensacion

        AnalisisSilo.objects.filter(silo=self.origen).delete()

        motivos = motivos_para_iniciar_condensacion(self.corrida)

        self.assertTrue(motivos)
        self.assertIn(self.origen.codigo, motivos[0])
        with self.assertRaises(ValidationError) as error:
            iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        self.assertIn(motivos[0], " ".join(error.exception.messages))

    def test_motivos_para_iniciar_rechazan_destino_bloqueado(self):
        from .servicios import motivos_para_iniciar_condensacion

        self.destino.estado = Silo.Estado.BLOQUEADO_CALIDAD
        self.destino.save(update_fields=["estado"])

        motivos = motivos_para_iniciar_condensacion(self.corrida)

        self.assertTrue(any(self.destino.codigo in motivo for motivo in motivos))
```

- [ ] **Step 2: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_condensacion --noinput`
Expected: ERROR `ImportError: cannot import name 'motivos_para_iniciar_condensacion'`.

- [ ] **Step 3: Extraer la función** — sobre `iniciar_condensacion` en `procesos/servicios.py`:

```python
def motivos_para_iniciar_condensacion(corrida, *, origen=None, destino=None):
    """
    Lo que impide iniciar esta corrida, en el orden en que el inicio lo
    comprueba. Lista vacía: se puede iniciar.

    Es la única implementación de esas reglas: `iniciar_condensacion` lanza el
    primer motivo, y el puesto de Evaporación los muestra junto a un botón
    deshabilitado. Con dos copias, la pantalla habilitaría «Iniciar» sobre una
    corrida que el servidor rechaza.
    """
    from inventario.servicios import motivo_equipo_no_habilitado
    from maestros.models import Silo
    from produccion.models import OrdenProduccion
    from recepcion.servicios import motivos_silo_no_disponible, saldo_silo

    origen = origen or corrida.silo_origen
    destino = destino or corrida.silo_destino
    motivos = []
    if corrida.orden.estado not in {
        OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO,
    }:
        motivos.append("La orden debe estar programada o en proceso.")
    if not corrida.ejecucion.equipo_id:
        motivos.append("La corrida requiere un evaporador asignado.")
    else:
        impedimento = motivo_equipo_no_habilitado(corrida.ejecucion.equipo)
        if impedimento:
            motivos.append(impedimento)
    motivos_silo = motivos_silo_no_disponible(origen, para="proceso")
    if motivos_silo:
        motivos.append(f"{origen.codigo}: " + " ".join(motivos_silo))
    if reservas_activas_silo(
        silo_id=origen.pk, tipo=ReservaSiloProceso.Tipo.DESTINO,
        excluir_ejecucion_id=corrida.ejecucion_id,
    ).exists():
        motivos.append(f"{origen.codigo} esta reservado como destino de otra ejecucion.")
    try:
        exigir_destino_sin_reserva(silo=destino, excluir_ejecucion_id=corrida.ejecucion_id)
    except ValidationError as error:
        motivos.extend(error.messages)
    if not destino.activo or destino.estado in {
        Silo.Estado.BLOQUEADO_CALIDAD, Silo.Estado.EN_CIP, Silo.Estado.FUERA_SERVICIO,
    }:
        motivos.append(f"{destino.codigo} no admite precondensado.")
    elif saldo_silo(destino) + corrida.litros_entrada > destino.capacidad_l:
        motivos.append(
            f"{destino.codigo} no tiene capacidad para reservar {corrida.litros_entrada} L."
        )
    return motivos
```

Luego, en `iniciar_condensacion`, **reemplaza** los bloques desde `if corrida.orden.estado not in {` hasta el `raise` de capacidad del destino (incluidos `motivo_equipo_no_habilitado`, `motivos_silo_no_disponible`, la reserva de origen, `exigir_destino_sin_reserva`, el estado del destino y la capacidad) por:

```python
    motivos = motivos_para_iniciar_condensacion(corrida, origen=origen, destino=destino)
    if motivos:
        raise ValidationError(motivos[0])
```

ubicado **después** de bloquear los silos (`silos = {...}`, `origen = ...`, `destino = ...`). El chequeo `corrida.estado != BORRADOR` y `corrida.clean()` se quedan donde están. Verifica que `reservas_activas_silo`, `ReservaSiloProceso` y `exigir_destino_sin_reserva` sean accesibles en el módulo (ya los usa `iniciar_condensacion`). Nota: los mensajes que antes iban como `{"silo_destino": ...}` ahora son texto plano; si alguna prueba existente afirma la clave `silo_destino` en ese error, ajústala a afirmar el texto.

- [ ] **Step 4: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_condensacion procesos.tests_concurrencia_equipo --noinput`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add backend/procesos/servicios.py backend/procesos/tests_condensacion.py
git commit -m "refactor(procesos): los motivos para iniciar una evaporación en una sola función"
```

---

### Task 2: Abrir y preparar en una transacción; destino válido

**Files:**
- Modify: `backend/procesos/servicios.py` (`crear_condensacion_guiada`, ~716)
- Modify: `backend/produccion/views.py` (`confirmar_borrador`, ~606-637)
- Test: `backend/procesos/tests_condensacion.py`, nuevo `backend/produccion/tests_borrador_evaporacion.py`

**Interfaces:**
- Consumes: `crear_condensacion_guiada(*, lote_id, silo_destino_id, usuario)`; `abrir_lote_desde_vale(...)`.
- Produces: `POST /api/produccion/lotes/{id}/confirmar-borrador/` acepta `{"silo_destino": <id>}`; sobre evaporador lo exige. Respuesta 200 = lote confirmado (con corrida creada).

- [ ] **Step 1: Prueba de destino** — en `FlujoCondensacionTests`:

```python
    def test_alta_guiada_rechaza_un_destino_bloqueado_por_calidad(self):
        self.corrida.delete()
        self.lote.ejecucion = self.ejecucion
        self.lote.save(update_fields=["ejecucion"])
        EntradaProceso.objects.create(
            ejecucion=self.ejecucion, silo=self.origen,
            cantidad=Decimal("600"), unidad="L",
        )
        self.destino.estado = Silo.Estado.BLOQUEADO_CALIDAD
        self.destino.save(update_fields=["estado"])

        with self.assertRaises(ValidationError) as error:
            crear_condensacion_guiada(
                lote_id=self.lote.pk, silo_destino_id=self.destino.pk, usuario=self.usuario,
            )

        self.assertIn(self.destino.codigo, str(error.exception))
        self.assertFalse(CorridaCondensacion.objects.filter(lote=self.lote).exists())
```

- [ ] **Step 2: Pruebas de confirmar** — crea `backend/produccion/tests_borrador_evaporacion.py`. Usa como base `produccion/tests_borrador.py` (`BorradorLoteTests`, que hereda de `tests_apertura.BaseApertura`) y el montaje de evaporador de `produccion/tests_lote_desde_vale.py::test_no_permite_saltar_la_etapa_inicial_posterior_al_vale`: el vale de `BorradorLoteTests` (`self.vale`, silo destino del vale `self.silo_b`), una ruta del producto polvo cuyas etapas sean `ESTANDARIZACION` (orden 1) → `EVAPORACION` (orden 2) → `SECADO` (orden 3), un `Equipo` de tipo `EVAPORADOR`, una `OrdenProduccion` `PROGRAMADA` del producto, y un silo de concentrado `disponible`:

```python
from decimal import Decimal

from maestros.models import Equipo, Silo
from procesos.models import CorridaCondensacion, EtapaProceso, Proceso, RutaProducto
from produccion.models import Lote, OrdenProduccion
from recepcion.models import MovimientoSilo

from .tests_borrador import BorradorLoteTests


class ConfirmarSobreEvaporadorTests(BorradorLoteTests):
    """Abrir el lote sobre un evaporador también prepara su corrida: todo o nada."""

    def setUp(self):
        super().setUp()
        RutaProducto.objects.filter(producto=self.polvo).delete()
        proceso = Proceso.objects.create(codigo="ruta-evap", nombre="Polvo por evaporador")
        for orden, (codigo, tipo) in enumerate([
            ("estandarizar", EtapaProceso.Tipo.ESTANDARIZACION),
            ("evaporar", EtapaProceso.Tipo.EVAPORACION),
            ("secar", EtapaProceso.Tipo.SECADO),
        ], start=1):
            EtapaProceso.objects.create(
                proceso=proceso, codigo=codigo, nombre=codigo, tipo=tipo, orden=orden,
            )
        RutaProducto.objects.create(
            sucursal=self.sucursal, producto=self.polvo, proceso=proceso, prioridad=1,
        )
        self.evaporador = Equipo.objects.create(
            sucursal=self.sucursal, codigo="ev-p", nombre="Evaporador P",
            tipo=Equipo.Tipo.EVAPORADOR, sigla="EP",
        )
        self.orden = OrdenProduccion.objects.create(
            sucursal=self.sucursal, codigo="OP-EVAP-1", producto=self.polvo,
            cantidad_planificada=12000, unidad="l", equipo=self.evaporador,
            estado=OrdenProduccion.Estado.PROGRAMADA,
        )
        self.concentrado = Silo.objects.create(
            sucursal=self.sucursal, codigo="PC-9", tipo=Silo.Tipo.SILO, capacidad_l=50000,
        )

    def borrador_sobre_evaporador(self):
        borrador = self.crear_borrador(observacion="Evaporación")
        datos = self.datos_completos()
        datos.pop("producto")
        datos.update({"equipo": self.evaporador.id, "orden": self.orden.id, "linea": ""})
        guardado = self.cliente.patch(
            f"/api/produccion/lotes/{borrador['id']}/guardar-borrador/", datos, format="json",
        )
        self.assertEqual(guardado.status_code, 200, guardado.json())
        return borrador["id"]

    def confirmar(self, borrador_id, **cuerpo):
        return self.cliente.post(
            f"/api/produccion/lotes/{borrador_id}/confirmar-borrador/", cuerpo, format="json",
        )

    def test_sin_destino_no_abre_nada(self):
        borrador_id = self.borrador_sobre_evaporador()

        respuesta = self.confirmar(borrador_id)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("silo_destino", respuesta.json())
        self.assertEqual(Lote.objects.get(pk=borrador_id).estado, Lote.Estado.BORRADOR)
        self.assertEqual(MovimientoSilo.objects.count(), 0)

    def test_con_destino_abre_el_lote_y_prepara_la_corrida(self):
        borrador_id = self.borrador_sobre_evaporador()

        respuesta = self.confirmar(borrador_id, silo_destino=self.concentrado.id)

        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        corrida = CorridaCondensacion.objects.get(lote_id=borrador_id)
        self.assertEqual(corrida.silo_destino, self.concentrado)
        self.assertEqual(corrida.estado, CorridaCondensacion.Estado.BORRADOR)
        self.assertEqual(MovimientoSilo.objects.filter(origen_id=borrador_id).count(), 1)

    def test_si_la_corrida_falla_no_queda_lote_ni_movimiento(self):
        self.concentrado.estado = Silo.Estado.BLOQUEADO_CALIDAD
        self.concentrado.save(update_fields=["estado"])
        borrador_id = self.borrador_sobre_evaporador()

        respuesta = self.confirmar(borrador_id, silo_destino=self.concentrado.id)

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(Lote.objects.get(pk=borrador_id).estado, Lote.Estado.BORRADOR)
        self.assertEqual(MovimientoSilo.objects.count(), 0)
        self.assertFalse(CorridaCondensacion.objects.exists())
```

Si el montaje necesita más datos para que `abrir_lote_desde_vale` encadene la ejecución de evaporación (p. ej. el borrador exige `linea` para torres pero no para evaporadores, o el código sugerido), ajusta **el escenario** mirando `produccion/tests_lote_desde_vale.py`, sin debilitar las aserciones.

- [ ] **Step 3: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test produccion.tests_borrador_evaporacion procesos.tests_condensacion --noinput`
Expected: FAIL — sin destino responde 200; con destino no hay corrida; el destino bloqueado se acepta.

- [ ] **Step 4: Destino válido en `crear_condensacion_guiada`** — después de `destino = Silo.objects.select_for_update().get(pk=silo_destino_id)`:

```python
    if not destino.activo or destino.estado != Silo.Estado.DISPONIBLE:
        raise ValidationError({
            "silo_destino": (
                f"{destino.codigo} no está disponible para recibir el concentrado "
                f"({destino.get_estado_display().lower()})."
            )
        })
```

- [ ] **Step 5: `confirmar_borrador` todo o nada** — en `produccion/views.py`, reemplaza el `try:` … `except DjangoValidationError` actual por:

```python
        from maestros.models import Equipo

        es_evaporador = bool(lote.equipo_id) and lote.equipo.tipo == Equipo.Tipo.EVAPORADOR
        silo_destino = request.data.get("silo_destino")
        if es_evaporador and not silo_destino:
            return Response(
                {"silo_destino": "Elige el silo de destino del concentrado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            # Transacción interna: si la corrida falla después de abrir el lote,
            # la excepción revierte las dos cosas antes de llegar al `except`.
            # Sin ella, el `return Response(400)` de abajo confirmaría el lote
            # abierto y la leche descontada sin corrida (trampa de CLAUDE.md).
            with transaction.atomic():
                confirmado = servicios_produccion.abrir_lote_desde_vale(
                    vale=lote.vale,
                    codigo_lote=lote.codigo_lote_propuesto.strip(),
                    fecha=lote.fecha,
                    litros=lote.litros_estandarizados_borrador,
                    usuario=request.user,
                    lote_borrador=lote,
                    op=lote.op,
                    orden=lote.orden,
                    equipo=lote.equipo,
                    linea=lote.linea,
                    turno=lote.turno,
                    observacion=lote.observacion,
                )
                if es_evaporador:
                    from procesos.servicios import crear_condensacion_guiada

                    crear_condensacion_guiada(
                        lote_id=confirmado.pk,
                        silo_destino_id=int(silo_destino),
                        usuario=request.user,
                    )
        except (DjangoValidationError, ValueError) as error:
            if isinstance(error, ValueError):
                return Response(
                    {"silo_destino": "El silo de destino no es válido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            detalle = error.message_dict if hasattr(error, "message_dict") else {
                "motivos": error.messages
            }
            return Response(detalle, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(confirmado).data)
```

Acota `silo_destino` al alcance del usuario como hace `CorridaCondensacionViewSet.crear_guiada` (`filtrar_por_scope(Silo.objects.all(), …)`); si no pertenece, 400 «El silo de destino no es válido.». `Silo.DoesNotExist` también debe dar 400, no 500.

- [ ] **Step 6: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test produccion procesos --noinput`
Expected: OK.

- [ ] **Step 7: Commit**

```bash
git add backend/procesos/servicios.py backend/procesos/tests_condensacion.py backend/produccion/views.py backend/produccion/tests_borrador_evaporacion.py
git commit -m "feat(produccion): abrir el lote sobre un evaporador prepara su corrida en la misma transacción"
```

---

### Task 3: Estado del puesto

**Files:**
- Modify: `backend/procesos/servicios.py` (nueva `estado_puesto_evaporacion`)
- Modify: `backend/procesos/views.py` (`CorridaCondensacionViewSet`, nueva acción `puesto`)
- Create: `backend/procesos/tests_puesto_evaporacion.py`
- Modify: `docs/superpowers/specs/2026-10-05-puesto-evaporacion-design.md` §3.3 (ruta)

**Interfaces:**
- Consumes: `motivos_para_iniciar_condensacion` (Task 1).
- Produces: `GET /api/procesos/condensaciones/puesto/` →

```json
{
  "evaporadores": [{
    "equipo_id": 3, "codigo": "scheffers3", "nombre": "Evaporador Scheffers 3",
    "estado": "disponible|preparada|en_curso|esperando_calidad",
    "corrida": null | { "id": 41, "codigo": "EJ-PROD-87", "lote_codigo": "…",
                        "silo_origen": "TK 3", "silo_destino": "SILO 6",
                        "litros_entrada": "20000.00", "iniciada_en": null },
    "motivos_para_iniciar": ["…"]
  }],
  "destinos": [{ "id": 6, "codigo": "SILO 6", "libre_l": "48000.00" }],
  "corridas_de_hoy": [{ "id": 40, "codigo": "EJ-PROD-86", "equipo": "Evaporador VEB",
                        "lote_codigo": "…", "estado": "cerrada", "estado_etiqueta": "Cerrada" }]
}
```

- [ ] **Step 1: Pruebas que fallan** — `backend/procesos/tests_puesto_evaporacion.py`, reusando el montaje de `FlujoCondensacionTests` (hereda de ella para no copiar el `setUp`):

```python
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Equipo, Silo
from procesos.models import CorridaCondensacion, EjecucionProceso
from recepcion.models import AnalisisSilo

from .tests_condensacion import FlujoCondensacionTests


class PuestoEvaporacionTests(FlujoCondensacionTests):
    def puesto(self):
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        respuesta = cliente.get("/api/procesos/condensaciones/puesto/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return respuesta.data

    def fila(self, datos, equipo):
        return next(item for item in datos["evaporadores"] if item["equipo_id"] == equipo.pk)

    def test_corrida_en_borrador_es_preparada_y_lista_para_iniciar(self):
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["estado"], "preparada")
        self.assertEqual(fila["corrida"]["id"], self.corrida.pk)
        self.assertEqual(fila["motivos_para_iniciar"], [])

    def test_sin_analisis_del_origen_la_preparada_dice_por_que(self):
        AnalisisSilo.objects.filter(silo=self.origen).delete()
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["estado"], "preparada")
        self.assertIn(self.origen.codigo, fila["motivos_para_iniciar"][0])

    def test_en_proceso_manda_sobre_una_preparada_del_mismo_equipo(self):
        self.corrida.estado = CorridaCondensacion.Estado.EN_PROCESO
        self.corrida.iniciada_en = timezone.now()
        self.corrida.save(update_fields=["estado", "iniciada_en"])
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["estado"], "en_curso")
        self.assertEqual(fila["corrida"]["id"], self.corrida.pk)

    def test_un_evaporador_sin_corrida_activa_esta_disponible(self):
        libre = Equipo.objects.create(
            sucursal=self.planta, codigo="ev-2", nombre="Evaporador 2",
            tipo=Equipo.Tipo.EVAPORADOR,
        )
        fila = self.fila(self.puesto(), libre)
        self.assertEqual(fila["estado"], "disponible")
        self.assertIsNone(fila["corrida"])

    def test_ejecucion_en_control_de_calidad_espera_calidad(self):
        self.corrida.estado = CorridaCondensacion.Estado.CERRADA
        self.corrida.save(update_fields=["estado"])
        self.ejecucion.estado = EjecucionProceso.Estado.PENDIENTE_CONTROL
        self.ejecucion.save(update_fields=["estado"])
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["estado"], "esperando_calidad")

    def test_los_destinos_ofrecidos_son_solo_disponibles(self):
        bloqueado = Silo.objects.create(
            sucursal=self.planta, codigo="PC-BLOQ", tipo=Silo.Tipo.SILO,
            capacidad_l=1000, estado=Silo.Estado.BLOQUEADO_CALIDAD,
        )
        codigos = [item["codigo"] for item in self.puesto()["destinos"]]
        self.assertIn(self.destino.codigo, codigos)
        self.assertNotIn(bloqueado.codigo, codigos)
```

Verifica los nombres reales de estados (`CorridaCondensacion.Estado.CERRADA`/`EN_PROCESO`, `EjecucionProceso.Estado.PENDIENTE_CONTROL`) y ajústalos si difieren; el criterio es el de la spec §3.3.

- [ ] **Step 2: Verificar que fallan** — Run: `… manage.py test procesos.tests_puesto_evaporacion --noinput` → 404.

- [ ] **Step 3: Servicio** — en `procesos/servicios.py`:

```python
def estado_puesto_evaporacion(usuario):
    """
    Lo que el puesto de Evaporación dibuja: un estado por evaporador, derivado
    de una sola corrida (la en proceso manda sobre la preparada), con los
    motivos que impiden iniciarla calculados por la misma función que decide
    al iniciar; los destinos que el cierre aceptará; y las corridas de hoy.
    """
    from maestros.models import Equipo, Silo
    from recepcion.servicios import saldo_silo

    equipos = filtrar_por_scope(
        Equipo.objects.filter(activo=True, tipo=Equipo.Tipo.EVAPORADOR).order_by("nombre"),
        usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    )
    corridas = CorridaCondensacion.objects.select_related(
        "ejecucion__equipo", "orden", "lote", "silo_origen", "silo_destino",
    ).filter(ejecucion__equipo__in=equipos)
    activas = {}
    for corrida in corridas.filter(
        estado__in=[CorridaCondensacion.Estado.EN_PROCESO, CorridaCondensacion.Estado.BORRADOR]
    ).order_by("pk"):
        actual = activas.get(corrida.ejecucion.equipo_id)
        if actual is None or (
            corrida.estado == CorridaCondensacion.Estado.EN_PROCESO
            and actual.estado != CorridaCondensacion.Estado.EN_PROCESO
        ):
            activas[corrida.ejecucion.equipo_id] = corrida
    esperando = {
        corrida.ejecucion.equipo_id: corrida
        for corrida in corridas.filter(
            ejecucion__estado=EjecucionProceso.Estado.PENDIENTE_CONTROL
        ).order_by("pk")
    }

    def resumen(corrida):
        return {
            "id": corrida.pk, "codigo": corrida.ejecucion.codigo,
            "lote_codigo": corrida.lote.codigo_lote if corrida.lote_id else None,
            "silo_origen": corrida.silo_origen.codigo,
            "silo_destino": corrida.silo_destino.codigo,
            "litros_entrada": corrida.litros_entrada,
            "iniciada_en": corrida.iniciada_en,
        }

    evaporadores = []
    for equipo in equipos:
        corrida = activas.get(equipo.pk)
        if corrida is not None:
            en_curso = corrida.estado == CorridaCondensacion.Estado.EN_PROCESO
            estado = "en_curso" if en_curso else "preparada"
            motivos = [] if en_curso else motivos_para_iniciar_condensacion(corrida)
        elif equipo.pk in esperando:
            corrida, estado, motivos = esperando[equipo.pk], "esperando_calidad", []
        else:
            estado, motivos = "disponible", []
        evaporadores.append({
            "equipo_id": equipo.pk, "codigo": equipo.codigo, "nombre": equipo.nombre,
            "estado": estado,
            "corrida": resumen(corrida) if corrida is not None else None,
            "motivos_para_iniciar": motivos,
        })

    destinos = []
    for silo in filtrar_por_scope(
        Silo.objects.filter(activo=True, estado=Silo.Estado.DISPONIBLE).order_by("codigo"),
        usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    ):
        destinos.append({
            "id": silo.pk, "codigo": silo.codigo,
            "libre_l": silo.capacidad_l - saldo_silo(silo),
        })

    hoy = timezone.localdate()
    corridas_de_hoy = [
        {
            "id": corrida.pk, "codigo": corrida.ejecucion.codigo,
            "equipo": corrida.ejecucion.equipo.nombre if corrida.ejecucion.equipo_id else None,
            "lote_codigo": corrida.lote.codigo_lote if corrida.lote_id else None,
            "estado": corrida.estado, "estado_etiqueta": corrida.get_estado_display(),
        }
        for corrida in corridas.filter(
            Q(iniciada_en__date=hoy) | Q(finalizada_en__date=hoy)
            | Q(estado=CorridaCondensacion.Estado.BORRADOR)
        ).order_by("-pk")
    ]
    return {"evaporadores": evaporadores, "destinos": destinos, "corridas_de_hoy": corridas_de_hoy}
```

Verifica que `filtrar_por_scope`, `Q` y `timezone` estén importados en `procesos/servicios.py` (agrega los imports que falten) y que `CorridaCondensacion` tenga `iniciada_en`/`finalizada_en` (si los nombres difieren, usa los reales).

- [ ] **Step 4: Acción** — en `CorridaCondensacionViewSet` (`procesos/views.py`), junto a `opciones_alta`:

```python
    @action(detail=False, methods=["get"])
    def puesto(self, request):
        """Estado del puesto de Evaporación: lo que la pantalla dibuja, sin recalcular."""
        return Response(estado_puesto_evaporacion(request.user))
```

e importa `estado_puesto_evaporacion` desde `.servicios`. Permiso: el mismo `OperaProcesoPorEtapa` del viewset (lectura para Condensación y Calidad); confirma con la prueba que un usuario de Calidad puede leer (agrega ese caso a la prueba si `OperaProcesoPorEtapa` distingue GET).

- [ ] **Step 5: Ajustar la spec** — en `docs/superpowers/specs/2026-10-05-puesto-evaporacion-design.md` §3.3 cambia `GET produccion/evaporacion/puesto/` por `GET procesos/condensaciones/puesto/` y agrega `destinos` al ejemplo.

- [ ] **Step 6: Verificar y commit**

Run: `… manage.py test procesos --noinput` → OK.

```bash
git add backend/procesos/servicios.py backend/procesos/views.py backend/procesos/tests_puesto_evaporacion.py docs/superpowers/specs/2026-10-05-puesto-evaporacion-design.md
git commit -m "feat(procesos): estado del puesto de Evaporación en un solo endpoint"
```

---

### Task 4: Servicios del frontend y formulario en modo evaporación

**Files:**
- Modify: `frontend/src/services/procesos.service.ts`, `frontend/src/services/produccion.service.ts`
- Create: `frontend/src/services/puesto-evaporacion.ts`, `frontend/tests/puesto-evaporacion.test.ts`
- Modify: `frontend/src/pages/Produccion/FormularioLote.tsx`

**Interfaces:**
- Consumes: endpoints de las Tasks 2 y 3.
- Produces:
  - `procesos.service.ts`: `export type EstadoEvaporador = "disponible" | "preparada" | "en_curso" | "esperando_calidad"`; `interface EvaporadorPuesto { equipo_id; codigo; nombre; estado: EstadoEvaporador; corrida: CorridaPuesto | null; motivos_para_iniciar: string[] }`; `interface CorridaPuesto { id; codigo; lote_codigo: string | null; silo_origen; silo_destino; litros_entrada: string; iniciada_en: string | null }`; `interface DestinoConcentrado { id; codigo; libre_l: string }`; `interface PuestoEvaporacion { evaporadores; destinos; corridas_de_hoy: { id; codigo; equipo: string | null; lote_codigo: string | null; estado; estado_etiqueta }[] }`; `obtenerPuestoEvaporacion(): Promise<PuestoEvaporacion>`; `obtenerCondensacion(id): Promise<CorridaCondensacion>` (GET `procesos/condensaciones/{id}/`).
  - `produccion.service.ts`: `confirmarBorradorLote(id: number, siloDestino?: number)` — envía `{ silo_destino }` solo si viene.
  - `puesto-evaporacion.ts`: `accionDeEvaporador(fila: EvaporadorPuesto): { tipo: "abrir" | "iniciar" | "cerrar" | "ninguna"; habilitada: boolean; motivo: string | null }`.
  - `FormularioLote` props: `{ alCerrar; alGuardar; modo?: "evaporacion" | "resto"; equipoInicial?: number; destinos?: DestinoConcentrado[] }`.

- [ ] **Step 1: Prueba de la regla pura** — `frontend/tests/puesto-evaporacion.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

import { accionDeEvaporador } from "../src/services/puesto-evaporacion.ts";

const base = { equipo_id: 1, codigo: "ev", nombre: "Evaporador", corrida: null, motivos_para_iniciar: [] as string[] };
const corrida = { id: 9, codigo: "EJ-9", lote_codigo: "L", silo_origen: "TK 3", silo_destino: "SILO 6", litros_entrada: "100", iniciada_en: null };

test("un evaporador disponible ofrece abrir lote", () => {
  assert.deepEqual(accionDeEvaporador({ ...base, estado: "disponible" }), { tipo: "abrir", habilitada: true, motivo: null });
});

test("una preparada sin motivos se puede iniciar", () => {
  assert.deepEqual(accionDeEvaporador({ ...base, estado: "preparada", corrida }), { tipo: "iniciar", habilitada: true, motivo: null });
});

test("una preparada con motivos muestra el primero y no habilita iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, motivos_para_iniciar: ["TK 3: sin análisis vigente."] };
  assert.deepEqual(accionDeEvaporador(fila), { tipo: "iniciar", habilitada: false, motivo: "TK 3: sin análisis vigente." });
});

test("en curso ofrece cerrar y esperando Calidad no ofrece nada", () => {
  assert.equal(accionDeEvaporador({ ...base, estado: "en_curso", corrida }).tipo, "cerrar");
  assert.equal(accionDeEvaporador({ ...base, estado: "esperando_calidad", corrida }).tipo, "ninguna");
});
```

Run: `cd frontend && npm test` → FAIL (módulo inexistente).

- [ ] **Step 2: Regla pura** — `frontend/src/services/puesto-evaporacion.ts`:

```ts
import type { EvaporadorPuesto } from "./procesos.service.ts";

/*
  Qué botón lleva la tarjeta de un evaporador. Solo traduce lo que mandó el
  servidor: el estado y los motivos los calcula `estado_puesto_evaporacion`
  con la misma función que decide al iniciar. Recalcularlos aquí sería una
  segunda implementación, y la que se equivoca primero es la de la pantalla.
*/
export function accionDeEvaporador(fila: EvaporadorPuesto): {
  tipo: "abrir" | "iniciar" | "cerrar" | "ninguna";
  habilitada: boolean;
  motivo: string | null;
} {
  switch (fila.estado) {
    case "disponible":
      return { tipo: "abrir", habilitada: true, motivo: null };
    case "preparada": {
      const motivo = fila.motivos_para_iniciar[0] ?? null;
      return { tipo: "iniciar", habilitada: motivo === null, motivo };
    }
    case "en_curso":
      return { tipo: "cerrar", habilitada: true, motivo: null };
    default:
      return { tipo: "ninguna", habilitada: false, motivo: null };
  }
}
```

Agrega en `procesos.service.ts` los tipos y funciones de **Interfaces** (`obtenerPuestoEvaporacion` = `api.get<PuestoEvaporacion>("procesos/condensaciones/puesto/")`; `obtenerCondensacion(id)` = `api.get<CorridaCondensacion>(\`procesos/condensaciones/${id}/\`)`), y cambia `confirmarBorradorLote`:

```ts
export async function confirmarBorradorLote(id: number, siloDestino?: number) {
  const { data } = await api.post<Lote>(
    `produccion/lotes/${id}/confirmar-borrador/`,
    siloDestino ? { silo_destino: siloDestino } : undefined,
  );
  return data;
}
```

Run: `npm test` → PASS.

- [ ] **Step 3: `FormularioLote` con modo** — en `frontend/src/pages/Produccion/FormularioLote.tsx`:
  - Props: agrega `modo?: "evaporacion" | "resto"` (por defecto `"resto"`), `equipoInicial?: number`, `destinos?: DestinoConcentrado[]`.
  - Estado nuevo `siloDestino` (string). Si `equipoInicial` viene, inicializa `equipo` con él (sin pisar un borrador recuperado que ya tenga equipo).
  - **Filtrado de equipos**: en modo `"evaporacion"`, `equiposCompatibles` queda solo con `item.tipo === "evaporador"`; en modo `"resto"`, se **excluyen** los de tipo `"evaporador"` (se abren en el puesto).
  - **Filtrado de vales**: en modo `"evaporacion"`, solo vales cuya familia tenga `"evaporador"` en `rutaPorFamilia[familia].tipos`; en modo `"resto"`, se excluyen los de familia `polvo` (solo van a evaporador). Muestra en modo `"resto"`, cuando un vale de familia `liquido` se elige y solo hay evaporadores, el aviso «Los productos que van a evaporador se abren en el puesto de Evaporación» con un `Link` a `/produccion/evaporacion`.
  - **Campo «Silo de destino del concentrado»** (requerido) visible cuando el equipo elegido es de tipo `evaporador`: un `<select>` con `destinos` (texto `«{codigo} · libre {cantidad(libre_l, "L")}»`), deshabilitando la opción cuyo `libre_l` sea menor que los litros escritos (con texto «sin capacidad»). Si `destinos` llega vacío: aviso «No hay silos disponibles para recibir el concentrado».
  - **Envío**: `await confirmarBorradorLote(borradorId, esEvaporador ? Number(siloDestino) : undefined)`. Antes de enviar, si es evaporador y no hay destino, `setError("Elige el silo de destino del concentrado.")` y no envía.
  - **Resumen**: el envío pasa por `ConfirmarAccion` mostrando vale, evaporador, orden, origen → destino, código y litros (con `cantidad`). Si el formulario ya tiene un paso de resumen, agrega ahí el destino.
  - Títulos: en modo `"evaporacion"` el modal se titula «Abrir lote y preparar evaporación» y el envío «Abrir lote»; en `"resto"` quedan «Abrir lote desde vale» / «Abrir lote».

- [ ] **Step 4: Verificar** — `npx tsc -b --pretty false`, `npx eslint src/pages/Produccion/FormularioLote.tsx src/services`, `npm test` → limpio.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/procesos.service.ts frontend/src/services/produccion.service.ts frontend/src/services/puesto-evaporacion.ts frontend/tests/puesto-evaporacion.test.ts frontend/src/pages/Produccion/FormularioLote.tsx
git commit -m "feat(produccion): formulario de lote en modo evaporación con silo de destino"
```

---

### Task 5: El puesto y el retiro de la evaporación vieja

**Files:**
- Create: `frontend/src/pages/Evaporacion/PuestoEvaporacion.tsx`, `frontend/src/pages/Evaporacion/TarjetaEvaporador.tsx`
- Modify: `frontend/src/app/routes.tsx`, `frontend/src/services/navegacion-operacional.ts`, `frontend/src/services/planta-ahora.ts`, `frontend/tests/navegacion-operacional.test.ts`, `frontend/tests/planta-ahora.test.ts`
- Modify: `frontend/src/pages/Produccion/Produccion.tsx`, `frontend/src/pages/Procesos/Procesos.tsx`
- Modify: `backend/procesos/dominio.py`, `backend/procesos/tests_destinos.py`
- Delete (si quedan sin uso): `frontend/src/pages/Produccion/EvaporadoresProduccion.tsx`, `frontend/src/services/estado-evaporador.ts`, `frontend/tests/estado-evaporador.test.ts`, `frontend/src/pages/Procesos/NuevaCondensacion.tsx`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `obtenerPuestoEvaporacion`, `obtenerCondensacion`, `iniciarCondensacion` (existente), `accionDeEvaporador`, `FormularioLote` con `modo="evaporacion"`, `CierreCondensacion` (`pages/Procesos/CierreCondensacion.tsx`, props `{ corrida, onCerrar, onCerrada }`).

- [ ] **Step 1: Tarjeta** — `frontend/src/pages/Evaporacion/TarjetaEvaporador.tsx`:

```tsx
import { Link } from "react-router-dom";

import { cantidad } from "../../services/formato";
import type { EvaporadorPuesto } from "../../services/procesos.service";
import { accionDeEvaporador } from "../../services/puesto-evaporacion";

const ROTULO = {
  disponible: "Disponible",
  preparada: "Preparada",
  en_curso: "En curso",
  esperando_calidad: "Esperando Calidad",
} as const;

/* Una tarjeta, un estado, una acción. Lo que dice lo decidió el servidor. */
export default function TarjetaEvaporador({ fila, ocupado, onAbrir, onIniciar, onCerrar }: {
  fila: EvaporadorPuesto;
  ocupado: boolean;
  onAbrir: (equipoId: number) => void;
  onIniciar: (corridaId: number) => void;
  onCerrar: (corridaId: number) => void;
}) {
  const accion = accionDeEvaporador(fila);
  const corrida = fila.corrida;
  return (
    <article aria-label={fila.nombre} className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5">
      <header className="flex items-start justify-between gap-3">
        <h3 className="text-lg font-semibold text-slate-900">{fila.nombre}</h3>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-800">{ROTULO[fila.estado]}</span>
      </header>
      {corrida && (
        <p className="text-sm text-slate-700">
          <span className="font-mono">{corrida.codigo}</span>{corrida.lote_codigo ? ` · lote ${corrida.lote_codigo}` : ""}
          <span className="block">{corrida.silo_origen} → {corrida.silo_destino} · {cantidad(corrida.litros_entrada, "L")}</span>
          {corrida.iniciada_en && <span className="block text-slate-600">Inició {new Date(corrida.iniciada_en).toLocaleString("es-CL")}</span>}
        </p>
      )}
      {accion.tipo === "abrir" && (
        <button type="button" onClick={() => onAbrir(fila.equipo_id)} className="rounded-xl bg-blue-700 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-800">Abrir lote desde vale</button>
      )}
      {accion.tipo === "iniciar" && corrida && (
        <>
          <button type="button" disabled={!accion.habilitada || ocupado} onClick={() => onIniciar(corrida.id)} className="rounded-xl bg-blue-700 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-40">
            {ocupado ? "Iniciando…" : "Iniciar evaporación"}
          </button>
          {accion.motivo && (
            <p className="text-sm text-amber-900">
              {accion.motivo}{" "}
              <Link to="/silos" className="font-semibold underline">Ir a silos</Link>
            </p>
          )}
        </>
      )}
      {accion.tipo === "cerrar" && corrida && (
        <button type="button" onClick={() => onCerrar(corrida.id)} className="rounded-xl bg-green-700 px-4 py-3 text-sm font-semibold text-white hover:bg-green-800">Registrar salida y cerrar</button>
      )}
    </article>
  );
}
```

- [ ] **Step 2: Página** — `frontend/src/pages/Evaporacion/PuestoEvaporacion.tsx`:

```tsx
import { lazy, Suspense, useState } from "react";

import { useCarga, mensajeDe } from "../../components/seccion/utilidades";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import {
  iniciarCondensacion, obtenerCondensacion, obtenerPuestoEvaporacion, type CorridaCondensacion,
} from "../../services/procesos.service";
import CierreCondensacion from "../Procesos/CierreCondensacion";
import TarjetaEvaporador from "./TarjetaEvaporador";

const FormularioLote = lazy(() => import("../Produccion/FormularioLote"));

/*
  Puesto de Evaporación: abrir el lote (que también prepara la corrida),
  iniciarla y cerrarla, en una pantalla. Antes eran 5 pasos en 3 pantallas.
*/
export default function PuestoEvaporacion() {
  const puesto = useCarga(obtenerPuestoEvaporacion);
  const [abriendoEn, setAbriendoEn] = useState<number | null>(null);
  const [iniciando, setIniciando] = useState<number | null>(null);
  const [cerrando, setCerrando] = useState<CorridaCondensacion | null>(null);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");

  const iniciar = async (corridaId: number) => {
    setIniciando(corridaId);
    setError("");
    try {
      const corrida = await iniciarCondensacion(corridaId);
      setMensaje(`Evaporación ${corrida.ejecucion_codigo} iniciada.`);
      await puesto.recargar();
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo iniciar la evaporación."));
    } finally {
      setIniciando(null);
    }
  };

  const prepararCierre = async (corridaId: number) => {
    setError("");
    try {
      setCerrando(await obtenerCondensacion(corridaId));
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo cargar la corrida."));
    }
  };

  return (
    <div className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header>
          <p className="text-sm font-semibold uppercase tracking-wider text-blue-700">Puesto de trabajo</p>
          <h1 className="mt-1 text-3xl font-bold text-slate-900">Evaporación</h1>
          <p className="mt-2 max-w-2xl text-slate-600">Abre el lote desde el vale y elige el destino del concentrado; luego inicia y cierra la corrida desde la tarjeta del evaporador.</p>
        </header>

        {mensaje && <p role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">{mensaje}</p>}
        {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {puesto.error && <p role="alert" className="text-sm text-red-800">{puesto.error}</p>}
        {puesto.cargando && !puesto.datos && <p className="text-sm text-slate-600">Cargando evaporadores…</p>}

        <section aria-label="Evaporadores" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {puesto.datos?.evaporadores.map((fila) => (
            <TarjetaEvaporador
              key={fila.equipo_id}
              fila={fila}
              ocupado={iniciando === fila.corrida?.id}
              onAbrir={(equipoId) => { setMensaje(""); setAbriendoEn(equipoId); }}
              onIniciar={(id) => void iniciar(id)}
              onCerrar={(id) => void prepararCierre(id)}
            />
          ))}
        </section>

        <section aria-label="Corridas de hoy" className="space-y-2">
          <h2 className="text-lg font-semibold text-slate-900">Corridas de hoy</h2>
          {puesto.datos && puesto.datos.corridas_de_hoy.length === 0 && <p className="text-sm text-slate-600">Hoy no hay corridas de evaporación.</p>}
          <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white">
            {puesto.datos?.corridas_de_hoy.map((c) => (
              <li key={c.id} className="flex flex-wrap justify-between gap-2 px-5 py-3 text-sm">
                <span><span className="font-mono">{c.codigo}</span> · {c.equipo ?? "—"}{c.lote_codigo ? ` · lote ${c.lote_codigo}` : ""}</span>
                <span className="text-slate-700">{c.estado_etiqueta}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {abriendoEn !== null && (
        <Suspense fallback={null}>
          <FormularioLote
            modo="evaporacion"
            equipoInicial={abriendoEn}
            destinos={puesto.datos?.destinos ?? []}
            alCerrar={() => setAbriendoEn(null)}
            alGuardar={() => { setMensaje("Lote abierto y evaporación preparada."); void puesto.recargar(); }}
          />
        </Suspense>
      )}
      {cerrando && (
        <CierreCondensacion
          corrida={cerrando}
          onCerrar={() => setCerrando(null)}
          onCerrada={async (corrida) => {
            setCerrando(null);
            setMensaje(`Salida de ${corrida.ejecucion_codigo} registrada; pasa a Calidad.`);
            await puesto.recargar();
          }}
        />
      )}
    </div>
  );
}
```

Verifica que `useCarga` y `mensajeDe` existan en `components/seccion/utilidades.ts` (existen) y que `mensajeErrorProceso` esté en `services/errores-proceso.ts` (existe). Agrega un botón «Abrir lote desde vale» en el encabezado para abrir el formulario sin evaporador preelegido (`setAbriendoEn(0)` y en `FormularioLote` trata `equipoInicial` 0 como «sin preelegir»).

- [ ] **Step 3: Ruta, menú y destinos**
  - `routes.tsx`: `const PuestoEvaporacion = lazy(() => import("../pages/Evaporacion/PuestoEvaporacion"));` y, dentro del bloque protegido por el módulo `produccion`, `<Route path="/produccion/evaporacion" element={diferido(<PuestoEvaporacion />)} />`. Asegúrate de que `/produccion/evaporacion` no choque con la ruta `/produccion` (si `/produccion` usa `path="/produccion/*"`, ajusta el orden).
  - Redirecciones (componente pequeño que lea `?seccion=` no sirve con `Navigate` puro): en `Procesos.tsx` y `Produccion.tsx`, si `seccion` es `condensacion` o `evaporacion`, `return <Navigate to="/produccion/evaporacion" replace />` al inicio del render.
  - `navegacion-operacional.ts`: la entrada «Evaporación» pasa a `ruta: "/produccion/evaporacion"`; actualiza `tests/navegacion-operacional.test.ts` y el marcado de enlace activo.
  - `planta-ahora.ts`: `evaporacion` y `condensacion` → `"/produccion/evaporacion"`; actualiza `tests/planta-ahora.test.ts`.
  - Backend `procesos/dominio.py`: `RUTAS_POR_ETAPA["evaporacion"]` y `["condensacion"]` → `"/produccion/evaporacion"`; actualiza `procesos/tests_destinos.py`.

- [ ] **Step 4: Retirar lo viejo**
  - `Produccion.tsx`: quita `{veCondensacion && <div id="evaporacion" …><EvaporadoresProduccion /></div>}` y el import; en su lugar, si `veCondensacion`, una línea: `<Link to="/produccion/evaporacion" …>Evaporación: abrir, iniciar y cerrar corridas en su puesto →</Link>`. La tarjeta «3. Evaporación» del bloque «Flujo por proceso» apunta a `/produccion/evaporacion`. Quita el `useEffect` de scroll a `?seccion=` si ya no queda sección que lo use. El `FormularioLote` que abre «Abrir lote desde vale» pasa `modo="resto"`.
  - `Procesos.tsx`: quita la sección `<section id="proceso-condensacion">`, el estado y funciones de condensación (`condensaciones`, `condensacionesCargadas`, `nuevaCondensacion`, `cargarCondensaciones`, la rama `"condensacion"` de `iniciarCorrida`, el `CierreCondensacion` de esa página) y los imports que queden sin uso.
  - Elimina con `git rm` los archivos de la lista **Delete** que queden sin importadores (`grep -rn "EvaporadoresProduccion\|estado-evaporador\|NuevaCondensacion" frontend/src frontend/tests`).
  - `grep -rn "proceso-condensacion\|seccion=condensacion\|seccion=evaporacion\|crear-guiada" frontend/src backend --include=*.ts --include=*.tsx --include=*.py` y corrige cada uso restante que apunte a lo retirado (el endpoint `condensaciones/crear-guiada/` puede quedar en el backend: no lo borres, solo deja de usarse desde el frontend).

- [ ] **Step 5: `CLAUDE.md`** — en «Decisiones vigentes», agrega:

```markdown
- **Evaporación tiene puesto propio** (desde 2026-10-05, `docs/superpowers/specs/2026-10-05-puesto-evaporacion-design.md`): `/produccion/evaporacion`. Abrir el lote sobre un evaporador **también prepara su corrida**: `confirmar-borrador` exige `silo_destino` y crea lote y corrida en una sola transacción —todo o nada—, porque con dos llamadas un fallo en la segunda dejaba el evaporador ocupado sin destino. «Iniciar» lo habilita el servidor: `motivos_para_iniciar_condensacion` es la única implementación de esas reglas, la usa `iniciar_condensacion` y la sirve `condensaciones/puesto/`. Solo se ofrecen destinos `disponible`. La evaporación ya no se abre ni se opera desde `/produccion` ni `/procesos`.
```

- [ ] **Step 6: Verificar** — frontend `npx tsc -b --pretty false`, `npx eslint .`, `npm test`; backend `… manage.py test procesos produccion --noinput`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src backend/procesos/dominio.py backend/procesos/tests_destinos.py frontend/tests CLAUDE.md
git commit -m "feat(produccion): puesto de Evaporación; la evaporación sale de /produccion y /procesos"
```

(Revisa `git status` antes: agrega por nombre si hay archivos ajenos.)

---

### Task 6: E2E y aceptación (controlador + implementador)

**Files:**
- Modify: `frontend/e2e/evaporacion.spec.ts`, `frontend/e2e/rutas.ts`, y los specs que usen la evaporación de `/procesos` o `/produccion` (`grep -rln "Nueva evaporación\|Crear corrida preparada\|Abrir lote desde vale\|proceso-condensacion" frontend/e2e`).

- [ ] **Step 1: Reescribir `evaporacion.spec.ts`** sobre el puesto, conservando los comentarios de por qué (orden del análisis, destino disponible) y los ayudantes de `e2e/ayudantes.ts`:
  1. **Abrir y preparar**: `irA(page, "/produccion/evaporacion")`; en la tarjeta de un evaporador **Disponible** (`page.getByRole("article", { name: /Evaporador/ })` filtrada por el texto «Disponible»), clic en «Abrir lote desde vale»; completar el formulario (vale con saldo, orden `OP-`, código, litros) y elegir «Silo de destino del concentrado» con una opción que no diga «sin capacidad»; confirmar en el resumen (`ConfirmarAccion`). Leer de la tarjeta (ahora **Preparada**) el silo de origen (`origen`) y el destino.
  2. **Calidad analiza el origen**: antes, afirmar que en la tarjeta el botón «Iniciar evaporación» está **deshabilitado** y que se ve el motivo que nombra el silo de origen; luego `analizarSilo(page, origen, LECHE_ESTANDARIZADA)`.
  3. **Iniciar**: volver al puesto, el botón ya habilitado, clic, esperar `condensaciones/{id}/iniciar/`.
  4. **Registrar salida y cerrar**: en la tarjeta **En curso**, «Registrar salida y cerrar»; completar `CierreCondensacion` como lo hacía el paso 5 actual; esperar el cierre.
  5. Afirmar que la corrida aparece en «Corridas de hoy» con estado de espera de Calidad (o el que corresponda tras cerrar).
- [ ] **Step 2: Otros specs** — ajusta los que usaban `/procesos` «Nueva evaporación» o `/produccion` para abrir lotes de familias que van a evaporador; `flujo-polvo-continuacion` recibe la salida de este spec (lote y silo destino) y no debería cambiar.
- [ ] **Step 3: `rutas.ts`** — agrega `{ ruta: "/produccion/evaporacion", nombre: "Producción · Evaporación" }`.
- [ ] **Step 4 (controlador)**: reiniciar el backend (`runserver --noreload`), `manage.py migrate`, `manage.py preparar_circuito_polvo --aplicar`, verificar evaporadores libres (sin tocar corridas ajenas), y correr `E2E_USUARIO=e2e_auditoria E2E_CLAVE=auditoria-e2e-ccaa E2E_CLAVE_AREAS=flujo-e2e-ccaa npx playwright test --project=circuito --project=flujo-polvo` → 4/4; auditoría de accesibilidad sin reglas nuevas en el puesto; suite completa del backend sin rojos.
- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/evaporacion.spec.ts frontend/e2e/rutas.ts
git commit -m "test(e2e): la evaporación se recorre en su puesto"
```
