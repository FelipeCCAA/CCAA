# Los 30 minutos de agitación avisan, no bloquean

**Fecha:** 2026-08-17
**Rama:** `feature-estandarizaciónfix`
**Base:** `feature-inocuidadJS` (9071583)
**Módulo:** `backend/estandarizacion`, `frontend/src/pages/Estandarizacion`

## Qué se cambia

Hoy `servicios.registrar_muestra` **rechaza** una muestra tomada antes de los 30
minutos de agitación. Pasa a **aceptarla y advertir**, y el vale guarda cuándo se
muestreó para que la advertencia sea auditable después.

Es el mismo criterio que el proyecto ya aplica en `codigo_lote_valido` —que avisa
y no restringe— y en la leche asignada del lote, que advierte sin detener la
declaración de producido.

## Por qué existe la regla, y qué se pierde

`MINUTOS_DE_AGITACION = 30` no es arbitrario. Viene del flujo de fábrica §10.3,
recogido en `docs/REGLAS_DE_PLANTA.md` §3: antes de esos minutos la mezcla no es
homogénea, así que el RC que devuelve la muestra no es el del silo.

Quitar el bloqueo permite liberar un vale contra un análisis que no mide lo que
dice medir. **La decisión es de planta y está tomada**; este documento la
implementa y deja el rastro para que el riesgo sea visible, no invisible.

Lo que compensa la pérdida es el registro: hasta ahora el sistema garantizaba los
30 minutos pero no dejaba constancia de nada; desde ahora no los garantiza pero
sí queda escrito, vale por vale, cuánto se agitó realmente.

## Qué NO cambia

- **La máquina de estados sigue exigiendo que se haya agitado.**
  `TRANSFERIDO → MUESTREADO` no es una transición válida, así que muestrear sin
  haber iniciado la agitación sigue fallando. Lo que deja de bloquear es la
  *duración*, no el paso.
- **`MINUTOS_DE_AGITACION = 30` se queda**, con su comentario. Pasa de ser el
  umbral del bloqueo a ser el umbral del aviso.
- **La hora la sigue poniendo el servidor.** No se acepta del cliente ni el
  inicio de la agitación ni la hora del muestreo: son lo que determina si la
  advertencia aparece, y recibirlas de fuera permitiría declarar minutos que no
  ocurrieron.
- **La validación de SNG ≤ 0 se queda.** Es un dato imposible, no una
  advertencia de tiempo.
- **`calidad`, el checklist del lote y `puede_liberar` no se tocan.** Un vale
  muestreado temprano no altera la liberación del lote que consumió esa mezcla.

## Diseño

### Modelo (`backend/estandarizacion/models.py`)

**Campo nuevo:** `muestreado_en = DateTimeField(null=True, blank=True)`, escrito
por el servidor al registrar la muestra.

**`minutos_agitando` se congela.** Hoy se calcula contra `timezone.now()`, así
que un vale mirado al día siguiente informa 1.400 minutos y no hay forma de saber
si la muestra se tomó a los 12 o a los 40. Pasa a calcularse contra
`muestreado_en` cuando existe, y contra `timezone.now()` mientras no exista.

**`puede_muestrear` (bool) → `avisos_de_muestreo` (`list[str]`).** Sigue la
convención declarada en CLAUDE.md: las decisiones devuelven motivos, no un
booleano. Vacía significa que no hay nada que advertir.

Sirve en los dos momentos sin ramificar, porque se apoya en `minutos_agitando`:
**antes** de muestrear cuenta contra el reloj actual y dice cuánto lleva; **después**
cuenta contra `muestreado_en` y dice a los cuántos minutos se muestreó. Es la
misma frase leída en dos instantes, no dos cálculos.

**Que la muestra fue temprana se deriva, no se guarda.** Se obtiene comparando
`muestreado_en` con `agitacion_desde` contra `MINUTOS_DE_AGITACION`, igual que
`rc_real` y el veredicto de calidad se recalculan en vez de persistirse. Una
bandera almacenada se desincroniza en cuanto alguien corrige una hora.

### Servicio (`backend/estandarizacion/servicios.py`)

**`registrar_muestra`:** desaparece el `raise` de las líneas 145–151 y se escribe
`muestreado_en = timezone.now()`. Pasa a devolver `(vale, avisos)` en vez de solo
el vale, siguiendo a `decidir`, que ya devuelve `(vale, evaluacion)` por la misma
razón: la vista necesita el resultado del cálculo, no solo el objeto guardado.

**`reagitar` limpia `muestreado_en`.** Es la trampa de este cambio: `reagitar` ya
reinicia `agitacion_desde` y borra el análisis, pero si conserva el sello del
ciclo anterior queda un `muestreado_en` **anterior** al nuevo `agitacion_desde`,
y `minutos_agitando` sale negativo. Lleva prueba propia.

### API (`serializers.py`, `views.py`)

- El serializer expone `muestreado_en` y `avisos` (lista), y retira
  `puede_muestrear`.
- La acción `muestrear/` responde 200 con los avisos en el cuerpo, donde antes
  respondía 409.

### Frontend

- `estandarizacion.service.ts`: el tipo cambia `puede_muestrear: boolean` por
  `avisos: string[]`, y suma `muestreado_en`.
- `Estandarizacion.tsx`: el botón de muestrear deja de estar deshabilitado por
  tiempo. Los avisos se muestran al capturar el análisis y en la ficha del vale,
  con el mismo tratamiento visual que ya recibe `evaluacion.motivo`.
- `Cronometro.tsx`: sigue contando —el operador quiere saber cuánto lleva— pero
  el texto pasa de permiso a información: deja de decir «Ya se puede muestrear».

### Migración

Una sola, para `muestreado_en`. Tras `makemigrations` hay que correr `migrate`:
el runner de pruebas migra solo la base de pruebas, así que una migración sin
aplicar deja la suite verde y revienta en el navegador.

## Pruebas

| Prueba | Qué pasa |
|---|---|
| `tests_vale.py:145` `test_no_se_muestrea_antes_de_los_treinta_minutos` | Invierte: muestrea y devuelve aviso. Se renombra. |
| `tests_vale.py:384` `test_muestrear_antes_de_tiempo_responde_409` | Invierte: 200 con aviso en el cuerpo. Se renombra. |
| `tests_vale.py:273` (el reagitar que no deja muestrear de inmediato) | Invierte |
| `tests_vale.py:172` `test_sin_agitar_no_se_muestrea` | **Sigue verde** — lo bloquea la transición, no el reloj |
| `tests_vale.py:163` `test_cumplidos_los_treinta_se_muestrea` | Sigue verde |
| `tests_vale.py:180` `test_el_reloj_lo_pone_el_servidor` | Sigue verde |

**Nuevas:**

1. Muestrear a los 20 minutos deja el vale en `MUESTREADO` y devuelve un aviso
   que nombra los minutos reales.
2. Muestrear pasados los 30 no devuelve ningún aviso.
3. `muestreado_en` congela `minutos_agitando`: el valor no crece al releer el
   vale más tarde.
4. `reagitar` limpia `muestreado_en`, y `minutos_agitando` vuelve a contar desde
   el nuevo inicio sin salir negativo.

## Documentación a corregir

Ambos textos afirman hoy que no se muestrea antes de 30 minutos, y dejarían de
describir el sistema:

- `docs/REGLAS_DE_PLANTA.md` §3
- `CLAUDE.md`, en el párrafo de Estandarización

`backend/usuarios/management/commands/sembrar_flujo_demo.py:294` retrasa
`agitacion_desde` 35 minutos precisamente para saltarse esta regla. El truco
queda innecesario; se puede dejar como está, porque un vale de demostración
agitado 35 minutos sigue siendo el caso normal que conviene sembrar.
