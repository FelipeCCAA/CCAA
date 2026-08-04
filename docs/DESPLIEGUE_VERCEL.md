# Despliegue temporal en Vercel

La aplicacion se despliega como dos proyectos de Vercel conectados al mismo
repositorio:

- `ccaa-backend`, con **Root Directory** `backend`.
- `ccaa-frontend`, con **Root Directory** `frontend`.
- Una base PostgreSQL Neon conectada al proyecto del backend.

No se usa Vercel Services porque sigue siendo una funcion beta con acceso por
solicitud. Separar los proyectos permite usar las URL estables de produccion y
mantener el frontend y la API aislados.

## 1. Subir la preparacion a GitHub

Revisar y subir estos cambios a la rama que se quiera publicar. Vercel creara
un despliegue nuevo cada vez que se haga push a esa rama.

## 2. Crear el proyecto del backend

1. En Vercel elegir **Add New > Project** e importar el repositorio CCAA.
2. Asignar el nombre `ccaa-backend`.
3. En **Root Directory** seleccionar `backend`.
4. No indicar Build Command ni Output Directory; Vercel detecta `manage.py`.
5. Antes de desplegar, agregar estas variables en **Settings > Environment
   Variables** para Production:

   ```text
   DJANGO_SECRET_KEY=<una clave larga, aleatoria y privada>
   DJANGO_DEBUG=false
   DJANGO_ALLOWED_HOSTS=.vercel.app
   DJANGO_SECURE_SSL_REDIRECT=true
   EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
   ```

   La clave se puede generar localmente desde `backend` con:

   ```powershell
   .\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

6. Desplegar. Al principio puede fallar al acceder a rutas que consultan datos,
   porque todavia falta conectar PostgreSQL.

## 3. Crear PostgreSQL con Neon

1. Abrir el proyecto `ccaa-backend` en Vercel.
2. Ir a **Storage** (o Marketplace), elegir **Neon Postgres** y crear una base
   gratuita conectada a este proyecto.
3. Comprobar en **Settings > Environment Variables** que la integracion creo
   `DATABASE_URL`.
4. Redeploy del backend para que tome la nueva variable.

## 4. Crear las tablas y el primer usuario

En el equipo local, sin guardar la URL en Git, asignar temporalmente la
`DATABASE_URL` copiada desde Neon y ejecutar:

```powershell
cd backend
$env:DATABASE_URL='<URL privada copiada desde Neon>'
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
Remove-Item Env:DATABASE_URL
```

La URL contiene una contrasena: no pegarla en capturas, commits ni mensajes.

Comprobar el backend en:

```text
https://ccaa-backend.vercel.app/api/salud/
```

Debe responder `{"estado": "ok"}`. El nombre real puede incluir un sufijo si
`ccaa-backend` ya estaba ocupado.

## 5. Crear el proyecto del frontend

1. Volver a **Add New > Project** e importar el mismo repositorio.
2. Asignar el nombre `ccaa-frontend`.
3. En **Root Directory** seleccionar `frontend`.
4. Elegir **Framework Preset: Vite**. Vercel debe detectar:
   - Build Command: `npm run build`
   - Output Directory: `dist`
5. Agregar para Production:

   ```text
   VITE_API_URL=https://ccaa-backend.vercel.app/api/
   ```

   Ajustar el dominio si Vercel asigno otro. La barra final `/` es importante.
6. Desplegar.

El archivo `frontend/vercel.json` hace que rutas como `/login` o `/dashboard`
continuen funcionando al actualizar la pagina.

## 6. Autorizar el frontend en Django

Con la URL final del frontend, volver a las variables de `ccaa-backend` y
agregar:

```text
CORS_ALLOWED_ORIGINS=https://ccaa-frontend.vercel.app
CSRF_TRUSTED_ORIGINS=https://ccaa-frontend.vercel.app
PASSWORD_RESET_FRONTEND_URL=https://ccaa-frontend.vercel.app/restablecer-contrasena
```

Guardar y hacer un redeploy del backend. Luego abrir el frontend e iniciar
sesion con el usuario creado en el paso 4.

## Eliminar el alojamiento despues

Eliminar ambos proyectos desde **Project Settings > General > Delete Project**
y eliminar la base desde Storage/Neon. El repositorio local no se borra.
`frontend/vercel.json` y `backend/.python-version` se pueden conservar sin que
afecten a otros proveedores, o quitar en un commit posterior.

Antes de eliminar Neon, exportar cualquier dato de prueba que se quiera
conservar. Borrar el proyecto Vercel no siempre elimina automaticamente el
recurso de base de datos del proveedor.
