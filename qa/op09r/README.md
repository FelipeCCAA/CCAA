# OP09 — segunda ejecución aislada de carga

Autorización del usuario: seis reglas, escalones 10/25/50/70, sin producción,
despliegues ni contratación. Sólo QA, fixtures ficticios y documentación.
No modifica código de aplicación ni límites de acceso.

## Identidad y requisitos

PostgreSQL17 existente, clúster nuevo `../op09r-runtime/pgdata`, rol
`op09r_test`, puerto loopback55469, única base `op09r_carga`.
`manage_isolated.py` verifica directorio, rol, dirección, puerto y catálogo;
limpia configuración heredada y rechaza `.env` de aplicación.
API exclusiva8229. Los datos se restauraron del respaldo **ficticio** OP09
20261022T133548Z, verificando su SHA256; fuente y evidencias anteriores intactas.
Las nuevas cuentas y lotes tienen prefijo `op09r_carga_`.

El motor Linux de Docker existente no quedó disponible. El servidor usado para
este diagnóstico es Django de desarrollo sobre Windows; **no representa ni
certifica la capacidad de un servidor productivo**. No se descargaron imágenes
ni instalaron dependencias. Correo en memoria, tareas eager, sin broker/workers.

## Protocolo

Calentamiento300s con10 usuarios; luego600s por escalón10/25/50/70; sostenida1800s
en el mayor aprobado, únicamente si no hubo parada. Cada usuario hace una
petición a la vez, con espera1–3s; cuatro áreas. Recepción guarda borradores,
Bodega traslada una unidad entre ubicaciones propias; Calidad y Producción leen.
No simula70 cierres industriales concurrentes.

Guardas: cualquier escritura fallida/incierta o repetición distinta detiene;
saldo negativo/reserva inesperada/diferencia por ubicación detiene; RAM>85%
detiene (muestra5s); CPU>80% en dos muestras30s, conexiones>80 o errores>=1%
tras100 solicitudes detienen. Aprobación exige duración completa, p95 lectura<1s
y escritura<2s, errores<1%, integridad y ausencia de parada. Nunca se reduce una
guarda ni se reinicia el ensayo fallido para sustituir su resultado.

El diario exclusivo `load-journal.jsonl` registra intención ANTES de HTTP con
UUID/payload ficticio, y resultado con estado, excepción, tiempo e ID; sin
tokens ni contraseñas. Ante parada, espera operaciones pendientes y recupera
traslados únicamente con el mismo UUID/payload. El resultado fallido permanece.
La conciliación compara exactamente intenciones/confirmaciones/filas por UUID,
campos de movimiento, saldos por ubicación y preservación del estado inicial.
Una escritura de borrador incierta queda pendiente, no se declara resuelta.

`login_turn.py`, después de terminar carga, cierra sesiones sintéticas y ensaya
70 credenciales válidas desde una IP, llegadas secuenciales separadas1s. No es
un benchmark de70 logins simultáneos. No borra caché ni cambia cuotas; conserva
429/Retry-After y cierra las sesiones abiertas al finalizar.

## Ejecución y evidencias

Usar únicamente el Python ya preparado en `../op00-runtime/.venv`, con el
clúster nuevo previamente comprobado. `seed.py` se ejecuta por shell Django
desde backend usando ruta `../qa/op09r/seed.py`; no está autorizado repetir la
preparación sobre una base usada. `load.py` rechaza movimientos previos y
archivos de resultados existentes. No ejecutar estos scripts contra otra BD.

Pruebas del registrador/guardas sin servicios:

```powershell
& ../op00-runtime/.venv/Scripts/python.exe -m unittest discover -s qa/op09r -p test_recorder.py -v
& ../op00-runtime/.venv/Scripts/ruff.exe check qa/op09r
```

Crudos en `../op09r-runtime`, fuera del repositorio. No publicar
`synthetic-sessions.json`, respaldos, archivos privados ni respuestas de login.
El informe de operación registra resultados medidos, fallos y niveles no
ejecutados; un resumen verde no sustituye el diario ni demuestra producción.
