# Línea base de rendimiento · 2026-08-25

## Alcance

- Entorno local de desarrollo, base local y `METRICAS_ACTIVAS=1`.
- 300 solicitudes GET, 15 ciclos sobre 20 consultas representativas de Panel,
  Leche, Producción, Procesos, Inventario, Planificación, Calidad, Auditoría y
  Mantenimiento.
- Todas las respuestas terminaron con HTTP 200.
- La automatización visual de Chrome no estaba disponible en el equipo. La
  captura se hizo mediante el recorrido API equivalente, autenticado como un
  usuario activo existente y sin escrituras operacionales.
- Ventana para detectar repeticiones: 5 segundos.

## Resultado

```text
300 requests medidos
Ordenado por tiempo total: un endpoint barato llamado muchas veces cuesta más que uno caro llamado una.

ruta                                                     n     p50     p95     p99     total    SQL   msSQL
/api/recepcion/recepciones/                             45      10      12      14       454    1.0     1.1
/api/auditoria/registros/                               15      15      39      39       268    2.0     4.2
/api/recepcion/recepciones/resumen/                     15       7      98      98       195    4.0     3.4
/api/produccion/lotes/                                  15      10      29      29       170    2.0     3.1
/api/procesos/ejecuciones/                              15       8      28      28       144    1.0     2.2
/api/produccion/ordenes/                                15       8      24      24       130    1.0     2.0
/api/recepcion/analisis-silo/                           15       8      20      20       128    1.0     2.3
/api/mantenimiento/ordenes/                             15       7      27      27       126    1.0     2.4
/api/recepcion/ocupacion/                               15       6      35      35       125    1.0     3.6
/api/planificacion/semanas/                             15       7      27      27       122    2.0     2.8
/api/calidad/liberaciones/                              15       7      15      15       111    1.0     1.4
/api/inventario/mrq/                                    15       6      20      20       109    1.0     1.5
/api/recoleccion/rutas/                                 15       6      22      22       104    1.0     2.0
/api/recepcion/recepciones/resumen-diario/              15       6      16      16       100    1.0     2.5
/api/inventario/existencias/                            15       5      22      22        88    1.0     1.8
/api/inventario/inspecciones/                           15       5      14      14        87    1.0     1.5
/api/inventario/lotes/                                  15       5      16      16        82    1.0     1.7
/api/maestros/silos/                                    15       4       4       4        54    1.0     0.9

Repeticiones dentro de 5 s (mismo usuario, misma ruta):
    3x  /api/recepcion/recepciones/
```

## Lectura inicial

- No aparece un N+1 en las rutas medidas: ninguna supera cuatro consultas SQL
  promedio por solicitud.
- El reporte diario agregado en C-03 tiene p50 de 6 ms, p95 de 16 ms y una
  consulta SQL promedio en esta base.
- El listado de recepciones concentra más tiempo total porque una pantalla pide
  tres estados del flujo. La repetición detectada es esperada en el recorrido,
  pero debe compararse con una sesión visual antes de decidir si se consolida.
- El mayor p95 aislado es `recepciones/resumen/` con 98 ms. Con solo 15 muestras
  no justifica una optimización todavía; es el primer candidato para una prueba
  con volumen real.

## Próxima comparación

Repetir el mismo recorrido con volumen semejante al histórico de planta. No
optimizar consultas ni agregar caché hasta comparar esa medición con esta línea
base.
