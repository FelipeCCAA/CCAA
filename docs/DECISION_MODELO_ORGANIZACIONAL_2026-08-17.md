# Decisión: operación sin sucursales

Fecha: 2026-08-17

CCAA se administra como una sola organización. Sucursales o plantas no forman
parte del modelo funcional y no deben aparecer en navegación, formularios,
perfiles, contratos del frontend ni variables de despliegue.

## Comportamiento vigente

- Los perfiles tienen alcance de empresa y no seleccionan una subdivisión.
- Las altas operacionales reciben su organización desde la sesión autenticada.
- El backend ignora cualquier subdivisión enviada por clientes antiguos.
- La configuración interna canónica se asigna automáticamente para conservar
  compatibilidad con claves foráneas y datos históricos.
- Django Admin tampoco ofrece esa configuración como campo editable.

## Compatibilidad técnica

Las columnas y clases históricas se mantienen temporalmente porque eliminarlas
en una sola migración afectaría numerosos registros relacionados. No son una
capacidad disponible para el negocio. Su eliminación física futura deberá ser
una migración escalonada, con reasignación y verificación previa de datos.
