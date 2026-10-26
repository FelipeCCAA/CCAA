# F01 — recepción nueva en silo reutilizado

26-10-2026. Rama `codex/f01-reuso-silo-recepcion`, base `561e11d1850d310401fe38dca73d200e1b0e74ae` (PR20). Corrección aislada autorizada por el usuario tras el bloqueo del vale ficticio VE6299-01. No modifica producción, historial industrial, inventario OPFLOW, recetas, tolerancias, migraciones ni despliegues. Un coordinador implementa y prueba; un QA revisa en sólo lectura.

## Problema y contrato

Una salida antigua sin consumo enlazado por FK seguía apareciendo como fuente del Silo 5 aunque ese contenido había sido consumido físicamente hasta cero. Una recepción posterior de 25.000 L y un descremado de 10.000 L dejaron 15.000 L nuevos; F01 comparaba ese físico contra 2.000 L documentales antiguos y bloqueaba el nuevo vale. El bloqueo evitaba atribuirle leche nueva al producto anterior, pero impedía continuar el ensayo.

La excepción sólo reconoce leche entera recibida en un Silo de tipo SILO cuando todas estas evidencias coinciden:

1. Libro completo ordenado por fecha/id, sin negativos intermedios. Último cero producido por una SALIDA de lote real, con lote/ejecución/vale/silo/planta y una entrada en L de idéntica cantidad correlacionados.
2. Todas las salidas de proceso del silo son estrictamente anteriores al vaciado; mermas, otras unidades y empate de fechas también impiden afirmar un ciclo exclusivo.
3. Después del vaciado hay exactamente un INGRESO, primero en el ciclo y asociado a una recepción entera DESCARGADA/CERRADA de la misma planta/silo/cantidad. No hay ajustes ni otros ingresos.
4. Cada salida física posterior tiene FIFO completo y sólo atribuido a esa recepción, sin origen desconocido.
5. Al transferir se exige análisis confirmado estrictamente posterior al ingreso, composición MG/SNG igual a la digitada en el vale y, si existe FK de análisis, identidad de la misma muestra. Se conservan los controles existentes de segundo revisor, vigencia, retención, reservas, capacidad, ruta y firma de los demás componentes.
6. No se elige ninguna salida del ciclo anterior ni se reescribe su consumo histórico. La nueva entrada cruda mantiene `salida_origen=NULL`; los movimientos y atribuciones existentes conservan la recepción verdadera. No hay segundo retiro.
7. La identidad `Recepcion.tipo_leche` no admite cambios por guardado normal una vez que existe su movimiento de descarga. API devuelve 409, antes de descargar sigue editable y enviar el mismo valor sigue permitido. No se introducen límites industriales ni una corrección retroactiva del tipo.

## Archivos y límites

- `backend/estandarizacion/recepciones.py`: prueba de vaciado y recepción nueva, sólo lectura.
- `backend/estandarizacion/origenes.py`: usa la prueba bajo el bloqueo de transferencia y oculta candidatos antiguos en el catálogo informativo.
- `backend/recepcion/models.py`: protección transaccional del tipo de leche descargada.
- `backend/recepcion/views.py`: lectura bajo lock y respuesta 409 al intentar cambiar esa identidad.
- `backend/estandarizacion/tests_reuso_recepcion.py` y `tests_reuso_concurrencia.py`: regresión del circuito y PostgreSQL real.

El catálogo no autoriza movimientos: la transferencia revalida. `transferir` ya mantiene `SELECT FOR UPDATE` del silo. La FK PostgreSQL de `SalidaProceso.silo` exige KEY SHARE al confirmar; las pruebas observan el bloqueo real en ambos órdenes, sin añadir cerrojos generales. Una salida que confirma primero hace rechazar el vale; una que aparece después de la validación sólo puede confirmar después del vale.

Esta prueba deliberadamente no acepta vaciados por ajustes, mezclas, múltiples recepciones o consumos sin correlación suficiente. No concilia el material histórico negativo ni completa F02 para mezclas/correcciones. `QuerySet.update`, operaciones masivas y SQL directo eluden `save`; no se afirma proteger ediciones históricas administrativas por esas vías. Ninguna de ellas se utilizó para reparar OPFLOW. Falta producto/especificación aprobada para polvo descremado; este vale corresponde a polvo entero.

## Verificación

Se conserva reproducción sobre base inmutable: los dos casos positivos fallan con el código anterior por el bloqueo material y por ofrecer el candidato antiguo. Una primera batería adicional tuvo errores de preparación de muestras: varias muestras se movieron a la misma fecha única; corregido el dato, otro caso conservaba inadvertidamente una muestra más reciente válida. No se relajaron guardas para hacerlos pasar. Corte posterior de 26 casos aprobado antes de añadir la protección final del tipo de recepción.

**Corte final local: 423/423 pruebas de Recepción y Estandarización aprobadas, 423 identidades únicas, 31 nuevas, ninguna omitida/fallida, 172,958s, exit0.** Incluye tres casos nuevos de concurrencia: ambos órdenes de alta de salida y cambio de tipo durante la transferencia. Ruff de todo backend, esquema sin cambios y diff-check aprobados. [Crudos, resumen e identidades](evidencias/f01-reuso-silo/summary.json). Los cortes solapados no se suman como pruebas únicas. La regresión global local anterior a la última protección se detuvo (exit-1); no es aceptación final.

**CI global del código1786601 APROBADA:** [run40374533419](https://github.com/FelipeCCAA/CCAA/actions/runs/40374533419), cuatro jobs SUCCESS. Backend1.881 ejecutadas en530,676s:1.876 aprobadas,5omitidas, cero fallos/errores. Frontend con pruebas/lint/TypeScript/build, almacenamiento privado y configuración aprobados. [Resultado final y extracto del job](evidencias/f01-reuso-silo/ci-final.json), separado del corte aún pendiente conservado como ci-at-handoff.json. Los commits siguientes sólo agregan documentación/evidencia; su CI propia se consulta separadamente y no se anticipa aprobada. Archivos backend/frontend idénticos al commit de código validado. [PR21 borrador](https://github.com/FelipeCCAA/CCAA/pull/21), sin fusión.

Comprobación del ensayo actual con PostgreSQL `SET TRANSACTION READ ONLY`: recepción 2, vaciado físico 20, ingreso 22, 15.000 L, análisis 13; catálogo nuevo sin candidatos antiguos. Hash de las ocho tablas industriales consultadas antes/después idéntico: `efc6874321e1a961e6c0c9a92ee4959e6731d3e2ba749f0b1b4b8795eef1c31a`. Vale3 sigue calculado, sin ejecución. No se ejecutó transferencia ni la totalidad de sus guardas en OPFLOW. Un intento inicial de verificación integral fue rechazado por PostgreSQL al intentar SELECT FOR UPDATE dentro de la lectura obligatoria; se limitó la inspección al helper/catálogo, sin simular una aprobación integral.

Revisión independiente: detectó y se corrigieron consulta incompleta de salidas posteriores, procedencia opcional del análisis y edición del tipo descargado. Retiró la sospecha inicial de phantom de salida tras verificar el conflicto de locks/FK y las pruebas propuestas. Sin bloqueantes estáticos adicionales; no ejecutó pruebas ni consultó la base. QA ejecutado por el coordinador.

Comprobación posterior por navegador: API local reiniciada desde esta rama en 8209, interfaz existente en 5209; mismos secretos de ensayo y base, sin migraciones. Sólo se pulsó `Actualizar vales y saldos` y se desplazó la vista. Desaparece el aviso de conciliación histórica y el botón Transferido queda disponible; **no se pulsó**. La habilitación visual no sustituye la validación del servidor.

Durante el trabajo hubo otras operaciones en el ensayo: vale VE6299-02 de 1.000 L seleccionado (entera 574,91 L con MG4,60/SNG7,20; descremada 425,09 L con MG0/SNG11), distintos del análisis13 de entera MG3,62/SNG8,61. Además el movimiento26 documenta despacho2 de 10.000 L desde Silo5; físico actual **5.000 L**, no los 15.000 L del corte previo. No fueron ejecutados por esta corrección. No se modificó ni confirmó ese nuevo vale, ni se cambió la selección del usuario. La inspección posterior sigue siendo READ ONLY y su hash antes/después es `b6333d2d5623e034366b2b6895e3c3c0531a4acba1a37f9407ca74b2c9f056c9`. No comparar hashes de cortes distintos como si demostraran ausencia de actividad de otros usuarios. El vale original de15.000 L ahora tampoco tiene suficiente componente entera; no indicar al usuario que lo transfiera sin volver a validar saldos y composición.

## Reproducir y revisar

Usar PostgreSQL17 aislado y configuración CI sin servicios externos. Desde backend: `python manage.py test estandarizacion.tests_reuso_recepcion estandarizacion.tests_reuso_concurrencia --verbosity 2 --noinput`; regresión adicional de Recepción/Estandarización, Ruff y `makemigrations --check --dry-run`. El harness OP00 comprueba host/puerto/rol/directorio/base propios antes de cualquier comando; no apunta a OPFLOW ni producción.

Reversión: no aplicar el PR, o revertir sus commits de código; no requiere migraciones ni restaurar datos. Si se revierte después de uso futuro, reaparece el bloqueo conservador ante un silo reutilizado y debe evaluarse ese impacto operativo. Un cambio de código no autoriza reinterpretar históricos.

## EXPLICADOR — siete puntos

1. **Problema:** el sistema confundía material antiguo del silo con leche nueva y frenaba el vale.
2. **Causa:** el consumo antiguo carecía del enlace documental, aunque el libro físico acreditaba el vaciado.
3. **Ejemplo:** 25.000 L nuevos menos 10.000 L de descremado dejan 15.000 L utilizables sólo si su origen y Calidad están demostrados.
4. **Solución:** separar ciclos mediante evidencia de vaciado, nueva recepción y FIFO, sin borrar historia.
5. **Trabajo:** regla acotada, catálogo, protección de identidad y pruebas; sin receta nueva ni cambios de inventario del ensayo.
6. **Pruebas:** casos positivos, ambiguos, firmas, reintento, API y carreras PostgreSQL; el resultado final se informa en el resumen, sin atribuirlo a revisión estática.
7. **Estado:** código1786601 implementado,423 pruebas locales aprobadas y CI global del código aprobada; PR21 borrador. Prueba de interfaz sólo de lectura, sin transferencia. No acredita todas las rutas, carga ni autorización de planta; no está fusionada ni desplegada.
