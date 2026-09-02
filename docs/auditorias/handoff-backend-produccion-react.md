Avanzamos bastante: quedaron terminadas todas las fases CRÍTICAS y la primera fase ALTA, exclusivamente en Django/DRF. React todavía no fue modificado.
Implementado
- Permisos operacionales por etapa y escrituras mediante servicios de dominio.
- Rutas productivas obligatorias, eliminando el fallback silencioso.
- Diagnóstico API de productos elaborables sin ruta:
  - GET /api/procesos/rutas-producto/diagnostico/
- Backfill de rutas existentes sin asignar rutas incorrectas a leche, crema o rework.
- Rollback completo si una transferencia o lote intenta avanzar sin trazabilidad.
- Exclusión concurrente de equipos:
  - preparación, ejecución, pausa y bloqueo reservan la máquina;
  - bloqueo transaccional;
  - restricción PostgreSQL contra ocupaciones dobles.
- Calidad intermedia para mantequilla:
  - crea solicitud pendiente automáticamente;
  - permite análisis de lote sin exigir silo;
  - bloquea Envasado hasta la aprobación;
  - cierra la corrida cuando Calidad libera.
- Corrida especializada de Secado:
  - nace automáticamente al abrir un lote en una torre;
  - registra alimentación, sólidos, polvo, finos, merma y controles;
  - calcula rendimiento;
  - cierre transaccional;
  - rollback ante balances imposibles;
  - endpoint: POST /api/procesos/secados/{id}/cerrar/.
Migraciones creadas
- [0014_completar_rutas_productivas.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\migrations\\0014_completar_rutas_productivas.py)
- [0015_impedir_doble_ocupacion_equipo.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\migrations\\0015_impedir_doble_ocupacion_equipo.py)
- [0006_analisis_lote_liberacion_proceso.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\calidad\\migrations\\0006_analisis_lote_liberacion_proceso.py)
- [0016_corrida_secado.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\migrations\\0016_corrida_secado.py)
No las apliqué sobre tu base real todavía.
Verificación
- 28 pruebas directamente relacionadas verificadas.
- No ejecuté la suite completa.
- makemigrations --check: correcto.
- Ruff: correcto.
- git diff --check: sin errores; solamente avisos normales LF/CRLF.
Para la futura fase React
La interfaz deberá incorporar:
- aviso visible ruta_producto antes de transferir o abrir lote;
- conflicto de equipo ocupado y refresco de disponibilidad;
- bandeja de mantequilla pendiente con análisis de lote;
- diferenciación analisis_tipo: silo | lote;
- puesto independiente de Secado consumiendo /api/procesos/secados/;
- formulario de cierre con alimentación, sólidos, polvo, finos, merma y controles;
- visualización separada de estado físico, material y Calidad.
Lo próximo es implementar formatos configurables de Envasado y después separar consumos de materiales por fase. Cuando terminemos esos bloques prepararé el handoff final completo para la skill desarrollador-react.

## Actualización backend — disponibilidad de equipos

Después del segundo bloque React se detectaron incompatibilidades entre frontend y backend relacionadas con disponibilidad de equipos.

Estas incompatibilidades fueron corregidas en Django/DRF.

### Regla definitiva de ocupación

Se centralizó la regla mediante:

`ESTADOS_QUE_OCUPAN_EQUIPO`

Los estados que ocupan o reservan físicamente un equipo son:

- `preparacion`
- `ejecucion`
- `pausada`
- `bloqueada`

El estado:

- `pendiente_control`

NO ocupa físicamente el equipo.

Esta regla debe considerarse la fuente de verdad para disponibilidad operacional.

### Endpoints corregidos

La misma regla quedó aplicada en:

- `GET /api/produccion/lotes/opciones-inicio/`
- `GET /api/procesos/salidas/disponibles/`
- `GET /api/procesos/mantequillas/opciones-alta/`
- validación para iniciar CIP/aseo.

La lógica de CIP anteriormente consideraba únicamente `ejecucion`; esto fue corregido.

### Mantequilla

Las opciones de mantequilla ahora informan también:

`ocupado_por`

sin eliminar ni modificar los campos anteriores del contrato.

### Ejecuciones operativas

`GET /api/procesos/ejecuciones/operativas/`

ahora entrega tanto el ID como el nombre del equipo.

Contrato relevante:

```json
{
  "id": 12,
  "codigo": "EJ-PROD-12",
  "estado": "ejecucion",
  "estado_etiqueta": "En ejecución",
  "etapa_nombre": "Secado",
  "etapa_tipo": "secado",
  "equipo_id": 4,
  "equipo_nombre": "Torre Egron 1",
  "acciones_permitidas": [],
  "entradas": [],
  "salidas": []
}
```

Cuando una ejecución no tenga equipo asignado:

```text
equipo_id = null
equipo_nombre = null
```

### Instrucción para React

React debe utilizar `equipo_id` para relacionar ejecuciones con equipos.

No mantener la relación temporal por `equipo_nombre`.

El backend continúa siendo la fuente de verdad para disponibilidad.

No crear un estado paralelo de ocupación en frontend.

### Verificación backend

- 7 pruebas relacionadas aprobadas.
- Estados de ocupación cubiertos.
- `makemigrations --check --dry-run`: correcto.
- Ruff: correcto.
- `git diff --check`: correcto.
- No se generaron nuevas migraciones.

