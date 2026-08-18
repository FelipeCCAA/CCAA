# Fase 13 · Dossier y trazabilidad

## Resultado

La genealogía existente ya relacionaba entradas y salidas de procesos, pero el flujo visual terminaba en Producción. Se extendió el dossier operacional para aceptar código de lote **o código de pallet** y reconstruir:

`recepción → silo → estandarización → proceso/lote → Calidad → envase/pallet → ubicación → despacho/cliente`.

`procesos/views.py` incorpora liberación, firmante, pallets, peso, ubicación y cliente final sin crear un segundo lote desconectado. `procesos.service.ts` y `Procesos.tsx` muestran estas etapas en el frontend. La consulta conserva el filtrado multiempresa/multiplanta y la genealogía bidireccional existente.

## Riesgos y tests

Las recepciones dentro de un silo mezclado siguen marcadas explícitamente como candidatas, sin inventar una relación uno-a-uno. Los tests de trazabilidad por código continúan pasando y el endpoint ahora resuelve también el identificador impreso del pallet.
