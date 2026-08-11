# Fase 1 — seguridad crítica

Estado: **cerrada y verificada el 11-08-2026**.

## Resultado

- Separación explícita entre rol (qué puede hacer) y alcance (empresa/sucursal).
- Scope obligatorio y coherente en perfiles; superusuario conserva alcance global.
- Querysets, detalles, escrituras, relaciones y acciones por PK quedan acotados al tenant en Usuarios, Maestros, Producción, Recepción, Calidad, Inocuidad, Inventario/Compras, Planificación, Procesos, Recolección, Mantenimiento, Estandarización y Auditoría.
- Los objetos operacionales incorporan empresa o sucursal directa o inequívocamente derivable.
- Los identificadores relacionados recibidos por la API se filtran por scope; un objeto ajeno se comporta como inexistente.
- Estados, actores, cantidades calculadas y firmas sensibles se asignan en backend o mediante acciones de dominio.
- Auditoría limitada a Administración/Calidad y filtrada por empresa/sucursal.
- La autenticación precarga el perfil y su tenant para evitar consultas repetidas por permiso.

## Archivos principales

- `backend/usuarios/tenancy.py`: política central reutilizable de scope, querysets, relaciones y creación.
- `backend/usuarios/{models,serializers,views,permisos,authentication}.py`: alcance, administración segura y autenticación.
- `backend/*/{models,serializers,views}.py`: adopción del scope en cada módulo operacional.
- `backend/inventario/servicios.py`: MRP, aprobaciones y alertas conservan sucursal y no mezclan stock.
- `backend/auditoria/{models,registro,serializers,views}.py`: atribución y lectura tenant-aware.
- Migraciones tenant: Usuarios `0008`, Maestros `0027`, Producción `0005`, Recepción `0006`, Calidad `0003`, Planificación `0003`, Procesos `0003`, Auditoría `0003`, Inventario `0018`.
- Pruebas negativas: `usuarios/tests_tenancy.py`, `maestros/tests_tenancy.py`, `produccion/tests_tenancy.py`, `inventario/tests_tenancy.py`.

## Evidencia

| Control | Resultado |
|---|---:|
| `manage.py check` | OK |
| `makemigrations --check --dry-run` | sin cambios |
| migración desde PostgreSQL vacío | OK |
| Ruff backend | OK |
| pruebas negativas focalizadas | 23/23 OK |
| Inventario | 62/62 OK |
| suite backend completa PostgreSQL | **838 OK, 5 skipped previstos** |
| ESLint frontend | OK |
| TypeScript + build Vite | OK |
| `git diff --check` | OK |

## Migraciones y riesgo

Las migraciones agregan claves tenant, completan datos históricos y luego aplican `NOT NULL` y restricciones únicas por empresa/sucursal. Para impedir una asignación silenciosa incorrecta, si existen registros sin tenant y la base contiene más de una empresa o sucursal compatible, la migración se detiene: esos registros deben clasificarse antes del despliegue. En tablas grandes, ejecutar en ventana de mantenimiento porque los `ALTER` y constraints pueden tomar bloqueo.

Variables nuevas para una instalación vacía:

```text
CCAA_INITIAL_COMPANY_RUT
CCAA_INITIAL_COMPANY_NAME
CCAA_INITIAL_BRANCH_CODE
CCAA_INITIAL_BRANCH_NAME
```

## Ubuntu: despliegue

```bash
cd /ruta/al/CCAA
git pull --ff-only
cp .env .env.backup.$(date +%Y%m%d%H%M%S)
docker compose -f compose.yml -f compose.production.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' \
  > "ccaa_pre_fase1_$(date +%Y%m%d%H%M%S).dump"
docker compose -f compose.yml -f compose.production.yml build
docker compose -f compose.yml -f compose.production.yml run --rm migrate
docker compose -f compose.yml -f compose.production.yml up -d
curl --fail --silent https://TU_DOMINIO/api/salud/
curl --fail --silent https://TU_DOMINIO/api/salud/listo/
```

Antes de ejecutar, completar las cuatro variables tenant en `.env`. Revisar que todos los perfiles queden asociados a la empresa/sucursal correcta.

## Rollback

No revertir estas migraciones parcialmente. Si falla la validación posterior: detener tráfico, desplegar el commit/imagen anterior y restaurar el dump completo en una base limpia. Conservar el dump hasta validar login, listados, creación y acciones críticas por cada sucursal.

## Pendientes fuera de Fase 1

- Fase 2: paginación frontend y comportamiento con más de 50 registros.
- Fase 3: rendimiento medido, N+1 de alertas, expedientes, trazabilidad, índices y carga.
- Fases posteriores: Redis/rate limit distribuido, PgBouncer, Celery y observabilidad.
