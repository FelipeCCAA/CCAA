1. Rutas productivas obligatorias
Problema
CCAA tenía rutas específicas para algunos productos, pero conservaba una ruta universal antigua y un fallback silencioso. Si un producto no tenía ruta configurada, el sistema podía iniciar igualmente un proceso genérico, con riesgo de saltarse etapas o perder trazabilidad.
Solución
- Las operaciones nuevas ahora exigen una ruta activa asociada al producto.
- Se agregó GET /api/procesos/rutas-producto/diagnostico/ para detectar productos elaborables sin ruta.
- Se creó un backfill para completar rutas existentes sin asignar rutas incorrectas a leche, crema o rework.
- El fallback quedó limitado a compatibilidad histórica y no se utiliza para crear operaciones nuevas.
Por qué
Cada producto necesita seguir su proceso real. Leche en polvo, mantequilla y precondensado comparten conceptos, pero no necesariamente las mismas etapas.
Relación con otros cambios
La ruta determina:
- qué lote puede abrirse;
- cuál es la siguiente etapa;
- qué equipo corresponde;
- qué permisos necesita el operador;
- qué control de Calidad debe cumplirse.
2. Diagnóstico y rollback cuando falta trazabilidad
Problema
Una transferencia o apertura de lote podía avanzar parcialmente y fallar después al intentar construir su trazabilidad. Eso podía dejar movimientos, volúmenes o estados incompletos.
Solución
- El diagnóstico de rutas se consulta bajo demanda desde React.
- Antes de transferir o abrir un lote se muestran producto, ruta y problemas de configuración.
- Las operaciones críticas se ejecutan dentro de transacciones.
- Si no puede crearse la ruta, entrada, salida o vínculo trazable, toda la operación hace rollback.
Por qué
Es preferible no registrar nada a registrar una operación productiva incompleta que luego no pueda reconstruirse.
Relación con otros cambios
Esto protege especialmente:
- transferencias desde Estandarización;
- apertura de lotes;
- creación de ejecuciones;
- posterior asignación de equipos;
- continuidad hacia Calidad y la siguiente etapa.
3. Permisos operacionales por etapa
Problema
Los permisos anteriores eran demasiado amplios. Algunos usuarios de Condensación o Secado podían escribir en endpoints correspondientes a otras etapas o incluso modificar configuración productiva.
Solución
Se separaron las responsabilidades entre:
- consultar;
- operar una etapa;
- configurar maestros;
- ejecutar acciones críticas.
Las escrituras productivas deben pasar por acciones explícitas y servicios del dominio. Los maestros como procesos, etapas y rutas quedan reservados a usuarios autorizados para configuración.
Por qué
Ocultar un botón en React no es seguridad. El backend debe impedir que un operador llame manualmente un endpoint correspondiente a otro puesto.
Relación con otros cambios
Los permisos dependen de la ruta y etapa de la ejecución. También afectan apertura, cierre, transferencia, Calidad, mantequilla, Secado y Envasado.
4. Disponibilidad y exclusión concurrente de equipos
Problema
Dos usuarios podían intentar ocupar simultáneamente el mismo equipo. Además, distintos endpoints no usaban el mismo criterio para decidir si una máquina estaba ocupada.
Solución
Se estableció una única regla backend:
- preparacion → reserva el equipo;
- ejecucion → ocupa el equipo;
- pausada → continúa ocupándolo;
- bloqueada → continúa ocupándolo;
- pendiente_control → no lo ocupa físicamente.
La exclusión está protegida mediante:
- transacciones;
- select_for_update sobre el equipo;
- restricción parcial de unicidad en PostgreSQL;
- constante compartida ESTADOS_QUE_OCUPAN_EQUIPO.
Por qué
Un botón deshabilitado no evita que dos solicitudes lleguen casi simultáneamente. La base de datos debe impedir físicamente la doble ocupación.
Relación con otros cambios
La exclusión se utiliza al abrir lotes, continuar procesos, seleccionar torres, evaporadores y equipos de mantequilla, y al comprobar condiciones CIP.
5. Disponibilidad visible en React
Problema
El operador podía seleccionar un equipo sin saber claramente si estaba disponible, reservado u ocupado. También se refrescaba demasiada información después de algunas acciones.
Solución
React muestra:
- Disponible;
- Reservado, para preparacion;
- Ocupado, para ejecucion, pausada y bloqueada.
Cuando es posible, también muestra la ejecución responsable. Los equipos se relacionan mediante equipo_id; equipo_nombre se utiliza solamente para mostrar texto.
Después de una acción se refresca únicamente el panel afectado:
- ejecuciones operativas;
- opciones de continuación;
- condensaciones o evaporadores cuando corresponde;
- salidas disponibles.
No se recargan Producción completa, Calidad, rutas y todos los lotes.
Por qué
Esto reduce consultas y evita decisiones basadas en información ambigua. También mejora el comportamiento para varios usuarios concurrentes.
Relación con otros cambios
React refleja la regla backend; no mantiene un sistema paralelo de ocupación. Los POST/PATCH bloquean el doble clic y no tienen reintentos automáticos.
6. Calidad intermedia de mantequilla
Problema
La mantequilla a granel podía quedar confundida entre el cierre de producción, la revisión de Calidad y el inicio de Envasado. Además, el flujo antiguo estaba orientado principalmente a análisis de silos.
Solución
Al cerrar una corrida de mantequilla:
1. se genera la salida de mantequilla a granel;
2. se crea una liberación de proceso pendiente;
3. aparece en Calidad como Mantequilla a granel pendiente;
4. Calidad puede liberarla o rechazarla;
5. solo la liberación habilita la continuidad hacia Envasado.
La bandeja muestra lote, corrida, producto, equipo, cantidad, unidad, estado y análisis disponibles.
Por qué
La mantequilla a granel es un producto intermedio que necesita conformidad antes de envasarse. No corresponde tratarla todavía como producto terminado de inventario.
Relación con otros cambios
Depende de la corrida de mantequilla y sus salidas. Afecta directamente Calidad y Envasado, pero no ocupa físicamente el equipo mientras espera el resultado.
7. Análisis de lote y bloqueo de Envasado
Problema
El flujo de Calidad intentaba adaptar todos los resultados a análisis de silo, aunque la mantequilla necesita análisis asociado a un lote.
Solución
Cuando analisis_tipo === "lote":
- no se pide silo;
- se selecciona un análisis del lote;
- se muestran los rangos de especificación junto a los resultados;
- la liberación envía analisis_lote_id;
- el rechazo exige un motivo.
Las acciones son explícitas:
- Liberar para Envasado;
- Rechazar.
Mientras Calidad esté pendiente, Envasado muestra:
Esperando aprobación de Calidad

Si se intenta envasar de todas formas, se presenta el mensaje operacional entregado por Django.
Por qué
El análisis debe corresponder al material real controlado. Inventar un silo artificial habría debilitado la trazabilidad.
Relación con otros cambios
La liberación cambia el estado del producto intermedio y habilita Envasado. El rechazo mantiene el material fuera del flujo siguiente.
8. Corrida especializada de Secado
Problema
Secado utilizaba solamente la ejecución y el lote genéricos. No representaba con claridad alimentación, torre, sólidos, producto en polvo, finos, pérdidas ni rendimiento.
Solución
Se agregó CorridaSecado, relacionada uno a uno con EjecucionProceso.
La corrida registra:
- alimentación;
- sólidos;
- polvo generado;
- finos;
- pérdidas;
- controles operacionales;
- rendimiento calculado.
Se crea automáticamente al abrir un lote en una etapa de torre. Su cierre es transaccional y rechaza balances de masa imposibles. El endpoint disponible es:
POST /api/procesos/secados/{id}/cerrar/
Por qué
Secado tiene controles y resultados propios. Mantener los elementos comunes en la ejecución, pero especializar la corrida, evita tanto duplicación como un megaformulario universal.
Relación con otros cambios
Secado depende de:
- ruta válida;
- lote trazable;
- entrada habilitada;
- torre disponible;
- exclusión de equipo.
Su resultado después se relaciona con Calidad, Envasado e inventario de producto final.
9. Cambios frontend realizados
Problema
Producción mezclaba demasiadas responsabilidades y no mostraba claramente errores, rutas, ocupación o controles intermedios.
Solución
Hasta ahora React incorpora tres bloques terminados:
1. Rutas productivas
   - diagnóstico bajo demanda;
   - mensajes claros para errores de ruta, etapa y equipo;
   - integración en apertura y continuación de lotes.
2. Disponibilidad de equipos
   - estados visible/reservado/ocupado;
   - selección bloqueada cuando corresponde;
   - refrescos parciales;
   - protección de doble envío.
3. Calidad de mantequilla
   - bandeja propia;
   - análisis de lote;
   - rangos de referencia;
   - liberar o rechazar;
   - bloqueo visible en Envasado.
Por qué
El operador ve solamente la información necesaria para tomar la siguiente decisión, mientras Django conserva la autoridad de las reglas.
Relación con otros cambios
El frontend consume lo ya terminado en backend. Todavía no se construyó el puesto frontend independiente de Secado.
10. Incompatibilidades backend/frontend
Problema
Durante la integración se encontraron diferencias reales entre lo que React necesitaba y lo que algunos endpoints entregaban.
Solución
Ya se corrigieron:
- endpoints que consideraban ocupado solamente ejecucion;
- opciones de mantequilla que no informaban correctamente la ocupación;
- ausencia de equipo_id en ejecuciones operativas.
El contrato actual de GET /api/procesos/ejecuciones/operativas/ mantiene:
- equipo_id, como identidad;
- equipo_nombre, para visualización.
Por qué
Relacionar equipos por nombre era frágil. Además, todas las pantallas deben aplicar exactamente la misma regla física de ocupación.
Relación con otros cambios
La corrección afecta selectores de equipos, apertura, continuación, evaporación, mantequilla y el futuro puesto de Secado.
Quedan dos incompatibilidades conocidas:
- Envasado todavía no recibe anticipadamente el estado de liberación de la mantequilla; actualmente conoce el bloqueo cuando Django rechaza el POST.
- Algunos resultados de mantequilla usan código de ejecución o nombre de etapa en campos que deberían representar el lote y producto reales de la salida.
11. Migraciones
Problema
Las nuevas garantías necesitan datos, restricciones y entidades persistentes.
Solución
Se crearon:
- procesos/0014_completar_rutas_productivas.py
- procesos/0015_impedir_doble_ocupacion_equipo.py
- calidad/0006_analisis_lote_liberacion_proceso.py
- procesos/0016_corrida_secado.py
Por qué
Estas migraciones completan rutas, protegen equipos, soportan análisis de lote/liberaciones y agregan la corrida especializada de Secado.
Relación con otros cambios
El código está preparado, pero estas migraciones aún deben aplicarse en la base de datos real antes de verificar todo operativamente. makemigrations --check no detectó migraciones adicionales pendientes.
12. Pruebas realizadas
Problema
Las reglas afectan varias áreas y podían romperse silenciosamente sin pruebas de transiciones, permisos y concurrencia.
Solución
Se ejecutaron solamente pruebas relacionadas:
- 28 pruebas backend correspondientes a las primeras fases;
- 7 pruebas backend para la unificación de ocupación;
- 3 pruebas frontend del bloque de rutas;
- 7 pruebas frontend de disponibilidad;
- 6 pruebas frontend de Calidad de mantequilla.
También pasaron las verificaciones relacionadas de:
- Ruff;
- TypeScript;
- ESLint sobre archivos modificados;
- makemigrations --check;
- git diff --check.
Por qué
Se verificaron los cambios concretos sin gastar tiempo ejecutando repetidamente toda la suite.
Relación con otros cambios
Estas pruebas cubren rutas, rollback, permisos, ocupación, contratos, mantequilla y comportamiento frontend. No equivalen todavía a una simulación integral en la base real.
Cómo queda conectado todo
El flujo base queda así:
Producto
→ Ruta productiva activa
→ Apertura de lote
→ Selección y reserva de equipo
→ Ejecución del proceso correspondiente
→ Control de Calidad cuando la etapa lo requiere
→ Siguiente etapa o Envasado
No todos los productos recorren exactamente las mismas etapas.
Para mantequilla:
Crema liberada
→ Corrida de mantequilla
→ Mantequilla a granel
→ Calidad con análisis de lote
→ Liberada
→ Envasado
Para leche en polvo:
Leche habilitada
→ Ruta del producto
→ Procesos previos / evaporación
→ Corrida especializada de Secado
→ Polvo a granel
→ Calidad
→ Envasado
→ Inventario
La ruta decide el camino; el lote mantiene la identidad; la ejecución registra cada transformación; el equipo representa la ocupación física; Calidad autoriza la continuidad.
Qué falta
Pendiente backend
- Corregir los dos contratos restantes de mantequilla: estado anticipado para Envasado y datos reales de lote/producto en Calidad.
- Formatos configurables de Envasado.
- Separación completa de consumos de materiales por fase productiva y fase de envasado.
- Completar los puntos posteriores del plan sobre genealogía, rework físico e idempotencia.
Pendiente frontend
- Puesto independiente de Secado conectado al backend ya implementado.
- Visualización de cierre, balance y rendimiento de la corrida de Secado.
- Mostrar anticipadamente el bloqueo de mantequilla cuando el backend exponga ese dato.
- Continuar separando las pantallas operacionales por puesto sin duplicar la lógica existente.
Pendiente de pruebas
- Aplicar las migraciones en un entorno controlado.
- Probar el recorrido completo de mantequilla hasta Envasado.
- Probar el recorrido completo de Secado con balance válido e inválido.
- Verificar concurrencia real usando PostgreSQL.
- La suite completa no se ha ejecutado.
Pendiente de auditoría
- Validar datos reales antes y después del backfill de rutas.
- Revisar posibles ocupaciones duplicadas existentes antes de aplicar la restricción.
- Confirmar manualmente permisos por puesto.
- Auditar el flujo integrado Ruta → Lote → Equipo → Calidad → siguiente etapa con usuarios reales de operación.