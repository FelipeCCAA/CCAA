# Puesto de Secado — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un solo puesto, `/produccion/secado`, donde se toma el concentrado (o la alimentación externa) para una torre, se inicia el secado y se cierra el balance, en vez de 3 pasos en 3 pantallas.

**Architecture:** El backend agrega `motivos_para_iniciar_secado` (única implementación de las reglas de inicio), `iniciar_secado` y la acción `secados/{id}/iniciar/`; cierra el inicio genérico (`ejecuciones/{id}/transicionar/` de `preparacion` a `ejecucion` en Secado); convierte la alimentación externa en una preparación (`preparar-desde-inventario`); y sirve el estado del puesto en `secados/puesto/`, con el saldo de cada concentrado calculado por la misma función que `preparar_continuacion`. El frontend agrega la página del puesto (tarjetas por torre que pintan lo que manda el servidor, formulario guiado «Tomar concentrado», corridas de hoy e historial con filtros de servidor) y retira `/secado`, el modal de alimentación externa y Secado de «Materiales intermedios liberados».

**Tech Stack:** Django 6 + DRF + PostgreSQL; React 19 + TypeScript + react-router (HashRouter); `node --test`; Playwright.

**Spec:** `docs/superpowers/specs/2026-10-06-puesto-secado-design.md` (con los ajustes de la sección «Desviaciones» y del Step 6 de la Task 3).

## Global Constraints

- Ruta del puesto: **`/produccion/secado`**. `/secado` **redirige** a `/produccion/secado`; menú, `rutaDeEtapa("secado")` (frontend) y `RUTAS_POR_ETAPA["secado"]` (backend) apuntan al puesto.
- Endpoints: `GET procesos/secados/puesto/`; `POST procesos/secados/{id}/iniciar/`; `POST procesos/secados/preparar-desde-inventario/`; `POST procesos/salidas/{id}/preparar-continuacion/` (existente). `secados/iniciar-desde-inventario/` **se elimina** (404), no queda como alias.
- Estados por torre: `"disponible" | "preparada" | "en_curso"`. Ejecución de Secado `preparacion` → `preparada`; `ejecucion`, `pausada` o `bloqueada` → `en_curso`; sin ejecución en `ESTADOS_QUE_OCUPAN_EQUIPO` → `disponible`. `cerrada`/`cancelada` no ocupan (`ESTADOS_EJECUCION_TERMINALES`).
- Claves JSON del puesto: `torres[].{equipo_id, codigo, nombre, estado, corrida, motivos_para_iniciar, avisos, en_calidad}`, `corrida.{id, lote_codigo, origen, cantidad, unidad, iniciada_en}`, `concentrados[].{salida_id, lote_codigo, producto, silo, disponible, unidad}`, `corridas_de_hoy[].{id, equipo, lote_codigo, estado, estado_calidad}` (más las claves extra declaradas en la Task 3). Decimales viajan como **texto**.
- `motivos_para_iniciar_secado(corrida)` es **la única implementación** de las reglas de inicio de Secado: `iniciar_secado` la usa y `secados/puesto/` la sirve.
- Mensaje exacto del inicio genérico rechazado: «Las corridas de secado se inician desde el puesto de Secado.» Solo para `preparacion` → `ejecucion`; pausar, bloquear, cancelar y **reanudar** (`pausada`/`bloqueada` → `ejecucion`) siguen por `transicionar`.
- Aviso de inspección exacto: «Falta la inspección pre-operativa de hoy (CCAA.Sec.FORM.003).» **Avisa, no bloquea.** Se decide con `calidad.dominio.cubre_al_lote` + `registro_completo` sobre los `RegistroEquipo` de esa torre y la fecha local de hoy.
- Preparar, iniciar y cerrar exigen el permiso de la etapa Secado (`procesos.permisos.puede_operar_tipo(usuario, EtapaProceso.Tipo.SECADO)`) en todos los caminos; leer el puesto: áreas Secado y Calidad, y administradores.
- La tarjeta de la torre **pinta lo que manda el servidor**; una sola acción por estado: «Tomar concentrado», «Iniciar secado», «Registrar balance y cerrar». Línea informativa «Polvo de {lote} esperando Calidad». Confirmación del formulario con `ConfirmarAccion` y botón «Preparar torre».
- `bandejaDeSecado` sigue siendo el único clasificador de corridas.
- Trampa de `CLAUDE.md`: dentro de `transaction.atomic()` un `return Response(...)` **confirma**; solo una excepción revierte. Las vistas nuevas devuelven errores **fuera** de transacciones o lanzan.
- Trampa de `CLAUDE.md`: el catálogo `DocumentoLiberacion` lo siembran migraciones también en la base de pruebas; las pruebas usan `update_or_create` para el documento propio de su empresa y no borran el catálogo.
- Toda cantidad en pantalla pasa por `cantidad(valor, unidad)` (`frontend/src/services/formato.ts`); toda operación irreversible por `ConfirmarAccion`.
- Español en código, comentarios, mensajes y UI. Django 6: `save()` solo por nombre. Archivos en LF.
- Pruebas backend: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test <etiquetas> --noinput`, **en serie, nunca `--parallel`**. Frontend: `npx tsc -b --pretty false`, `npx eslint .`, `npm test`.
- No reescribir archivos con acentos con PowerShell `Get-Content | Set-Content` (usar Edit). Commits en español, convencionales, sin líneas de atribución, agregando archivos **por nombre**; nunca `frontend/e2e/.auth/estado.json`.

## Desviaciones: lo que el código dice distinto de la spec

1. **`preparar-continuacion` ya exige el permiso de la etapa** (spec §3.4 suponía un hueco). `OperaProcesoPorEtapa._tipo_solicitado` y `has_object_permission` resuelven `request.data["etapa"]` cuando `view.action == "preparar_continuacion"` (`backend/procesos/permisos.py:86,105`), y `procesos/tests_descremacion.py` (~l. 760) ya documenta el 403 de Condensación. La Task 2 agrega solo la **prueba de regresión** de la spec (pasa al primer intento; es una caracterización, no un rojo).
2. **El saldo de una salida tiene tres implementaciones**: `preparar_continuacion` (usos como origen + despacho a granel autorizado/despachado, `servicios.py:950-956`), `SalidaProcesoViewSet.disponibles` (usos + `MovimientoSilo` de salida por lote/silo, sin despacho, `views.py:1339-1373`) y `consultas_planta` (solo usos). La Task 1 extrae `disponible_de_salida(salida)` de `preparar_continuacion` y el puesto usa esa. `disponibles` queda como está: deja de ofrecer Secado (Task 5) y unificarla es otro cambio.
3. **Un aseo observado no es motivo, es aviso.** `motivo_equipo_no_habilitado` solo bloquea un CIP en curso; el observado lo informa `advertencia_aseo_equipo` y `procesos/tests.py::test_un_aseo_observado_avisa_pero_no_bloquea` lo fija. La prueba «motivo por aseo observado» de la spec §5 se escribe como **aviso**.
4. **Reanudar también es pasar a `ejecucion`.** `EjecucionProceso.TRANSICIONES` permite `pausada → ejecucion` y `bloqueada → ejecucion`; rechazar todo paso a `ejecucion` dejaría una torre pausada sin forma de reanudarse. Se rechaza solo `preparacion → ejecucion` de Secado, y **en la vista** `transicionar` (no en `transicionar_ejecucion`, que el propio `iniciar_secado` usa y que `EquipoHabilitadoPorAseoTests` prueba con etapa Secado). `operativas` deja de ofrecer `ejecucion` para esas mismas ejecuciones.
5. **Ningún comando de siembra inicia Secado por `transicionar`.** `sembrar_flujo_demo` abre el lote sobre una torre con `abrir_lote_desde_vale` (ejecución nacida en `ejecucion`); `preparar_circuito_polvo` no toca ejecuciones de Secado. El único uso por API en pruebas es `tests_permisos_operacionales.test_transicion_exige_version_y_rechaza_una_obsoleta` (se migra a reanudar).
6. **La alimentación externa descuenta bodega al preparar** (`registrar_salida` en `crear_secado_desde_inventario`). «Sigue con saldo» al iniciar no tiene nada que comprobar: el saldo ya salió. El motivo comprueba solo que el lote de proveedor siga utilizable (`LoteInventario.utilizable`). Cancelar una preparación externa no devuelve el stock: comportamiento existente, fuera de alcance, queda anotado.
7. **`CorridaSecado.lote` es `OneToOne`.** Una segunda toma parcial del mismo concentrado revienta con `IntegrityError` en el `get_or_create` de `preparar_continuacion`, y una salida **sin lote** crea una ejecución de Secado sin `CorridaSecado`, que con el inicio genérico cerrado quedaría imposible de iniciar. La Task 2 agrega a `preparar_continuacion` (solo etapa Secado) dos rechazos con mensaje, y el puesto no ofrece concentrados cuyo lote ya tenga corrida de Secado. `tests_descremacion.test_continuacion_usa_la_primera_etapa_de_la_ruta_de_la_rama` (salida sin lote → Secado) se ajusta dándole lote.
8. **`preparar_continuacion` no mira la decisión de Calidad** de la salida (la trae con `select_related` y no la usa). `motivos_para_iniciar_secado` sí: «Calidad rechazó…» / «…no está liberado por Calidad».
9. **`RegistroEquipo` por torre y empresa.** El expediente (`calidad/views.py:342`) no filtra por equipo; el puesto sí (`equipo=torre`, «de esa torre» según la spec). `DocumentoLiberacion` es único por `(empresa, codigo)`: se busca el de la empresa de la torre; si la empresa no tiene el documento, no hay aviso (no hay dónde registrarlo).
10. **Hay un cuarto camino de inicio fuera de alcance:** abrir un lote desde un vale **sobre una torre** (`produccion.servicios._encadenar_con_la_estandarizacion`) crea la ejecución de Secado directamente en `ejecucion`, sin `adquirir_equipo`, sin estas reglas y sin el permiso de Secado (`confirmar-borrador` solo exige permiso sobre evaporadores). El puesto la muestra como `en_curso`. Se anota para un cambio posterior; esta spec no lo menciona.
11. **Claves extra en el JSON** (necesarias, no decorativas): `concentrados[].etapa_id` (lo exige `preparar-continuacion`), `corrida.{ejecucion_id, ejecucion_codigo, ejecucion_estado}`, `torres[].falta_inspeccion` y `torres[].resolver_en` (el enlace sale de un dato tipado, no de leer el texto del motivo), y `estados` (catálogo del filtro del historial, servido por el backend).
12. `iniciar` responde **400** (spec); el `iniciar` de Evaporación responde 409. Se respeta la spec.

## Usos a migrar

| Uso | Dónde | Tarea |
|---|---|---|
| `iniciar-desde-inventario` / `iniciar_desde_inventario` | `backend/procesos/views.py:847-886`; `backend/procesos/tests_secado.py:300,333`; `backend/procesos/tests_flujo_suero.py:231`; `frontend/src/services/secado.service.ts:88-95`; `frontend/e2e/flujo-suero.spec.ts:35` | 2, 4, 6 |
| `crear_secado_desde_inventario` | `backend/procesos/servicios.py:2383`; import en `backend/procesos/views.py:59` | 2 |
| `iniciarSecadoExterno` / `InicioSecadoExterno` | `frontend/src/pages/Secado/InicioSecadoExterno.tsx` (se elimina); `frontend/src/pages/Secado/Secado.tsx:11,147` (se elimina) | 4, 5 |
| `preparar_continuacion` con etapa Secado | `backend/procesos/tests.py:440` (falla antes, sin cambio), `:478` (con lote, sin cambio); `backend/procesos/tests_descremacion.py:604` (salida sin lote → **se ajusta**), `:845` (con lote, sin cambio) | 2 |
| `transicionar` a `ejecucion` de una ejecución de Secado | API: `backend/procesos/tests_permisos_operacionales.py:255-281` (**se migra**); servicio (no afectado, la regla vive en la vista): `backend/procesos/tests.py:865-872`; pantallas: `frontend/src/pages/Produccion/BandejaTrabajoArea.tsx:69,129`, `frontend/src/pages/Procesos/Procesos.tsx:75,210`; E2E: `frontend/e2e/flujo-polvo-continuacion.spec.ts:66-72`. `sembrar_flujo_demo` y `preparar_circuito_polvo`: sin usos | 1, 5, 6 |
| `acciones_permitidas` de `operativas` | `backend/procesos/views.py:1037-1041`; `tests_permisos_operacionales.test_bandeja_operativa…` (sigue verde: queda `cancelada`) | 1 |
| Enlaces a `/secado` | `frontend/src/app/routes.tsx:223`; `frontend/src/services/navegacion-operacional.ts:58`; `frontend/src/services/planta-ahora.ts:9`; `frontend/src/services/access-control.ts:66`; `frontend/src/pages/Produccion/Produccion.tsx:270`; `frontend/src/pages/Leche/Silos.tsx:338`; `backend/procesos/dominio.py:55`; `backend/procesos/tests_destinos.py:24`; `frontend/tests/navegacion-operacional.test.ts:60`; `frontend/tests/planta-ahora.test.ts:9,24`; `frontend/e2e/flujo-polvo-continuacion.spec.ts:75`; `frontend/e2e/flujo-suero.spec.ts:27`. (`frontend/tests/notificaciones-operacionales.test.ts:16` usa «/secado» como texto opaco: sin cambio) | 5, 6 |
| «Continuar a Secado» | `backend/procesos/views.py:1433` (etiqueta se queda); `backend/procesos/tests_descremacion.py:601` (sin cambio); `frontend/src/pages/Produccion/SalidasIntermedias.tsx` (nueva rama de enlace); `frontend/e2e/flujo-polvo-continuacion.spec.ts:59` | 5, 6 |
| `bandejaDeSecado` | `frontend/src/pages/Secado/Secado.tsx:34` (se elimina) → `situacionDeCorrida` en `frontend/src/services/puesto-secado.ts`; `frontend/tests/secado-proceso.test.ts` (sin cambio) | 4, 5 |
| `estadoFisicoSecado`, `siguienteAccionSecado`, `obtenerSecados` | solo `Secado.tsx` → se eliminan | 4, 5 |
| `CorridaSecadoSerializer.get_estado_calidad` | `backend/procesos/serializers.py:397-409` → delega en `estado_calidad_secado` | 3 |

## Mapa de archivos

| Archivo | Cambio | Tarea |
|---|---|---|
| `backend/procesos/servicios.py` | `disponible_de_salida`, `motivos_para_iniciar_secado`, `avisos_de_torre`, `iniciar_secado`, `inicio_reservado_al_puesto`; `preparar_continuacion` usa el helper y rechaza Secado sin lote / lote ya secado; `preparar_secado_desde_inventario` (renombre); `estado_calidad_secado`, `estado_puesto_secado` | 1, 2, 3 |
| `backend/procesos/views.py` | `CorridaSecadoViewSet.iniciar`, `.preparar_desde_inventario`, `.puesto`, filtros; `EjecucionProcesoViewSet.transicionar` y `operativas` | 1, 2, 3 |
| `backend/procesos/serializers.py` | `get_estado_calidad` delega | 3 |
| `backend/procesos/tests_puesto_secado.py` | nuevo | 1, 2, 3 |
| `backend/procesos/tests_secado.py`, `tests_flujo_suero.py`, `tests_descremacion.py`, `tests_permisos_operacionales.py` | migrar usos | 1, 2 |
| `backend/procesos/dominio.py`, `backend/procesos/tests_destinos.py` | ruta de la etapa | 5 |
| `frontend/src/services/secado.service.ts` | tipos y llamadas del puesto | 4 |
| `frontend/src/services/puesto-secado.ts`, `permisos-secado.ts` + `frontend/tests/puesto-secado.test.ts`, `permisos-secado.test.ts` | nuevos | 4 |
| `frontend/src/services/secado-proceso.ts`, `frontend/tests/secado-proceso.test.ts` | quitar dos tablas sin uso | 4 |
| `frontend/src/pages/Secado/PuestoSecado.tsx`, `TarjetaTorre.tsx`, `TomarConcentrado.tsx` | nuevos | 5 |
| `frontend/src/pages/Secado/Secado.tsx`, `InicioSecadoExterno.tsx` | eliminar | 5 |
| `frontend/src/app/routes.tsx`, `services/navegacion-operacional.ts`, `services/planta-ahora.ts`, `services/access-control.ts` + tests | ruta, menú, destino | 5 |
| `frontend/src/pages/Produccion/SalidasIntermedias.tsx`, `Produccion.tsx`, `BandejaTrabajoArea.tsx`, `pages/Procesos/Procesos.tsx`, `pages/Leche/Silos.tsx` | retirar Secado | 5 |
| `CLAUDE.md` | decisión nueva | 5 |
| `frontend/e2e/flujo-polvo-continuacion.spec.ts`, `flujo-suero.spec.ts`, `rutas.ts`, `README.md` | E2E | 6 |

---

### Task 1: Iniciar una corrida de Secado, una sola implementación

**Files:**
- Modify: `backend/procesos/servicios.py` (constantes arriba; `disponible_de_salida` junto a `motivos_destino_concentrado`; `preparar_continuacion` ~898-999; nuevas funciones antes de `crear_secado_desde_inventario` ~2383)
- Modify: `backend/procesos/views.py` (`CorridaSecadoViewSet` ~743; `EjecucionProcesoViewSet.operativas` ~1037 y `.transicionar` ~1083)
- Create: `backend/procesos/tests_puesto_secado.py`
- Modify: `backend/procesos/tests_permisos_operacionales.py` (`test_transicion_exige_version_y_rechaza_una_obsoleta`, ~255)

**Interfaces:**
- Produces (en `procesos/servicios.py`):
  - `CODIGO_INSPECCION_PREOPERATIVA = "CCAA.Sec.FORM.003"`
  - `AVISO_INSPECCION_PREOPERATIVA = "Falta la inspección pre-operativa de hoy (CCAA.Sec.FORM.003)."`
  - `MENSAJE_INICIO_SECADO_EN_PUESTO = "Las corridas de secado se inician desde el puesto de Secado."`
  - `disponible_de_salida(salida) -> Decimal`
  - `motivos_para_iniciar_secado(corrida, *, ejecucion=None) -> list[str]` (vacía = se puede iniciar)
  - `avisos_de_torre(torre, *, hoy=None) -> list[str]`
  - `iniciar_secado(*, corrida_id, usuario) -> CorridaSecado` (lanza `ValidationError(motivos[0])`)
  - `inicio_reservado_al_puesto(ejecucion, estado_nuevo) -> bool`
  - `POST /api/procesos/secados/{id}/iniciar/` → 200 `CorridaSecadoSerializer`; 400 `{"code", "message", "details"}` con motivos; 403 sin permiso de Secado.
  - `POST /api/procesos/ejecuciones/{id}/transicionar/ {"estado": "ejecucion"}` sobre Secado en `preparacion` → 400 `{"code": "VALIDACION_DOMINIO", "message": "Las corridas de secado se inician desde el puesto de Secado.", …}`.
  - Fixture `BasePuestoSecado` en `tests_puesto_secado.py` (la usan las Tasks 2 y 3).

- [ ] **Step 1: Fixture y pruebas que fallan** — crea `backend/procesos/tests_puesto_secado.py`:

```python
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso, RegistroEquipo
from inventario.models import CicloCIP
from maestros.models import DocumentoLiberacion, Equipo, Mandante, Producto, Silo
from produccion.models import Lote, OrdenProduccion
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import (
    CorridaSecado, EjecucionProceso, EtapaProceso, Proceso, RutaProducto, SalidaProceso,
)
from .servicios import (
    AVISO_INSPECCION_PREOPERATIVA, CODIGO_INSPECCION_PREOPERATIVA,
    MENSAJE_INICIO_SECADO_EN_PUESTO, iniciar_secado, motivos_para_iniciar_secado,
    preparar_continuacion,
)


class BasePuestoSecado(TestCase):
    """
    Un concentrado liberado por Calidad, en un silo, cuya siguiente etapa es
    Secado, y dos torres libres. Es lo que el puesto ve al empezar el turno.
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(rut="PSEC-1", nombre="Empresa puesto secado")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="PSEC", nombre="Planta puesto secado"
        )
        self.secador = self._usuario("secador-puesto", PerfilUsuario.Area.SECADO)
        self.condensador = self._usuario("condensador-puesto", PerfilUsuario.Area.CONDENSACION)
        self.calidad = self._usuario("calidad-puesto", PerfilUsuario.Area.CALIDAD, Rol.CALIDAD)
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Mandante puesto", codigo_cliente="psc"
        )
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Leche entera en polvo", familia=Producto.Familia.POLVO,
        )
        proceso = Proceso.objects.create(codigo="polvo-puesto-sec", nombre="Polvo puesto")
        self.etapa_evaporacion = EtapaProceso.objects.create(
            proceso=proceso, codigo="ev", nombre="Evaporación",
            tipo=EtapaProceso.Tipo.EVAPORACION, orden=1,
        )
        self.etapa_secado = EtapaProceso.objects.create(
            proceso=proceso, codigo="sec", nombre="Secado",
            tipo=EtapaProceso.Tipo.SECADO, orden=2,
        )
        self.ruta = RutaProducto.objects.create(
            sucursal=self.planta, producto=self.producto, proceso=proceso, prioridad=1,
        )
        self.evaporador = Equipo.objects.create(
            sucursal=self.planta, codigo="ev-ps", nombre="Evaporador PS",
            tipo=Equipo.Tipo.EVAPORADOR,
        )
        self.torre = Equipo.objects.create(
            sucursal=self.planta, codigo="e1-ps", nombre="Torre PS 1",
            tipo=Equipo.Tipo.TORRE, sigla="P1",
        )
        self.otra_torre = Equipo.objects.create(
            sucursal=self.planta, codigo="e2-ps", nombre="Torre PS 2",
            tipo=Equipo.Tipo.TORRE, sigla="P2",
        )
        self.silo = Silo.objects.create(
            sucursal=self.planta, codigo="CONC-PS", tipo=Silo.Tipo.SILO, capacidad_l=50000,
        )
        self.orden = OrdenProduccion.objects.create(
            sucursal=self.planta, codigo="OP-PS-1", producto=self.producto,
            cantidad_planificada=Decimal("1000"), unidad="l",
            estado=OrdenProduccion.Estado.EN_PROCESO,
        )
        self.lote = self._lote("CCAA6279PS-01")
        self.salida = self._concentrado(self.lote)
        self.liberacion = self.salida.liberacion_calidad
        # El documento de la inspección es por empresa (`documento_liberacion_
        # codigo_unico`). Se crea el de esta empresa con `update_or_create`:
        # las migraciones siembran el catálogo de otra organización también en
        # la base de pruebas (trampa de CLAUDE.md), y no se borra.
        self.inspeccion, _ = DocumentoLiberacion.objects.update_or_create(
            empresa=self.empresa, codigo=CODIGO_INSPECCION_PREOPERATIVA,
            defaults={
                "nombre": "Inspección Pre-operativa E1-E2", "area": "secado",
                "frecuencia": "por_ciclo",
                "plantilla": [
                    {"clave": "responsable", "etiqueta": "Responsable", "tipo": "texto", "req": True},
                ],
            },
        )

    def _usuario(self, nombre, area, rol=Rol.PRODUCCION):
        usuario = User.objects.create_user(nombre)
        PerfilUsuario.objects.create(
            usuario=usuario, empresa=self.empresa, sucursal=self.planta, area=area, rol=rol,
        )
        return usuario

    def _lote(self, codigo):
        return Lote.objects.create(
            sucursal=self.planta, codigo_lote=codigo, producto=self.producto,
            orden=self.orden, fecha=timezone.localdate(), estado=Lote.Estado.EN_PROCESO,
        )

    def _concentrado(self, lote, cantidad="1000"):
        evaporacion = EjecucionProceso.objects.create(
            codigo=f"EJ-EV-{lote.codigo_lote}", etapa=self.etapa_evaporacion,
            sucursal=self.planta, equipo=self.evaporador,
            estado=EjecucionProceso.Estado.CERRADA,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=evaporacion, lote=lote, silo=self.silo, producto=self.producto,
            ruta_producto=self.ruta, destino=SalidaProceso.Destino.PENDIENTE,
            cantidad=Decimal(cantidad), unidad="L",
        )
        LiberacionProceso.objects.create(salida=salida, estado=LiberacionProceso.Estado.LIBERADO)
        return salida

    def cliente(self, usuario=None):
        cliente = APIClient()
        cliente.force_authenticate(usuario or self.secador)
        return cliente

    def preparar(self, cantidad="600", torre=None, salida=None):
        ejecucion = preparar_continuacion(
            salida_id=(salida or self.salida).pk, etapa_id=self.etapa_secado.pk,
            equipo_id=(torre or self.torre).pk, cantidad=cantidad, usuario=self.secador,
        )
        return ejecucion.corrida_secado

    def inspeccion_de(self, torre, *, fecha=None, valores=None):
        return RegistroEquipo.objects.create(
            sucursal=self.planta, documento=self.inspeccion, equipo=torre,
            fecha=fecha or timezone.localdate(),
            estado=RegistroEquipo.Estado.COMPLETADO,
            valores={"responsable": "Ana"} if valores is None else valores,
        )


class IniciarSecadoTests(BasePuestoSecado):
    def test_sin_motivos_una_preparada_se_puede_iniciar(self):
        corrida = self.preparar()
        self.assertEqual(motivos_para_iniciar_secado(corrida), [])

        respuesta = self.cliente().post(f"/api/procesos/secados/{corrida.pk}/iniciar/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertIsNotNone(corrida.ejecucion.inicio)

    def test_el_aviso_de_inspeccion_queda_en_el_evento_de_inicio(self):
        corrida = self.preparar()

        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)

        evento = corrida.ejecucion.eventos.get(estado_nuevo=EjecucionProceso.Estado.EJECUCION)
        self.assertIn(AVISO_INSPECCION_PREOPERATIVA, evento.motivo)

    def test_una_torre_en_cip_no_inicia_y_la_ejecucion_sigue_preparada(self):
        corrida = self.preparar()
        CicloCIP.objects.create(
            sucursal=self.planta, area=PerfilUsuario.Area.SECADO, equipo=self.torre,
            inicio=timezone.now() - timedelta(hours=1), estado=CicloCIP.Estado.EN_CURSO,
        )
        motivos = motivos_para_iniciar_secado(corrida)
        self.assertTrue(any("CIP" in motivo for motivo in motivos))

        respuesta = self.cliente().post(f"/api/procesos/secados/{corrida.pk}/iniciar/")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(respuesta.data["message"], motivos[0])
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)

    def test_un_aseo_observado_avisa_pero_no_impide_iniciar(self):
        corrida = self.preparar()
        CicloCIP.objects.create(
            sucursal=self.planta, area=PerfilUsuario.Area.SECADO, equipo=self.torre,
            inicio=timezone.now() - timedelta(hours=3), estado=CicloCIP.Estado.OBSERVADO,
        )
        self.assertEqual(motivos_para_iniciar_secado(corrida), [])

    def test_si_calidad_rechazo_el_concentrado_no_inicia(self):
        corrida = self.preparar()
        self.liberacion.estado = LiberacionProceso.Estado.RECHAZADO
        self.liberacion.save(update_fields=["estado"])

        motivos = motivos_para_iniciar_secado(corrida)

        self.assertTrue(any("rechazó" in motivo for motivo in motivos))
        with self.assertRaises(ValidationError) as error:
            iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)
        self.assertEqual(error.exception.messages[0], motivos[0])

    def test_una_corrida_ya_iniciada_no_vuelve_a_iniciar(self):
        corrida = self.preparar()
        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)

        respuesta = self.cliente().post(f"/api/procesos/secados/{corrida.pk}/iniciar/")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)

    def test_sin_permiso_de_secado_responde_403(self):
        corrida = self.preparar()

        respuesta = self.cliente(self.condensador).post(
            f"/api/procesos/secados/{corrida.pk}/iniciar/"
        )

        self.assertEqual(respuesta.status_code, 403)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)


class InicioGenericoCerradoTests(BasePuestoSecado):
    def transicionar(self, ejecucion, estado, motivo=""):
        ejecucion.refresh_from_db()
        return self.cliente().post(
            f"/api/procesos/ejecuciones/{ejecucion.pk}/transicionar/",
            {"estado": estado, "version": ejecucion.version, "motivo": motivo},
            format="json",
        )

    def test_transicionar_no_inicia_una_preparada_de_secado(self):
        corrida = self.preparar()

        respuesta = self.transicionar(corrida.ejecucion, "ejecucion")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(respuesta.data["message"], MENSAJE_INICIO_SECADO_EN_PUESTO)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)

    def test_pausar_y_reanudar_siguen_por_transicionar(self):
        corrida = self.preparar()
        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)

        pausa = self.transicionar(corrida.ejecucion, "pausada")
        reanudar = self.transicionar(corrida.ejecucion, "ejecucion")

        self.assertEqual(pausa.status_code, 200, pausa.data)
        self.assertEqual(reanudar.status_code, 200, reanudar.data)

    def test_la_bandeja_operativa_no_ofrece_iniciar_una_preparada_de_secado(self):
        corrida = self.preparar()

        bandeja = self.cliente().get("/api/procesos/ejecuciones/operativas/")

        fila = next(item for item in bandeja.data if item["id"] == corrida.ejecucion_id)
        self.assertNotIn("ejecucion", fila["acciones_permitidas"])
        self.assertIn("cancelada", fila["acciones_permitidas"])
```

- [ ] **Step 2: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_secado --noinput`
Expected: ERROR `ImportError: cannot import name 'AVISO_INSPECCION_PREOPERATIVA'`.

- [ ] **Step 3: Constantes y saldo compartido** — en `procesos/servicios.py`, debajo de `ESTADOS_EJECUCION_TERMINALES`:

```python
# Registro de planta que la torre pide antes de operar. Avisa, no bloquea:
# que bloquee lo decide Calidad, y sería sobre `avisos_de_torre`.
CODIGO_INSPECCION_PREOPERATIVA = "CCAA.Sec.FORM.003"
AVISO_INSPECCION_PREOPERATIVA = (
    f"Falta la inspección pre-operativa de hoy ({CODIGO_INSPECCION_PREOPERATIVA})."
)
MENSAJE_INICIO_SECADO_EN_PUESTO = "Las corridas de secado se inician desde el puesto de Secado."
```

Debajo de `motivos_destino_concentrado`:

```python
def disponible_de_salida(salida):
    """
    Lo que queda de una salida para continuar: su cantidad menos lo que otras
    ejecuciones ya tomaron como origen y lo comprometido en despachos a granel
    autorizados o despachados.

    Una cantidad, una consulta: `preparar_continuacion` rechaza con esta misma
    función y el puesto de Secado ofrece con ella. Con dos cuentas, la pantalla
    ofrecía litros que el formulario, ya completo, rechazaba (caso 1 de «La
    pantalla ofrece lo que el backend va a rechazar», CLAUDE.md).
    """
    consumido = salida.usos_como_origen.aggregate(total=Sum("cantidad"))["total"] or 0
    comprometido = salida.detalles_despacho_granel.filter(
        despacho__estado__in=["autorizado", "despachado"]
    ).aggregate(total=Sum("cantidad"))["total"] or 0
    return salida.cantidad - consumido - comprometido
```

En `preparar_continuacion`, reemplaza las líneas desde `consumido = salida.usos_como_origen…` hasta `disponible = salida.cantidad - consumido - comprometido_despacho` por:

```python
    disponible = disponible_de_salida(salida)
```

(el `if cantidad > disponible: raise …` que sigue se queda igual).

- [ ] **Step 4: Reglas, avisos e inicio** — en `procesos/servicios.py`, antes de `crear_secado_desde_inventario`:

```python
def inicio_reservado_al_puesto(ejecucion, estado_nuevo):
    """
    ¿Es este paso el inicio de una corrida de Secado? Ese paso solo lo da
    `iniciar_secado`, que es quien aplica `motivos_para_iniciar_secado`.
    Reanudar (`pausada`/`bloqueada` → `ejecucion`) no es iniciar: sigue por la
    transición genérica, o una torre pausada no tendría cómo volver.
    """
    return (
        estado_nuevo == EjecucionProceso.Estado.EJECUCION
        and ejecucion.estado == EjecucionProceso.Estado.PREPARACION
        and ejecucion.etapa.tipo == EtapaProceso.Tipo.SECADO
    )


def motivos_para_iniciar_secado(corrida, *, ejecucion=None):
    """
    Lo que impide iniciar esta corrida de Secado. Lista vacía: se puede.

    Es la única implementación de esas reglas: `iniciar_secado` lanza el primer
    motivo y el puesto los muestra junto a un botón deshabilitado. Un aseo
    observado o una inspección pre-operativa que falta **no** están aquí: son
    avisos (`avisos_de_torre`), no bloquean.
    """
    from calidad.models import LiberacionProceso
    from inventario.servicios import motivo_equipo_no_habilitado

    ejecucion = ejecucion or corrida.ejecucion
    motivos = []
    if ejecucion.estado != EjecucionProceso.Estado.PREPARACION:
        motivos.append(
            f"{ejecucion.codigo} no está preparada: está "
            f"{ejecucion.get_estado_display().lower()}."
        )
    entradas = list(ejecucion.entradas.select_related(
        "salida_origen__silo", "lote_inventario",
    ))
    if not entradas:
        motivos.append("Para iniciar se requiere al menos una entrada de proceso.")
    if not ejecucion.equipo_id:
        motivos.append("La corrida requiere una torre asignada.")
    else:
        impedimento = motivo_equipo_no_habilitado(ejecucion.equipo)
        if impedimento:
            motivos.append(impedimento)
    for entrada in entradas:
        salida = entrada.salida_origen
        if salida is not None:
            nombre = salida.silo.codigo if salida.silo_id else f"la salida {salida.pk}"
            decision = getattr(salida, "liberacion_calidad", None)
            estado = decision.estado if decision is not None else None
            if estado == LiberacionProceso.Estado.RECHAZADO:
                motivos.append(f"Calidad rechazó el concentrado de {nombre}.")
            elif estado != LiberacionProceso.Estado.LIBERADO:
                motivos.append(f"El concentrado de {nombre} no está liberado por Calidad.")
            if disponible_de_salida(salida) < 0:
                motivos.append(
                    f"El concentrado de {nombre} ya no tiene saldo: otra ejecución lo consumió."
                )
        elif entrada.lote_inventario_id and not entrada.lote_inventario.utilizable:
            # El stock ya salió de bodega al preparar; lo que puede cambiar
            # después es la decisión de Calidad sobre el lote del proveedor.
            motivos.append(
                f"El lote externo {entrada.lote_inventario.codigo} ya no está liberado por Calidad."
            )
    return motivos


def avisos_de_torre(torre, *, hoy=None):
    """
    Lo que conviene saber antes de operar la torre y **no bloquea**: el último
    aseo con advertencia y la falta de una inspección pre-operativa completa
    de hoy. «Hay inspección» se decide como en el expediente del lote
    (`cubre_al_lote` + `registro_completo`), pero acotado a **esta** torre.
    """
    from types import SimpleNamespace

    from calidad.dominio import cubre_al_lote, registro_completo
    from calidad.models import RegistroEquipo
    from inventario.servicios import advertencia_aseo_equipo
    from maestros.models import DocumentoLiberacion

    avisos = []
    aseo = advertencia_aseo_equipo(torre)
    if aseo:
        avisos.append(aseo)
    empresa_id = torre.sucursal.empresa_id if torre.sucursal_id else None
    documento = DocumentoLiberacion.objects.filter(
        empresa_id=empresa_id, codigo=CODIGO_INSPECCION_PREOPERATIVA, activo=True,
    ).first()
    if documento is None:
        # Sin el documento configurado no hay dónde registrar la inspección:
        # avisar de algo imposible de cumplir solo enseña a ignorar el aviso.
        return avisos
    jornada = SimpleNamespace(fecha=hoy or timezone.localdate(), turno="")
    # Basta mirar el último mes: la frecuencia más larga que se deduce sola es
    # la semanal (`cubre_al_lote`); `segun_programa` declara su vigencia.
    registros = RegistroEquipo.objects.filter(
        documento=documento, equipo=torre, fecha__lte=jornada.fecha,
    ).order_by("-fecha")[:31]
    if not any(
        cubre_al_lote(registro, documento, jornada) and registro_completo(registro, documento)
        for registro in registros
    ):
        avisos.append(AVISO_INSPECCION_PREOPERATIVA)
    return avisos


@transaction.atomic
def iniciar_secado(*, corrida_id, usuario):
    """
    Pasa una corrida de Secado preparada a ejecución. Recalcula los motivos
    con la ejecución bloqueada —entre que el puesto los mostró y el clic pudo
    entrar un CIP o un rechazo de Calidad— y deja los avisos en el evento.
    """
    corrida = CorridaSecado.objects.select_for_update(of=("self",)).get(pk=corrida_id)
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",))
        .select_related("etapa", "equipo__sucursal")
        .get(pk=corrida.ejecucion_id)
    )
    motivos = motivos_para_iniciar_secado(corrida, ejecucion=ejecucion)
    if motivos:
        raise ValidationError(motivos[0])
    avisos = avisos_de_torre(ejecucion.equipo)
    transicionar_ejecucion(
        ejecucion_id=ejecucion.pk,
        estado_nuevo=EjecucionProceso.Estado.EJECUCION,
        usuario=usuario,
        motivo=(
            "Advertencia no bloqueante: " + " ".join(avisos)
            if avisos else "Inicio desde el puesto de Secado."
        ),
    )
    return (
        CorridaSecado.objects.select_related(
            "ejecucion__etapa", "ejecucion__equipo", "orden", "lote__producto",
            "finalizada_por",
        ).prefetch_related("ejecucion__salidas__liberacion_calidad").get(pk=corrida.pk)
    )
```

- [ ] **Step 5: Vistas** — en `procesos/views.py`:
  - Agrega a la importación de `.servicios`: `MENSAJE_INICIO_SECADO_EN_PUESTO, inicio_reservado_al_puesto, iniciar_secado`.
  - En `CorridaSecadoViewSet`, junto a `cerrar`:

```python
    @action(detail=True, methods=["post"])
    def iniciar(self, request, pk=None):
        """Inicia una corrida preparada: el único camino de inicio de Secado."""
        try:
            corrida = iniciar_secado(corrida_id=self.get_object().pk, usuario=request.user)
        except DjangoValidationError as error:
            return respuesta_error_dominio(error)
        return Response(self.get_serializer(corrida).data)
```

  - En `EjecucionProcesoViewSet.transicionar`, después de validar `version` y **antes** del `try:` que llama a `transicionar_ejecucion` (fuera de toda transacción, así que el `return` no confirma nada):

```python
        actual = self.get_object()
        if inicio_reservado_al_puesto(actual, request.data.get("estado", "")):
            return respuesta_error_dominio(
                DjangoValidationError(MENSAJE_INICIO_SECADO_EN_PUESTO)
            )
```

  y en el `transicionar_ejecucion(...)` que sigue usa `ejecucion_id=actual.pk` en vez de `self.get_object().pk`.
  - En `operativas`, reemplaza el valor de `"acciones_permitidas"` por:

```python
                "acciones_permitidas": (
                    sorted(
                        accion
                        for accion in EjecucionProceso.TRANSICIONES.get(ejecucion.estado, set())
                        if not inicio_reservado_al_puesto(ejecucion, accion)
                    )
                    if puede_operar_tipo(request.user, ejecucion.etapa.tipo)
                    else []
                ),
```

- [ ] **Step 6: Migrar la prueba de versión** — en `procesos/tests_permisos_operacionales.py::test_transicion_exige_version_y_rechaza_una_obsoleta`, cambia `estado=EjecucionProceso.Estado.PREPARACION` por `estado=EjecucionProceso.Estado.PAUSADA` y agrega encima del `create` el comentario:

```python
        # Pausada y no preparada: iniciar una corrida de Secado ya no pasa por
        # `transicionar` (es del puesto), pero reanudarla sí. La prueba sigue
        # midiendo el control de versión sobre una transición a `ejecucion`.
```

El resto de la prueba (sin versión → 400; `ejecucion` con versión 1 → 200; `pausada` con versión 1 → 409; estado final `EJECUCION`) queda igual.

- [ ] **Step 7: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_secado procesos.tests_permisos_operacionales procesos.tests procesos.tests_descremacion procesos.tests_secado --noinput`
Expected: OK.

- [ ] **Step 8: Commit**

```bash
git add backend/procesos/servicios.py backend/procesos/views.py backend/procesos/tests_puesto_secado.py backend/procesos/tests_permisos_operacionales.py
git commit -m "feat(procesos): iniciar Secado tiene un solo camino y una sola función de motivos"
```

---

### Task 2: Tomar alimentación prepara, para las dos fuentes

**Files:**
- Modify: `backend/procesos/servicios.py` (`preparar_continuacion`; `crear_secado_desde_inventario` → `preparar_secado_desde_inventario`)
- Modify: `backend/procesos/views.py` (`CorridaSecadoViewSet.iniciar_desde_inventario` → `preparar_desde_inventario`)
- Modify: `backend/procesos/tests_puesto_secado.py`, `backend/procesos/tests_secado.py` (`InicioSecadoDesdeInventarioTests`), `backend/procesos/tests_flujo_suero.py` (~231), `backend/procesos/tests_descremacion.py` (`test_continuacion_usa_la_primera_etapa_de_la_ruta_de_la_rama`, ~548)

**Interfaces:**
- Consumes: `BasePuestoSecado`, `iniciar_secado` (Task 1).
- Produces:
  - `preparar_secado_desde_inventario(*, orden, existencia, equipo, codigo_lote, cantidad, usuario) -> CorridaSecado` — deja la ejecución en `preparacion`, `inicio=None`, evento `preparacion_secado_externo`.
  - `POST /api/procesos/secados/preparar-desde-inventario/` `{orden, existencia, equipo, codigo_lote, cantidad}` → 201 `CorridaSecadoSerializer` (`estado: "preparacion"`). `iniciar-desde-inventario/` → 404.
  - `preparar_continuacion` con etapa Secado: salida sin lote → `ValidationError("Secado necesita el lote del concentrado: esta salida no tiene lote.")`; lote con corrida de Secado → `ValidationError("El lote {codigo} ya tiene una corrida de Secado; un lote se seca en una sola corrida.")`.

- [ ] **Step 1: Pruebas que fallan** — agrega a `tests_puesto_secado.py`:

```python
class PrepararSecadoTests(BasePuestoSecado):
    def test_preparar_continuacion_hacia_secado_exige_el_permiso_de_secado(self):
        antes = EjecucionProceso.objects.count()

        respuesta = self.cliente(self.condensador).post(
            f"/api/procesos/salidas/{self.salida.pk}/preparar-continuacion/",
            {"etapa": self.etapa_secado.pk, "equipo": self.torre.pk, "cantidad": "100"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(EjecucionProceso.objects.count(), antes)

    def test_un_lote_se_seca_en_una_sola_corrida(self):
        self.preparar(cantidad="400")

        with self.assertRaises(ValidationError) as error:
            self.preparar(cantidad="300", torre=self.otra_torre)

        self.assertIn("ya tiene una corrida de Secado", error.exception.messages[0])

    def test_una_salida_sin_lote_no_se_prepara_para_secado(self):
        self.salida.lote = None
        self.salida.save(update_fields=["lote"])

        with self.assertRaises(ValidationError) as error:
            self.preparar()

        self.assertIn("no tiene lote", error.exception.messages[0])
```

En `tests_secado.py::InicioSecadoDesdeInventarioTests`:
  - Renombra `test_inicia_secado_con_lote_externo_liberado_y_descuenta_stock` a `test_prepara_secado_con_lote_externo_liberado_y_descuenta_stock`, cambia la URL a `/api/procesos/secados/preparar-desde-inventario/` y, después de `corrida = CorridaSecado.objects.get(pk=respuesta.data["id"])`, agrega:

```python
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
        self.assertIsNone(corrida.ejecucion.inicio)
        inicio = self.cliente.post(f"/api/procesos/secados/{corrida.pk}/iniciar/")
        self.assertEqual(inicio.status_code, 200, inicio.data)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
```

  - En `test_calidad_pendiente_no_puede_alimentar_secado`, cambia la URL a `preparar-desde-inventario/`.
  - Agrega:

```python
    def test_el_nombre_que_iniciaba_ya_no_existe(self):
        respuesta = self.cliente.post(
            "/api/procesos/secados/iniciar-desde-inventario/",
            {
                "orden": self.orden.pk, "existencia": self.existencia.pk,
                "equipo": self.torre.pk, "codigo_lote": "SUE-POL-404",
                "cantidad": "10.000",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(Lote.objects.filter(codigo_lote="SUE-POL-404").exists())

    def test_si_calidad_rechaza_el_lote_externo_despues_de_preparar_no_inicia(self):
        from .servicios import motivos_para_iniciar_secado

        respuesta = self.cliente.post(
            "/api/procesos/secados/preparar-desde-inventario/",
            {
                "orden": self.orden.pk, "existencia": self.existencia.pk,
                "equipo": self.torre.pk, "codigo_lote": "SUE-POL-REC",
                "cantidad": "100.000",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.lote_externo.estado_calidad = LoteInventario.EstadoCalidad.RECHAZADO
        self.lote_externo.save(update_fields=["estado_calidad"])
        corrida = CorridaSecado.objects.get(pk=respuesta.data["id"])

        self.assertIn("PROV-SUE-001", motivos_para_iniciar_secado(corrida)[0])
        inicio = self.cliente.post(f"/api/procesos/secados/{corrida.pk}/iniciar/")
        self.assertEqual(inicio.status_code, 400, inicio.data)
```

En `tests_flujo_suero.py` (~231): cambia la URL a `/api/procesos/secados/preparar-desde-inventario/`, y después de `corrida = CorridaSecado.objects.get(pk=inicio.data["id"])` agrega:

```python
        iniciada = self._cliente(self.secador).post(f"/api/procesos/secados/{corrida.pk}/iniciar/")
        self.assertEqual(iniciada.status_code, 200, iniciada.data)
```

En `tests_descremacion.py::test_continuacion_usa_la_primera_etapa_de_la_ruta_de_la_rama`: en el `SalidaProceso.objects.create(...)` cambia `lote=None` por `lote=lote_rama` y créalo justo antes:

```python
        # Secado mueve el lote a la torre (`CorridaSecado.lote`): una salida
        # sin lote no tiene qué secar, y `preparar_continuacion` la rechaza.
        lote_rama = Lote.objects.create(
            sucursal=self.sucursal, codigo_lote="RAMA-SEC-1",
            producto=self.producto_descremada, fecha=timezone.localdate(),
        )
```

(importa `Lote` desde `produccion.models` si el archivo no lo importa).

- [ ] **Step 2: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_secado procesos.tests_secado procesos.tests_flujo_suero --noinput`
Expected: FAIL — `preparar-desde-inventario/` 404; la segunda toma da `IntegrityError`; la salida sin lote se prepara. `test_preparar_continuacion_hacia_secado_exige_el_permiso_de_secado` **pasa ya** (desviación 1).

- [ ] **Step 3: Rechazos en `preparar_continuacion`** — después del `if cantidad > disponible: raise …` y antes de `ejecucion = EjecucionProceso(`:

```python
    if etapa.tipo == EtapaProceso.Tipo.SECADO:
        # `CorridaSecado.lote` es uno a uno: un lote se seca en una sola
        # corrida. Sin estos dos rechazos, la segunda toma reventaba con un
        # IntegrityError y una salida sin lote dejaba una preparación sin
        # corrida, que el puesto no puede iniciar.
        if not salida.lote_id:
            raise ValidationError(
                "Secado necesita el lote del concentrado: esta salida no tiene lote."
            )
        if CorridaSecado.objects.filter(lote_id=salida.lote_id).exists():
            raise ValidationError(
                f"El lote {salida.lote.codigo_lote} ya tiene una corrida de Secado; "
                "un lote se seca en una sola corrida."
            )
```

- [ ] **Step 4: La alimentación externa prepara** — en `procesos/servicios.py`, renombra `crear_secado_desde_inventario` a `preparar_secado_desde_inventario` y:
  - Docstring: `"""Prepara una torre con materia prima externa liberada; el inicio es `iniciar_secado`."""`
  - Quita `advertencia_aseo_equipo` del import y las líneas `advertencia = advertencia_aseo_equipo(equipo)` y el `observacion=(…)` del `Lote(...)`: el aviso de aseo se registra ahora en el evento de inicio (`iniciar_secado`).
  - En `EjecucionProceso(...)`, reemplaza `estado=EjecucionProceso.Estado.EJECUCION, inicio=timezone.now(),` por `estado=EjecucionProceso.Estado.PREPARACION,`.
  - En el `EventoProceso.objects.create(...)` final: `tipo="preparacion_secado_externo"`, `estado_nuevo=EjecucionProceso.Estado.PREPARACION`.
  - El descuento de bodega (`registrar_salida`) se queda al preparar (desviación 6).

- [ ] **Step 5: Vista** — en `CorridaSecadoViewSet`, reemplaza el decorador y el nombre:

```python
    @action(detail=False, methods=["post"], url_path="preparar-desde-inventario")
    def preparar_desde_inventario(self, request):
```

y dentro usa `preparar_secado_desde_inventario(...)`. Actualiza el import de `.servicios` (`crear_secado_desde_inventario` → `preparar_secado_desde_inventario`). Comprueba con `grep -rn "crear_secado_desde_inventario\|iniciar-desde-inventario\|iniciar_desde_inventario" backend` que no queda ningún uso.

- [ ] **Step 6: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos --noinput`
Expected: OK.

- [ ] **Step 7: Commit**

```bash
git add backend/procesos/servicios.py backend/procesos/views.py backend/procesos/tests_puesto_secado.py backend/procesos/tests_secado.py backend/procesos/tests_flujo_suero.py backend/procesos/tests_descremacion.py
git commit -m "feat(procesos): tomar alimentación para Secado prepara la torre, también desde inventario"
```

---

### Task 3: Estado del puesto e historial con filtros de servidor

**Files:**
- Modify: `backend/procesos/servicios.py` (`estado_calidad_secado`, `estado_puesto_secado`)
- Modify: `backend/procesos/serializers.py` (`CorridaSecadoSerializer.get_estado_calidad`)
- Modify: `backend/procesos/views.py` (`CorridaSecadoViewSet`: `puesto`, `FiltraConsultaMixin`)
- Modify: `backend/procesos/tests_puesto_secado.py`
- Modify: `docs/superpowers/specs/2026-10-06-puesto-secado-design.md` (§3.1, §3.3, §5)

**Interfaces:**
- Consumes: `motivos_para_iniciar_secado`, `avisos_de_torre`, `disponible_de_salida`, `AVISO_INSPECCION_PREOPERATIVA`, `BasePuestoSecado` (Tasks 1-2).
- Produces: `GET /api/procesos/secados/puesto/` →

```json
{
  "torres": [{
    "equipo_id": 7, "codigo": "e1", "nombre": "Torre de secado Egron 1",
    "estado": "disponible | preparada | en_curso",
    "corrida": null | { "id": 12, "ejecucion_id": 90, "ejecucion_codigo": "CONT-40-AB12CD34",
                        "ejecucion_estado": "preparacion", "lote_codigo": "CCAA6279VB-01",
                        "origen": "SILO 6", "cantidad": "18000.00", "unidad": "L",
                        "iniciada_en": null },
    "motivos_para_iniciar": ["Torre de secado Egron 1 está en CIP: no puede producir mientras se asea."],
    "resolver_en": "/calidad/inocuidad" | "/calidad" | null,
    "avisos": ["Falta la inspección pre-operativa de hoy (CCAA.Sec.FORM.003)."],
    "falta_inspeccion": true,
    "en_calidad": null | { "id": 11, "lote_codigo": "CCAA6278VB-01" }
  }],
  "concentrados": [{ "salida_id": 40, "etapa_id": 5, "lote_codigo": "CCAA6279VB-01",
                     "producto": "Leche entera en polvo", "silo": "SILO 6",
                     "disponible": "18000.00", "unidad": "L" }],
  "corridas_de_hoy": [{ "id": 11, "equipo": "e1", "lote_codigo": "CCAA6278VB-01",
                        "estado": "cerrada", "estado_calidad": "pendiente" }],
  "estados": [{ "valor": "preparacion", "etiqueta": "Preparación" }]
}
```

  - `GET /api/procesos/secados/?q=&estado=&desde=&hasta=&page=` filtra en el servidor (`q`: lote, código de ejecución o producto; `estado`: estado de la ejecución; fechas sobre `ejecucion__creada_en`).
  - `estado_calidad_secado(corrida) -> "no_requerida" | "pendiente" | "liberado" | "rechazado"`.

- [ ] **Step 1: Pruebas que fallan** — agrega a `tests_puesto_secado.py`:

```python
class PuestoSecadoTests(BasePuestoSecado):
    def puesto(self, usuario=None):
        respuesta = self.cliente(usuario).get("/api/procesos/secados/puesto/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return respuesta.data

    def fila(self, datos, torre):
        return next(item for item in datos["torres"] if item["equipo_id"] == torre.pk)

    def test_una_torre_sin_ejecucion_esta_disponible(self):
        fila = self.fila(self.puesto(), self.torre)
        self.assertEqual(fila["estado"], "disponible")
        self.assertIsNone(fila["corrida"])
        self.assertEqual(fila["motivos_para_iniciar"], [])

    def test_una_preparada_lista_para_iniciar(self):
        corrida = self.preparar(cantidad="600")
        fila = self.fila(self.puesto(), self.torre)
        self.assertEqual(fila["estado"], "preparada")
        self.assertEqual(fila["corrida"]["id"], corrida.pk)
        self.assertEqual(fila["corrida"]["lote_codigo"], self.lote.codigo_lote)
        self.assertEqual(fila["corrida"]["origen"], self.silo.codigo)
        self.assertEqual(fila["corrida"]["cantidad"], "600.000")
        self.assertEqual(fila["motivos_para_iniciar"], [])
        self.assertIsNone(fila["resolver_en"])

    def test_una_preparada_con_motivo_dice_por_que_y_donde_se_resuelve(self):
        self.preparar()
        CicloCIP.objects.create(
            sucursal=self.planta, area=PerfilUsuario.Area.SECADO, equipo=self.torre,
            inicio=timezone.now() - timedelta(hours=1), estado=CicloCIP.Estado.EN_CURSO,
        )
        fila = self.fila(self.puesto(), self.torre)
        self.assertIn("CIP", fila["motivos_para_iniciar"][0])
        self.assertEqual(fila["resolver_en"], "/calidad/inocuidad")

    def test_el_concentrado_rechazado_aparece_como_motivo(self):
        self.preparar()
        self.liberacion.estado = LiberacionProceso.Estado.RECHAZADO
        self.liberacion.save(update_fields=["estado"])
        fila = self.fila(self.puesto(), self.torre)
        self.assertTrue(any("rechazó" in motivo for motivo in fila["motivos_para_iniciar"]))
        self.assertEqual(fila["resolver_en"], "/calidad")

    def test_en_ejecucion_pausada_o_bloqueada_esta_en_curso(self):
        corrida = self.preparar()
        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)
        for estado in ("ejecucion", "pausada", "bloqueada"):
            EjecucionProceso.objects.filter(pk=corrida.ejecucion_id).update(estado=estado)
            with self.subTest(estado=estado):
                fila = self.fila(self.puesto(), self.torre)
                self.assertEqual(fila["estado"], "en_curso")
                self.assertEqual(fila["corrida"]["ejecucion_estado"], estado)

    def test_inspeccion_completa_de_hoy_no_avisa(self):
        self.inspeccion_de(self.torre)
        fila = self.fila(self.puesto(), self.torre)
        self.assertNotIn(AVISO_INSPECCION_PREOPERATIVA, fila["avisos"])
        self.assertFalse(fila["falta_inspeccion"])

    def test_sin_inspeccion_de_hoy_avisa(self):
        fila = self.fila(self.puesto(), self.torre)
        self.assertIn(AVISO_INSPECCION_PREOPERATIVA, fila["avisos"])
        self.assertTrue(fila["falta_inspeccion"])

    def test_la_inspeccion_de_ayer_no_cubre_hoy(self):
        self.inspeccion_de(self.torre, fecha=timezone.localdate() - timedelta(days=1))
        self.assertIn(AVISO_INSPECCION_PREOPERATIVA, self.fila(self.puesto(), self.torre)["avisos"])

    def test_una_inspeccion_incompleta_no_cubre(self):
        self.inspeccion_de(self.torre, valores={})
        self.assertIn(AVISO_INSPECCION_PREOPERATIVA, self.fila(self.puesto(), self.torre)["avisos"])

    def test_la_inspeccion_de_otra_torre_no_cubre_esta(self):
        self.inspeccion_de(self.otra_torre)
        self.assertIn(AVISO_INSPECCION_PREOPERATIVA, self.fila(self.puesto(), self.torre)["avisos"])

    def test_polvo_pendiente_en_calidad_se_informa_y_la_torre_queda_libre(self):
        lote = self._lote("CCAA6278PS-01")
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-SEC-CAL", etapa=self.etapa_secado, sucursal=self.planta,
            equipo=self.torre, estado=EjecucionProceso.Estado.CERRADA,
        )
        corrida = CorridaSecado.objects.create(ejecucion=ejecucion, orden=self.orden, lote=lote)
        salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=lote, producto=self.producto,
            naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
            destino=SalidaProceso.Destino.PENDIENTE, cantidad=Decimal("300"), unidad="kg",
        )
        LiberacionProceso.objects.create(salida=salida)
        fila = self.fila(self.puesto(), self.torre)
        self.assertEqual(fila["estado"], "disponible")
        self.assertEqual(fila["en_calidad"], {"id": corrida.pk, "lote_codigo": lote.codigo_lote})

    def test_concentrados_solo_con_saldo_y_secado_como_siguiente_etapa(self):
        datos = self.puesto()
        self.assertEqual([c["salida_id"] for c in datos["concentrados"]], [self.salida.pk])
        concentrado = datos["concentrados"][0]
        self.assertEqual(concentrado["etapa_id"], self.etapa_secado.pk)
        self.assertEqual(concentrado["disponible"], "1000.000")

        self.preparar(cantidad="400")
        # Con saldo (600 L) pero su lote ya tiene corrida: no se vuelve a ofrecer.
        self.assertEqual(self.puesto()["concentrados"], [])

    def test_no_se_ofrece_un_concentrado_sin_liberar(self):
        self.liberacion.estado = LiberacionProceso.Estado.PENDIENTE
        self.liberacion.save(update_fields=["estado"])
        self.assertEqual(self.puesto()["concentrados"], [])

    def test_corridas_de_hoy_sin_huerfanos(self):
        corrida = self.preparar()
        iniciar_secado(corrida_id=corrida.pk, usuario=self.secador)
        huerfano_lote = self._lote("CCAA6279PS-99")
        huerfana = EjecucionProceso.objects.create(
            codigo="EJ-SEC-HUERFANA", etapa=self.etapa_secado, sucursal=self.planta,
            equipo=self.otra_torre, estado=EjecucionProceso.Estado.CANCELADA,
        )
        CorridaSecado.objects.create(ejecucion=huerfana, orden=self.orden, lote=huerfano_lote)

        datos = self.puesto()

        self.assertEqual(
            [(c["id"], c["equipo"], c["estado"]) for c in datos["corridas_de_hoy"]],
            [(corrida.pk, self.torre.codigo, "ejecucion")],
        )
        self.assertEqual(self.fila(datos, self.otra_torre)["estado"], "disponible")

    def test_calidad_lee_el_puesto(self):
        self.assertIn("torres", self.puesto(self.calidad))

    def test_el_historial_filtra_en_el_servidor(self):
        corrida = self.preparar()
        otro = self._lote("CCAA6280PS-01")
        self.preparar(salida=self._concentrado(otro), torre=self.otra_torre)

        por_lote = self.cliente().get("/api/procesos/secados/", {"q": self.lote.codigo_lote})
        por_estado = self.cliente().get("/api/procesos/secados/", {"estado": "ejecucion"})

        self.assertEqual([c["id"] for c in por_lote.data["results"]], [corrida.pk])
        self.assertEqual(por_estado.data["results"], [])
```

- [ ] **Step 2: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_secado --noinput`
Expected: FAIL — `secados/puesto/` responde 404 (lo toma como `pk`); el filtro `q` no filtra.

- [ ] **Step 3: Servicio** — en `procesos/servicios.py`, después de `iniciar_secado`:

```python
def estado_calidad_secado(corrida):
    """La decisión de Calidad sobre el polvo de una corrida, o `no_requerida`."""
    if not corrida.ejecucion.etapa.requiere_calidad:
        return "no_requerida"
    salida = next(
        (
            salida for salida in corrida.ejecucion.salidas.all()
            if salida.lote_id == corrida.lote_id
            and salida.naturaleza == SalidaProceso.Naturaleza.PRINCIPAL
        ),
        None,
    )
    decision = getattr(salida, "liberacion_calidad", None) if salida else None
    return decision.estado if decision else "pendiente"


def estado_puesto_secado(usuario):
    """
    Lo que el puesto de Secado dibuja: un estado por torre derivado de su
    ejecución de Secado activa (la que ocupa el equipo; una en curso manda
    sobre una preparada), con los motivos que impiden iniciar calculados por
    la misma función que decide al iniciar; los concentrados que se pueden
    tomar, con el saldo que `preparar_continuacion` va a aceptar; y las
    corridas de hoy. La pantalla no recalcula nada de esto.

    Las ejecuciones `cerrada`/`cancelada` no ocupan la torre: un huérfano de
    un E2E abortado no deja la máquina tomada (`ESTADOS_QUE_OCUPAN_EQUIPO`).
    """
    from calidad.models import LiberacionProceso
    from inventario.servicios import motivo_equipo_no_habilitado
    from maestros.models import Equipo
    from usuarios.tenancy import filtrar_por_scope

    torres = list(filtrar_por_scope(
        Equipo.objects.filter(activo=True, tipo=Equipo.Tipo.TORRE)
        .select_related("sucursal").order_by("codigo"),
        usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    ))
    ids = [torre.pk for torre in torres]

    activas = {}
    for ejecucion in (
        EjecucionProceso.objects.filter(
            etapa__tipo=EtapaProceso.Tipo.SECADO, equipo_id__in=ids,
            estado__in=ESTADOS_QUE_OCUPAN_EQUIPO,
        )
        .select_related("etapa", "equipo", "corrida_secado__lote")
        .prefetch_related("entradas__silo", "entradas__lote_inventario")
        .order_by("pk")
    ):
        actual = activas.get(ejecucion.equipo_id)
        if actual is None or (
            actual.estado == EjecucionProceso.Estado.PREPARACION
            and ejecucion.estado != EjecucionProceso.Estado.PREPARACION
        ):
            activas[ejecucion.equipo_id] = ejecucion

    en_calidad = {}
    for corrida in (
        CorridaSecado.objects.filter(
            ejecucion__equipo_id__in=ids,
            ejecucion__salidas__naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
            ejecucion__salidas__liberacion_calidad__estado=LiberacionProceso.Estado.PENDIENTE,
        ).select_related("ejecucion", "lote").order_by("pk")
    ):
        en_calidad[corrida.ejecucion.equipo_id] = corrida

    def resumen(ejecucion):
        corrida = getattr(ejecucion, "corrida_secado", None)
        entrada = next(iter(ejecucion.entradas.all()), None)
        origen = None
        if entrada is not None and entrada.silo_id:
            origen = entrada.silo.codigo
        elif entrada is not None and entrada.lote_inventario_id:
            origen = entrada.lote_inventario.codigo
        return {
            "id": corrida.pk if corrida else None,
            "ejecucion_id": ejecucion.pk,
            "ejecucion_codigo": ejecucion.codigo,
            "ejecucion_estado": ejecucion.estado,
            "lote_codigo": corrida.lote.codigo_lote if corrida else None,
            "origen": origen,
            # Texto, como en los serializers: el tipo del frontend es `string`.
            "cantidad": str(entrada.cantidad) if entrada else None,
            "unidad": entrada.unidad if entrada else None,
            "iniciada_en": ejecucion.inicio,
        }

    filas = []
    for torre in torres:
        ejecucion = activas.get(torre.pk)
        motivos, resolver_en = [], None
        if ejecucion is None:
            estado = "disponible"
        elif ejecucion.estado == EjecucionProceso.Estado.PREPARACION:
            estado = "preparada"
            corrida = getattr(ejecucion, "corrida_secado", None)
            if corrida is None:
                motivos = [
                    f"{ejecucion.codigo} no tiene lote de Secado: cancélala y vuelve "
                    "a tomar el concentrado."
                ]
            else:
                motivos = motivos_para_iniciar_secado(corrida, ejecucion=ejecucion)
                if motivos:
                    # Dónde se resuelve, como dato: la pantalla no adivina
                    # leyendo el texto del motivo.
                    resolver_en = (
                        "/calidad/inocuidad" if motivo_equipo_no_habilitado(torre) else "/calidad"
                    )
        else:
            estado = "en_curso"
        avisos = [] if estado == "en_curso" else avisos_de_torre(torre)
        pendiente = en_calidad.get(torre.pk)
        filas.append({
            "equipo_id": torre.pk, "codigo": torre.codigo, "nombre": torre.nombre,
            "estado": estado,
            "corrida": resumen(ejecucion) if ejecucion is not None else None,
            "motivos_para_iniciar": motivos,
            "resolver_en": resolver_en,
            "avisos": avisos,
            "falta_inspeccion": AVISO_INSPECCION_PREOPERATIVA in avisos,
            "en_calidad": (
                {"id": pendiente.pk, "lote_codigo": pendiente.lote.codigo_lote}
                if pendiente is not None else None
            ),
        })

    concentrados = []
    salidas = filtrar_por_scope(
        SalidaProceso.objects.filter(
            liberacion_calidad__estado=LiberacionProceso.Estado.LIBERADO,
            silo__isnull=False, lote__isnull=False, lote__corrida_secado__isnull=True,
            destino__in=[
                SalidaProceso.Destino.PENDIENTE,
                SalidaProceso.Destino.SIGUIENTE_PROCESO,
                SalidaProceso.Destino.ESTANDARIZACION,
            ],
        ).exclude(naturaleza=SalidaProceso.Naturaleza.MERMA)
        .select_related("ejecucion__etapa", "silo", "lote__producto", "ruta_producto")
        .order_by("lote__codigo_lote", "pk"),
        usuario, campo_sucursal="ejecucion__sucursal_id",
        campo_empresa="ejecucion__sucursal__empresa_id",
    )
    for salida in salidas:
        siguiente = siguiente_etapa_para_salida(salida=salida)
        if siguiente is None or siguiente.tipo != EtapaProceso.Tipo.SECADO:
            continue
        disponible = disponible_de_salida(salida)
        if disponible <= 0:
            continue
        concentrados.append({
            "salida_id": salida.pk, "etapa_id": siguiente.pk,
            "lote_codigo": salida.lote.codigo_lote,
            "producto": salida.lote.producto.nombre if salida.lote.producto_id else "",
            "silo": salida.silo.codigo,
            "disponible": str(disponible), "unidad": salida.unidad,
        })

    hoy = timezone.localdate()
    corridas_de_hoy = [
        {
            "id": corrida.pk,
            "equipo": corrida.ejecucion.equipo.codigo if corrida.ejecucion.equipo_id else None,
            "lote_codigo": corrida.lote.codigo_lote,
            "estado": corrida.ejecucion.estado,
            "estado_calidad": estado_calidad_secado(corrida),
        }
        # Iniciadas o cerradas hoy: una preparación que nunca empezó no es
        # trabajo del día, y un huérfano cancelado sin iniciar tampoco.
        for corrida in CorridaSecado.objects.filter(ejecucion__equipo_id__in=ids)
        .filter(Q(ejecucion__inicio__date=hoy) | Q(finalizada_en__date=hoy))
        .select_related("ejecucion__etapa", "ejecucion__equipo", "lote")
        .prefetch_related("ejecucion__salidas__liberacion_calidad")
        .order_by("-pk")
    ]
    return {
        "torres": filas,
        "concentrados": concentrados,
        "corridas_de_hoy": corridas_de_hoy,
        "estados": [
            {"valor": valor, "etiqueta": etiqueta}
            for valor, etiqueta in EjecucionProceso.Estado.choices
        ],
    }
```

- [ ] **Step 4: Serializer de una sola regla** — en `CorridaSecadoSerializer` reemplaza el cuerpo de `get_estado_calidad`:

```python
    def get_estado_calidad(self, corrida):
        from .servicios import estado_calidad_secado

        return estado_calidad_secado(corrida)
```

- [ ] **Step 5: Vista y filtros** — en `procesos/views.py`:
  - `from inventario.views import FiltraConsultaMixin` (inventario no importa `procesos` a nivel de módulo, no hay ciclo; la Step 7 lo verifica).
  - Importa `estado_puesto_secado` desde `.servicios`.
  - `CorridaSecadoViewSet`:

```python
class CorridaSecadoViewSet(FiltraConsultaMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "ejecucion__sucursal_id"
    tenant_lookup_empresa = "ejecucion__sucursal__empresa_id"
    queryset = CorridaSecado.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden", "lote__producto",
        "finalizada_por",
    ).prefetch_related("ejecucion__salidas__liberacion_calidad").order_by("-pk")
    # Historial del puesto: se filtra en el servidor porque la lista está
    # paginada (mismo contrato que Existencias y el historial de Despacho).
    busqueda_en = ("lote__codigo_lote", "ejecucion__codigo", "lote__producto__nombre")
    filtro_estado = "ejecucion__estado"
    filtro_fecha = "ejecucion__creada_en"
```

  y la acción, junto a `opciones_alimentacion_externa`:

```python
    @action(detail=False, methods=["get"])
    def puesto(self, request):
        """Estado del puesto de Secado: lo que la pantalla dibuja, sin recalcular."""
        return Response(estado_puesto_secado(request.user))
```

- [ ] **Step 6: Ajustar la spec** — en `docs/superpowers/specs/2026-10-06-puesto-secado-design.md`:
  - §3.1: agrega al ejemplo `corrida.{ejecucion_id, ejecucion_codigo, ejecucion_estado}`, `resolver_en`, `falta_inspeccion`, `concentrados[].etapa_id` y `estados`, con una línea: «Las claves extra existen para no adivinar: `etapa_id` lo exige `preparar-continuacion`; el enlace y el aviso de inspección viajan tipados».
  - §3.3: «la torre está habilitada (`motivo_equipo_no_habilitado`: no en CIP)»; el aseo observado pasa a la lista de avisos. Agrega: «Una salida sin lote o un lote que ya tiene corrida de Secado no se preparan (`CorridaSecado.lote` es uno a uno)».
  - §3.3, «Un solo camino de inicio»: «rechaza pasar de `preparacion` a `ejecucion`… Reanudar desde `pausada` o `bloqueada` sigue disponible».
  - §5: «`motivos_para_iniciar` vacío y con motivo (CIP, salida de origen rechazada); aseo observado: aviso».

- [ ] **Step 7: Verificar y commit**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos inventario --noinput`
Expected: OK.

```bash
git add backend/procesos/servicios.py backend/procesos/serializers.py backend/procesos/views.py backend/procesos/tests_puesto_secado.py docs/superpowers/specs/2026-10-06-puesto-secado-design.md
git commit -m "feat(procesos): estado del puesto de Secado y su historial filtrado en el servidor"
```

---

### Task 4: Servicios del frontend y reglas puras

**Files:**
- Modify: `frontend/src/services/secado.service.ts`
- Create: `frontend/src/services/puesto-secado.ts`, `frontend/src/services/permisos-secado.ts`
- Create: `frontend/tests/puesto-secado.test.ts`, `frontend/tests/permisos-secado.test.ts`
- Modify: `frontend/src/services/secado-proceso.ts`, `frontend/tests/secado-proceso.test.ts` (comentario)

**Interfaces:**
- Consumes: endpoints de las Tasks 1-3.
- Produces (`secado.service.ts`):
  - `export type EstadoTorre = "disponible" | "preparada" | "en_curso";`
  - `export interface CorridaTorre { id: number | null; ejecucion_id: number; ejecucion_codigo: string; ejecucion_estado: string; lote_codigo: string | null; origen: string | null; cantidad: string | null; unidad: string | null; iniciada_en: string | null }`
  - `export interface TorrePuesto { equipo_id: number; codigo: string; nombre: string; estado: EstadoTorre; corrida: CorridaTorre | null; motivos_para_iniciar: string[]; resolver_en: string | null; avisos: string[]; falta_inspeccion: boolean; en_calidad: { id: number; lote_codigo: string } | null }`
  - `export interface ConcentradoPuesto { salida_id: number; etapa_id: number; lote_codigo: string; producto: string; silo: string; disponible: string; unidad: string }`
  - `export interface CorridaDeHoySecado { id: number; equipo: string | null; lote_codigo: string; estado: string; estado_calidad: string }`
  - `export interface PuestoSecado { torres: TorrePuesto[]; concentrados: ConcentradoPuesto[]; corridas_de_hoy: CorridaDeHoySecado[]; estados: { valor: string; etiqueta: string }[] }`
  - `obtenerPuestoSecado(): Promise<PuestoSecado>`; `iniciarSecado(id: number): Promise<CorridaSecado>`; `prepararSecadoExterno(datos: PreparacionSecadoExterno): Promise<CorridaSecado>`; `buscarSecados(filtros?: Filtros): Promise<Pagina<CorridaSecado>>`. `iniciarSecadoExterno`, `InicioSecadoExterno` y `obtenerSecados` se eliminan.
- Produces (`puesto-secado.ts`): `accionDeTorre(fila: TorrePuesto): { tipo: "tomar" | "iniciar" | "cerrar" | "ninguna"; habilitada: boolean; motivo: string | null }`; `situacionDeCorrida(estado: string, estadoCalidad?: string): string`.
- Produces (`permisos-secado.ts`): `puedeOperarSecado(usuario): boolean`.

- [ ] **Step 1: Pruebas que fallan** — `frontend/tests/puesto-secado.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

import { accionDeTorre, situacionDeCorrida } from "../src/services/puesto-secado.ts";

const base = {
  equipo_id: 1, codigo: "e1", nombre: "Torre 1", corrida: null,
  motivos_para_iniciar: [] as string[], resolver_en: null, avisos: [] as string[],
  falta_inspeccion: false, en_calidad: null,
};
const corrida = {
  id: 12, ejecucion_id: 90, ejecucion_codigo: "CONT-40", ejecucion_estado: "preparacion",
  lote_codigo: "CCAA6279VB-01", origen: "SILO 6", cantidad: "18000.00", unidad: "L", iniciada_en: null,
};

test("una torre disponible ofrece tomar concentrado", () => {
  assert.deepEqual(accionDeTorre({ ...base, estado: "disponible" }), { tipo: "tomar", habilitada: true, motivo: null });
});

test("una preparada sin motivos se puede iniciar", () => {
  assert.deepEqual(accionDeTorre({ ...base, estado: "preparada", corrida }), { tipo: "iniciar", habilitada: true, motivo: null });
});

test("una preparada con motivos muestra el primero y no habilita iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, motivos_para_iniciar: ["Torre 1 está en CIP.", "otro"] };
  assert.deepEqual(accionDeTorre(fila), { tipo: "iniciar", habilitada: false, motivo: "Torre 1 está en CIP." });
});

test("los avisos no deshabilitan iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, avisos: ["Falta la inspección"], falta_inspeccion: true };
  assert.equal(accionDeTorre(fila).habilitada, true);
});

test("una preparación sin corrida de Secado no se puede iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida: { ...corrida, id: null }, motivos_para_iniciar: [] };
  assert.equal(accionDeTorre(fila).habilitada, false);
});

test("en curso ofrece cerrar, salvo bloqueada", () => {
  const enCurso = { ...base, estado: "en_curso" as const, corrida: { ...corrida, ejecucion_estado: "ejecucion" } };
  assert.deepEqual(accionDeTorre(enCurso), { tipo: "cerrar", habilitada: true, motivo: null });
  const bloqueada = { ...enCurso, corrida: { ...corrida, ejecucion_estado: "bloqueada" } };
  assert.equal(accionDeTorre(bloqueada).habilitada, false);
  assert.match(accionDeTorre(bloqueada).motivo ?? "", /bloqueada/);
});

test("la situación de una corrida sale de bandejaDeSecado", () => {
  assert.equal(situacionDeCorrida("ejecucion"), "En la torre");
  assert.equal(situacionDeCorrida("cerrada", "pendiente"), "Esperando Calidad");
  assert.equal(situacionDeCorrida("cerrada", "liberado"), "Terminada");
  assert.equal(situacionDeCorrida("cancelada"), "Cancelada");
});
```

`frontend/tests/permisos-secado.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

import { puedeOperarSecado } from "../src/services/permisos-secado.ts";

const conArea = (area: string, rol = "produccion") => ({ rol, perfil: { area } });

test("Secado opera su puesto", () => {
  assert.equal(puedeOperarSecado(conArea("secado")), true);
});

test("Condensación no opera la torre, como en el servidor", () => {
  assert.equal(puedeOperarSecado(conArea("condensacion")), false);
});

test("Calidad consulta pero no opera", () => {
  assert.equal(puedeOperarSecado(conArea("calidad", "calidad")), false);
});

test("Administración y el administrador operan", () => {
  assert.equal(puedeOperarSecado(conArea("administracion")), true);
  assert.equal(puedeOperarSecado({ rol: "admin", perfil: null }), true);
});

test("sin sesión o sin área no se opera", () => {
  assert.equal(puedeOperarSecado(null), false);
  assert.equal(puedeOperarSecado({ rol: "produccion", perfil: null }), false);
});
```

Run: `cd frontend && npm test` → FAIL (módulos inexistentes).

- [ ] **Step 2: Reglas puras** — `frontend/src/services/puesto-secado.ts`:

```ts
import { bandejaDeSecado } from "./secado-proceso.ts";
import type { TorrePuesto } from "./secado.service.ts";

export interface AccionTorre {
  tipo: "tomar" | "iniciar" | "cerrar" | "ninguna";
  habilitada: boolean;
  motivo: string | null;
}

/*
  Qué botón lleva la tarjeta de una torre. Solo traduce lo que mandó el
  servidor: estado y motivos los calcula `estado_puesto_secado` con la misma
  función que decide al iniciar (`motivos_para_iniciar_secado`). Los avisos
  no entran aquí a propósito: avisan, no deshabilitan.

  La única regla propia es la de una corrida bloqueada, que es espejo de
  `cerrar_secado` (solo cierra `ejecucion` o `pausada`): ofrecer el balance
  sobre una bloqueada es ofrecer algo que el servidor rechaza.
*/
export function accionDeTorre(fila: TorrePuesto): AccionTorre {
  switch (fila.estado) {
    case "disponible":
      return { tipo: "tomar", habilitada: true, motivo: null };
    case "preparada": {
      const motivo = fila.motivos_para_iniciar[0] ?? null;
      return { tipo: "iniciar", habilitada: motivo === null && fila.corrida?.id != null, motivo };
    }
    case "en_curso":
      if (fila.corrida?.ejecucion_estado === "bloqueada") {
        return {
          tipo: "cerrar",
          habilitada: false,
          motivo: "La corrida está bloqueada: resuelve el bloqueo antes de cerrar.",
        };
      }
      return { tipo: "cerrar", habilitada: fila.corrida?.id != null, motivo: null };
    default:
      return { tipo: "ninguna", habilitada: false, motivo: null };
  }
}

const SITUACION = {
  activas: "En la torre",
  calidad: "Esperando Calidad",
  terminadas: "Terminada",
  historial: "Cancelada",
} as const;

/* Cómo se nombra una corrida en «Corridas de hoy» y en el historial. La
   clasificación es `bandejaDeSecado` y nada más: una sola regla. */
export function situacionDeCorrida(estado: string, estadoCalidad?: string): string {
  return SITUACION[bandejaDeSecado(estado, estadoCalidad)];
}
```

`frontend/src/services/permisos-secado.ts`:

```ts
import type { Usuario } from "./sesion.ts";

/*
  Quién opera el puesto de Secado. Refleja `procesos.permisos`
  (`TIPOS_OPERABLES_POR_AREA`): la etapa Secado la opera el área Secado y el
  administrador —rol efectivo `admin`, que el servidor también da al área
  Administración—. Calidad ve el puesto en modo consulta; Condensación no
  opera la torre aunque escriba lotes.

  Cortesía para no ofrecer botones que el servidor rechaza con 403; el
  permiso se aplica allá.
*/
type ConPerfil = (Pick<Usuario, "rol"> & { perfil: Pick<NonNullable<Usuario["perfil"]>, "area"> | null }) | null | undefined;

export function puedeOperarSecado(usuario: ConPerfil): boolean {
  if (!usuario) return false;
  const area = usuario.perfil?.area;
  return usuario.rol === "admin" || area === "administracion" || area === "secado";
}
```

- [ ] **Step 3: Servicio** — en `frontend/src/services/secado.service.ts`:
  - Imports: `import { conFiltros, type Filtros } from "./paginacion";` (deja `Pagina` desde `./procesos.service`).
  - Agrega los tipos de **Interfaces** (`EstadoTorre`, `CorridaTorre`, `TorrePuesto`, `ConcentradoPuesto`, `CorridaDeHoySecado`, `PuestoSecado`).
  - Renombra `interface InicioSecadoExterno` a `PreparacionSecadoExterno` (mismos campos).
  - Elimina `obtenerSecados` e `iniciarSecadoExterno`; agrega:

```ts
export async function obtenerPuestoSecado(): Promise<PuestoSecado> {
  const { data } = await api.get<PuestoSecado>("procesos/secados/puesto/");
  return data;
}

export async function iniciarSecado(id: number): Promise<CorridaSecado> {
  const { data } = await api.post<CorridaSecado>(`procesos/secados/${id}/iniciar/`);
  return data;
}

export async function prepararSecadoExterno(
  datos: PreparacionSecadoExterno,
): Promise<CorridaSecado> {
  const { data } = await api.post<CorridaSecado>(
    "procesos/secados/preparar-desde-inventario/", datos,
  );
  return data;
}

/* Historial del puesto: filtros y página viajan al servidor. */
export async function buscarSecados(filtros: Filtros = {}): Promise<Pagina<CorridaSecado>> {
  const { data } = await api.get<Pagina<CorridaSecado>>(conFiltros("procesos/secados/", filtros));
  return data;
}
```

- [ ] **Step 4: Tablas sin uso** — en `frontend/src/services/secado-proceso.ts` elimina `estadoFisicoSecado` y `siguienteAccionSecado` (solo las usaba `Secado.tsx`, que la Task 5 elimina; la tarjeta de torre dice lo mismo desde el servidor). En `frontend/tests/secado-proceso.test.ts` reemplaza el comentario inicial por:

```ts
/*
  Lo que decide algo —qué bandeja recibe cada corrida, y si el balance
  cierra— está cubierto abajo. `situacionDeCorrida` (puesto-secado) nombra
  la bandeja; su prueba vive en puesto-secado.test.ts.
*/
```

Nota: `Secado.tsx` e `InicioSecadoExterno.tsx` dejan de compilar en este paso; se eliminan en la Task 5. Para que este commit compile, elimínalos **aquí** con `git rm frontend/src/pages/Secado/Secado.tsx frontend/src/pages/Secado/InicioSecadoExterno.tsx` y en `frontend/src/app/routes.tsx` reemplaza temporalmente `<Route path="/secado" element={diferido(<Secado />)} />` por `<Route path="/secado" element={<Navigate to="/produccion" replace />} />` y quita el `lazy` de `Secado`. La Task 5 pone la ruta definitiva.

- [ ] **Step 5: Verificar**

Run: `cd frontend && npm test && npx tsc -b --pretty false && npx eslint src/services src/app tests`
Expected: PASS / sin errores.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services/secado.service.ts frontend/src/services/puesto-secado.ts frontend/src/services/permisos-secado.ts frontend/src/services/secado-proceso.ts frontend/tests/puesto-secado.test.ts frontend/tests/permisos-secado.test.ts frontend/tests/secado-proceso.test.ts frontend/src/app/routes.tsx
git commit -m "feat(secado): servicios y reglas puras del puesto de Secado"
```

(`git rm` ya dejó preparadas las dos eliminaciones.)

---

### Task 5: El puesto y el retiro de lo viejo

**Files:**
- Create: `frontend/src/pages/Secado/PuestoSecado.tsx`, `TarjetaTorre.tsx`, `TomarConcentrado.tsx`
- Modify: `frontend/src/app/routes.tsx`, `frontend/src/services/navegacion-operacional.ts`, `frontend/src/services/planta-ahora.ts`, `frontend/src/services/access-control.ts`, `frontend/tests/navegacion-operacional.test.ts`, `frontend/tests/planta-ahora.test.ts`
- Modify: `frontend/src/pages/Produccion/SalidasIntermedias.tsx`, `Produccion.tsx`, `BandejaTrabajoArea.tsx`, `frontend/src/pages/Procesos/Procesos.tsx`, `frontend/src/pages/Leche/Silos.tsx`
- Modify: `backend/procesos/dominio.py`, `backend/procesos/tests_destinos.py`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `obtenerPuestoSecado`, `iniciarSecado`, `obtenerSecado`, `buscarSecados`, `prepararSecadoExterno`, `obtenerOpcionesSecadoExterno`, `accionDeTorre`, `situacionDeCorrida`, `puedeOperarSecado` (Task 4); `prepararContinuacion(salidaId, { etapa, equipo, cantidad })` (`procesos.service.ts`); `CierreSecado` (`{ corrida, alCerrar, alCompletarse }`); `ConfirmarAccion`; `TablaConsulta`; `useCarga`, `mensajeDe`; `mensajeErrorProceso`.

- [ ] **Step 1: Tarjeta** — `frontend/src/pages/Secado/TarjetaTorre.tsx`:

```tsx
import { Link } from "react-router-dom";

import { cantidad } from "../../services/formato";
import { accionDeTorre } from "../../services/puesto-secado";
import type { TorrePuesto } from "../../services/secado.service";

const ROTULO = { disponible: "Disponible", preparada: "Preparada", en_curso: "En curso" } as const;

/* Una tarjeta, un estado, una acción. Lo que dice lo decidió el servidor. */
export default function TarjetaTorre({ fila, ocupado, puedeOperar, onTomar, onIniciar, onCerrar }: {
  fila: TorrePuesto;
  ocupado: boolean;
  /* Quien no opera Secado (Calidad) ve el mismo estado, los mismos motivos
     y avisos, sin botones: ninguno le daría otra cosa que un 403. */
  puedeOperar: boolean;
  onTomar: (equipoId: number) => void;
  onIniciar: (corridaId: number) => void;
  onCerrar: (corridaId: number) => void;
}) {
  const accion = accionDeTorre(fila);
  const corrida = fila.corrida;
  const corridaId = corrida?.id ?? null;
  return (
    <article aria-label={fila.nombre} className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">{fila.nombre}</h3>
          <p className="font-mono text-xs text-slate-600">{fila.codigo}</p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-800">{ROTULO[fila.estado]}</span>
      </header>
      {corrida && (
        <p className="text-sm text-slate-700">
          {corrida.lote_codigo
            ? <>Lote <span className="font-mono">{corrida.lote_codigo}</span></>
            : <span className="font-mono">{corrida.ejecucion_codigo}</span>}
          {corrida.origen && (
            <span className="block">Desde {corrida.origen} · {cantidad(corrida.cantidad, corrida.unidad ?? undefined)}</span>
          )}
          {corrida.iniciada_en && <span className="block text-slate-600">Inició {new Date(corrida.iniciada_en).toLocaleString("es-CL")}</span>}
        </p>
      )}
      {fila.en_calidad && (
        <p className="text-sm text-violet-800">Polvo de <span className="font-mono">{fila.en_calidad.lote_codigo}</span> esperando Calidad</p>
      )}
      {accion.tipo === "tomar" && puedeOperar && (
        <button type="button" onClick={() => onTomar(fila.equipo_id)} className="rounded-xl bg-amber-700 px-4 py-3 text-sm font-semibold text-white hover:bg-amber-800">Tomar concentrado</button>
      )}
      {accion.tipo === "iniciar" && puedeOperar && corridaId !== null && (
        <button type="button" disabled={!accion.habilitada || ocupado} onClick={() => onIniciar(corridaId)} className="rounded-xl bg-amber-700 px-4 py-3 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-40">
          {ocupado ? "Iniciando…" : "Iniciar secado"}
        </button>
      )}
      {accion.tipo === "cerrar" && puedeOperar && corridaId !== null && (
        <button type="button" disabled={!accion.habilitada} onClick={() => onCerrar(corridaId)} className="rounded-xl bg-green-700 px-4 py-3 text-sm font-semibold text-white hover:bg-green-800 disabled:opacity-40">Registrar balance y cerrar</button>
      )}
      {accion.motivo && (
        <p className="text-sm text-red-800">
          {accion.motivo}
          {fila.resolver_en && <>{" "}<Link to={fila.resolver_en} className="font-semibold underline">Ver dónde se resuelve</Link></>}
        </p>
      )}
      {fila.avisos.length > 0 && (
        <ul className="space-y-1 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {fila.avisos.map((aviso) => <li key={aviso}>{aviso}</li>)}
          {fila.falta_inspeccion && (
            <li><Link to="/registros" className="font-semibold underline">Registrar la inspección pre-operativa</Link></li>
          )}
        </ul>
      )}
    </article>
  );
}
```

- [ ] **Step 2: Formulario guiado** — `frontend/src/pages/Secado/TomarConcentrado.tsx`:

```tsx
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { X } from "lucide-react";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import { prepararContinuacion } from "../../services/procesos.service";
import {
  obtenerOpcionesSecadoExterno, prepararSecadoExterno,
  type ConcentradoPuesto, type OpcionesSecadoExterno, type TorrePuesto,
} from "../../services/secado.service";

type Fuente = "concentrado" | "externa";
const campo = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-amber-600";

/*
  Tomar alimentación para una torre: fuente → torre → cantidad → resumen.
  Las dos fuentes **preparan** y nada más; iniciar es otro paso, en la
  tarjeta, con las mismas reglas para las dos. Las opciones vienen del
  servidor: los concentrados con el saldo que `preparar-continuacion`
  aceptará, y solo las torres que el puesto da por disponibles.
*/
export default function TomarConcentrado({ torres, concentrados, torreInicial, alCerrar, alPreparar }: {
  torres: TorrePuesto[];
  concentrados: ConcentradoPuesto[];
  torreInicial?: number;
  alCerrar: () => void;
  alPreparar: (mensaje: string) => void;
}) {
  const [fuente, setFuente] = useState<Fuente>("concentrado");
  const [salidaId, setSalidaId] = useState("");
  const [torre, setTorre] = useState(torreInicial ? String(torreInicial) : "");
  const [valor, setValor] = useState("");
  const [opciones, setOpciones] = useState<OpcionesSecadoExterno | null>(null);
  const [orden, setOrden] = useState("");
  const [existencia, setExistencia] = useState("");
  const [codigoLote, setCodigoLote] = useState("");
  const [revisando, setRevisando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const enviando = useRef(false);

  useEffect(() => {
    if (fuente !== "externa" || opciones) return;
    const controller = new AbortController();
    // Diferido como en el modal anterior: StrictMode monta dos veces y el
    // segundo montaje no debe heredar la promesa que el primero canceló.
    const tarea = window.setTimeout(() => {
      obtenerOpcionesSecadoExterno(controller.signal)
        .then(setOpciones)
        .catch((causa) => {
          if (!controller.signal.aborted) setError(mensajeErrorProceso(causa, "No se pudieron cargar las materias primas para Secado."));
        });
    }, 0);
    return () => { window.clearTimeout(tarea); controller.abort(); };
  }, [fuente, opciones]);

  const libres = torres.filter((item) => item.estado === "disponible");
  const torreElegida = libres.find((item) => item.equipo_id === Number(torre));
  const concentrado = concentrados.find((item) => item.salida_id === Number(salidaId));
  const ordenElegida = opciones?.ordenes.find((item) => item.id === Number(orden));
  const existencias = useMemo(
    () => (opciones?.existencias ?? []).filter((item) => !ordenElegida || item.insumo_id === ordenElegida.insumo_origen_id),
    [opciones, ordenElegida],
  );
  const existenciaElegida = existencias.find((item) => item.id === Number(existencia));
  const unidad = fuente === "concentrado" ? concentrado?.unidad ?? "" : "kg";
  const maximo = fuente === "concentrado" ? concentrado?.disponible : existenciaElegida?.cantidad_disponible;
  const completo = Boolean(torreElegida) && Number(valor) > 0 && (
    fuente === "concentrado" ? Boolean(concentrado) : Boolean(ordenElegida && existenciaElegida && codigoLote.trim())
  );

  const filas = fuente === "concentrado"
    ? [
      { etiqueta: "Fuente", valor: "Concentrado liberado" },
      { etiqueta: "Concentrado", valor: concentrado ? `Lote ${concentrado.lote_codigo} · ${concentrado.silo}` : "—" },
      { etiqueta: "Torre", valor: torreElegida?.nombre ?? "—" },
      { etiqueta: "Cantidad", valor: cantidad(valor, unidad) },
    ]
    : [
      { etiqueta: "Fuente", valor: "Alimentación externa" },
      { etiqueta: "Orden", valor: ordenElegida ? `${ordenElegida.codigo} · ${ordenElegida.producto_nombre}` : "—" },
      { etiqueta: "Lote externo", valor: existenciaElegida ? `${existenciaElegida.insumo_nombre} · ${existenciaElegida.lote_codigo}` : "—" },
      { etiqueta: "Lote de salida", valor: codigoLote.trim() || "—" },
      { etiqueta: "Torre", valor: torreElegida?.nombre ?? "—" },
      { etiqueta: "Cantidad", valor: cantidad(valor, "kg") },
    ];

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (completo) setRevisando(true);
  };

  const confirmar = async () => {
    if (enviando.current || !torreElegida) return;
    enviando.current = true;
    setGuardando(true);
    setError("");
    try {
      if (fuente === "concentrado" && concentrado) {
        await prepararContinuacion(concentrado.salida_id, {
          etapa: concentrado.etapa_id, equipo: torreElegida.equipo_id, cantidad: Number(valor),
        });
        alPreparar(`${torreElegida.nombre} preparada con el lote ${concentrado.lote_codigo}.`);
      } else {
        const corrida = await prepararSecadoExterno({
          orden: Number(orden), existencia: Number(existencia), equipo: torreElegida.equipo_id,
          codigo_lote: codigoLote.trim(), cantidad: Number(valor),
        });
        alPreparar(`${torreElegida.nombre} preparada con alimentación externa; lote de salida ${corrida.lote_codigo}.`);
      }
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo preparar la torre."));
      setRevisando(false);
    } finally {
      enviando.current = false;
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby="titulo-tomar-concentrado">
      <form onSubmit={revisar} className="mx-auto my-8 max-w-3xl space-y-5 rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-amber-700">Puesto de Secado</p>
            <h2 id="titulo-tomar-concentrado" className="mt-1 text-2xl font-bold text-slate-900">Tomar concentrado</h2>
            <p className="mt-2 text-sm text-slate-600">Deja la torre preparada. El secado se inicia después, desde la tarjeta de la torre.</p>
          </div>
          <button type="button" onClick={alCerrar} disabled={guardando} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>

        <fieldset className="flex flex-wrap gap-4 text-sm font-medium text-slate-700" disabled={revisando}>
          <legend className="mb-2 text-sm font-semibold text-slate-900">Fuente</legend>
          <label className="inline-flex items-center gap-2"><input type="radio" name="fuente" checked={fuente === "concentrado"} onChange={() => { setFuente("concentrado"); setValor(""); }} />Concentrado liberado</label>
          <label className="inline-flex items-center gap-2"><input type="radio" name="fuente" checked={fuente === "externa"} onChange={() => { setFuente("externa"); setValor(""); }} />Alimentación externa</label>
        </fieldset>

        <fieldset className="grid gap-4 sm:grid-cols-2" disabled={revisando}>
          {fuente === "concentrado" ? (
            concentrados.length === 0
              ? <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900 sm:col-span-2">No hay concentrados liberados con saldo cuya siguiente etapa sea Secado.</p>
              : (
                <label className="text-sm font-medium text-slate-700 sm:col-span-2">Concentrado
                  <select required value={salidaId} onChange={(e) => { setSalidaId(e.target.value); setValor(concentrados.find((c) => c.salida_id === Number(e.target.value))?.disponible ?? ""); }} className={campo}>
                    <option value="">Seleccionar…</option>
                    {concentrados.map((item) => <option key={item.salida_id} value={item.salida_id}>{item.lote_codigo} · {item.producto} · {item.silo} · {cantidad(item.disponible, item.unidad)}</option>)}
                  </select>
                </label>
              )
          ) : (
            <>
              <label className="text-sm font-medium text-slate-700">Orden / producto
                <select required value={orden} onChange={(e) => { setOrden(e.target.value); setExistencia(""); }} className={campo}>
                  <option value="">Seleccionar…</option>
                  {(opciones?.ordenes ?? []).map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.producto_nombre}</option>)}
                </select>
              </label>
              <label className="text-sm font-medium text-slate-700">Lote externo liberado
                <select required value={existencia} onChange={(e) => setExistencia(e.target.value)} disabled={!orden} className={campo}>
                  <option value="">Seleccionar…</option>
                  {existencias.map((item) => <option key={item.id} value={item.id}>{item.insumo_nombre} · {item.lote_codigo} · {cantidad(item.cantidad_disponible, item.unidad)}</option>)}
                </select>
              </label>
              <label className="text-sm font-medium text-slate-700">Código lote de salida
                <input required value={codigoLote} onChange={(e) => setCodigoLote(e.target.value)} className={campo} />
              </label>
            </>
          )}
          <label className="text-sm font-medium text-slate-700">Torre
            <select required value={torre} onChange={(e) => setTorre(e.target.value)} className={campo}>
              <option value="">Seleccionar…</option>
              {libres.map((item) => <option key={item.equipo_id} value={item.equipo_id}>{item.codigo} · {item.nombre}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">Cantidad <span className="text-slate-500">({unidad || "—"})</span>
            <input required type="number" min="0.001" step="0.001" max={maximo} value={valor} onChange={(e) => setValor(e.target.value)} className={campo} />
          </label>
        </fieldset>
        {libres.length === 0 && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">No hay torres disponibles: todas están preparadas o en curso.</p>}

        {error && !revisando && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {revisando ? (
          <ConfirmarAccion
            titulo="Preparar la torre con esta alimentación"
            filas={filas}
            textoConfirmar="Preparar torre"
            ocupado={guardando}
            error={error}
            onConfirmar={() => void confirmar()}
            onVolver={() => setRevisando(false)}
          />
        ) : (
          <div className="flex justify-end gap-3">
            <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700">Cancelar</button>
            <button type="submit" disabled={!completo} className="rounded-xl bg-amber-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">Revisar y confirmar</button>
          </div>
        )}
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Página** — `frontend/src/pages/Secado/PuestoSecado.tsx`:

```tsx
import { useState } from "react";
import { Plus, RefreshCw } from "lucide-react";

import { mensajeDe, useCarga } from "../../components/seccion/utilidades";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import { puedeOperarSecado } from "../../services/permisos-secado";
import { situacionDeCorrida } from "../../services/puesto-secado";
import {
  buscarSecados, iniciarSecado, obtenerPuestoSecado, obtenerSecado, type CorridaSecado,
} from "../../services/secado.service";
import { obtenerSesion } from "../../services/sesion";
import TablaConsulta from "../Inventario/TablaConsulta";
import CierreSecado from "./CierreSecado";
import TarjetaTorre from "./TarjetaTorre";
import TomarConcentrado from "./TomarConcentrado";

/* `equipoId` ausente = abrir sin torre preelegida (botón del encabezado). */
type Tomando = { equipoId?: number } | null;

const fecha = (iso: string | null) => (iso ? new Date(iso).toLocaleString("es-CL") : "—");

/*
  Puesto de Secado: tomar el concentrado (o la alimentación externa) para una
  torre, iniciar y cerrar el balance, en una pantalla. Antes eran tres pasos
  en tres pantallas, y el inicio vivía en una bandeja genérica.
*/
export default function PuestoSecado() {
  const puesto = useCarga(obtenerPuestoSecado);
  const [tomando, setTomando] = useState<Tomando>(null);
  const [iniciando, setIniciando] = useState<number | null>(null);
  const [cerrando, setCerrando] = useState<CorridaSecado | null>(null);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  // Mismo criterio que el servidor (`puede_operar_tipo` con la etapa Secado).
  const puedeOperar = puedeOperarSecado(obtenerSesion()?.usuario);

  const iniciar = async (corridaId: number) => {
    setMensaje("");
    setError("");
    setIniciando(corridaId);
    try {
      const corrida = await iniciarSecado(corridaId);
      setMensaje(`Secado ${corrida.ejecucion_codigo} iniciado en ${corrida.equipo_nombre ?? "la torre"}.`);
      await puesto.recargar();
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo iniciar el secado."));
      await puesto.recargar();
    } finally {
      setIniciando(null);
    }
  };

  const prepararCierre = async (corridaId: number) => {
    setMensaje("");
    setError("");
    try {
      setCerrando(await obtenerSecado(corridaId));
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo cargar la corrida."));
    }
  };

  return (
    <main className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-amber-700">Puesto de trabajo</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-900">Secado</h1>
            <p className="mt-2 max-w-2xl text-slate-600">Toma el concentrado liberado para una torre; luego inicia el secado y registra el balance desde la tarjeta de la torre.</p>
            {!puedeOperar && <p className="mt-2 text-sm font-medium text-slate-600">Vista de consulta: las acciones las registra Secado.</p>}
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => void puesto.recargar()} aria-label="Actualizar" title="Actualizar" className="rounded-xl border border-slate-300 bg-white p-3 text-slate-600 hover:border-amber-400 hover:text-amber-700">
              <RefreshCw className="h-5 w-5" />
            </button>
            {puedeOperar && (
              <button type="button" onClick={() => { setMensaje(""); setTomando({}); }} className="inline-flex items-center gap-2 rounded-xl bg-amber-700 px-5 py-3 text-sm font-semibold text-white hover:bg-amber-800">
                <Plus className="h-5 w-5" />Tomar concentrado
              </button>
            )}
          </div>
        </header>

        {mensaje && <p role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">{mensaje}</p>}
        {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {puesto.error && <p role="alert" className="text-sm text-red-800">{puesto.error}</p>}
        {puesto.cargando && !puesto.datos && <p className="text-sm text-slate-600">Cargando torres…</p>}

        <section aria-label="Torres" className="grid gap-4 md:grid-cols-2">
          <h2 className="sr-only">Torres</h2>
          {puesto.datos?.torres.map((fila) => (
            <TarjetaTorre
              key={fila.equipo_id}
              fila={fila}
              ocupado={iniciando !== null && iniciando === fila.corrida?.id}
              puedeOperar={puedeOperar}
              onTomar={(equipoId) => { setMensaje(""); setTomando({ equipoId }); }}
              onIniciar={(id) => void iniciar(id)}
              onCerrar={(id) => void prepararCierre(id)}
            />
          ))}
        </section>

        <section aria-label="Corridas de hoy" className="space-y-2">
          <h2 className="text-lg font-semibold text-slate-900">Corridas de hoy</h2>
          {puesto.datos && puesto.datos.corridas_de_hoy.length === 0 && <p className="text-sm text-slate-600">Hoy no hay corridas de secado iniciadas ni cerradas.</p>}
          {puesto.datos && puesto.datos.corridas_de_hoy.length > 0 && (
            <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white">
              {puesto.datos.corridas_de_hoy.map((c) => (
                <li key={c.id} className="flex flex-wrap justify-between gap-2 px-5 py-3 text-sm">
                  <span>Lote <span className="font-mono">{c.lote_codigo}</span> · {c.equipo ?? "—"}</span>
                  <span className="text-slate-700">{situacionDeCorrida(c.estado, c.estado_calidad)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Historial de Secado" className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Historial</h2>
          <TablaConsulta<CorridaSecado>
            titulo="Historial de corridas de Secado"
            cargar={buscarSecados}
            clave={(f) => f.id}
            ubicaciones={[]}
            conUbicacion={false}
            conFechas
            etiquetaBusqueda="Lote, corrida o producto"
            vacio="No hay corridas que coincidan."
            estados={(puesto.datos?.estados ?? []).map((o) => ({ valor: o.valor, texto: o.etiqueta }))}
            columnas={[
              { titulo: "Lote", celda: (f) => <span className="font-mono">{f.lote_codigo}</span> },
              { titulo: "Torre", celda: (f) => f.equipo_nombre ?? "—" },
              { titulo: "Producto", celda: (f) => f.producto_nombre },
              { titulo: "Inicio", celda: (f) => fecha(f.iniciada_en) },
              { titulo: "Polvo", numerica: true, celda: (f) => cantidad(f.kg_polvo, "kg") },
              { titulo: "Situación", celda: (f) => situacionDeCorrida(f.estado, f.estado_calidad) },
            ]}
          />
        </section>
      </div>

      {tomando !== null && puesto.datos && (
        <TomarConcentrado
          torres={puesto.datos.torres}
          concentrados={puesto.datos.concentrados}
          torreInicial={tomando.equipoId}
          alCerrar={() => setTomando(null)}
          alPreparar={(texto) => { setTomando(null); setMensaje(texto); void puesto.recargar(); }}
        />
      )}
      {cerrando && (
        <CierreSecado
          corrida={cerrando}
          alCerrar={() => setCerrando(null)}
          alCompletarse={(corrida) => {
            setCerrando(null);
            setMensaje(`Corrida ${corrida.ejecucion_codigo} cerrada; el polvo pasa a Calidad si la etapa lo exige.`);
            void puesto.recargar();
          }}
        />
      )}
    </main>
  );
}
```

- [ ] **Step 4: Ruta, menú y destinos**
  - `routes.tsx`: `const PuestoSecado = lazy(() => import("../pages/Secado/PuestoSecado"));` y el bloque del módulo `secado` queda:

```tsx
                    <Route element={<RutaModulo modulo="secado" />}>
                        <Route path="/produccion/secado" element={diferido(<PuestoSecado />)} />
                        <Route path="/secado" element={<Navigate to="/produccion/secado" replace />} />
                    </Route>
```

  - `navegacion-operacional.ts`: la entrada «Secado» pasa a `ruta: "/produccion/secado"` con `alias: ["/secado"]`.
  - `access-control.ts` (`destinoInicial`, `porArea`): `secado: "/produccion/secado"`.
  - `planta-ahora.ts`: `secado: "/produccion/secado"`.
  - `tests/navegacion-operacional.test.ts:60`: `assert.equal(navegacion.inicio.ruta, "/produccion/secado");`. `tests/planta-ahora.test.ts:9,24`: `"/produccion/secado"`.
  - Backend `procesos/dominio.py`: `RUTAS_POR_ETAPA["secado"] = "/produccion/secado"`; `procesos/tests_destinos.py:24` igual.

- [ ] **Step 5: Retirar lo viejo**
  - `SalidasIntermedias.tsx`: antes de la rama `preparando === salida.id ? (`, agrega una rama que manda al puesto (mismo patrón que Mantequilla):

```tsx
              ) : salida.acciones_permitidas.some((accion) => accion.codigo === "continuar_secado") ? (
                <Link
                  to="/produccion/secado"
                  className="mt-4 inline-flex items-center gap-2 rounded-lg bg-amber-700 px-3 py-2 text-sm font-semibold text-white"
                >
                  Tomar en el puesto de Secado
                  <ArrowRight className="h-4 w-4" />
                </Link>
```

  - `Produccion.tsx:270`: `to="/produccion/secado"`.
  - `Silos.tsx:338`: `accion?.codigo === "continuar_secado" ? "/produccion/secado" : null`.
  - `Procesos.tsx:210`: en la celda «Acción», antes del `"Sin acción directa"`, si `item.etapa_tipo === "secado" && item.estado === "preparacion"` muestra `<Link to="/produccion/secado" className="text-xs font-semibold text-amber-800 underline">Iniciar en el puesto de Secado</Link>` (importa `Link` de `react-router-dom` si falta). El botón «Iniciar» ya no aparece para esas filas porque el servidor no ofrece `ejecucion` (Task 1).
  - `BandejaTrabajoArea.tsx`: el texto del enlace «Abrir tarea» pasa a `{ejecucion.etapa_tipo === "secado" && ejecucion.estado === "preparacion" ? "Iniciar en el puesto de Secado" : "Abrir tarea"}` (el destino ya es `rutaDeEtapa`, que ahora apunta al puesto).
  - Comprueba: `grep -rn "\"/secado\"\|iniciarSecadoExterno\|InicioSecadoExterno\|obtenerSecados\|estadoFisicoSecado\|siguienteAccionSecado" frontend/src frontend/tests` → sin resultados (salvo el `Navigate` de la redirección y su `alias`).

- [ ] **Step 6: `CLAUDE.md`** — en «Decisiones vigentes», justo después del punto «Evaporación tiene puesto propio», agrega:

```markdown
- **Secado tiene puesto propio** (desde 2026-10-06, `docs/superpowers/specs/2026-10-06-puesto-secado-design.md`): `/produccion/secado`; `/secado` redirige. En Secado no se abre lote: «Tomar concentrado» mueve a la torre el lote que salió del evaporador (`preparar-continuacion`) o crea el de la alimentación externa (`secados/preparar-desde-inventario/`), y **las dos fuentes solo preparan**. «Iniciar» lo habilita el servidor: `motivos_para_iniciar_secado` es la única implementación de esas reglas, la usa `iniciar_secado` (`secados/{id}/iniciar/`) y la sirve `secados/puesto/`; `ejecuciones/{id}/transicionar/` rechaza pasar una ejecución de Secado de `preparacion` a `ejecucion` («Las corridas de secado se inician desde el puesto de Secado.»), pero reanudar una pausada o bloqueada sigue por ahí. La inspección pre-operativa (`CCAA.Sec.FORM.003`) y el aseo observado **avisan, no bloquean**. El saldo de un concentrado es `disponible_de_salida`, la misma función con la que `preparar_continuacion` rechaza. Un lote se seca en una sola corrida (`CorridaSecado.lote` es uno a uno): una salida sin lote o un lote ya secado no se preparan. Queda fuera un cuarto camino: abrir un lote desde un vale **sobre una torre** nace en ejecución, sin estas reglas.
```

- [ ] **Step 7: Verificar** — frontend `npx tsc -b --pretty false`, `npx eslint .`, `npm test`; backend `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos --noinput`.

- [ ] **Step 8: Commit** (revisa `git status` antes; agrega por nombre):

```bash
git add frontend/src/pages/Secado/PuestoSecado.tsx frontend/src/pages/Secado/TarjetaTorre.tsx frontend/src/pages/Secado/TomarConcentrado.tsx frontend/src/app/routes.tsx frontend/src/services/navegacion-operacional.ts frontend/src/services/planta-ahora.ts frontend/src/services/access-control.ts frontend/tests/navegacion-operacional.test.ts frontend/tests/planta-ahora.test.ts frontend/src/pages/Produccion/SalidasIntermedias.tsx frontend/src/pages/Produccion/Produccion.tsx frontend/src/pages/Produccion/BandejaTrabajoArea.tsx frontend/src/pages/Procesos/Procesos.tsx frontend/src/pages/Leche/Silos.tsx backend/procesos/dominio.py backend/procesos/tests_destinos.py CLAUDE.md
git commit -m "feat(secado): puesto de Secado; Secado sale de /secado y de los materiales intermedios"
```

---

### Task 6: E2E y aceptación (controlador + implementador)

**Files:**
- Modify: `frontend/e2e/flujo-polvo-continuacion.spec.ts` (pasos 2 y 3), `frontend/e2e/flujo-suero.spec.ts` (pasos 1 y 2), `frontend/e2e/rutas.ts`, `frontend/e2e/README.md`

- [ ] **Step 1: `flujo-polvo-continuacion.spec.ts`** — reemplaza los pasos 2 y 3 por:

```ts
  if (reanudarDesde <= 2) await test.step("2 · Secado toma el concentrado en su puesto y lo inicia", async () => {
    await usarSesionArea(page, "e2e_secado");
    await irA(page, "/produccion/secado");
    const libre = page.getByRole("article").filter({ hasText: "Disponible" }).first();
    await expect(libre).toBeVisible({ timeout: 20_000 });
    await libre.getByRole("button", { name: "Tomar concentrado" }).click();
    const modal = page.getByRole("dialog");
    await elegirOpcion(campo(modal, "Concentrado"), new RegExp(flujo.lote));
    await modal.getByRole("button", { name: "Revisar y confirmar" }).click();
    await trasGuardar(page, "/preparar-continuacion/", async () => {
      await modal.getByRole("button", { name: "Preparar torre" }).click();
    });

    // La torre queda preparada y «Iniciar secado» lo habilita el servidor.
    const torre = page.getByRole("article").filter({ hasText: flujo.lote });
    await expect(torre).toContainText("Preparada", { timeout: 20_000 });
    const iniciar = torre.getByRole("button", { name: "Iniciar secado" });
    await expect(iniciar).toBeEnabled();
    await trasGuardar(page, "/iniciar/", async () => iniciar.click());
    await expect(torre).toContainText("En curso", { timeout: 20_000 });
  });

  if (reanudarDesde <= 3) await test.step("3 · Secado registra un balance válido", async () => {
    await irA(page, "/produccion/secado");
    const torre = page.getByRole("article").filter({ hasText: flujo.lote });
    await expect(torre).toBeVisible({ timeout: 20_000 });
    await torre.getByRole("button", { name: "Registrar balance y cerrar" }).click();
    const cierre = page.getByRole("dialog");
    await campo(cierre, "Alimentación medida").fill("1500");
    await campo(cierre, "Sólidos de entrada").fill("48");
    await campo(cierre, "Polvo obtenido").fill("500");
    await campo(cierre, "Finos recuperados").fill("10");
    await campo(cierre, "Merma registrada").fill("5");
    await campo(cierre, "Temperatura de salida").fill("82");
    await expect(cierre.getByText("Resumen del balance")).toBeVisible();
    const respuesta = await trasGuardar(page, "/cerrar/", async () => {
      await cierre.getByRole("button", { name: "Confirmar balance y cerrar" }).click();
    });
    const corrida = await respuesta.json();
    loteId = Number(corrida.lote);
    expect(loteId).toBeGreaterThan(0);
    const hoy = page.getByRole("region", { name: "Corridas de hoy" });
    await expect(hoy.getByRole("listitem").filter({ hasText: flujo.lote })).toContainText("Esperando Calidad");
  });
```

  Quita `irA(page, "/procesos")` y el `transicionar` del paso 2 anterior. Si la región «Corridas de hoy» no se expone como `region` (una `section` con `aria-label` lo es), usa `page.locator("section[aria-label='Corridas de hoy']")`.

- [ ] **Step 2: `flujo-suero.spec.ts`** — reemplaza los pasos 1 y 2:

```ts
  if (!soloInventario) await test.step("1 · Secado prepara la torre con un lote externo y la inicia", async () => {
    await usarSesionArea(page, "e2e_secado");
    await irA(page, "/produccion/secado");
    const torre = page.getByRole("article").filter({ hasText: /TOR-SUERO-E2E/i });
    await expect(torre).toContainText("Disponible", { timeout: 20_000 });
    await torre.getByRole("button", { name: "Tomar concentrado" }).click();
    const modal = page.getByRole("dialog");
    await modal.getByLabel("Alimentación externa").check();
    await elegirOpcion(campo(modal, "Orden / producto"), /Suero en polvo E2E/i);
    await elegirOpcion(campo(modal, "Lote externo liberado"), /SUERO-EXTERNO-E2E/i);
    await campo(modal, "Código lote de salida").fill(lote);
    await campo(modal, "Cantidad").fill("800");
    await modal.getByRole("button", { name: "Revisar y confirmar" }).click();
    const respuesta = await trasGuardar(page, "/preparar-desde-inventario/", async () => {
      await modal.getByRole("button", { name: "Preparar torre" }).click();
    });
    loteId = Number((await respuesta.json()).lote);
    expect(loteId).toBeGreaterThan(0);
    await expect(torre).toContainText("Preparada", { timeout: 20_000 });
    await trasGuardar(page, "/iniciar/", async () => {
      await torre.getByRole("button", { name: "Iniciar secado" }).click();
    });
    await expect(torre).toContainText("En curso", { timeout: 20_000 });
  });

  if (!soloInventario) await test.step("2 · El operador registra el balance físico", async () => {
    const torre = page.getByRole("article").filter({ hasText: /TOR-SUERO-E2E/i });
    await torre.getByRole("button", { name: "Registrar balance y cerrar" }).click();
    const modal = page.getByRole("dialog");
    await expect(campo(modal, "Alimentación medida")).toHaveValue("800.000");
    await campo(modal, "Sólidos de entrada").fill("90");
    await campo(modal, "Polvo obtenido").fill("700");
    await campo(modal, "Finos recuperados").fill("10");
    await campo(modal, "Merma registrada").fill("5");
    await campo(modal, "Temperatura de salida").fill("80");
    await expect(modal.getByText("Resumen del balance")).toBeVisible();
    await trasGuardar(page, "/cerrar/", async () => {
      await modal.getByRole("button", { name: "Confirmar balance y cerrar" }).click();
    });
    const hoy = page.locator("section[aria-label='Corridas de hoy']");
    await expect(hoy.getByRole("listitem").filter({ hasText: lote })).toContainText("Esperando Calidad");
  });
```

  La etiqueta del campo cantidad es «Cantidad» (con «(kg)» en un `span` anidado, que `campo()` ignora por leer solo `text()`).

- [ ] **Step 3: `rutas.ts`** — junto a `/produccion/evaporacion`: `{ ruta: "/produccion/secado", nombre: "Producción · Secado" },`.

- [ ] **Step 4: `README.md`** — en «Circuito de producción de leche en polvo», la descripción de `flujo-polvo-continuacion.spec.ts` dice que Secado toma el concentrado, lo inicia y registra el balance **en su puesto** (`/produccion/secado`). En «Circuito visual de Suero y Big Bag», el recorrido pasa a «lote externo liberado → torre preparada → Secado iniciado en el puesto → Calidad intermedia → …».

- [ ] **Step 5 (controlador): aceptación**
  - Reiniciar el backend (`runserver --noreload`), `manage.py migrate`, `manage.py preparar_circuito_polvo --aplicar`, comprobar torres libres en `/produccion/secado` (sin tocar corridas ajenas).
  - `E2E_USUARIO=e2e_auditoria E2E_CLAVE=auditoria-e2e-ccaa E2E_CLAVE_AREAS=flujo-e2e-ccaa npx playwright test --project=circuito --project=evaporacion --project=flujo-polvo` → 4/4.
  - `manage.py preparar_circuito_suero --aplicar` y `npx playwright test --project=flujo-suero` → verde.
  - Auditoría de accesibilidad (`npm run auditoria`) sin reglas nuevas en `/produccion/secado`.
  - Suite completa del backend: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test --noinput` sin rojos.

- [ ] **Step 6: Commit**

```bash
git add frontend/e2e/flujo-polvo-continuacion.spec.ts frontend/e2e/flujo-suero.spec.ts frontend/e2e/rutas.ts frontend/e2e/README.md
git commit -m "test(e2e): el secado se recorre en su puesto, desde concentrado y desde inventario"
```

---

## Autorrevisión contra la spec

| Spec | Tarea |
|---|---|
| §1 problema (3 pasos, reglas dispersas, dos comportamientos según fuente, inspección ignorada) | 1 (reglas en una función), 2 (dos fuentes preparan), 3 (aviso de inspección), 5 (un solo puesto) |
| §2 decisiones: dos pasos, externa también en dos, inspección avisa, puesto propio | 1, 2, 3, 5 |
| §3.1 estado del puesto: estados por torre, terminales no ocupan | 3 (`estado_puesto_secado`, `ESTADOS_QUE_OCUPAN_EQUIPO`) |
| §3.1 `motivos_para_iniciar` | 1 (función), 3 (servida) |
| §3.1 `avisos`: aseo + inspección con `cubre_al_lote` + `registro_completo`, fecha local de hoy | 1 (`avisos_de_torre`), 3 (pruebas: sin/ayer/incompleta/otra torre/completa) |
| §3.1 `en_calidad` | 3 |
| §3.1 `concentrados` con saldo de la misma función que `preparar_continuacion` | 1 (`disponible_de_salida` extraído), 3 |
| §3.1 `corridas_de_hoy` sin huérfanos; decimales como texto; lectura Secado/Calidad/admin | 3 |
| §3.2 concentrado liberado vía `preparar-continuacion`; externa `preparar-desde-inventario` en `preparacion`; acción antigua eliminada | 2 |
| §3.3 `iniciar` con `select_for_update`, recalcula, 400, avisos al evento | 1 |
| §3.3 `transicionar` rechaza el inicio genérico con el mensaje exacto; pausar/bloquear/cancelar siguen | 1 (+ reanudar, desviación 4) |
| §3.4 permisos en todos los caminos; prueba con usuario de Condensación | 1 (iniciar 403), 2 (preparar-continuacion 403, ya existente: desviación 1) |
| §3.5 lo que no cambia (`cerrar_secado`, balance, cola, liberación) | sin cambios; `tests_secado` sigue verde (1-3) |
| §4.1 tarjetas, una acción por estado, motivos con enlace, avisos ámbar, enlace a `/registros`, `en_calidad` | 4 (`accionDeTorre`), 5 (`TarjetaTorre`) |
| §4.2 formulario guiado, dos fuentes, `ConfirmarAccion` «Preparar torre» | 5 (`TomarConcentrado`) |
| §4.3 corridas de hoy + historial con filtros de servidor; `bandejaDeSecado` único clasificador | 3 (filtros), 4 (`situacionDeCorrida`), 5 |
| §4.4 acceso: `puedeOperarSecado` con prueba; Calidad consulta | 4, 5 |
| §4.1 «Lo que se retira»: redirección `/secado`, menú, `rutaDeEtapa`, `ruta_de_etapa`, Secado fuera de materiales intermedios, bandejas genéricas con enlace, modal externo integrado | 4 (eliminar modal), 5 |
| §5 pruebas backend (todas las listadas) | 1, 2, 3 |
| §5 pruebas frontend (`accionDeTorre`, `puedeOperarSecado`, `bandejaDeSecado` sin cambios) | 4 |
| §5 E2E (`flujo-polvo-continuacion`, cadena 4/4, `flujo-suero`, `rutas.ts`) | 6 |
| §6 riesgos: búsqueda de usos de `transicionar` e `iniciar-desde-inventario` | sección «Usos a migrar»; 1, 2, 4, 6 |
| §7 fuera de alcance | respetado; el cuarto camino de inicio queda anotado (desviación 10) |
| `CLAUDE.md` «Secado tiene puesto propio» junto al de Evaporación | 5 |

Tipos y nombres cruzados verificados: `motivos_para_iniciar_secado`, `avisos_de_torre`, `iniciar_secado`, `disponible_de_salida`, `inicio_reservado_al_puesto`, `preparar_secado_desde_inventario`, `estado_puesto_secado`, `estado_calidad_secado` (backend); `TorrePuesto`, `ConcentradoPuesto`, `PuestoSecado`, `accionDeTorre`, `situacionDeCorrida`, `puedeOperarSecado`, `obtenerPuestoSecado`, `iniciarSecado`, `prepararSecadoExterno`, `buscarSecados` (frontend) se usan con la misma firma en todas las tareas.
