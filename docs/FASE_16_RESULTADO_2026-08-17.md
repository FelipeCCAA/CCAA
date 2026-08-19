# Fase 16 · Integración y verificación

## Cobertura integrada

La suite valida usuarios y escalamiento, planificación, recepción, silos, estandarización, procesos, secado/envase, mantequilla, Calidad, inventario, despacho, auditoría, concurrencia, tenancy y seguridad.

Durante la primera ejecución completa se detectó una incompatibilidad entre catálogos sembrados y el tenant predeterminado de pruebas. Se corrigió en `usuarios/tenancy.py` para reutilizar la empresa/planta local sembrada solo durante pruebas, manteniendo el comportamiento fail-closed en producción. También se retiró un throttle global que alteraba el contrato de consultas; los endpoints de autenticación y recuperación conservan sus límites específicos compartidos.

## Evidencias

- `manage.py check`: correcto.
- `makemigrations --check`: sin cambios pendientes.
- Ruff: correcto.
- ESLint: correcto.
- TypeScript `tsc --noEmit`: correcto.
- `git diff --check`: correcto.
- Tests dirigidos de fases 12–13: 10/10.
- Regresión histórica de Inventario: 58/58.
- Suite completa backend: **1.019/1.019 correctos**, con 5 omisiones declaradas.
- Build Vite: bloqueado por la instalación local del binario nativo `@tailwindcss/oxide-win32-x64-msvc` (`UNLOADABLE_DEPENDENCY`) y `spawn EPERM`; no es un error TypeScript ni de la implementación.

La suite se ejecutó sobre una base de pruebas PostgreSQL nueva, aplicando toda la cadena de migraciones desde cero y destruyéndola al terminar.
