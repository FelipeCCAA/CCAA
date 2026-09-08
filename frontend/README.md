# Frontend CCAA

Interfaz React 19 + TypeScript construida con Vite. En producción se compila
dentro de la imagen de Nginx definida en `infra/nginx/Dockerfile`.

## Desarrollo local

```powershell
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1
```

La aplicación queda disponible en `http://127.0.0.1:5173/` y también en la IP
local anunciada por Vite. En desarrollo consume `/api/` mediante el proxy de
Vite hacia Django en `http://127.0.0.1:8000`; `VITE_API_URL` permite cambiarlo.

## Verificación

```powershell
npm.cmd run lint
npm.cmd run build
```

En el servidor Ubuntu no se ejecuta Vite: Docker genera `dist/` durante el
build y Nginx sirve sus archivos estáticos.
