# Fases 2 y 3 — Usuarios/permisos y planificación semanal

## Fase 2: usuarios, áreas, roles y permisos

### Hallazgo

El sistema ya protegía el alcance empresa/sucursal y permitía que un jefe de
área administrara únicamente personal de su área. La brecha era la falta de
capacidades industriales granulares delegables: la autorización operativa se
derivaba casi completamente de rol y área.

### Implementación

- Se añadieron permisos industriales mediante `auth.Permission` de Django;
  no se creó un sistema de autorización paralelo.
- El catálogo cubre creación/edición/cierre/anulación de Producción, acciones
  de Secado, bloqueo/liberación de Calidad, Inventario, Despacho y exportación
  de Auditoría.
- `permisos_asignables_por()` limita la delegación por área. Un jefe de Secado
  no puede entregar Calidad o Despacho.
- El superusuario puede delegar todas las capacidades sin convertir al
  receptor en superusuario.
- Login y `/usuarios/yo/` exponen las capacidades efectivas al frontend.
- El panel administrativo permite asignarlas con el catálogo devuelto por el
  backend.
- La migración `usuarios/0014` crea los permisos nativos de Django.

### Endpoints

- `GET /api/usuarios/trabajadores/permisos-disponibles/`
- `PATCH /api/usuarios/trabajadores/{id}/` acepta `permisos` y valida el
  alcance del actor.

### Validación

- 13 pruebas de administración y permisos: OK.
- Django check, Ruff, ESLint y TypeScript: OK.

### Pendiente de evolución

Los endpoints industriales existentes mantienen sus reglas de rol/área por
compatibilidad. Las capacidades granulares deben adoptarse por acción en cada
fase de dominio; no se eliminan las guardas existentes antes de esa migración.

## Fase 3: planificación semanal

### Hallazgo

Ya existían programa horario, balance derivado, publicación, reapertura,
cierre y contraste con transacciones reales. Faltaban cancelación con motivo,
duplicación y la regla de conservación histórica al eliminar.

### Implementación

- Nuevo estado terminal `CANCELADA`.
- Cancelación con motivo, actor y fecha, dentro de una transacción con bloqueo
  de fila.
- Duplicación transaccional de cabecera, balances y bloques hacia un nuevo
  borrador.
- Solo una semana borrador completamente vacía admite DELETE.
- Una semana con balances/bloques, publicada, cerrada o cancelada conserva su
  historia.
- El frontend permite duplicar y cancelar, muestra el motivo y diferencia el
  estado cancelado.
- La migración `planificacion/0004` agrega los datos de cancelación y el nuevo
  estado.

### Endpoints

- `POST /api/planificacion/semanas/{id}/cancelar/`
- `POST /api/planificacion/semanas/{id}/duplicar/`
- `DELETE /api/planificacion/semanas/{id}/` queda limitado a borradores vacíos.

### Validación

- Pruebas de borrado seguro, cancelación obligatoria y duplicación completa:
  OK.
- `makemigrations --check --dry-run`: sin cambios pendientes.
- Django check, Ruff, ESLint y TypeScript: OK.

## Riesgos y despliegue

- Ejecutar primero `python manage.py migrate`; ambas migraciones son aditivas.
- Los nuevos permisos nacen sin asignaciones, por lo que no amplían privilegios
  automáticamente.
- Las semanas existentes conservan sus estados actuales.
