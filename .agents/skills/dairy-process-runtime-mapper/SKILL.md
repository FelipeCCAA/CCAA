---
name: dairy-process-runtime-mapper
description: Reconstruye cómo funciona realmente el proceso productivo lácteo del sistema desde la perspectiva de operadores y administradores, conectando procesos, subprocesos, productos, subproductos, lotes, estados, decisiones, calidad, trazabilidad y ejecución técnica entre React, API, Django y base de datos. Genera documentación Mermaid y un HTML visual aislado del sistema productivo.
---

# Dairy Process Runtime Mapper

## Rol

Actúa simultáneamente como:

- arquitecto funcional;
- analista de procesos productivos;
- especialista en trazabilidad;
- especialista en sistemas MES/ERP para industria alimentaria;
- analista técnico Django/React;
- experto en reconstrucción de procesos lácteos existentes.

Tu objetivo es explicar cómo funciona REALMENTE el sistema productivo actual desde dos perspectivas conectadas:

1. **Perspectiva operativa**
   - qué hace el operador;
   - en qué orden;
   - qué proceso puede iniciar;
   - qué producto está procesando;
   - qué lote recibe;
   - qué resultado genera;
   - qué proceso puede continuar después.

2. **Perspectiva técnica**
   - qué pantalla React utiliza;
   - qué endpoint se ejecuta;
   - qué View/Controller recibe;
   - qué Service aplica reglas;
   - qué modelo se modifica;
   - qué dato se persiste;
   - qué módulo consume ese resultado posteriormente.

NO implementes cambios.

NO refactorices.

NO corrijas código.

NO diseñes todavía el sistema futuro.

Primero reconstruye el funcionamiento productivo actual.

# Objetivo principal

Construir una representación clara del sistema donde una persona pueda responder:

- ¿qué ocurre desde que llega la leche?
- ¿qué proceso puede ejecutarse después?
- ¿qué productos salen de cada proceso?
- ¿qué subproductos aparecen?
- ¿qué procesos pueden bifurcarse?
- ¿qué procesos vuelven a conectarse?
- ¿qué lote nace en cada etapa?
- ¿qué lote consume otro proceso?
- ¿qué módulo valida antes de avanzar?
- ¿qué análisis de Calidad se requiere?
- ¿qué producto termina en inventario?
- ¿qué producto termina directamente en despacho?
- ¿qué proceso genera materia prima para otro proceso?
- ¿qué ocurre realmente en React y Django cuando el operador ejecuta cada paso?

# Principio fundamental

NO fuerces todos los procesos a una línea única.

Un sistema productivo lácteo puede contener:

- bifurcaciones;
- convergencias;
- procesos paralelos;
- subproductos;
- reprocesos;
- almacenamiento intermedio;
- procesos opcionales;
- procesos obligatorios;
- destinos alternativos.

Ejemplo conceptual:

```text
Leche
  │
  ├──→ Descremado
  │       │
  │       ├──→ Crema
  │       │       ├──→ Mantequilla
  │       │       └──→ Otro uso confirmado
  │       │
  │       └──→ Leche descremada
  │               │
  │               └──→ Estandarización
  │
  └──→ Estandarización
          │
          └──→ Evaporación
                  │
                  ├──→ Precondensado → Despacho
                  │
                  └──→ Secado → Polvo → Envasado → Inventario
```

Este ejemplo es solamente conceptual.

Debes reconstruir el flujo REAL desde el repositorio.

# Regla de evidencia

Nunca dibujes una relación únicamente porque parezca lógica desde el punto de vista industrial.

Debes demostrarla mediante código, configuración, modelos, frontend, tests o documentación confirmada.

Toda conclusión importante debe incluir:

`archivo:rango_de_lineas`

Clasifica cada relación como:

`CONFIRMADO`

`INFERIDO`

`NO CONFIRMADO`

`PLANIFICADO`

No presentes una práctica habitual de la industria láctea como si estuviera implementada en el sistema.

# Perspectivas obligatorias

Debes analizar el sistema desde cinco perspectivas.

## 1. Operador

¿Qué hace físicamente o administrativamente?

Ejemplo:

- selecciona silo;
- inicia proceso;
- registra volumen;
- selecciona producto;
- registra máquina;
- obtiene muestra;
- espera Calidad;
- continúa proceso;
- finaliza lote.

## 2. Producto

¿Qué producto o subproducto está siendo procesado?

Identifica:

- materia prima;
- producto intermedio;
- subproducto;
- producto terminado;
- producto a granel;
- producto de despacho;
- producto destinado a otro proceso.

## 3. Proceso

¿Qué operación productiva ocurre?

Ejemplos posibles, solo si existen:

- recepción;
- almacenamiento en silo;
- descremado;
- estandarización;
- evaporación;
- secado;
- mantequilla;
- envasado;
- liberación;
- inventario;
- despacho.

## 4. Calidad

Determina:

- dónde se toma muestra;
- qué análisis existe;
- qué proceso queda bloqueado;
- qué condición permite avanzar;
- qué ocurre ante rechazo;
- qué lote o proceso se libera.

## 5. Sistema

Determina qué ocurre técnicamente:

```text
Operador
↓
React
↓
API
↓
Django View
↓
Service
↓
Modelo
↓
PostgreSQL
↓
Estado actualizado
↓
Siguiente proceso habilitado
```

# Fase 1 — Inventario productivo

Identifica todos los procesos productivos existentes.

Construye:

| Proceso | Tipo | Entrada | Salida | Responsable | Estado |
|---|---|---|---|---|---|

Tipos posibles:

- proceso principal;
- subproceso;
- transformación;
- almacenamiento;
- control;
- liberación;
- despacho;
- inventario.

# Fase 2 — Catálogo de productos

Identifica todos los productos que realmente existen en código y datos maestros.

Clasifica:

- materia prima;
- producto intermedio;
- subproducto;
- producto terminado;
- producto a granel.

Genera:

| Producto | Nace en | Puede entrar a | Destino final | Inventario |
|---|---|---|---|---|

# Fase 3 — Relaciones proceso-producto

Construye un grafo:

`Producto → Proceso → Producto`

Ejemplo conceptual:

```text
Leche entera
    ↓
Descremado
    ├──→ Crema
    └──→ Leche descremada
```

Luego:

```text
Leche entera
+
Leche descremada
+
Crema
    ↓
Estandarización
    ↓
Leche estandarizada
```

Únicamente cuando el código confirme estas relaciones.

# Fase 4 — Secuencia real de operador

Para cada proceso reconstruye qué debe hacer un operador.

Ejemplo:

```text
1. Seleccionar origen
2. Seleccionar producto
3. Seleccionar lote
4. Seleccionar equipo
5. Iniciar proceso
6. Registrar parámetros
7. Solicitar muestra
8. Esperar resultado
9. Continuar
10. Cerrar proceso
```

No inventes pasos.

Debes obtenerlos de:

- pantallas;
- formularios;
- endpoints;
- validaciones;
- services;
- estados;
- tests.

# Fase 5 — Encadenamiento

Determina qué proceso habilita al siguiente.

Construye una matriz:

| Proceso actual | Resultado | Próximo proceso permitido | Condición |
|---|---|---|---|

Identifica:

- secuencia obligatoria;
- secuencia opcional;
- bifurcación;
- convergencia;
- espera;
- bloqueo;
- final de flujo.

# Fase 6 — Trazabilidad

Reconstruye la cadena completa de trazabilidad.

Debes seguir cuando exista:

- recepción;
- silo;
- lote origen;
- vale;
- corrida;
- producto intermedio;
- muestra;
- análisis;
- lote destino;
- envasado;
- pallet;
- inventario;
- despacho.

Construye:

```text
ORIGEN
↓
LOTE / VALE
↓
PROCESO
↓
LOTE RESULTANTE
↓
SIGUIENTE PROCESO
↓
PRODUCTO FINAL
```

Debe permitir responder:

> ¿De dónde salió este producto?

y también:

> ¿En qué terminó esta leche/lote?

# Fase 7 — Bifurcaciones

Identifica procesos donde una entrada genera más de una salida.

Ejemplo conceptual:

```text
Descremado
├── Crema
└── Leche descremada
```

Para cada salida determina:

- dónde se almacena;
- qué lote recibe;
- qué proceso puede consumirla;
- si puede ir directamente a despacho;
- si puede quedar disponible como materia prima.

# Fase 8 — Convergencias

Identifica procesos que reciben material desde distintos orígenes.

Ejemplo conceptual:

```text
Leche entera ──────┐
Leche descremada ──┼──→ Estandarización
Crema ─────────────┘
```

Determina:

- reglas de compatibilidad;
- selección de origen;
- cantidades;
- estados requeridos;
- validaciones.

# Fase 9 — Calidad

Construye el flujo real de Calidad por proceso.

Ejemplo conceptual:

```text
Proceso
↓
Muestreo
↓
Análisis
↓
¿Conforme?
├── Sí → Continuar
└── No → Bloquear / corregir / rechazar
```

Relaciona Calidad con el proceso productivo correcto.

No dibujes una sola Calidad genérica si existen diferentes análisis por etapa.

# Fase 10 — Finales de flujo

Identifica todos los posibles destinos finales:

- inventario;
- despacho;
- producto a granel;
- producto envasado;
- reproceso;
- descarte;
- otro proceso.

No asumas que todos los productos terminan en inventario.

# Fase 11 — Ejecución técnica

Para cada proceso importante genera también su secuencia técnica.

Ejemplo:

```text
Operador
↓
Pantalla React
↓
POST /api/...
↓
ViewSet
↓
Service
↓
Modelo Corrida
↓
PostgreSQL
↓
Estado creado
↓
Frontend actualizado
```

Debe incluir los nombres reales encontrados.

# Diagramas obligatorios

## 1. Línea productiva global

Debe ser el diagrama principal.

Usa:

```mermaid
flowchart LR
```

Debe representar:

- procesos;
- subprocesos;
- productos;
- subproductos;
- bifurcaciones;
- convergencias;
- destinos finales.

# 2. Línea de trazabilidad

Usa Mermaid.

Debe permitir seguir:

```text
Materia prima
→ lote
→ proceso
→ nuevo lote
→ proceso
→ producto final
```

# 3. Vista operador

Usa:

```mermaid
flowchart TD
```

Muestra el orden real de acciones.

# 4. Vista por producto

Genera un diagrama por cada producto principal.

Ejemplo:

```text
LECHE EN POLVO
Recepción
↓
...
↓
Inventario
```

# 5. Vista por proceso

Para procesos complejos genera:

```text
ENTRADA
↓
PROCESO
├── SALIDA A
└── SALIDA B
```

# 6. Secuencia técnica

Usa:

```mermaid
sequenceDiagram
```

# 7. Máquina de estados

Usa:

```mermaid
stateDiagram-v2
```

cuando exista ciclo de vida.

# 8. Relación producto-proceso

Genera un mapa:

```text
PRODUCTO
↓
PROCESO
↓
PRODUCTO
```

# 9. Calidad

Genera un diagrama específico mostrando dónde Calidad participa y qué procesos bloquea o habilita.

# 10. Destinos finales

Representa claramente qué flujos terminan en:

```text
INVENTARIO
DESPACHO
OTRO PROCESO
PRODUCTO A GRANEL
```

# Salida Markdown

Crear:

`docs/architecture/02-production-runtime.md`

Debe contener:

1. Resumen ejecutivo.
2. Mapa productivo global.
3. Procesos encontrados.
4. Productos encontrados.
5. Subproductos encontrados.
6. Relación producto-proceso.
7. Secuencia del operador.
8. Flujo por producto.
9. Flujo por proceso.
10. Bifurcaciones.
11. Convergencias.
12. Calidad.
13. Trazabilidad.
14. Destinos finales.
15. Ejecución técnica.
16. Estados.
17. Procesos incompletos.
18. Inconsistencias.
19. Elementos no confirmados.
20. Evidencia.

# Reporte visual HTML

Genera además:

`docs/architecture/html/production-runtime.html`

Este será el documento visual principal para operadores, administradores, desarrolladores y responsables de procesos.

# Aislamiento del HTML

El HTML es exclusivamente documentación.

No modificar:

- frontend/
- backend/
- templates/
- static/
- public/
- src/
- package.json
- vite.config.*
- settings.py
- urls.py
- Docker;
- nginx;
- base de datos;
- CI/CD.

No agregues rutas para mostrarlo.

No lo integres al frontend.

No agregues dependencias al sistema para generarlo.

La carpeta:

`docs/architecture/html/`

debe poder eliminarse sin afectar absolutamente nada del sistema.

# Diseño del HTML

El reporte debe priorizar comprensión.

Debe tener una navegación aproximada:

- Vista general
- Línea productiva
- Productos
- Procesos
- Operador
- Calidad
- Trazabilidad
- Estados
- Sistema técnico
- Inconsistencias
- Evidencia

# Diagrama principal

La primera vista importante debe ser:

`LÍNEA PRODUCTIVA REAL`

No debe ser un simple diagrama técnico.

Debe mostrar visualmente:

```text
PRODUCTO
↓
PROCESO
↓
PRODUCTO / SUBPRODUCTO
↓
SIGUIENTE PROCESO
```

Los procesos deben distinguirse visualmente de los productos.

Ejemplo conceptual:

```text
[LECHE]
   │
   ▼
(DESCREMADO)
   │
   ├────→ [CREMA]
   │
   └────→ [LECHE DESCREMADA]
```

# Vista por producto

Cada producto principal debe tener una tarjeta o sección propia.

Mostrar:

- origen;
- procesos;
- lotes;
- Calidad;
- destino final;
- trazabilidad;
- evidencia.

# Vista por proceso

Cada proceso debe mostrar:

## Entrada

## Acción del operador

## Sistema utilizado

## Datos requeridos

## Reglas

## Salida

## Próximo proceso

## Calidad

## Trazabilidad

## Evidencia

# Vista operador

Incluye una sección:

`¿Qué hace un operador desde inicio a fin?`

Representa el flujo real en lenguaje comprensible.

No lo conviertas únicamente en documentación técnica.

# Vista administrador

Incluye:

`¿Qué puede observar/controlar un administrador?`

Identifica únicamente capacidades existentes.

Ejemplos posibles:

- procesos activos;
- lotes;
- estados;
- bloqueos;
- resultados;
- trazabilidad;
- inventario;
- despacho.

# Vista técnica

Después de explicar la operación, muestra cómo cada acción se traduce técnicamente:

```text
OPERADOR
↓
REACT
↓
API
↓
DJANGO
↓
SERVICE
↓
MODEL
↓
POSTGRESQL
```

Esto debe permitir relacionar negocio con código.

# Colores conceptuales

Si el HTML utiliza estilos, diferencia visualmente:

- materia prima;
- producto intermedio;
- subproducto;
- proceso;
- Calidad;
- almacenamiento;
- inventario;
- despacho;
- sistema técnico;
- error/bloqueo.

Los estilos deben existir solamente en el documento HTML.

# Navegación de trazabilidad

El HTML debe facilitar seguir un recorrido de izquierda a derecha:

```text
ORIGEN → PROCESO → RESULTADO → PROCESO → RESULTADO
```

y también el recorrido inverso:

```text
PRODUCTO FINAL ← PROCESO ← LOTE ← PROCESO ← ORIGEN
```

# Detección de problemas de flujo

Identifica:

- proceso sin entrada válida;
- proceso sin salida clara;
- producto sin destino;
- subproducto sin consumidor;
- transición inexistente;
- paso que puede saltarse;
- Calidad no conectada;
- proceso que permite avanzar incorrectamente;
- trazabilidad rota;
- flujo documentado pero no implementado;
- frontend y backend con secuencias diferentes.

Clasifica:

`FLOW-001`

con severidad:

- CRITICAL
- HIGH
- MEDIUM
- LOW

# Procesos incompletos

Cuando exista una parte implementada parcialmente:

```text
PARCIALMENTE IMPLEMENTADO
```

Explica:

- qué existe;
- qué falta;
- dónde se corta;
- qué impide completar el flujo.

# Código muerto o huérfano

Marca como:

`POSIBLE CÓDIGO HUÉRFANO`

cuando encuentres:

- endpoint sin consumidor;
- proceso sin interfaz;
- modelo sin flujo;
- estado imposible de alcanzar;
- pantalla sin backend correspondiente.

No elimines nada.

# Regla AS-IS

Este agente describe únicamente:

`CÓMO FUNCIONA HOY`

No debe diseñar el funcionamiento futuro.

Las mejoras detectadas pueden registrarse como:

`OBSERVACIÓN`

pero deben enviarse posteriormente al Architecture Auditor o Improvement Planner.

# Criterio de finalización

No finalices hasta poder explicar:

```text
Materia prima
→ proceso
→ producto/subproducto
→ siguiente proceso
→ control de Calidad
→ lote
→ destino
```

para cada línea productiva principal.

Además debes poder explicar:

```text
Acción operador
→ React
→ API
→ Django
→ persistencia
→ estado resultante
→ próxima acción habilitada
```

# Archivos mínimos

Debes crear:

`docs/architecture/02-production-runtime.md`

`docs/architecture/html/production-runtime.html`

# Regla final de seguridad

La ejecución de esta Skill es de lectura sobre el sistema.

Solo puedes crear o actualizar documentación.

NO:

- cambies lógica productiva;
- corrijas procesos;
- modifiques models;
- modifiques services;
- cambies endpoints;
- cambies React;
- ejecutes migraciones;
- modifiques base de datos;
- alteres infraestructura;
- cambies dependencias.

Si descubres un error, documenta el error.

No lo corrijas.

Si generar el HTML requiere modificar el sistema, no lo hagas.

Genera toda la documentación visual únicamente dentro de:

`docs/architecture/`