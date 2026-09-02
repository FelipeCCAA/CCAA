# Resultado E2E del flujo de leche en polvo

Fecha de ejecución: 2 de septiembre de 2026.

## Recorrido verificado

Recepción de leche → análisis de silos → estandarización y liberación del vale
→ evaporación/precondensado → aprobación intermedia de Calidad → Secado →
análisis de lote y aprobación de Calidad → Envasado → pallet de 500 kg →
liberación final → Bodega/Inventario.

La cadena final ejecutada por pantalla terminó correctamente. La evidencia
creada fue:

- lote: `CCAA-EVA-057404`;
- producto: Leche entera en polvo;
- producción declarada: 500 kg;
- pallet: `PAL-057404`;
- peso del pallet: 500 kg (20 sacos de 25 kg);
- liberación final: liberado;
- estado del pallet: en inventario;
- ubicación visible: `PT-DISP`.

## Bloqueos corregidos durante la ejecución

- Calidad ahora puede registrar análisis de silo sin obtener permiso para
  crear o modificar recepciones de camiones.
- Se aplicaron las migraciones pendientes de Calidad y Procesos que hacían que
  la bandeja devolviera HTTP 500.
- Las especificaciones de análisis de silo y de lote quedaron separadas.
- Al continuar hacia Secado se crea la corrida especializada conservando lote,
  orden, ejecución y trazabilidad de origen.
- Secado pendiente de Calidad bloquea Envasado hasta su liberación.
- La bandeja de Calidad identifica el producto y lote reales de cada salida.
- El preparador E2E crea una OP nueva cuando la anterior ya fue consumida.
- El recorrido Playwright permite reanudar desde una fase confirmada sin
  repetir escrituras de las etapas anteriores.

## Validaciones ejecutadas

- Playwright: continuación completa desde precondensado hasta Inventario: OK.
- Playwright: Recepción y Estandarización hasta vale liberado: OK; el antiguo
  tramo posterior detectó un selector renombrado y fue actualizado.
- Playwright: Evaporación/precondensado: OK.
- Django: 9 pruebas directamente relacionadas: OK.
- Ruff: OK.
- `makemigrations --check --dry-run`: sin cambios pendientes.
- TypeScript: OK.
- ESLint sobre archivos modificados: OK.
- `git diff --check`: OK (solo avisos de conversión LF/CRLF de Git).

## Observación

Los rangos intermedios usados por el circuito E2E están marcados como
provisorios. Calidad debe reemplazarlos por la especificación aprobada de
planta antes de utilizar este producto en una operación comercial.
