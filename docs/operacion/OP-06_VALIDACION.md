# OP-06 — Identidad, permisos y sesiones

**Estado: IMPLEMENTADA Y VALIDADA LOCALMENTE EN LA RAMA.** Rama `codex/op-06-identidad`, desde OP-05 `c21b1f37bb1d848893c996bff86ab05cc7db8877`. Frontend `5bdca62`, backend `a62622c`. La revisión humana y los checks del PR son hitos separados, cuya evidencia final se conserva en el informe AVANCE del PR. El usuario aprobó las seis reglas y su implementación, pruebas aisladas y PR. No se autoriza producción, despliegue, merge, credenciales nuevas ni inventario real. CCAA no utiliza Supabase ni incorpora Empresa/Sucursal como dimensiones funcionales.

El catálogo cita WP013/014, pero su detalle no está en el material local. El contrato de esta entrega son las seis reglas expresamente propuestas y aprobadas en la conversación; no se atribuyen requisitos inventados a esos WP.

## Reglas y criterios de aceptación

| Regla aprobada | Resultado exigido |
|---|---|
| Acceso revalidado | Una contraseña antigua o cuenta desactivada durante un acceso concurrente no obtiene una sesión nueva; comprobar dentro del bloqueo de User. |
| Contraseña inicial | La contraseña entregada por administración obliga a cambiarla antes de operar; el cambio revoca la sesión y exige nuevo ingreso. No convertir automáticamente cuentas históricas. |
| Autorización administrativa | Crear un administrador explícito o por área Administración, promoverlo o cambiar de área exige autorización explícita; superusuario exento. |
| Delegación por área | Los jefes conservan la asignación de permisos operacionales permitidos en su propia área, sin exigirles `change_roles` para esa delegación. |
| Cambio de identidad | Un cambio efectivo de área, nivel, rol o permisos cierra las sesiones del afectado dentro de la misma transacción. Repetir los mismos valores no cierra sesiones nuevas. |
| Pantalla actualizada | Antes de mostrar módulos protegidos se consulta `/api/usuarios/yo/`, sin reutilizar respuesta de caché. Un error bloquea la operación y permite reintentar; un 401 cierra la sesión correspondiente. |

## Diseño y límites

El bloqueo de User coordina acceso, gestión de identidad, cambio de contraseña y desactivación. La transacción de edición incluye perfil, permisos y revocación: si falla, no queda una identidad parcialmente modificada. Se mantienen sesión única, caducidad, tokens opacos guardados como hash y límites de delegación ya existentes.

La administración técnica de Django también respeta revocación, ámbito de área y autorización. La comprobación de M2M e inline se realiza después de guardarlos y antes de confirmar la transacción. El alta nueva requiere perfil y contraseña temporal juntos; se rechaza un alta forjada sin inline, sin crear un User parcial. Los usuarios históricos sin perfil y el superusuario CLI conservan su contrato anterior. El perfil no cambia de dueño por edición o copia forjada.

El personal sin superusuario no puede editar cuentas root, autoconcederse permisos sensibles ni asignar grupos o permisos técnicos. Conserva los permisos industriales delegables en su área. El reset ajeno exige `reset_password`, revoca tokens y marca la contraseña temporal; cambiar la clave propia del superusuario revoca sus tokens sin obligarlo a cambiarla de nuevo. La clave temporal no puede validarse como nueva contraseña idéntica a la anterior.

El panel técnico escribe grupos sólo con superusuario. Cambiar efectivamente sus permisos o borrar el grupo, individualmente o en bloque, revoca las sesiones de sus miembros. El orden Group→User, con IDs ordenados, se comparte con el guardado de membresías del UserAdmin. Un cambio de nombre o guardado idéntico conserva sesiones. No se añaden señales generales para operaciones ORM arbitrarias ni se promete controlar SQL administrativo externo.

En pantalla, se conserva la elección Recordarme. Una respuesta pendiente de una cuenta anterior no debe sobrescribir una sesión nueva ni cerrarla por un 401 antiguo. Se comparte sólo una consulta de identidad en vuelo por token; nunca su respuesta ya terminada. No se añade sondeo periódico ni cambia la política de caducidad.

Las capacidades comunicadas a pantalla incluyen permisos directos y de grupo; `permisos_asignados` conserva sólo los directos para no confundir herencia con asignación. Los listados de trabajadores y sesiones precargan grupos y permisos en bloque.

No hay nuevas tablas, migraciones, proveedores ni servicios. Las tablas existentes afectadas son `auth_user`, `usuarios_perfilusuario`, `auth_user_user_permissions`, `auth_user_groups`, `auth_group`, `auth_group_permissions`, `usuarios_sesionusuario` y registros de seguridad/auditoría existentes. Toda escritura de validación utiliza datos sintéticos.

## Evidencia

- Baseline backend: cuatro pruebas, cuatro fallos esperados en 35,385 s (`../op00-runtime/op06-baseline.log`). Demuestran clave inicial sin cambio obligatorio, alta administrativa sin autorización, permiso modificado con token anterior vigente y acceso con clave antigua tras cambio concurrente.
- Baseline Chrome: cuatro fallos esperados (`op06-ui-baseline.log`), incluida reutilización de caché de identidad.
- Primera integración backend: 50 pruebas en 102,773 s, 49 aprobadas y un fallo de una expectativa anterior: crear administrador sin `change_roles`. Se ajustó sólo la preparación de ese caso para conceder autorización explícita y comprobar cambio obligatorio de contraseña.
- Primera suite completa de usuarios: 200 pruebas en 250,189 s, 198 aprobadas y dos expectativas anteriores de alta de Administración sin `change_roles`. Se concedió el permiso explícito sólo en esas dos preparaciones; se conservaron las aserciones de ausencia de sucursal y compatibilidad histórica. La focal posterior incluyó esos casos y pasó.
- Baselines admin: la primera corrida de cuatro casos confirmó dos defectos y detectó dos formularios de prueba incompletos. Se corrigieron sólo los datos de fecha/ruta/opción de contraseña; las siguientes corridas demostraron también reset y edición de permisos con token anterior vigente. No se contabilizan los formularios inválidos como defectos productivos.
- Baseline de grupos: tres pruebas en 6,326 s; dos fallos esperados por permiso modificado con sesión vigente y edición de grupo por staff; el guardado sin cambios ya conservaba la sesión.
- Integración admin/API: 44/44 en 174,675 s. Focal de entrega: 51/51 en 108,516 s. Últimas dos regresiones, clave propia del superusuario y copia de perfil forjada, 2/2 en 3,034 s. Estos cortes no se suman como pruebas únicas.
- Primera integración Chrome: 3/4. El doble efecto de desarrollo de React generaba dos consultas iniciales; se corrigió compartiendo la consulta en vuelo, sin cachear su respuesta.
- Frontend final: 107/107 pruebas, lint y build con comprobación TypeScript aprobados (`op06-frontend-entrega.log`, `op06-lint-entrega.log`, `op06-build-entrega.log`). Aviso preexistente `INEFFECTIVE_DYNAMIC_IMPORT` de FormularioMaestro. Revisión React acotada de los dos componentes: hooks con limpieza/dependencias, consulta deduplicada y controles de formulario etiquetados; sin nuevas bibliotecas.
- Chrome OP-06 final: 7/7 en 36,2 s (`op06-ui-entrega.log`): espera de validación, perfil vigente, error/reintento con Recordarme, 401, consulta fresca, 401 de cuenta anterior y altas administrativas con/sin permiso vigente. Red simulada, sin pruebas contra servidor productivo.
- Regresión Chrome: OP-02 1/1 en 20,5 s; OP-03 5/5 en 13,0 s; OP-04 5/5 en 12,2 s; OP-05 5/5 en 30,8 s. Se adaptó exclusivamente el mock `/usuarios/yo/` al nuevo contrato de entrada, conservando cada actor sintético y sus aserciones.

Ruff global backend, `check`, comprobación de migraciones sin escritura y configuración endurecida ficticia aprobados. No se detectaron cambios de esquema. El aviso `security.W021` sobre HSTS preload es preexistente; `check --deploy` aquí es una validación de configuración sin despliegue ni servicio productivo.

- Cierre de API/rendimiento: 17/17 en 112,070 s (`op06-api-rendimiento-final.log`), incluidas tres carreras y presupuestos de cuatro consultas constantes para cinco trabajadores y cinco sesiones con permisos de grupo. No es una prueba de carga de 70 usuarios.
- Postcondición de alta User+perfil aun cuando Django omita el inline por permisos: 1/1 en 7,810 s (`op06-alta-atomica-final.log`), staff de Administración sin permiso de alta de perfil, HTTP 403 y ningún usuario huérfano persistido.
- Ruff final backend completo: aprobado (`op06-ruff-final.log`). Revisión independiente por lectura sobre `a62622c`, sin bloqueantes nuevos de las guardas revisadas; las ejecuciones corresponden al coordinador, no al revisor.
- Clúster exacto OP-00 detenido al cierre, exit 0, sin `postmaster.pid`. DevelopMain y base OP-05 comprobadas sin cambios en `d34df44ca30c402e9da34dc7b75f7652c2751fef` y `c21b1f3` respectivamente.

Los resultados de la CI del commit entregado se conservan en los checks y el informe AVANCE del PR, sin anticipar aprobación. [Consultar PR por cabecera](https://github.com/FelipeCCAA/CCAA/pulls?q=is%3Apr+head%3Acodex%2Fop-06-identidad) y [ejecuciones por rama](https://github.com/FelipeCCAA/CCAA/actions?query=branch%3Acodex%2Fop-06-identidad). La revisión se apila sobre OP-05 #12; no fusionar directamente con DevelopMain ni saltar dependencias.

## Archivos y trazabilidad

| Regla | Código afectado | Evidencia |
|---|---|---|
| Acceso confirmado con credenciales vigentes | `backend/usuarios/views.py::login` | Tres carreras con conexiones PostgreSQL separadas; una comprueba espera real mediante `pg_blocking_pids`. |
| Clave inicial propia antes de operar | `serializers.py::TrabajadorSerializer.create`, `views.py::cambiar_password`, `admin.py::PerfilUsuarioInline/UsuarioAdmin` | Alta, intento de reutilizar clave, bloqueo antes del cambio, nuevo ingreso, alta sin perfil rechazada. |
| Promociones autorizadas | `views.py::TrabajadorViewSet`, `admin.py::_confirmar_identidad_admin` | Altas explícitas/implícitas de administración, cambio de área/nivel, intento de elevar privilegios y reset de root rechazados. |
| Delegación conservada | `permisos_industriales.py`, guardas de API/admin | Pruebas existentes de delegación industrial y caso positivo en admin; capacidades efectivas por grupo. |
| Invalidación transaccional | `views.py`, `admin.py::UsuarioAdmin/PerfilUsuarioAdmin/GrupoAdmin` | Token viejo rechazado, rollback al fallar revocación, no-op, desactivación, cambios y borrados de grupo. |
| Pantalla actualizada | `frontend/src/components/RutaProtegida/RutaProtegida.tsx`, `services/api.ts`, `services/sesion.ts`, `pages/Administracion/Administracion.tsx` | Cuatro pruebas de sesión, siete escenarios Chrome y regresiones previas OP-02 a OP-05. |

En la tabla, las rutas backend abreviadas pertenecen a `backend/usuarios/`. Pruebas nuevas: `tests_op06_identidad.py` y `tests_op06_admin.py`. Se ajustaron `tests.py` y `tests_sin_sucursales.py` sólo para dar autorización explícita a tres altas que así lo requieren, y `tests_rendimiento.py` para comprobar herencia y consultas constantes. El helper de precarga se comparte entre trabajadores y sesiones. Los mocks de cuatro recorridos Chrome incorporan la respuesta `/usuarios/yo/`; no cambian sus procesos industriales ni aserciones anteriores.

Documentación de estado: este expediente, `TASK_BACKLOG.md` y `PROGRESS.md`. Commits de funcionamiento y pruebas: frontend [`5bdca62`](https://github.com/FelipeCCAA/CCAA/commit/5bdca62), backend [`a62622c`](https://github.com/FelipeCCAA/CCAA/commit/a62622c). Hay 41 casos nuevos en los dos archivos OP-06 backend y una nueva prueba de presupuesto de consultas de sesiones; cuatro casos de sesión en Node y siete recorridos Chrome. Los cortes de ejecución incluyen regresiones anteriores y no se suman como casos distintos.

## Reproducción aislada

Usar el harness OP-00 documentado. Antes de Django valida `data_directory=../op00-runtime/pgdata`, rol `op00_test`, dirección `127.0.0.1`, puerto `55439` y catálogo de bases permitido. Ejecuta con variables limpias y sin `.env`. Sólo crea/destruye la base sintética de pruebas; no conecta servicios externos. El coordinador serializa las suites de BD.

```text
../op00-runtime/.venv/Scripts/python.exe ../op00-runtime/run_backend.py test usuarios --verbosity 1 --noinput
npm test
npm run lint
npm run build
npx playwright test --config op06-ui/playwright.config.ts
```

El comando Python se ejecuta desde la raíz del repositorio; npm/Playwright desde frontend. Chrome utiliza red interceptada, bloquea destinos externos y apunta el proxy de respaldo a un puerto local sin servicio. OP-03 a OP-05 conservan sus configuraciones de navegador; OP-02 usa la configuración temporal aislada del runtime OP-00.

## Recuperación y pendientes

Revertir el código en una futura entrega revisada no reabre tokens revocados ni elimina el indicador de cambio obligatorio ya guardado. No se propone reactivar sesiones antiguas para retroceder. No se alteran cuentas históricas automáticamente ni decisiones industriales.

La revocación rige para las nuevas autenticaciones de solicitudes; no cancela operaciones que ya estaban en curso ni revierte hechos industriales confirmados. No se certifican UAT con personas, carga de 70 usuarios, latencia máxima o restauración de backup. Las carreras de acceso/password/desactivación se ejecutaron; el orden de bloqueos de grupos se revisó y su comportamiento funcional se probó, sin presentarlo como una prueba de todas sus intercalaciones posibles. No se cambian reglas de firma, litros, FIFO o mantequilla de OP anteriores. OP-07 es la siguiente actividad lista por dependencia; sólo diagnóstico/preparación no destructiva hasta autorización de implementación propia.

## Equipo y explicación

Coordinador: integración, frontend, QA, PM y AVANCE; apoyo de backend y revisión independiente. Se reutilizan los dos agentes necesarios y sus modelos configurados, sin activar los dieciséis roles. Las pruebas automáticas y simuladas no se presentan como validación humana de operadores.

**AVANCE:** seis reglas implementadas y verificadas localmente; commits y evidencia arriba, rama preparada para revisión apilada sobre OP-05. El resultado general de CI y el enlace definitivo del PR se adjuntan a su informe de entrega. No se despliega ni fusiona. Próxima actividad OP-07: diagnóstico y preparación, implementación requiere autorización propia.

**EXPLICADOR:** 1) Problema: cambios administrativos podían dejar accesos anteriores vigentes. 2) Causa: validación antes del bloqueo y caminos de edición sin revocación. 3) Ejemplo: una clave antigua intentaba entrar mientras se cambiaba. 4) Solución aplicada: comprobar al confirmar, controlar promociones, cerrar sesiones afectadas y verificar identidad al abrir. 5) Trabajo real: código y pruebas en rama, con dos agentes de apoyo y coordinación, sin producción. 6) Pruebas: backend/API/admin/grupos/concurrencia y pantalla aprobados localmente según evidencia anterior; CI se verifica en el PR. 7) Estado: VALIDADO MEDIANTE PRUEBAS en entorno aislado; revisión humana pendiente, sin despliegue ni certificación productiva.
