uditoría terminada sin modificar código. La integración está bien encaminada, pero todavía no está lista para una prueba productiva completa: hay cuatro migraciones sin aplicar y tres contradicciones relevantes entre rutas, Calidad y estados físicos.
1. Migraciones pendientes en la base real
Problema
El código utiliza funcionalidades cuya estructura todavía no existe en la base local real.
Backend actual
showmigrations confirmó pendientes:
- calidad.0006_analisis_lote_liberacion_proceso
- procesos.0014_completar_rutas_productivas
- procesos.0015_impedir_doble_ocupacion_equipo
- procesos.0016_corrida_secado
Frontend actual
React ya muestra mantequilla con análisis de lote, disponibilidad concurrente y Secado independiente. Esas pantallas pueden fallar o quedar incompletas contra esta base.
Riesgo
Errores 500, ausencia de corridas de Secado y falta de protección física contra doble ocupación.
Solución recomendada
Aplicar las migraciones en un entorno controlado, respaldar antes y validar los datos migrados.
Debe cambiar
Ninguno: es una acción de despliegue/base de datos.
Prioridad
CRÍTICO.
2. La etapa inicial de una ruta puede saltarse procesos
Problema
Al abrir un lote, Django busca una etapa del tipo correspondiente al equipo, pero no exige que sea la primera etapa activa de la ruta.
Backend actual
exigir_etapa_para_producto() acepta cualquier etapa activa del tipo solicitado. Un cliente manual podría seleccionar una torre e iniciar Secado aunque la ruta indique Evaporación antes.
La continuación entre etapas sí está correctamente protegida y no permite saltos.
Frontend actual
[FormularioLote.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Produccion\\FormularioLote.tsx) evita parte del problema mediante reglas fijas por familia, por ejemplo polvo → evaporador. React está compensando una validación que debería pertenecer a Django.
Riesgo
Saltar una etapa obligatoria y generar una genealogía formalmente válida, pero operacionalmente incorrecta.
Solución recomendada
Django debe determinar y validar las etapas iniciales permitidas por la ruta. El endpoint de opciones debe entregar esas etapas y sus equipos compatibles. React solamente debe representarlas, eliminando el mapa fijo por familia.
Debe cambiar
Ambos.
Prioridad
CRÍTICO.
3. Secado no entrega la identidad del equipo
Problema
El serializer de Secado tiene equipo_nombre, pero no equipo_id.
Backend actual
[CorridaSecadoSerializer](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\serializers.py) omite el ID aunque la relación ya está cargada y no produciría consultas adicionales.
Frontend actual
[secado.service.ts](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\services\\secado.service.ts) no puede declarar equipo_id. React no relaciona por nombre —eso está bien—, pero tampoco puede integrar la corrida con la disponibilidad técnica del equipo.
Riesgo
No se puede cruzar de manera segura una corrida de Secado con la torre correspondiente.
Solución recomendada
Agregar aditivamente equipo_id, conservando equipo_nombre para mostrar texto.
Debe cambiar
Ambos.
Prioridad
ALTO.
4. Secado no entrega la hora de inicio
Problema
La ejecución tiene inicio, pero el contrato de Secado no lo expone.
Backend actual
El dato existe en EjecucionProceso.inicio.
Frontend actual
La tarjeta muestra literalmente “Inicio no expuesto por API”.
Riesgo
Limitación operacional: el secador y el supervisor no pueden saber desde su pantalla cuándo comenzó la corrida.
Solución recomendada
Agregar iniciada_en desde ejecucion.inicio y mantener finalizada_en. No duplicar el dato en CorridaSecado.
Debe cambiar
Ambos.
Prioridad
MEDIO.
5. Cierre de Secado contradice la configuración de Calidad
Problema
Las rutas sembradas marcan Secado con requiere_calidad=True, pero el servicio de cierre ignora esa configuración.
Backend actual
[cerrar_secado()](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\servicios.py):
- registra balance y salida;
- deja el lote producido;
- pone la orden en pendiente_calidad;
- cierra la ejecución;
- no crea LiberacionProceso.
Además, la salida queda destinada directamente a Envasado.
Frontend actual
React coloca en “Esperando Calidad” solamente corridas con pendiente_control. Como Django siempre devuelve cerrada, esa bandeja queda vacía.
Riesgo
La configuración declara un control obligatorio que el servicio no ejecuta. También se mezclan tres significados: operación cerrada, material pendiente y Calidad pendiente.
Solución recomendada
Hacer que el cierre respete EtapaProceso.requiere_calidad:
- Si requiere Calidad: crear LiberacionProceso y dejar la continuidad bloqueada hasta la decisión.
- Si no requiere Calidad: cerrar normalmente.
- Exponer separadamente estado_proceso, requiere_calidad y estado_calidad.
- Confirmar mediante configuración si la planta exige liberación antes de Envasado; no hardcodearlo por producto.
Debe cambiar
Ambos.
Prioridad
CRÍTICO.
6. Envasado descubre tarde el bloqueo de mantequilla
Problema
Envasado no sabe preventivamente si la mantequilla está liberada.
Backend actual
[registrar_envasado()](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\produccion\\servicios.py) bloquea correctamente el POST si falta liberación. Sin embargo, el listado de lotes no informa la elegibilidad.
Frontend actual
[Envasado.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Envasado\\Envasado.tsx) muestra el lote como disponible y aprende el bloqueo únicamente después de intentar crear el pallet.
Riesgo
El operador completa un formulario que nunca podrá guardar.
Solución recomendada
Crear un contrato de opciones/bandeja de Envasado que entregue:
- envasado_habilitado;
- motivo_bloqueo;
- estado de Calidad intermedia;
- lote, producto y formato aplicable.
Mantener igualmente la validación en el POST.
Debe cambiar
Ambos.
Prioridad
ALTO.
7. Calidad muestra lote y producto incorrectos para mantequilla
Problema
Cuando la salida no es condensación ni descremación, el backend utiliza la etapa y la ejecución como sustitutos del producto y lote reales.
Backend actual
En [_resultados_intermedios()](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\calidad\\views.py), la mantequilla termina mostrando normalmente:
- producto_nombre: nombre de la etapa;
- lote_codigo: código de ejecución.
Aunque SalidaProceso.lote contiene el lote y producto correctos.
Frontend actual
React representa fielmente esos campos, por lo que no es quien genera el error.
Además, clasifica toda salida con analisis_tipo === "lote" como mantequilla. Eso funciona hoy solo porque el filtro backend devuelve mantequilla como única salida no asociada a silo.
Riesgo
Calidad puede analizar o identificar visualmente el material equivocado. Al incorporar Secado con análisis de lote, React lo confundiría con mantequilla.
Solución recomendada
El contrato debe incluir:
- salida_id;
- lote_id y lote_codigo reales;
- producto_id y producto_nombre reales;
- etapa_tipo como código estable;
- analisis_tipo exclusivamente para decidir silo versus lote.
React debe identificar mantequilla mediante etapa_tipo === "mantequilla".
Debe cambiar
Ambos.
Prioridad
ALTO.
8. Un rechazo de Calidad vuelve a ocupar físicamente el equipo
Problema
Se está utilizando EjecucionProceso.bloqueada tanto para un bloqueo físico de operación como para un rechazo del material.
Backend actual
[rechazar_resultado_proceso()](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\calidad\\views.py) cambia toda ejecución rechazada a bloqueada.
La regla central considera bloqueada como equipo físicamente ocupado.
Frontend actual
React aplica correctamente esa regla y mostrará la máquina ocupada, aunque la corrida ya terminó y el rechazo pertenezca al material.
Riesgo
Una mantequera, evaporador o torre puede quedar artificialmente ocupada por un rechazo posterior de Calidad.
Solución recomendada
Separar responsabilidades:
- LiberacionProceso.rechazado: estado de Calidad/material.
- Silo.BLOQUEADO_CALIDAD: retención física en silo.
- EjecucionProceso.bloqueada: solamente cuando la operación/equipo permanece físicamente bloqueada.
Un rechazo posterior al cierre no debería ocupar automáticamente la máquina.
Debe cambiar
Backend.
Prioridad
ALTO.
9. La caché puede impedir un refresco real después de un conflicto
Problema
React dice refrescar la disponibilidad afectada, pero la caché global puede devolver la lectura anterior durante diez segundos.
Backend actual
Entrega correctamente la fuente de verdad.
Frontend actual
[api.ts](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\services\\api.ts) guarda todos los GET durante diez segundos. Un POST fallido por conflicto no limpia la caché; el GET posterior de ejecuciones operativas puede reutilizar datos antiguos.
Riesgo
Después de recibir “equipo ocupado por EJ-X”, la interfaz puede seguir mostrando el equipo disponible.
Solución recomendada
Excluir de caché o invalidar explícitamente consultas volátiles:
- ejecuciones operativas;
- opciones de equipos;
- corridas activas;
- bandejas de Calidad.
Conservar caché para catálogos estables.
Debe cambiar
Frontend.
Prioridad
ALTO.
10. Calidad refresca más información de la necesaria
Problema
Después de liberar o rechazar una salida, React recarga expedientes completos y resultados intermedios juntos.
Backend actual
Los resultados de proceso solo pueden solicitarse dentro de calidad/expedientes/?incluir_procesos=1.
Frontend actual
expedientes.recargar() vuelve a evaluar la primera página de lotes, checklists y resultados aunque cambió una sola salida.
Riesgo
Consultas innecesarias y mayor tiempo de respuesta a medida que crezca el histórico.
Solución recomendada
Exponer un GET específico para la bandeja de resultados de proceso o retornar la representación actualizada en liberar/rechazar. React debe actualizar esa salida o recargar únicamente dicha bandeja.
Debe cambiar
Ambos.
Prioridad
MEDIO.
11. La idempotencia de Envasado no está completada
Problema
Django soporta operacion_id, pero React no lo envía.
Backend actual
Puede devolver un registro existente si recibe la misma operación nuevamente.
Frontend actual
Bloquea doble clic correctamente, pero una pérdida de respuesta seguida de reenvío puede crear un segundo pallet.
Riesgo
Duplicación física y contable de pallets.
Solución recomendada
Generar un UUID estable al abrir el formulario, enviarlo como operacion_id y reutilizarlo hasta recibir una respuesta concluyente.
Debe cambiar
Frontend; posteriormente conviene que Backend lo haga obligatorio para nuevas operaciones.
Prioridad
ALTO.
12. Los permisos industriales configurables no gobiernan las acciones
Problema
Existen capacidades como secado_proceso_cerrar, pero las operaciones se autorizan solo por área.
Backend actual
OperaProcesoPorEtapa protege correctamente Condensación versus Secado, pero no consulta los permisos industriales individuales.
Frontend actual
También decide por área y administración. Quitar la capacidad a un operador no cambia sus botones ni el permiso real.
Riesgo
La administración puede creer que revocó una acción cuando en realidad el usuario todavía puede ejecutarla.
Solución recomendada
Definir una sola política:
- mantener autorización exclusivamente por área y dejar de presentar esas capacidades como efectivas; o
- hacer que backend y frontend consulten las capacidades correspondientes.
La seguridad definitiva debe seguir en Django.
Debe cambiar
Ambos.
Prioridad
ALTO.
Contratos que ya están correctos
- Existen exactamente los endpoints de Secado solicitados: listado, detalle y cierre.
- La corrida de Secado nace automáticamente al abrir el lote en una torre.
- El cierre de Secado es transaccional, bloquea corrida, ejecución y lote, y revierte un balance imposible.
- ejecuciones/operativas/ entrega equipo_id y equipo_nombre.
- Preparación, ejecución, pausa y bloqueo ocupan; pendiente_control no ocupa.
- Los paneles generales relacionan equipos mediante ID.
- La continuación de una salida exige la siguiente etapa del mismo proceso y una liberación previa.
- Los errores ruta_producto llegan estructurados y React conserva su mensaje operacional.
- Mantequilla crea salida a granel, liberación intermedia pendiente y análisis de lote.
- Liberar mantequilla usa analisis_lote_id; no solicita silo.
- Envasado vuelve a validar la liberación en backend.
- Análisis de silo y análisis de lote están separados en el contrato.
- React bloquea doble submit y no reintenta automáticamente los POST.
- Secado se carga únicamente al entrar en su módulo, sin polling continuo.
Contratos que deben corregirse
- Entrada inicial de ruta y etapa inicial permitida.
- equipo_id e inicio en Secado.
- Estado de Calidad de Secado separado del estado productivo.
- Identidad real de lote/producto en resultados de Calidad.
- Elegibilidad preventiva para Envasado.
- Rechazo de Calidad sin ocupar automáticamente la máquina.
- Invalidación de caché en datos operativos.
- Refresco específico de la bandeja afectada.
- Idempotencia enviada desde React.
- Política efectiva de permisos industriales.
Orden recomendado de correcciones
1. Aplicar las cuatro migraciones pendientes.
2. Impedir saltos en la etapa inicial de las rutas.
3. Resolver la contradicción requiere_calidad de Secado.
4. Completar el serializer de Secado.
5. Corregir identidad y clasificación de resultados de Calidad.
6. Exponer elegibilidad de Envasado.
7. Separar rechazo de material de bloqueo físico.
8. Corregir caché y refrescos dirigidos.
9. Completar idempotencia de Envasado.
10. Unificar permisos por capacidades o por área.
Qué NO conviene tocar
- No reemplazar EjecucionProceso ni las corridas especializadas.
- No crear un estado universal para proceso, equipo, material y Calidad.
- No unir análisis de silo y análisis de lote.
- No mover la autoridad de rutas, equipos o liberaciones a React.
- No eliminar equipo_nombre; debe mantenerse junto a equipo_id.
- No crear manualmente corridas de Secado.
- No rehacer Producción como un panel universal.
- No modificar la regla física de ocupación ya acordada; debe corregirse quién asigna bloqueada.
Estado general de integración
La estructura base es buena: rutas, ejecución común, corridas especializadas, Calidad y frontend por puestos están correctamente separadas. La disponibilidad de equipos y Mantequilla tienen defensas backend reales.
El estado actual es funcional en desarrollo, pero todavía no seguro para validar el flujo completo en la base real. Los bloqueadores principales son las migraciones pendientes, la posibilidad de saltar la primera etapa de una ruta y la contradicción de Calidad en Secado.
No ejecuté pruebas ni modifiqué archivos durante esta auditoría. Sí comprobé directamente el estado de migraciones contra la base local.


2:49 PM