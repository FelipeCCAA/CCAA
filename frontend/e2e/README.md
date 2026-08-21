# Auditoría de accesibilidad

Recorre todas las pantallas de la aplicación con [axe-core](https://github.com/dequelabs/axe-core)
sobre Chromium y deja un informe en `informe-accesibilidad.md`.

## Qué mide — y qué no

Mide lo que una máquina puede comprobar sin opinar: contraste de color, campos
sin etiqueta, botones sin nombre accesible, tablas sin encabezados, orden de
títulos y tamaño de objetivo táctil.

**No mide usabilidad.** No dice si una pantalla se entiende, si el flujo tiene
demasiados pasos, ni si el motivo por el que un lote no se puede liberar sirve
para que el operario sepa qué hacer. Eso solo lo contesta ver a alguien de
planta usándola. Esta auditoría despeja lo objetivo para que esa sesión se
gaste en lo que de verdad hay que discutir.

De las normas se incluye `wcag22aa`, que es donde vive `target-size`: en planta,
el tamaño del objetivo y el contraste deciden si alguien con guantes, frente a
una pantalla con reflejo, acierta el campo a la primera.

## Cómo se corre

Una vez, para crear la cuenta de la auditoría:

```powershell
cd backend
.venv\Scripts\python.exe manage.py crear_usuario_e2e
```

El comando imprime las variables a definir. Después:

```powershell
cd frontend
$env:E2E_USUARIO = "e2e_auditoria"
$env:E2E_CLAVE = "auditoria-e2e-ccaa"
npm run auditoria
```

Levanta Vite y Django solo si no los tienes ya corriendo. Para verlo pantalla a
pantalla: `npm run auditoria:ui`.

## Qué deja

| Archivo | Qué es |
|---|---|
| `informe-accesibilidad.md` | El informe, agrupado por regla. Es lo que hay que leer. |
| `.registro/hallazgos.jsonl` | Registro crudo, una línea por hallazgo. |
| `.informe-html/` | Informe de Playwright, con capturas y trazas de cada fallo. |
| `.auth/estado.json` | La sesión. **Contiene un token real**, por eso está en `.gitignore`. |

El informe se agrupa **por regla y no por pantalla** a propósito: el menú
lateral está en las treinta pantallas internas, así que un contraste flojo ahí
produce treinta hallazgos idénticos. Por pantalla se lee como treinta problemas;
por regla dice lo que es, un arreglo que cubre treinta pantallas.

## Que la corrida falle es lo normal

Cada pantalla con defectos falla su prueba, y las comprobaciones son «soft» para
que la corrida siga y mida todas antes de terminar en rojo. El objetivo de la
primera pasada es el inventario completo, no un semáforo.

Cuando el informe esté en cero y se quiera mantener ahí, esto sirve tal cual
como red de regresión: un botón nuevo sin etiqueta vuelve a ponerlo en rojo.

## Detalles que conviene saber antes de tocarlo

- La aplicación usa `HashRouter`: las direcciones son `/#/dashboard`. Navegar a
  `/dashboard` a secas devuelve el mismo `index.html` y se auditaría treinta
  veces la misma pantalla.
- Los hallazgos se escriben en disco según aparecen, no se acumulan en memoria.
  Playwright reinicia el worker tras cada prueba fallida, y aquí fallar es lo
  normal: en memoria, el informe salía con los datos de la última prueba.
- El inventario de pantallas (`rutas.ts`) está escrito a mano y no deducido del
  router. Una lista generada se mantiene sola, pero también deja de auditar sola
  lo que alguien borre.
- La auditoría comprueba que terminó en la ruta que pidió. Si la sesión no
  valiera, `RutaProtegida` mandaría todo al login y las treinta pantallas
  saldrían limpias por haber medido treinta veces el formulario de acceso.
