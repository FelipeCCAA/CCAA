# Gestión Productiva · Planta CCAA

Sistema de gestión productiva de la planta de secado de Campos Australes (leche en polvo,
crema y mantequilla): recepción de leche → producción de lotes → control de calidad →
liberación → despacho.

Estado: **en construcción**. El modelo de datos y las reglas de negocio ya están definidos
y probados en el prototipo (ver [`prototipo/`](prototipo/)); se están trasladando a una
aplicación cliente/servidor con persistencia compartida.

---

## La regla que gobierna el sistema

> **Un despacho exige un lote liberado.**
> Un lote se libera si **todos sus formularios de calidad están completos y firmados** *y* su
> **calidad es conforme** contra la especificación vigente a la fecha del lote.
> Si no es conforme, solo puede salir como **liberación bajo concesión**: con motivo escrito,
> autorizador identificado y marca permanente.

Todo lo demás existe para poder aplicar esa regla y demostrar después que se aplicó.

---

## Estructura del repositorio

```
CCAA/
├── backend/      API y base de datos — Django 6 + Django REST Framework
├── frontend/     Interfaz de usuario — React 19 + TypeScript + Vite + Tailwind 4
└── prototipo/    Prototipo funcional de referencia (HTML/JS, sin servidor)
```

### `prototipo/`

Prototipo que define **qué debe hacer el sistema**. Corre abriendo `prototipo/index.html`
en el navegador, sin servidor ni instalación, y guarda en `localStorage`.

No es código a desplegar: es la **especificación ejecutable** del proyecto. Contiene el
modelo de datos completo (20 entidades), las reglas de negocio y 110 pruebas que las cubren.
Se consulta al construir cada módulo.

Documentación clave:

| Documento | Qué contiene |
|---|---|
| [prototipo/MODELO_DATOS.md](prototipo/MODELO_DATOS.md) | Las 20 entidades, las decisiones de modelado y su justificación |
| [prototipo/PLANIFICADOR.md](prototipo/PLANIFICADOR.md) | Programa semanal de planta y balance de leche |
| [prototipo/CONTEXTO_ARCHIVOS_FUENTE.md](prototipo/CONTEXTO_ARCHIVOS_FUENTE.md) | Los Excel de planta de donde salen los datos |
| [prototipo/README.md](prototipo/README.md) | Los módulos explicados uno a uno |
| [DECISIONES.md](DECISIONES.md) | Decisiones de plataforma: qué se decidió, por qué y qué se pierde |

Para verificar que las reglas siguen intactas: abrir `prototipo/pruebas.html` en el
navegador. Ejecuta las 110 pruebas y muestra el resultado en pantalla.

---

## Cómo levantar el proyecto

Se necesitan **dos terminales**, una para cada parte.

### Backend

Necesita un **PostgreSQL**. El porqué está en [DECISIONES.md](DECISIONES.md) §001;
el corto es que en SQLite el bloqueo de filas no existe y la firma de una
liberación no se puede proteger de una modificación concurrente.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # solo la primera vez, y ajustar la contraseña
python manage.py migrate
python manage.py runserver
```

Queda en `http://127.0.0.1:8000/`. La raíz responde 404: solo existen `/admin/` y
`/api/`. El archivo `.env` es local de cada equipo y no se versiona.

Para trabajar sin un PostgreSQL levantado se puede poner `DB_ENGINE=sqlite` en
el `.env`. **No es equivalente**: al arrancar avisa de lo que se pierde, y sin
esa variable puesta a mano se niega a arrancar con `DEBUG=False`. Sirve para
programar, no para operar.

Si `Activate.ps1` falla por permisos, ejecutar una vez:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### Frontend

```powershell
cd frontend
npm install     # solo la primera vez
npm run dev
```

Queda en `http://localhost:5173/`. Recarga solo al guardar archivos.

---

## La API

Toda la API exige identificarse. La única excepción es el login, porque sin
ella nadie podría obtener un token.

```
POST /api/usuarios/login/    devuelve { token, usuario }
POST /api/usuarios/logout/   invalida el token en el servidor
GET  /api/usuarios/yo/       el usuario del token

GET/POST/PUT/DELETE
  /api/maestros/mandantes/  /productos/  /especificaciones/
  /api/maestros/silos/  /vehiculos/
  /api/maestros/parametros/          catálogo de fisicoquímicos
  /api/produccion/lotes/  /analisis/
  /api/produccion/resumen/           indicadores del panel
  /api/recepcion/recepciones/  /movimientos/
  /api/recepcion/recepciones/<id>/descargar/   ingresa la leche al silo
  /api/recepcion/ocupacion/          saldo de cada silo
  /api/maestros/documentos/          catálogo del checklist, con su plantilla
  /api/calidad/registros/  /liberaciones/
  /api/calidad/expedientes/          lotes por liberar, con su avance
  /api/calidad/expedientes/<lote>/   el expediente completo de un lote
  /api/calidad/expedientes/<lote>/liberar/    firma la liberación
  /api/calidad/expedientes/<lote>/conceder/   firma bajo concesión, con motivo
```

Los `expedientes` no guardan nada: arman lo que hay que mirar para decidir.
El avance documental y el veredicto de calidad se calculan en cada llamada
([§2.2](prototipo/MODELO_DATOS.md) y [§2.6](prototipo/MODELO_DATOS.md)), así
que no hay nada que sincronizar. Firmar es lo único que cambia el estado del
mundo, y responde **409 con los motivos** si la regla no se cumple.

El token viaja en la cabecera `Authorization: Token <valor>`. En el frontend
lo adjunta un interceptor de axios ([services/api.ts](frontend/src/services/api.ts)),
que además cierra la sesión y manda al login si el backend responde 401.

Los permisos se declaran **cerrados por defecto**: un endpoint nuevo que
olvide declararlos queda protegido, no abierto. Hay una prueba que lo vigila
descubriendo las rutas del enrutador, de modo que cubre también las que se
agreguen después.

### Roles

Los cinco del proceso, definidos en [prototipo/MODELO_DATOS.md](prototipo/MODELO_DATOS.md).
El criterio es **todos leen todo, cada uno escribe en lo suyo**: que Recepción
consulte los lotes de Producción es necesario para trabajar; lo que no puede
es editarlos.

| | leer | escribir |
|---|---|---|
| Maestros (productos, especificaciones) | todos | `admin` |
| Producción (lotes, análisis) | todos | `produccion`, `admin` |
| Recepción y silos | todos | `recepcion`, `admin` |
| Liberación y documentos del checklist | todos | `calidad`, `admin` |

El catálogo de documentos es un maestro, pero lo escribe **Calidad**. El módulo
promete que Calidad cambia un campo y el formulario cambia sin desplegar
([§2.6](prototipo/MODELO_DATOS.md)); si para eso hubiera que pedírselo a un
administrador, la promesa quedaría vacía.

`lectura` y los usuarios sin perfil no escriben en ninguna parte. Un
superusuario de Django es `admin` aunque no tenga perfil, para que quien
instaló el sistema no quede fuera de él.

Las clases están en [backend/usuarios/permisos.py](backend/usuarios/permisos.py).
El frontend consulta el rol solo para no ofrecer botones que el backend va a
rechazar; el permiso se aplica en el servidor.

Para probar la API a mano conviene entrar antes a `/admin/`: la sesión del
navegador también autentica, así que las URLs se pueden abrir directamente.

---

## Arquitectura

El prototipo se diseñó en tres capas para que el cambio de plataforma afectara a una sola.
Este repositorio es ese cambio: reemplaza el almacenamiento en el navegador por un backend
compartido, que es lo que el flujo real exige (Recepción, Producción y Calidad son personas
distintas en turnos distintos).

| Capa del prototipo | Destino en este repositorio |
|---|---|
| `js/modelo/esquema.js` | Modelos de Django |
| `js/modelo/dominio.js` | Reglas de negocio en Python |
| `js/modelo/recetas.js` | Explosión de recetas multinivel, en Python |
| `js/modelo/planificador.js` | Consumo derivado y balance, en Python |
| `js/modelo/repositorio.js` | Se descarta: lo reemplazan el ORM y la API |
| `js/modelo/pruebas.js` | Pruebas en pytest |
| `js/app.js`, `js/ui/componentes.js` | Páginas y componentes React |

### Frontend

```
frontend/src/
├── app/          App.tsx, routes.tsx (rutas agrupadas por layout)
├── layouts/      mainlayout (con menú lateral), authlayout (login)
├── components/   Componentes reutilizables (Navbar, Button)
├── pages/        Una carpeta por módulo
└── services/     api.ts (cliente axios) y servicios por módulo
```

Las páginas internas se registran dentro de `<Route element={<MainLayout />}>` en
[frontend/src/app/routes.tsx](frontend/src/app/routes.tsx) y heredan el menú lateral.
Para que un módulo aparezca en el menú, se le asigna su ruta en
[frontend/src/components/Navbar/Navbar.tsx](frontend/src/components/Navbar/Navbar.tsx)
(los que tienen `ruta: null` se muestran en gris como "Pronto").

---

## Estado de los módulos

| Módulo | Estado |
|---|---|
| Login | Funcional, con token. Falta recuperar contraseña |
| Panel general | Funcional, conectado a la API |
| Producción | Listado, filtros, alta y borrado. Falta editar |
| Recepción y silos | Registro, controles del camión, descarga y ocupación |
| Liberación (Calidad) | Checklist con formularios dinámicos, cotejo contra el laboratorio, firma y concesión |
| Despachos | Pendiente |
| Maestros / Administración | Pendiente |
| Planificador | Pendiente |

---

## Definiciones pendientes con Calidad y Producción

Detalle en [prototipo/MODELO_DATOS.md](prototipo/MODELO_DATOS.md) §8.

1. **Especificaciones oficiales** por producto y mandante. Las actuales son referenciales.
2. **¿Los análisis son por lote o por despacho?** El modelo admite varios por lote y agrega
   por el peor caso; falta confirmar que ese criterio es el correcto.
3. **Qué documentos de liberación aplican a cada familia de producto.**
4. **¿Está poblada la columna `OP` en `Produccion.xlsx`?** Si lo está, puede ser la clave
   natural del lote y el modelo se simplifica.
5. **Límites de control de recepción** (acidez, pH, temperatura, crioscopía).

Ninguna bloquea las primeras fases. La 1 y la 3 tampoco bloquean *construir* el módulo
de Calidad, y por eso ya está construido: los formularios son datos, no código
([§2.6](prototipo/MODELO_DATOS.md)), y las especificaciones están versionadas ([§2.3](prototipo/MODELO_DATOS.md)).
Lo que bloquean es **ponerlo a operar**: sin las especificaciones oficiales y sin saber
qué documentos exige cada familia, el motor funciona pero libera contra rangos
referenciales y contra un checklist inventado. Se responden cargando datos desde
`/admin/`, no modificando código.
