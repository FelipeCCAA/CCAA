# Despliegue Docker de CCAA

Esta guía corresponde a la infraestructura base de la Fase 0. PostgreSQL,
Django y Nginx están versionados; solo Nginx publica puertos. Redis, PgBouncer
y Celery se incorporarán después de medir y validar sus fases respectivas.

## Requisitos Ubuntu

- Ubuntu 24.04 LTS o equivalente mantenido.
- Docker Engine con el plugin Compose.
- DNS apuntando al servidor.
- Certificado TLS existente con `fullchain.pem` y `privkey.pem`.
- Espacio separado y monitorizado para datos y backups.

## Primera instalación

```bash
git clone URL_DEL_REPOSITORIO CCAA
cd CCAA
cp .env.compose.example .env
chmod 600 .env
openssl rand -base64 48
```

Editar `.env` y reemplazar todos los ejemplos. Para producción son obligatorios:

```dotenv
POSTGRES_DB=ccaa
POSTGRES_USER=ccaa
POSTGRES_PASSWORD=SECRETO_DIFERENTE
DJANGO_ENV=production
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=RESULTADO_ALEATORIO_DE_AL_MENOS_50_CARACTERES
DJANGO_ALLOWED_HOSTS=ccaa.example.com
DJANGO_HEALTHCHECK_HOST=ccaa.example.com
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SECURE_HSTS_SECONDS=31536000
CORS_ALLOWED_ORIGINS=https://ccaa.example.com
CSRF_TRUSTED_ORIGINS=https://ccaa.example.com
CCAA_TLS_DIR=/etc/letsencrypt/live/ccaa.example.com
```

Los archivos del directorio TLS deben llamarse `fullchain.pem` y
`privkey.pem`. El directorio se monta en modo solo lectura.

Validar antes de crear servicios:

```bash
docker compose -f compose.yml -f compose.production.yml config --quiet
docker compose -f compose.yml -f compose.production.yml build
docker compose -f compose.yml -f compose.production.yml run --rm backend python manage.py check --deploy
```

El warning de HSTS preload es esperado mientras el dominio no se haya decidido
inscribir conscientemente en la lista preload de los navegadores. No debe
silenciarse ni activarse por accidente.

Levantar y comprobar:

```bash
docker compose -f compose.yml -f compose.production.yml up -d
docker compose -f compose.yml -f compose.production.yml ps
curl --fail --silent https://ccaa.example.com/api/salud/
curl --fail --silent https://ccaa.example.com/api/salud/listo/
docker compose -f compose.yml -f compose.production.yml exec backend python manage.py check
```

## Después de cada `git pull`

Crear primero un backup consistente:

```bash
mkdir -p backups
chmod 700 backups
set -o allexport
. ./.env
set +o allexport
docker compose exec -T db pg_dump --format=custom --no-owner --username="$POSTGRES_USER" "$POSTGRES_DB" > "backups/ccaa-$(date -u +%Y%m%dT%H%M%SZ).dump"
```

Luego actualizar sin ejecutar migraciones fuera del contenedor definido:

```bash
git pull --ff-only
docker compose -f compose.yml -f compose.production.yml config --quiet
docker compose -f compose.yml -f compose.production.yml build
docker compose -f compose.yml -f compose.production.yml up -d
docker compose -f compose.yml -f compose.production.yml ps
curl --fail --silent https://ccaa.example.com/api/salud/listo/
```

`migrate` es un servicio de una sola ejecución y debe terminar correctamente
antes de que el backend nuevo quede saludable.

## Verificación de exposición

```bash
docker compose -f compose.yml -f compose.production.yml ps
ss -lntp
```

Solo deben publicarse 80/443 (o los puertos configurados). No deben aparecer
5432 ni 8000 en interfaces del host.

## Rollback

Antes de desplegar, registrar el commit estable:

```bash
git rev-parse HEAD
```

Si el esquema nuevo es compatible hacia atrás, volver al commit registrado y
reconstruir:

```bash
git switch --detach COMMIT_ESTABLE
docker compose -f compose.yml -f compose.production.yml build
docker compose -f compose.yml -f compose.production.yml up -d
curl --fail --silent https://ccaa.example.com/api/salud/listo/
```

Si una migración no es compatible, detener escrituras y restaurar el backup en
una base vacía durante una ventana de mantenimiento. No ejecutar `migrate app
numero_anterior` sin revisar primero `sqlmigrate`: una reversión puede borrar
datos. La restauración debe ensayarse en staging antes del primer despliegue.

## Variables que exige el despliegue

Además de las de arriba, sin estas cuatro **`usuarios.0008` aborta**: crea la
empresa y la sucursal iniciales a las que se asignan los perfiles existentes, y
se niega a inventarlas.

```dotenv
CCAA_INITIAL_COMPANY_RUT=76.000.000-0
CCAA_INITIAL_COMPANY_NAME=Campos Australes
CCAA_INITIAL_BRANCH_CODE=PLANTA
CCAA_INITIAL_BRANCH_NAME=Planta Osorno
```

Y estas gobiernan las defensas del acceso. La primera no es opcional con Nginx
delante:

```dotenv
# Sin esto el limite por IP es esquivable: DRF usaria la cabecera
# X-Forwarded-For entera como identidad y quien ataca estrena contador
# mandando una distinta en cada peticion.
PROXIES_DE_CONFIANZA=1

THROTTLE_LOGIN_IP=60/hour
THROTTLE_LOGIN_USUARIO=15/hour
TOKEN_TTL_HORAS=12
```

## Desbloquear un acceso

El límite se levanta solo: la ventana es deslizante, así que cada intento
caduca una hora después de haberse hecho. Cuando no se puede esperar:

**Desde el admin** — *Usuarios › Intentos de acceso*. La columna «Límite» dice
si esa cuenta está bloqueada y por cuánto; se marcan las filas y se elige
«Desbloquear el acceso de estas cuentas».

**Desde la consola:**

```bash
docker compose exec backend python manage.py desbloquear_login --listar
docker compose exec backend python manage.py desbloquear_login --usuario jperez
```

Desbloquear una cuenta **no** libera su dirección ni al revés: son dos límites
que protegen de cosas distintas. Restablecer la contraseña tampoco desbloquea
—el contador es del intento, no de la cuenta— y reiniciar el contenedor menos,
porque la caché vive en PostgreSQL para sobrevivir a eso.

## Límite de peticiones en Nginx

El throttle de Django rechaza antes de comprobar la contraseña, que es donde
está el gasto. Pero una petición rechazada por Django todavía cuesta un ciclo
completo de Python. Nginx rechaza **antes de que Python arranque**:

```nginx
# En el bloque http
limit_req_zone $binary_remote_addr zone=login:10m rate=60r/m;
limit_req_status 429;
```
```nginx
location = /api/usuarios/login/ {
    limit_req zone=login burst=20 nodelay;
    proxy_pass http://backend;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    # …el resto de cabeceras habituales
}
```

**El ritmo va holgado a propósito.** La planta sale a internet por una sola
dirección: un `10r/m` dejaría al turno entero fuera por culpa de un atacante.
El límite estricto es el de **cuenta**, y ese vive en Django porque Nginx no lee
el cuerpo de la petición.

## Límites conocidos de esta fase

- Los valores de workers/threads son una base conservadora, no capacidad
  certificada; se ajustarán con pruebas de carga en Fase 4.
- No existe aún PgBouncer, Redis, throttling distribuido ni Celery.
- El volumen Docker de PostgreSQL no reemplaza backups externos.
- La renovación automática de certificados depende de la solución TLS del
  servidor y debe incluir un `nginx -s reload` probado.
