# Auditoría de accesibilidad — CCAA

Generado por `e2e/accesibilidad.spec.ts` (axe-core sobre Chromium).

Cubre lo que una máquina puede comprobar: contraste, etiquetas, nombres
accesibles, encabezados de tabla, orden de títulos y tamaño de objetivo
táctil. **No** dice si una pantalla se entiende ni si el flujo tiene
demasiados pasos: eso lo contesta ver a un operario usándola.

## Resumen

- Pantallas auditadas: **33**
- Reglas incumplidas: **3**
- Elementos afectados: **28**

| Regla | Gravedad | Elementos | Pantallas |
|---|---|---|---|
| `select-name` | critical | 24 | 12 |
| `scrollable-region-focusable` | serious | 3 | 3 |
| `target-size` | serious | 1 | 1 |

## `select-name` — critical

Select element must have an accessible name

- Elementos afectados: **24** en **12** pantalla(s)
- Referencia: https://dequeuniversity.com/rules/axe/4.13/select-name?application=playwright

Aparece en 12 de las pantallas auditadas.

Clases que más se repiten entre los elementos afectados:

- `border-slate-300` — 22 de 24 elementos
- `border-slate-200` — 2 de 24 elementos
- `text-slate-700` — 2 de 24 elementos
- `text-slate-600` — 1 de 24 elementos

Ejemplos:

- `.overflow-hidden.rounded-2xl:nth-child(1) > .p-5 > form > select:nth-child(1)`
  Element does not have an implicit (wrapped) <label> Element does not have an explicit <label> aria-label attribute does not exist or is empty aria-labelledby attribute does not exist, references elements that do not exist or references elem
  ```html
  <select required="" class="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm outline-none focus:border-green-600"><option value="">Material…</opti
  ```
- `select:nth-child(3)`
  Element does not have an implicit (wrapped) <label> Element does not have an explicit <label> aria-label attribute does not exist or is empty aria-labelledby attribute does not exist, references elements that do not exist or references elem
  ```html
  <select required="" class="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm outline-none focus:border-green-600"><option value="">Ubicación…</opt
  ```
- `.overflow-hidden.rounded-2xl:nth-child(2) > .p-5 > form > select`
  Element does not have an implicit (wrapped) <label> Element does not have an explicit <label> aria-label attribute does not exist or is empty aria-labelledby attribute does not exist, references elements that do not exist or references elem
  ```html
  <select required="" class="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm outline-none focus:border-green-600"><option value="">Existencia y lo
  ```

## `scrollable-region-focusable` — serious

Scrollable region must have keyboard access

- Elementos afectados: **3** en **3** pantalla(s)
- Referencia: https://dequeuniversity.com/rules/axe/4.13/scrollable-region-focusable?application=playwright

Pantallas: Producción · Leche · Historial · Auditoría

Ejemplos:

- `.overflow-x-auto`
  Element should have focusable content Element should be focusable
  ```html
  <div class="overflow-x-auto">
  ```

## `target-size` — serious

All touch targets must be 24px large, or leave sufficient space

- Elementos afectados: **1** en **1** pantalla(s)
- Referencia: https://dequeuniversity.com/rules/axe/4.13/target-size?application=playwright

Pantallas: Iniciar sesión

Clases que más se repiten entre los elementos afectados:

- `text-slate-600` — 1 de 1 elementos

Ejemplos:

- `button[type="button"]`
  Target has insufficient size (20px by 20px, should be at least 24px by 24px) Target has insufficient space to its closest neighbors. Safe clickable space has a diameter of 20px instead of at least 24px.
  ```html
  <button type="button" class="text-slate-600" aria-label="Mostrar contraseña">
  ```
