# Perfil de produccion: VPS 4 vCPU / 4 GiB

## Objetivo y limite de esta estimacion

Este perfil prioriza la interaccion web sobre el trabajo de fondo sin cambiar
reglas ni respuestas de la aplicacion. Seis requests pueden ejecutar Python en
paralelo (`3 workers x 2 threads`) y Celery procesa una sola tarea pesada. Las
sesiones abiertas casi no consumen recursos por si solas: la capacidad depende
de cuantas personas hacen una operacion al mismo tiempo y de su costo SQL.

La linea base local de agosto de 2026 observo p95 de hasta 98 ms en las rutas
representativas, pero no contiene el volumen ni el hardware final. Por eso este
perfil es un punto de partida seguro, no una promesa de usuarios concurrentes.
Como primera hipotesis de carga, 50 personas con una interaccion cada 5 segundos
generan unas 10 requests/s; se debe certificar en el VPS con datos comparables a
produccion antes de aumentar los workers.

## Trabajo evitado por el codigo

La capacidad no se obtuvo solamente aumentando procesos. Se redujo el trabajo
que provoca cada persona, conservando respuestas y reglas:

- Maestros baja de 11 GET simultaneos al entrar a 1. Cada pestana conserva su
  resultado durante la visita y sus formularios/codigos se descargan al usarlos.
- Aseos baja de 4 GET iniciales a 2; equipos y silos se consultan al programar.
- Produccion baja de 4 GET simultaneos a 2. Pallets se cargan automaticamente
  600 ms despues y los parametros solo al pulsar "Agregar analisis".
- Un autoguardado de borrador ya no vacia las veinte lecturas breves del
  navegador: invalida solo su `mi-borrador`. Confirmar sigue refrescando todo.
- Los listados dejaron de consultar relaciones por fila. En los escenarios de
  regresion medidos: insumos 17 a 4 SQL, recolecciones 8 a 2, trabajadores 12 a
  2 y ordenes de mantenimiento 12 a 3. Solicitudes MRQ quedan en 2 SQL aunque
  crezcan sus lineas.
- La genealogia consulta una vez por profundidad y no por rama (5 a 2 SQL en
  profundidad 1 con dos origenes). Expedientes de Calidad agrupa sus datos una
  vez en memoria, en vez de recorrer todas las tablas auxiliares por cada lote.

Estos numeros son presupuestos de regresion con datos pequenos y sirven para
impedir que reaparezca un N+1. No sustituyen la prueba escalonada con el volumen
historico real.

## Presupuesto estable de memoria

| Servicio | Reserva | Limite | Decisión principal |
| --- | ---: | ---: | --- |
| PostgreSQL | 512 MiB | 1024 MiB | 50 conexiones, `shared_buffers=256MB` |
| Django/Gunicorn | 384 MiB | 896 MiB | 3 workers, 2 threads cada uno |
| Celery worker | 256 MiB | 640 MiB | concurrencia 1, prefetch 1 |
| Celery Beat | 64 MiB | 192 MiB | solo agenda |
| Redis broker | 64 MiB | 160 MiB | datos 64 MB, AOF, `noeviction` |
| Redis cache | 64 MiB | 224 MiB | datos 96 MB, AOF, `noeviction` |
| Nginx | 32 MiB | 128 MiB | estaticos, TLS y proxy |
| **Total estable** | **1376 MiB** | **3264 MiB** | **832 MiB nominales libres** |

`migrate` tiene un limite adicional de 512 MiB, pero termina antes de iniciar
Gunicorn y Celery, de modo que no se suma al total estable. Los limites son el
ultimo fusible, no memoria que Docker reserve de antemano. El margen restante
es para Ubuntu, Docker y cache de pagina; no se deben instalar otros servicios
pesados en este host. Un swap pequeno puede servir como red de emergencia, pero
no se debe contar como capacidad porque degrada fuertemente la latencia.

Backend, migraciones, Celery y Beat comparten una sola imagen. En el VPS el
build se ejecuta en serie y Vite limita el heap Node a 768 MiB, evitando cuatro
builds Python repetidos o un pico de compilacion que compita con produccion.

Los limites de CPU por servicio suman mas de cuatro porque son techos de rafaga,
no reservas. Bajo contencion, `cpu_shares` da prioridad a Gunicorn, PostgreSQL y
Nginx; Celery no puede consumir mas de un vCPU.

## Por que hay dos Redis

El broker y la cache no comparten proceso. `redis` conserva las tareas con AOF
y nunca expulsa mensajes. `redis-cache` guarda contadores de throttle, locks y
tokens; tambien conserva AOF para que reiniciar o desplegar no reinicie los
limites de acceso. Ambos usan `noeviction`: olvidar un contador por LRU podria
debilitar los limites de acceso. Si cualquiera alcanza su techo, rechaza nuevas
escrituras y produce un error observable en vez de agotar la RAM del host. Se
debe alertar al 70 % del `used_memory` del broker y al 80 % de la cache.

## Conexiones y timeouts

- Gunicorn admite seis requests en ejecucion y recicla cada worker entre 1000 y
  1100 requests para contener crecimiento gradual de memoria.
- Django reutiliza cada conexion PostgreSQL hasta 60 segundos. Con seis hilos
  web, un proceso Celery y tareas operativas, `max_connections=50` deja margen
  amplio sin permitir el consumo de memoria del valor generico 100.
- Nginx reutiliza conexiones hacia Gunicorn al limpiar la cabecera `Connection`.
  En TLS usa HTTP/2 para multiplexar solicitudes del navegador.
- Nginx deja de esperar una respuesta a los 30 segundos y Gunicorn corta un
  worker atascado a los 35. El trabajo MRP ya vive en Celery y conserva su techo
  de 20 minutos.
- El healthcheck de Nginx responde localmente con 204. Solo el healthcheck del
  backend consulta PostgreSQL, cada 15 segundos; no se duplica esa consulta.

## Validacion antes de aceptar trafico

Validar estructura y configuracion sin mostrar secretos:

```bash
docker compose -f compose.yml -f compose.production.yml config --quiet
COMPOSE_PARALLEL_LIMIT=1 docker compose -f compose.yml -f compose.production.yml build
docker compose -f compose.yml -f compose.production.yml up -d
docker compose -f compose.yml -f compose.production.yml ps
docker compose -f compose.yml -f compose.production.yml exec nginx nginx -t
```

Comprobar limites efectivos y consumo:

```bash
docker inspect ccaa-backend-1 --format '{{.HostConfig.Memory}} {{.HostConfig.NanoCpus}} {{.HostConfig.PidsLimit}}'
docker stats --no-stream
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "show max_connections; show shared_buffers; show work_mem;"
docker compose exec redis redis-cli INFO memory
docker compose exec redis redis-cli INFO persistence
docker compose exec redis-cache redis-cli INFO memory
```

Comprobar que liveness y readiness estan separados:

```bash
curl --fail --silent --output /dev/null https://ccaa.example.com/nginx-health
curl --fail --silent https://ccaa.example.com/api/salud/listo/
```

Hacer una prueba no destructiva por escalones de 10, 25, 50 y 75 personas con
el recorrido real de lectura. Como umbral inicial, detener el escalon si hay
errores superiores al 1 %, p95 mayor a 1 segundo durante cinco minutos, memoria
estable sobre 85 %, CPU sostenida sobre 80 %, mas de 35 conexiones PostgreSQL o
crecimiento continuo de la cola Celery. Registrar `docker stats`, latencias,
errores, conexiones y `used_memory` de ambos Redis en cada escalon.

Subir Gunicorn a cuatro workers solo si sobra RAM (pico del backend menor a
650 MiB), PostgreSQL no muestra espera y CPU no es el limite. No aumentar a la
vez workers, threads y `work_mem`: cada uno multiplica recursos de manera
distinta y una prueba conjunta no permite saber cual causo la regresion.

## Operacion

- Alertar si un contenedor reinicia por OOM o se acerca al 85 % de su limite.
- Alertar al 70 % del Redis broker: llegar al techo impide encolar tareas.
- Vigilar conexiones activas/esperando y transacciones ociosas en PostgreSQL.
- En la primera adopcion del Redis de cache separado, desplegar en una ventana
  controlada: las claves de cache que estaban en la DB 1 del Redis compartido
  no se trasladan. A partir de ese primer arranque, su AOF conserva throttles.
- Mantener al menos 20 % de disco libre para PostgreSQL, AOF, imagenes y logs.
- Los logs Docker rotan en tres archivos de 10 MB por contenedor. Nginx es el
  unico access log; Gunicorn conserva errores pero no duplica cada request.
