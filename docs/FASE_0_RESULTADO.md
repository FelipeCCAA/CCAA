# Resultado de Fase 0 — Base segura

**Fecha:** 2026-08-11  
**Base:** `main` en `7f52d07`  
**Estado:** implementada; aceptación Docker pendiente por daemon no disponible.

## Cambios realizados

- `backend/config/settings.py` y `backend/config/seguridad.py`: PostgreSQL
  obligatorio, entornos explícitos y fail-fast para staging/producción.
- `backend/config/views.py` y `backend/config/urls.py`: liveness separado de
  readiness con consulta mínima a PostgreSQL y respuesta 503 sanitizada.
- `backend/config/tests.py`: diez regresiones de configuración y salud.
- `backend/calidad/checks.py`: un motor sin bloqueos siempre es error.
- `backend/Dockerfile`, `infra/nginx/*`, `compose*.yml`: base reproducible con
  Nginx, Gunicorn y PostgreSQL; solo Nginx publica puertos.
- `.dockerignore` y `backend/.dockerignore`: secretos, entornos virtuales y
  artefactos locales fuera de imágenes.
- `.github/workflows/ci.yml`: PostgreSQL 17, migraciones, 815 pruebas, Ruff,
  check productivo, ESLint, TypeScript y build.
- `backend/requirements-dev.txt` y `backend/pyproject.toml`: lint backend
  reproducible y acotado a errores objetivos.
- `docs/HARDENING_PRODUCCION.md` y `docs/DESPLIEGUE_DOCKER.md`: plan, comandos
  Ubuntu, backup, verificación y rollback.

## Problemas solucionados y evidencia

| Antes | Después | Evidencia |
|---|---|---|
| `DB_ENGINE=sqlite` arrancaba | falla con `ImproperlyConfigured` | prueba unitaria y proceso real |
| producción podía usar defaults inseguros | informa todos los valores inválidos y no arranca | pruebas de `seguridad.py` |
| salud HTTP ignoraba la base | readiness ejecuta `SELECT 1` y devuelve 503 sin detalles | cuatro pruebas de healthcheck |
| CI inexistente | pipeline versionado sobre PostgreSQL | sintaxis Compose/archivos revisados; ejecución remota ocurrirá al publicar |
| build podía copiar `backend/.env` | contextos Docker excluyen `.env` | ambos `.dockerignore` |

## Pruebas ejecutadas

| Comando/control | Resultado |
|---|---|
| `manage.py check` | OK |
| `manage.py makemigrations --check --dry-run` | OK, sin cambios |
| `manage.py migrate --noinput` desde base vacía | OK |
| `manage.py test` sobre PostgreSQL 17.10 | **815 OK**, 5 saltadas, 389,709 s |
| concurrencia `calidad.tests_concurrencia` | bloqueos reales OK |
| `ruff check .` | OK |
| `npm run lint` | OK |
| `npx tsc --noEmit` | OK |
| `npm run build` | OK, Vite 8.1.5 |
| `docker compose config --quiet` | OK en base y producción |
| `manage.py check --deploy` | sin errores; warning consciente de HSTS preload |
| `git diff --check` | OK |

Los cinco tests saltados verifican el comportamiento de motores sin
`select_for_update`; no aplican a PostgreSQL. Las tres pruebas de bloqueo y
concurrencia sí ejecutaron y pasaron.

## Verificación Docker pendiente

`docker compose build` no pudo ejecutarse. El CLI está instalado, pero el pipe
`dockerDesktopLinuxEngine` no existe y no hay daemon Docker activo. Por tanto,
no se afirma todavía que:

- las imágenes construyan en este equipo;
- la sintaxis Nginx cargue dentro de la imagen;
- los healthchecks Compose transicionen correctamente;
- únicamente 80/443 queden publicados durante ejecución real.

Para cerrar el control en un equipo con daemon:

```bash
cp .env.compose.example .env
# reemplazar POSTGRES_PASSWORD
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
curl --fail http://localhost:8080/api/salud/listo/
docker compose down
```

No se debe avanzar a Fase 1 hasta que este bloque termine correctamente o CI
demuestre el build equivalente.

## Rendimiento

Esta fase no modifica endpoints de negocio y no reclama mejoras de latencia.
La suite completa tardó 389,709 s en el equipo de desarrollo. Los presupuestos
y comparaciones de endpoints pertenecen a Fase 3.

## Migraciones

No se agregaron ni modificaron migraciones. `makemigrations --check` confirma
que el modelo y el historial están sincronizados.

## Variables nuevas o formalizadas

- `DJANGO_ENV`
- `DB_ENGINE=postgresql`
- `DJANGO_HEALTHCHECK_HOST`
- `CCAA_HTTP_PORT`, `CCAA_HTTPS_PORT`, `CCAA_TLS_DIR`
- `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`

No hay secretos nuevos versionados.

## Rollback

Los cambios de esta fase no cambian esquema ni datos. El rollback de código
consiste en desplegar el commit anterior. La configuración previa permitía
SQLite y no debe reutilizarse para operar. Los pasos completos y el tratamiento
de futuras migraciones están en `docs/DESPLIEGUE_DOCKER.md`.

## Pendientes explícitos

- Build y smoke test Docker con daemon real.
- HSTS preload requiere decisión consciente una vez verificado HTTPS de todos
  los subdominios; el warning no se silencia.
- Dimensionamiento Gunicorn y límites de recursos requieren mediciones.
- Redis, PgBouncer, throttling y Celery pertenecen a fases posteriores.
- Tenancy, IDOR y mass assignment siguen abiertos hasta Fase 1.
