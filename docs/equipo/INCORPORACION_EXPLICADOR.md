# Integración de EXPLICADOR y lectura del avance

Fecha: 20-10-2026. EXPLICADOR se incorpora como rol 16. Revisó los expedientes existentes y contrastó OP-02 con el especialista; no volvió a auditar el repositorio completo. Las cifras de pruebas siguientes pertenecen a corridas previas registradas, no a nuevas ejecuciones del explicador.

## EXPLICADOR — OP-00

**1. PROBLEMA DETECTADO:** faltaba una base reproducible para comprobar cambios sin tocar la operación real.

**2. CAUSA TÉCNICA:** las pruebas de reset heredaban configuración de entorno; las del resumen dependían del calendario y el frontend no ejecutaba su suite en CI. Referencias y antecedentes: [expediente OP-00](../operacion/OP-00_VALIDACION.md).

**3. EJEMPLO OPERACIONAL:** una prueba que pasa o falla por la fecha no demuestra que el resumen de producción sea correcto. Es una explicación del riesgo, no un incidente industrial observado.

**4. SOLUCIÓN RECOMENDADA:** utilizar PostgreSQL desechable, entorno controlado y verificaciones reproducibles antes de integrar cambios.

**5. TRABAJO REALIZADO:** coordinación y AVANCE, revisión/QA e implementación ajustaron pruebas y CI. Se añadió la ejecución de pruebas frontend y se controlaron entorno y reloj de fixtures. No se cambiaron las reglas del resumen ni se efectuaron despliegues.

**6. PRUEBAS Y RESULTADOS:** [CI 39430749532](https://github.com/FelipeCCAA/CCAA/actions/runs/39430749532): backend 1.529 casos, 1.524 aprobados y 5 omitidos; frontend 85/85. Evidencia histórica del código validado, no pruebas ejecutadas en esta incorporación.

**7. ESTADO FINAL:** VALIDADO MEDIANTE PRUEBAS en su rama. [PR #6](https://github.com/FelipeCCAA/CCAA/pull/6) preparado sin merge/despliegue según el cierre registrado. No certifica operación industrial ni capacidad para 70 usuarios.

## EXPLICADOR — OP-01

**1. PROBLEMA DETECTADO:** una firma o una hoja autorizada podía seguir respaldando evidencia u origen que habían cambiado.

**2. CAUSA TÉCNICA:** faltaba ligar el acto de Calidad y la autorización a la evidencia revisada y comprobar su vigencia al ejecutar. La corrección está en `calidad/vigencia.py`, los modelos/vistas de Calidad y `inventario/servicios.py` (`autorizar_despacho`, `ejecutar_despacho`).

**3. EJEMPLO OPERACIONAL — SIMULADO:** Calidad firma; después se corrige un análisis o se cambia el origen del despacho. La autorización anterior ya no describe exactamente lo que va a salir.

**4. SOLUCIÓN RECOMENDADA:** identificar cada firma, conservar su evidencia, retirar la vigencia ante cambios relevantes y exigir nueva firma y autorización. Revalidar origen, muestra, cantidad y estados al ejecutar.

**5. TRABAJO REALIZADO:** coordinación/arquitectura, especialista de Inventario, revisión/QA y AVANCE implementaron y revisaron los cambios del [expediente OP-01](../operacion/OP-01_VALIDACION.md). Se añadieron cuatro campos de firma a cada aprobación y un JSON a la hoja mediante dos migraciones aditivas, sin autoaprobar históricos. Calidad, Producción, Inventario y la interfaz conservan guardas y auditoría. Código validado `479624a`; cierre documental `60bf962`.

**6. PRUEBAS Y RESULTADOS:** [CI 39446921296](https://github.com/FelipeCCAA/CCAA/actions/runs/39446921296): backend 1.586 casos, 1.581 aprobados, 5 omitidos; frontend 88/88, checks y build aprobados. Local: 96 y 16 aprobados, con seis carreras entre conexiones reales. Un reintento no debe producir otra salida: eso es idempotencia. Ante un error, todas las escrituras relacionadas se revierten: eso es rollback dentro de una operación atómica. Los tres recorridos de escritorio no son UAT ni un E2E industrial.

**7. ESTADO FINAL:** VALIDADO MEDIANTE PRUEBAS en su rama; [PR #7](https://github.com/FelipeCCAA/CCAA/pull/7) preparado en borrador, sin merge/despliegue según el cierre registrado. Históricos necesitan firma expresa y plan de aplicación real. Una ficha histórica puede verse verde aunque Despacho la rechace; no equivale a autorización de salida. Reservas globales/genealogía OP-03, carga y recuperación siguen fuera de este cierre.

## EXPLICADOR — seguimiento posterior de CI de OP-01

**1. PROBLEMA DETECTADO:** la corrida documental posterior no terminó aprobada, aunque sus comprobaciones de backend pasaron.

**2. CAUSA TÉCNICA:** al eliminar la base desechable `test_ccaa_ci`, PostgreSQL informó dos sesiones conectadas. Los logs no identifican cuáles eran. QA encontró dos candidatos anteriores a OP-01 (`procesos/tests_concurrencia_version.py:47` y `usuarios/tests_sesiones.py:199`), que usan trabajadores y `close_old_connections()`; ese cierre puede conservar conexiones sanas recientes. Es una hipótesis, no una atribución demostrada. Los nuevos hilos de OP-01 incluyen cierre incondicional y comprobación de terminación.

**3. EJEMPLO OPERACIONAL — EXPLICATIVO:** terminar las comprobaciones y dejar abierta la base impide completar la limpieza del entorno de pruebas. No demuestra un fallo en un despacho real.

**4. SOLUCIÓN RECOMENDADA:** identificar las sesiones antes del cierre mediante `pg_stat_activity` y correlacionarlas con los trabajadores de las pruebas; corregir el responsable únicamente después de confirmar la causa.

**5. TRABAJO REALIZADO:** QA revisó logs y código en modo lectura; EXPLICADOR y AVANCE registraron la limitación. **Solución pendiente de implementación.** No se repitió la corrida ni se cambió código o base de datos.

**6. PRUEBAS Y RESULTADOS:** [CI 39449334479](https://github.com/FelipeCCAA/CCAA/actions/runs/39449334479), commit documental `60bf962`: 1.586 casos en 520,977 s, `OK (skipped=5)`; después falló la eliminación de la base y el job terminó con código 1. Frontend y comprobación de configuración productiva terminaron aprobados. No hay cambios de backend ni workflow entre `479624a` y `60bf962`. La corrida aprobada anterior conserva su valor histórico, pero **la última CI está fallida**.

**7. ESTADO FINAL:** EN ANÁLISIS. Falta identificar las dos sesiones y validar la corrección del cierre; no se acredita un defecto productivo ni se declara esta corrida aprobada.

## EXPLICADOR — OP-02

**1. PROBLEMA DETECTADO:** el débito de componentes y el ingreso declarado no se concilian antes de transferir. Además, una edición genérica posterior permite cambiar la receta, con riesgo de que diverja de los movimientos y la copia de ejecución ya registrados.

**2. CAUSA TÉCNICA:** `estandarizacion/servicios.py::transferir` registra salidas por `litros_entera/descremada/crema` e ingreso por `volumen`. Los movimientos del libro se crean como `recepcion.MovimientoSilo` en ese servicio; la edición genérica del vale no los reescribe. El serializer y `clean()` revisan silos y presencia, no esa igualdad; el `ModelViewSet` permite PUT/PATCH de esos campos. `procesos/servicios.py::registrar_estandarizacion` guarda una copia al transferir y devuelve la existente en reintentos. Evidencia estática, aún sin reproducción de ejecución.

**3. EJEMPLO OPERACIONAL — SIMULADO:** se indican 4.000 L de entera y 6.000 L de descremada, pero 12.000 L de destino. La operación puede ser atómica —guardar todo o nada— y aun registrar una diferencia aritmética. No se observó ese caso en datos reales ni se ejecutó su reproducción.

**4. SOLUCIÓN RECOMENDADA:** conciliar antes de mover, conservar la receta física ejecutada y registrar ajustes mediante actos explícitos y auditables. Acordar primero litros/masa, densidades si corresponden, precisión y redondeo, diferencias admisibles y correcciones posteriores. La tolerancia RC no es la tolerancia del balance. Preservar agitación, muestra, corrección y remuestreo legítimos.

**5. TRABAJO REALIZADO:** Auditor/especialista y coordinación verificaron las rutas; PM preparó el [diagnóstico OP-02](../operacion/OP-02_DIAGNOSTICO.md), y EXPLICADOR lo tradujo a esta explicación. **Solución pendiente de implementación** y de validación de reglas. Sin código, migraciones, datos o infraestructura modificados por OP-02.

**6. PRUEBAS Y RESULTADOS:** no se ejecutaron pruebas de OP-02. Existen `estandarizacion/tests_dominio.py::test_las_partes_suman_el_volumen` y `tests_vale.py::test_transferir_mueve_litros_entre_silos`, inspeccionadas y no ejecutadas en esta actividad; se proponen negativos de balance y edición posterior, fallo con reversión completa, reintento y dos operadores concurrentes. Los resultados de OP-01 no validan esos criterios nuevos.

**7. ESTADO FINAL:** EN ANÁLISIS. OP-00 habilita el entorno, pero las decisiones industriales y la implementación de OP-02 todavía no están aprobadas. [Expediente y plan de pruebas](../operacion/OP-02_DIAGNOSTICO.md).

## AVANCE — incorporación del equipo

- Equipo: 16 roles registrados, activados selectivamente; no se afirma que existan dieciséis ejecuciones simultáneas.
- Completado en esta incorporación: configuración documental, lectura del avance y diagnóstico estático acotado de OP-02.
- Estado OP: OP-00 y código OP-01 con evidencia aprobada previa; última CI documental de OP-01 fallida durante limpieza, en análisis. OP-02 en análisis; OP-03 a OP-09 pendientes según el registro existente. No se calcula porcentaje.
- Próxima actividad: validar contrato de balance, redondeo y correcciones; después preparar implementación autorizable y sus pruebas.
- Backlog y código funcional conservados. No nuevas pruebas de ejecución, servicios externos, migraciones ni despliegues.
