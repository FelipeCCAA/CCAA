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

## Límites conocidos de esta fase

- Los valores de workers/threads son una base conservadora, no capacidad
  certificada; se ajustarán con pruebas de carga en Fase 4.
- No existe aún PgBouncer, Redis, throttling distribuido ni Celery.
- El volumen Docker de PostgreSQL no reemplaza backups externos.
- La renovación automática de certificados depende de la solución TLS del
  servidor y debe incluir un `nginx -s reload` probado.
