# OP-09 — prueba operacional por pantalla, corte parcial 2026-10-23

**BLOQUEADA ANTES DE DESCARGAR. Ningún circuito completo aprobado.**
Se conserva el entorno y la misma recepción para retomar, sin volver a sembrar
operaciones ni dar por ejecutados los procesos pendientes.

## Autorización y aislamiento

Usuario autorizó todos los circuitos productivos por pantalla, una acción
operacional cada10segundos por usuario, trazabilidad/cantidades/destinos y
capturas con campos y botones. Excluyó Planificación, Compras y Mantenimiento;
se prepararon órdenes e insumos ficticios como prerrequisitos, sin operar esos
módulos. No se autoriza modificar aplicación, producción, desplegar ni contratar.

Clúster nuevo vacío `opflow-runtime/pgdata`, rol `opflow_test`, loopback55479,
base `opflow_circuito`. Migraciones existentes y maestros ficticios, ninguna
restauración de datos operacionales anteriores. API8209 y web5209 loopback;
entorno limpiado de variables externas, rechazo `.env`, identidad de clúster
verificada. Correo en memoria, tareas eager. Una revisión QA de apoyo.

Preparación: productos/silos/equipos/rutas/especificaciones ficticias, cuentas
por área y stock inicial de embalajes. El primer preparador de polvo falló
porque faltaba autor técnico para movimientos de insumos; no se ocultó el fallo.
Se creó autor de semilla inactivo con contraseña inutilizable, nunca empleado
para operar UI. Los operadores usan roles reales sin privilegios de superusuario.
No se usaron preparadores que crean suero o mantequilla ya aprobados: saltarían
precisamente las operaciones que el usuario pidió comprobar.

## Hechos ejecutados y cantidades

| Paso | Hecho comprobado | Responsable |
| --- | --- | --- |
| Llegada | Recepción1, guía OPF-ENT-01, camión ficticio QAOP09, leche entera25.000L | e2e_recepcion |
| Muestra | M-OPF-ENT-01, módulo1, crioscopía ficticia−0,521°C | e2e_recepcion |
| Decisión | Temperatura4,2; acidez15,4; pH6,72; MG3,62; SNG8,61; Delvo/inhibidores negativos y controles conformes | e2e_calidad |
| Auditoría | pH de enjuague7,05 con motivo ficticio documentado | e2e_calidad |
| Destino | Silo3 asignado y confirmado por pantalla, silo_id1 | e2e_recepcion |
| Descarga | **No ejecutada:0 movimientos de silo** | Interacción bloqueada |

La decisión de Calidad y la asignación corresponden a usuarios distintos
(calidad_por_id3, asignador_id10). Valores de análisis son datos ficticios
del escenario existente, no análisis reales ni tolerancias nuevas de planta.
La recepción está `liberada`, no `descargada`: **25.000L aprobados en recepción
no equivalen a25.000L ingresados físicamente al saldo del silo**.

No hay vales, lotes producidos, corridas, envases, pallets ni despachos creados.
No hay leche descremada, crema, mantequilla o polvo producidos por este ensayo.
Los embalajes iniciales no se presentan como producto envasado.

## Bloqueo y recuperación intentada

Al pulsar `Descargar`, el control del navegador devolvió timeout de
`Input.dispatchMouseEvent`. Después, la pestaña1 dejó de responder a comandos
de foco/lectura/recarga/cierre (`Emulation.setFocusEmulationEnabled`).
El botón invoca `window.confirm` antes del POST:
`frontend/src/pages/Leche/TablaRecepciones.tsx:154`.

No se observó POSTdescargar en el registro local de API. Se verificó el estado
persistido en sólo lectura: recepción1 liberada, silo1 asignado y0 movimientos.
No se repitió una escritura incierta ni se registró la descarga por API/ORM.
Esto demuestra un bloqueo de interacción del ensayo, **no prueba todavía un
defecto del inventario ni de la aplicación**. La relación causal exacta con la
confirmación nativa no queda certificada: `getJsDialog` no devolvió diálogo.

Se consultó la recuperación documentada: se intentaron recarga y controles
alternativos; el puesto de Calidad seguía permitiendo lecturas. Se abrió una
pestaña nueva y se cerró únicamente la sesión ficticia huérfana de Recepción
como preparación de autenticación. No se modificó leche, Calidad ni stock.
Los nuevos intentos de acceso por ratón/teclado tampoco generaron nuevos HTTP.
El cierre de la pestaña bloqueada no pudo completarse por el mismo timeout.
Se solicitó al usuario indicar si ve una confirmación pendiente.

La memoria observada se mantuvo aproximadamente57–65%, inferior a la guarda85%.
No se atribuye este corte a la falta de memoria observada en las cargas previas.
El observador de memoria se mantiene activo y bloqueará nuevas acciones si
supera85%; no cierra aplicaciones ajenas. Entorno local conservado para revisión.

## Ritmo y limitaciones de evidencia

Cada acción lógica —completar formulario, guardar, confirmar, aprobar— espera
al menos10segundos desde el fin de la anterior del operador. Las consultas y
autoguardados de la aplicación no se espacian artificialmente. Se verificaron
23 intervalos de acciones registradas, mínimo **10,007s**. No se certifica
carga70 ni concurrencia de procesos completos: sólo dos puestos iniciados.

Un primer helper de registro capturó el nombre inicial del actor en el REPL:
seq11–17 pertenecen a Calidad aunque el JSON original dice Recepción. Se
conserva el original y una corrección explícita, corroborada con identidad
visible y responsable persistido. Aquel helper imponía intervalo global10s,
más restrictivo que por usuario. Después se sustituyó por contexto mutable
único, con usuario visible verificado antes de cada operación.

El primer helper de capturas también quedó ligado a Recepción: imágenes007–009
**no acreditan el formulario de Calidad**. Se conservan como captura incorrecta,
sin publicarlas con ese significado. Las capturas010 y011 sí se verificaron
visualmente: muestran recepción aprobada y formulario de asignación a Silo3.
Las evidencias seleccionadas no incluyen contraseñas, sesiones ni archivos privados.

Revisor QA comprobó sólo archivos guardados: cantidades/estado, responsables
distintos, cero movimientos/corridas/pallets/despachos y cadencia. El extractor
de52 modelos del dominio usa transacciónREADONLY/REPEATABLE READ; no modifica
filas ni infiere aprobación de circuitos. Ruff de QA aprobado. No se repitieron
suites backend/frontend: no hay cambios de aplicación.

## Alcance todavía pendiente

Descarga y análisis de silo con segunda firma, despacho de leche, estandarización,
descremado y ambas salidas, evaporación/precondensado, secado, mantequilla y
coproductos, envase, liberación final, Bodega/despacho de productos, suero externo,
rework, variantes de catálogo y escenarios negativos/áreas solapadas:
**NO EJECUTADOS en este corte**. No usar resultados antiguos como sustituto.

Siguiente paso: recuperar el navegador/confirmación pendiente y retomar
**la recepción1 existente**, comprobando primero su estado; no volver a crear
la llegada ni repetir movimientos sin conciliación. No cambiar confirmaciones
ni aprobaciones de aplicación sin autorización adicional para corregir código.

## AVANCE y EXPLICADOR

**AVANCE:** prueba iniciada y bloqueada antes de descargar; evidencia parcial
conservada, sin producción/despliegue. No se declara tarea operacional completa.

1. **PROBLEMA DETECTADO:** la interacción del navegador quedó bloqueada al descargar.
2. **CAUSA TÉCNICA:** timeoutCDP; hay confirmación nativa antes del POST, pero su
   causalidad exacta no está demostrada. No es prueba de un fallo de stock.
3. **EJEMPLO REAL DE OPERACIÓN:**25.000L están aprobados y asignados a Silo3,
   pero aún no figuran descargados.
4. **SOLUCIÓN RECOMENDADA:** recuperar la pestaña/confirmación y retomar el mismo
   registro tras verificarlo; conservar controles y trazabilidad.
5. **TRABAJO REALIZADO POR LOS AGENTES:** coordinador preparó/operó UI; un QA
   preparó extractor y revisó evidencia; ninguna modificación de aplicación.
6. **PRUEBAS Y RESULTADOS:** llegada, muestra, decisión y asignación ejecutadas;
  23 intervalos>=10s, descarga y todos los circuitos completos pendientes.
7. **ESTADO FINAL:** **BLOQUEADO PARA CONTINUAR PRUEBA POR PANTALLA**.
