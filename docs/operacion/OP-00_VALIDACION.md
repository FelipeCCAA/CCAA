# OP-00 — Base aislada de pruebas y CI

## Contrato y límites

Objetivo: ejecutar las pruebas de CCAA sobre PostgreSQL desechable y hacer que
CI ejecute las pruebas frontend además de lint, tipos y build. Corresponde a
WP-001; no depende de decisiones industriales ni autoriza OP-01 a OP-09.

La implementación modifica exclusivamente tests, el workflow y documentación.
No cambia comandos productivos, settings, modelos, migraciones, dependencias
declaradas, tolerancias ni operaciones de planta. No requiere infraestructura
contratada, credenciales de producción, despliegue ni reparación de datos.

## Reproducción canónica

El workflow [.github/workflows/ci.yml](../../.github/workflows/ci.yml) es el perfil
reproducible: Python 3.13, PostgreSQL 17 en un servicio nuevo del job y Node 24.
El job crea su propia base `ccaa_ci`; el runner de Django crea y elimina su base
de test. Sus credenciales declaradas son exclusivamente de ese servicio efímero.
No cargar un `.env` de aplicación ni reutilizar un destino con datos reales.

Dentro de ese entorno, desde `backend/`:

```text
python -m pip install --requirement requirements-dev.txt
ruff check .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test usuarios.tests_reset_datos_operacionales --noinput --verbosity 2
python manage.py test --noinput --verbosity 1
```

Desde `frontend/`, con el lockfile versionado:

```text
npm ci
npm test
npm run lint
npm run build
```

El comando `test` mantiene el entorno global `DJANGO_ENV=ci`. Solo los dos
casos existentes que necesitan alcanzar la confirmación y el borrado simulado
usan `override_settings(DJANGO_ENV="test")`; la vista previa nueva también
declara su entorno de prueba. El comando de reset sigue rechazando `ci`,
`staging` y `production`: no se amplía `ENTORNOS_PERMITIDOS` para lograr una CI verde.

## Aislamiento de la validación local

La ejecución local de este expediente empleó Python 3.13.14, Node 24.18.0 y
PostgreSQL 17.10. Se creó un clúster nuevo fuera del checkout, en
`../op00-runtime/pgdata`, con rol de prueba `op00_test`, escucha exclusiva en
`127.0.0.1:55439` y bases `op00_base` / `test_op00_base`. No se inició ni cambió
ningún servicio PostgreSQL existente. Los paquetes Python se instalaron en un
virtualenv de esa carpeta; los manifiestos y lockfiles permanecen intactos.

Antes de cada llamada a Django, el harness local comprobó mediante SQL la
carpeta de datos, el rol, la dirección y el puerto exactos. Rechaza otra instancia
o bases distintas de las dos declaradas. Pasa un entorno limpio al subprocess,
deshabilita `.env`, deja `CACHE_URL` y `CELERY_BROKER_URL` vacíos y no transmite
credenciales de correo o servicios. Caché usa la base de test y Celery modo eager.
El harness y los logs locales son evidencia auxiliar, no código productivo ni
un reemplazo del servicio PostgreSQL efímero definido por CI.

Django crea el esquema a partir de las migraciones existentes únicamente en la
base desechable. El reset probado afecta los modelos de `MODELOS_OPERACIONALES`
en esa base, incluyendo `inventario_notificacion`; las pruebas verifican que
`auth_user` y maestros de productos/equipos se conserven. `cache_ccaa` también
pertenece a esa instancia. No se ejecuta el reset directamente sobre una base
de aplicación real.

## Regresión y evidencia exigida

La línea base `d34df44ca30c402e9da34dc7b75f7652c2751fef`, con `DJANGO_ENV=ci`,
reprodujo tres pruebas: una aprobada, un fallo y un error. Las dos últimas
recibían el rechazo de entorno antes de alcanzar la conducta que pretendían probar.

La suite focalizada ampliada contiene siete pruebas:

- Destino que parece productivo: rechazo.
- Confirmación de base incorrecta: rechazo y datos conservados.
- Reset en entorno de test: operación eliminada, usuarios y maestros conservados.
- Aplicación con confirmación exacta en `ci`, `staging` y `production`: rechazo,
  con notificación y usuario conservados en cada subcaso.
- Vista previa: salida explícita y datos conservados.
- Motor diferente de PostgreSQL: rechazo sin usar ese motor.
- Desarrollo con host remoto: rechazo.

Los resultados, revisiones, commits y estado del PR se consolidan en
[PROGRESS.md](../../PROGRESS.md); los criterios y dependencias están en
[TASK_BACKLOG.md](../../TASK_BACKLOG.md). No interpretar la existencia de una
prueba como resultado aprobado: el registro distingue ejecutadas y pendientes.

## Riesgos y recuperación

El riesgo principal de la validación es elegir una conexión o caché reales;
la identidad de la instancia y el entorno limpio son precondiciones, no una
comprobación posterior al borrado. El PostgreSQL local usa autenticación de
prueba sin contraseña y debe permanecer ligado a loopback mientras se valida;
no es una configuración para producción.

Para revertir el cambio basta revertir su commit en una rama revisable: no hay
migración nueva ni modificación del comportamiento industrial que deshacer.
Al terminar, detener únicamente el proceso del clúster de OP-00, conservando los
logs; no detener servicios existentes ni borrar directorios de bases reales.

OP-00 no certifica integridad operacional completa, restauración productiva,
recorrido E2E ni capacidad de 70 usuarios. Tampoco convierte los hallazgos
pendientes de OP-01 a OP-09 en correcciones implementadas.
