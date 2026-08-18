# Fase 15 · Optimización y seguridad

## Seguridad

Se verificaron autenticación con expiración de token, límites de login y recuperación, caché compartida, cierre por defecto de la API, CORS/CSRF, cookies seguras, HTTPS, HSTS configurable, headers, validación de entorno productivo y aislamiento por tenant. Las operaciones sensibles nuevas verifican permisos y relaciones en backend; no aceptan estado, firmante ni planta desde el navegador.

## Rendimiento e infraestructura

- Se añadieron índices compuestos para despacho por planta/estado/fecha y movimientos por pallet/fecha.
- Querysets críticos usan `select_related`/`prefetch_related`; la prueba del listado de lotes mantiene su techo de 5 consultas.
- La paginación global sigue activa.
- `compose.yml` incorpora Redis persistente, worker Celery y Celery Beat, sin exponer Redis a la red pública.
- El MRP conserva ejecución asíncrona e idempotencia de estado; Beat recalcula alertas operacionales cada hora.
- Nginx, Gunicorn, PostgreSQL y redes privadas existentes se conservaron.

La inferencia del tenant de compatibilidad existe únicamente bajo test/CI; en producción un perfil incompleto falla cerrado.
