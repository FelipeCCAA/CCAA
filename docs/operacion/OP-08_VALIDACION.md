# OP-08 — Envases, archivos y correo

Implementación autorizada en `codex/op-08-envases-archivos-correo`, desde OP-07 `e2fb6de2261c248fa815e9409781feebc400d2e7`. El usuario aprobó las seis reglas, rama, pruebas y PR. Revisión apilada sobre OP-07 #14; sin merge, despliegue, producción, inventario real ni correo real. El PR y su informe AVANCE registran el SHA entregado y el resultado de CI general, sin anticiparlo aquí.

## Reglas y trazabilidad

| Regla aprobada | Implementación / prueba |
|---|---|
| Un pedido de envasado se confirma una vez | `produccion/servicios.py`: bloqueo asesor por UUID antes del lote, firma SHA256 canónica del pedido y actor. Mismo pedido recupera; distinta carga/actor se rechaza, incluso concurrentemente. API exige UUID. UI conserva UUID y cuerpo antes de enviar, separados por cuenta/lote. |
| Cierre completo o nada | Transacción existente de materiales, pallets, inventario y auditoría conservada; pruebas de fallo tardío y dos conexiones PostgreSQL. No cambia cantidades, balances ni liberación de Calidad. |
| Evidencia sólo para documentos existentes y autorizados | `inventario/documentos_adjuntos.py` lista cerrada de nueve tipos; reutiliza permisos y consultas de cada documento en subida, listado, detalle y descarga. Eliminación del documento protegida, también concurrente. |
| Archivo válido y recuperable | `adjuntos.py`, serializers/views: tamaño, formato, CSV textual UTF-8, XLSX estructural y límites de expansión; hash SHA256 y descarga autenticada privada. Compensación si falla almacenamiento/BD; pruebas de almacenamiento parcialmente escrito, auditoría fallida, ausencia/manipulación y carrera subida/borrado. |
| Correo describe lo ocurrido | Recuperación conserva token/flujo nativos; administración informa transporte aceptado, fallido o incierto. Solicitar no equivale a cambiar contraseña. Respuesta pública genérica para cuenta inexistente o fallo de transporte. |
| Tiempo/reintento limitado | Graph: timeout positivo hasta 30 s; reintento una vez sólo ante 401 explícito. Timeout/resultado incierto no dispara reenvío automático; errores/eventos no exponen credenciales. |

Archivos principales: `backend/produccion/{models,serializers,servicios,views,tests_envase}.py`, migración `0017_registroenvase_solicitud_firma.py`; `backend/inventario/{adjuntos,documentos_adjuntos,serializers,views,apps,admin,tests_adjuntos,tests_op08_archivos}.py`; `backend/usuarios/{email_backends,recuperacion_correo,views,tests_recuperacion,tests_op08_correo}.py`. Frontend: FormularioEnvase, Envasado/pendientes, Administracion y produccion.service; fixtures Chrome `frontend/op08-ui/`. Configuración preparada: settings, Dockerfile/.dockerignore, compose, nginx y CI.

Migración **aditiva nullable**, probada únicamente en bases desechables. No calcula firmas inventadas de historia: UUID histórico sin firma se consulta mediante `por-operacion`, no se reproduce un pedido supuesto. Los catálogos inactivos permiten recuperar un pedido idéntico, pero siguen rechazados en nuevas altas.

Pendientes del navegador: sobreviven a recarga dentro de la sesión del navegador; un reintento incierto conserva cuerpo/UUID incluso tras 400/403. Otra cuenta no ve esos pendientes. Consultar historial/operación antes de iniciar otro pedido si se pierde el almacenamiento local; no se garantiza persistencia tras cerrar la sesión del navegador o borrar sus datos.

## Evidencia ejecutada

Arnés local OP-00 valida directorio propio, rol `op00_test`, `127.0.0.1:55439`, catálogo sintético y ausencia de `.env`. Resultados guardados fuera del repositorio en `../op00-runtime/`. Cortes se solapan; no sumarlos como pruebas únicas.

| Ejecución | Resultado |
|---|---|
| Baseline archivos/correo | 10 casos: diez fallos de subcasos y dos errores previstos por contratos ausentes. `op08-baseline-root.log`. |
| Baseline envasado | Cinco casos, dos fallos por UUID con distinta carga; tres aprobados. `op08-envases-baseline.log`. |
| Archivos/correo y regresiones | 45/45, 100,912 s. `op08-root-focal3.log`. |
| Integración backend | 40/40, 43,253 s: envasado, archivos y correo. `op08-integracion-final.log`. |
| Carrera adicional subida/borrado | 1/1, 2,702 s, dos conexiones; bloqueo comprobado con `pg_blocking_pids`. `op08-archivos-carrera.log`. |
| Frontend | 111/111, cero omitidas; lint y TypeScript/build. `op08-frontend-*-final.log`. |
| Chrome | 5/5 en 13,5 s; API simulada, solicitudes externas bloqueadas. Recuperación exacta tras recarga, aislamiento entre cuentas, 400/403 tras incertidumbre, lote visible sin embalajes y correo sin reenvío. `op08-browser-cierre.log`. No equivale a UAT ni E2E con BD. |
| Estática/esquema | Ruff global, diff-check, Django check y makemigrations --check --dry-run aprobados. |
| Infra preparada | Compose config validada sin interpolar credenciales ni crear contenedores. Docker local no disponible; job CI `private-storage` construye imagen y verifica escritura no root/lectura en dos contenedores sin red sobre volumen efímero. Su resultado se informa sólo cuando termine. |

Fallos intermedios documentados: 25 casos con dos errores (mock renombrado y request auxiliar sin authenticators), 43 casos con siete errores de cierre FileResponse bajo TestCase (cambiado a TransactionTestCase), navegador inicial un fallo por fixture de usuarios paginado cuando API devuelve array. Se corrigieron fixtures/entorno manteniendo aserciones; no se contaron como aprobados. Revisión detectó además compensación de almacenamiento parcial, protección del documento y recuperación visible con bandeja agotada; corregidos antes de entrega.

Reproducción en entorno de pruebas configurado: `python manage.py test produccion.tests_envase inventario.tests_op08_archivos usuarios.tests_op08_correo --noinput`; regresiones: `inventario.tests_adjuntos usuarios.tests_recuperacion`. Frontend: `npm test`, `npm run lint`, `npm run build`; Chrome: `npx playwright test --config op08-ui/playwright.config.ts`. CI ejecuta toda la suite backend, frontend y configuración endurecida con credenciales ficticias.

Código/pruebas localmente verificados: `e592252d093c0721d15aff2e57939c0cf3444804`. Revisión independiente final: sin bloqueante concreto pendiente; recuperación de lote sin embalajes comprobada por lectura y Chrome. PostgreSQL OP-00 detenido con éxito y `postmaster.pid` ausente. Configuración React revisada con checklist de hooks, estado y respuestas inciertas.

## Límites y siguiente paso

- Archivos privados en `/srv/adjuntos-privados` con volumen persistente preparado; no se aplicó esta configuración ni se trasladaron archivos existentes. Un volumen no es un backup. Revisar corte y restauración antes de cualquier despliegue futuro.
- Compensación de excepciones normales no es una transacción distribuida ante caída del host o del almacenamiento. Validación de formatos no es antivirus. CSV admitido es UTF-8; tipos históricos no reconocidos requieren revisión, no mapeo automático.
- Respuesta pública de recuperación conserva privacidad de contenido; no se certifica tiempo constante: una cuenta real puede esperar transporte y una inexistente retornar antes. Sin cola nueva ni reenvío automático ante incertidumbre.
- No se certifican 70 usuarios, disponibilidad productiva, restauración, correo real ni validación industrial. No se cambian tolerancias/reglas de Calidad. Sin consultas Supabase ni logs.
- Sólo dos agentes auxiliares, implementación envasado y revisión independiente (`gpt-6-sol high`); coordinador integra archivos/correo, QA, PM, AVANCE y EXPLICADOR. No se activaron los 16 roles.
- OP-09 queda lista para diagnóstico y preparación no destructiva. Su carga real, concurrencia objetivo, restauración o infraestructura necesitan alcance y autorización propios; no se implementan por extensión de OP-08.

## EXPLICADOR

1. **Problema:** un reintento podía confundirse con un cierre distinto; evidencia y correo no distinguían bien autorización o resultado incierto.
2. **Causa:** faltaba comparar el pedido completo, proteger el archivo con su documento y separar aceptación del correo de cambio de clave.
3. **Ejemplo:** se pierde la respuesta tras crear un pallet; al reintentar se recupera ese mismo pallet sin descontar materiales otra vez.
4. **Solución:** misma clave y mismos datos, evidencia privada/verificada y mensajes de correo precisos.
5. **Trabajo:** implementación en rama, pruebas sintéticas y revisión independiente; configuración persistente preparada, sin aplicación productiva.
6. **Pruebas:** resultados locales arriba; CI general y almacenamiento se registran en el PR cuando concluyen.
7. **Estado:** preparado para revisión humana tras checks; no está fusionado ni desplegado. OP-09 es la próxima actividad pendiente.
