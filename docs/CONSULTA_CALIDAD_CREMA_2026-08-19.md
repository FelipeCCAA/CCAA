# Consulta a Calidad — cómo funciona el proceso de crema

**Fecha:** 2026-08-19 (revisada el 2026-08-20)
**De:** TI (Gestión Productiva Planta)
**Para:** Calidad

---

## Por qué preguntamos, y qué NO les estamos pidiendo

Estamos incorporando la crema al sistema. Hoy **no existe**: hay estanques de crema
declarados, pero nada que registre qué se hizo con ella entre la descremadora y su
destino. La consecuencia práctica es que **el balance de grasa no cierra** — la grasa que
se le quita a la leche entera no tiene dónde quedar anotada.

**No les estamos pidiendo el catálogo de cremas.** El sistema parte en blanco: al
desplegar, ustedes cargan los productos vigentes, sus especificaciones y sus formularios,
y eso se hace configurando la aplicación, no programándola. Las cremas que aparecen en
los libros viejos —Svelty, Champiñones— **quedan fuera a propósito**; si alguna sigue
vigente, se crea su hoja al configurar, como cualquier otra.

Lo que necesitamos antes de escribir el modelo es **la forma del proceso**: cómo se
comporta una operación de crema, independientemente de qué cremas se configuren después.
Son cuatro preguntas, y ninguna se responde mirando un listado de productos.

---

## 1. Las cuatro preguntas que definen el modelo

### 1.a — ¿Una operación de crema puede repartirse en varios destinos?

Una corrida de descremadora genera crema y esa crema va a algún lado. La pregunta es si
**una misma operación** puede terminar repartida —parte a despacho, parte a mantequilla,
parte a stock— o si cada operación tiene **un solo** destino.

*Por qué importa:* si siempre es uno, el destino es un campo del vale. Si puede
repartirse, hace falta un detalle por destino con sus kilos, y el vale pasa a tener hijos.
Empezar por el caso simple y descubrir después que se reparte obliga a rehacer el
registro; al revés solo sobra una tabla.

### 1.b — La reestandarización: ¿el mismo vale, o uno nuevo?

El formato trae un bloque de reestandarización debajo del de estandarización, con sus
propios análisis de liberación.

Cuando una crema se reestandariza, ¿es **el mismo documento** que vuelve atrás y se
vuelve a liberar, o es **una operación nueva** que consume la crema anterior?

*Por qué importa:* decide si el vale tiene un ciclo que puede retroceder, o si son dos
documentos encadenados. También decide qué se ve en la trazabilidad: una crema que se
reestandarizó dos veces, ¿son tres registros o uno con tres estados?

### 1.c — Los paros: ¿son del vale o de la máquina?

El vale trae la clasificación de tiempos: preparación, arranque, limpieza, aseo
intermedio, cambio de producto/formato, operacionales, y los no planeados con su motivo.

¿Esos paros son **de la operación de crema**, o son **de la descremadora** como equipo, y
por lo tanto valen igual cuando esa misma máquina está haciendo otra cosa?

*Por qué importa:* si son del equipo, el registro sirve para toda su producción y
alimenta la disponibilidad de máquina; si son del vale, solo existen cuando se hace
crema y no se pueden sumar entre sí.

### 1.d — ¿La crema se libera, o se despacha?

¿La crema es un **producto terminado** que pasa por expediente de liberación con su
checklist, igual que un lote de polvo? ¿O es un **intermedio** que se despacha o se
consume internamente sin ese paso?

*Por qué importa:* decide si la crema entra al sistema de liberación —con documentos
obligatorios y firma— o si es un movimiento de inventario con su análisis.

---

## 2. Lo que se configura al desplegar (no lo respondan ahora)

Esto lo van a cargar ustedes en el sistema cuando esté listo. Lo dejamos escrito para que
sepan qué se les va a pedir, no para que lo respondan hoy:

- **Qué cremas se producen**, con su nombre y su código.
- **Los límites de cada una**: materia grasa, acidez, temperatura, pH, crioscopía.
- **La acción correctiva de cada parámetro** — el formato antiguo declaraba, por ejemplo,
  «repetir análisis y si persiste avisar a Q.A.» para materia grasa y «no procesar» para
  acidez. El sistema guarda esa acción junto al límite.
- **Los destinos**: cuáles son clientes y cuáles son estanques internos.

Los valores del formato viejo —MG 22,5–23,5 %, acidez 10,5–14,5 °Th, T ≤ 8 °C, pH 6,5–6,8,
crioscopía 512–540— nos sirvieron para entender **qué parámetros** se controlan. No los
vamos a cargar: los vigentes los ponen ustedes.

---

## 3. Tres preguntas que no detienen nada

Podemos avanzar sin estas respuestas. Cada una define un comportamiento que hoy estamos
resolviendo por el lado conservador: **el sistema avisa en vez de impedir**.

- **3.a — Leche con más de 48 h en silo.** El Instructivo trae el control con alcohol 75°,
  hervor y organoléptico. Cuando lo incorporemos: ¿la permanencia mayor a 48 h **impide
  usar** el silo hasta revalidar, o solo **avisa**?
- **3.b — Caducidad del análisis de silo.** Ya está en el sistema: si entra un camión
  después de la muestra, el análisis queda marcado como no vigente. Falta la otra mitad:
  ¿un silo **en reposo** necesita re-muestrearse cada cierto tiempo? ¿Cada cuánto?
- **3.c — Plan de autocontrol de instrumentos.** ¿Qué instrumentos entran, con qué patrón,
  tolerancia y frecuencia? (Del Milkoscan tenemos el formato: patrón de materia grasa y de
  sólidos totales, tolerancia ±0,05, diario.)

---

## 4. Lo que no les estamos preguntando

Para que no gasten tiempo:

- **Si la Entrega de Turnos sigue viva** — es pregunta para planta.
- **De dónde sale el maestro de predios** — es decisión de TI con Recolección.
- **Los umbrales de recepción, estandarización y PCC 1** — ya están cargados; no cambian
  con esta consulta.

---

## Cómo responder

Las cuatro de la sección 1 son las que necesitamos, y probablemente se contesten más
rápido conversando que por escrito: son preguntas sobre cómo trabaja la planta, no sobre
el sistema.

Si les acomoda, lo vemos en quince minutos con el vale de crema a la vista.
