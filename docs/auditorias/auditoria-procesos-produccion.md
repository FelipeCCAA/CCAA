Auditoría de Producción CCAA
No modifiqué código ni ejecuté pruebas. La revisión fue estática sobre modelos, servicios, permisos, rutas y pantallas actuales, aplicando la skill experto-procesos-lacteos.
1. Procesos que existen actualmente
Proceso	Implementación actual	Evaluación
Recepción de leche	Camión, muestreo, decisión de Calidad, descarga y movimiento a silo	Bien estructurado
Gestión de silos	Ingresos, salidas, trasvasijes, saldo y atribución FIFO por recepción	Sólido
Descremación	Leche entera → leche descremada + crema + merma	Existe como corrida especializada
Estandarización	Vale, cálculo RC, mezcla de silos, agitación, muestra y transferencia	Existe y se conecta al motor de procesos
Evaporación/condensación	Silo origen → evaporador → silo de precondensado	Corrida especializada y trazable
Secado	Precondensado → torre → producto en polvo a granel	Existe, pero usa el lote genérico
Mantequilla	Crema liberada → mantequilla + suero + merma	Corrida especializada
Envasado	Registro de envase, controles y creación de pallets	Separado visualmente de Producción
Calidad intermedia	Libera o rechaza resultados almacenados en silo	Implementado
Calidad final	Análisis, checklist, expediente, bloqueo y liberación	Implementado
Inventario	Consumo de insumos, cuarentena, existencias, pallets y despacho	Conectado parcialmente
Rework	Aprobado, bloqueado o destruido por Calidad	Implementado inicialmente
CIP/Aseo	Ciclos CIP y verificación de Calidad	Integrado como advertencia y bloqueo físico
Planificación	Órdenes, semanas, recursos y capacidades	Existe, pero su conexión operativa puede mejorar


Las principales estructuras son Proceso → EtapaProceso → EjecucionProceso → EntradaProceso/SalidaProceso, junto con OrdenProduccion y Lote. Véanse [procesos/models.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\models.py) y [produccion/models.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\produccion\\models.py).
2. Cómo se conectan
El flujo funcional actual es:
Recepción
→ movimiento y atribución FIFO en silo
→ vale de estandarización
→ ejecución de estandarización
→ lote/orden de producción
→ evaporación o proceso seleccionado
→ salida intermedia bloqueada
→ análisis y liberación de Calidad
→ continuación a siguiente etapa
→ secado o mantequilla
→ envasado
→ pallet en cuarentena
→ liberación final
→ ingreso a Bodega
Aspectos positivos:
- Los movimientos de silo guardan lote, producto, equipo, usuario y operación.
- La estandarización se representa también como una ejecución industrial.
- Una salida intermedia no puede continuar sin liberación de Calidad.
- La continuación valida que no se salten etapas.
- El equipo no puede operar durante un CIP activo.
- Los pallets quedan en cuarentena antes de Inventario.
- La trazabilidad puede buscarse por lote o código de pallet.
3. Procesos mezclados o mal separados
Crítico — Ruta maestra genérica incorrecta
La ruta sembrada inicialmente obliga a una secuencia universal:
Recepción → Estandarización → Descremación
→ Evaporación → Condensación → Secado → Envasado
Esto no corresponde a todos los productos. Descremación es una rama opcional, y evaporación/condensación representan prácticamente la misma familia de transformación, no necesariamente dos etapas consecutivas. Está definido en [0002_sembrar_flujo_lacteo.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\migrations\\0002_sembrar_flujo_lacteo.py).
Las rutas por producto permiten corregirlo, pero el sistema conserva caminos de respaldo que pueden usar el proceso genérico cuando falta configuración.
Alto — Producción y Procesos son dos centros operativos
Actualmente:
- /produccion maneja lotes, secado, controles, evaporadores y acceso a procesos.
- /procesos maneja descremación, evaporación, mantequilla, rework, rutas y genealogía.
El operador debe saber anticipadamente dónde está cada acción. Además, /procesos mezcla:
- operación de máquinas;
- configuración de rutas;
- historial;
- trazabilidad;
- rework;
- procesos de productos distintos.
Esto aumenta el riesgo de operar la corrida equivocada.
Alto — Secado no tiene corrida especializada
Evaporación, descremación y mantequilla tienen modelos de corrida propios. Secado solamente utiliza:
- lote genérico;
- ejecución genérica;
- controles horarios;
- declaración final de kilos.
Eso dificulta representar claramente:
- precondensado exacto consumido;
- torre;
- inicio y término;
- polvo a granel;
- rendimiento;
- finos/rework;
- pérdida de sólidos;
- detenciones.
Alto — Estandarización puede continuar sin trazabilidad industrial
Si no existe una etapa configurada, la transferencia física sigue y registrar_estandarizacion() devuelve None. Algo similar ocurre al abrir un lote si falta la etapa correspondiente a la máquina. La decisión evita detener la planta, pero deja operaciones reales fuera de la cadena formal de procesos. Véanse [procesos/servicios.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\servicios.py) y [produccion/servicios.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\produccion\\servicios.py).
Alto — Envasado está diseñado únicamente para sacos de 25 kg
La interfaz fija:
- formato de 25 kg;
- máximo 20 unidades;
- pallet máximo 500 kg;
- texto “sacos”.
Esto sirve para leche en polvo, pero no para mantequilla en cajas ni futuros formatos. También admite equipos tipo torre como equipos de envasado, lo que permite una selección operacional incorrecta. Véase [FormularioEnvase.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Produccion\\FormularioEnvase.tsx).
Alto — Calidad de mantequilla está ubicada antes del envasado
Al cerrar mantequilla, la corrida queda “pendiente de Calidad” y la interfaz dice que Calidad debe revisar antes de Envasado. Se están mezclando dos controles distintos:
1. aprobación del producto a granel para poder envasar;
2. liberación comercial del producto ya envasado.
Ambos son necesarios, pero deben aparecer como compuertas diferentes.
4. Vistas para operadores
Lo que está bien:
- Envasado ya posee módulo propio.
- Calidad tiene una bandeja transversal.
- Producción muestra estados, equipos, silos, cantidades y destino.
- Las listas están paginadas.
- Varias secciones pesadas se cargan solo cuando se abren.
- El formulario de inicio filtra equipos según familia.
- Los operadores reciben avisos sobre aseo y Calidad.
Problemas encontrados:
- La portada de Producción todavía muestra demasiadas responsabilidades juntas.
- Un operador de secado puede ver acciones de evaporación, mantequilla y descremación en “Procesos”.
- No existe una bandeja exclusiva del puesto: “pendiente para mi equipo”.
- Configuración de rutas aparece dentro de una pantalla operacional.
- El detalle del lote concentra controles, inocuidad, asignación, cierre, análisis y materiales.
- El operador debe seleccionar manualmente el análisis de silo correspondiente.
- Parte de las rutas mostradas en el frontend están codificadas por familia, en lugar de provenir completamente del maestro RutaProducto.
- Las tablas anchas de procesos no son ideales para uso rápido en planta.
La navegación evidencia la duplicidad con entradas separadas “Producción” y “Procesos” en [Navbar.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\components\\Navbar\\Navbar.tsx).
5. Automatizaciones posibles
Prioridad alta:
- Crear automáticamente una solicitud de muestra al cerrar cada salida que requiera Calidad.
- Vincular esa muestra con corrida, lote, silo y etapa; Calidad no debería buscarla manualmente.
- Preparar automáticamente la siguiente tarea después de una liberación.
- Mostrar únicamente equipos compatibles y disponibles para esa etapa.
- Calcular rendimiento de evaporación, secado, descremación y mantequilla.
- Alertar diferencias entre masa de entrada, producto, coproductos y merma.
- Consumir envases y pallets durante Envasado, no genéricamente al cerrar Producción.
- Generar una orden de corrección cuando falte stock, en vez de cerrar dejando solamente un evento pendiente.
- Derivar la interfaz y sus controles desde la ruta configurada del producto.
Prioridad media:
- Sugerir el silo FIFO apropiado.
- Sugerir cantidades según orden y saldo disponible.
- Mostrar el “siguiente paso” en cada lote.
- Generar alertas por espera excesiva entre evaporación, Calidad y secado.
- Notificar a Calidad y al siguiente puesto sin que el operador tenga que actualizar manualmente.
6. Trazabilidad, lotes, silos, equipos y Calidad
Trazabilidad
El motor de entradas y salidas es correcto. Sin embargo, la pantalla de genealogía presenta las recepciones como “candidatas” por haber estado previamente en el silo, aunque internamente existe atribución FIFO. La genealogía debería mostrar litros atribuidos por recepción, diferenciando claramente:
- atribución calculada FIFO;
- mezcla física;
- dato exacto;
- estimación.
Actualmente esa aclaración aparece en [procesos/views.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\views.py).
Lotes
Lote representa a la vez identidad del material, documento de producción y resultado final. Funciona para el flujo histórico, pero se vuelve ambiguo en procesos multietapa. La identidad del lote debe mantenerse, mientras cada transformación debe continuar siendo una EjecucionProceso independiente.
Silos
El libro de movimientos y los bloqueos transaccionales son una fortaleza. Falta hacer más visible:
- contenido/producto actual;
- lotes o recepciones que lo componen;
- cantidad reservada;
- calidad vigente;
- próxima operación;
- estado físico versus estado de Calidad.
Equipos
Existe control de ocupación y CIP, pero los permisos no están segmentados por proceso. EscribeProduccion permite a Condensación y Secado escribir sobre prácticamente todos los endpoints de procesos. Ocultar botones no evita que un usuario llame manualmente a otro endpoint. Véanse [permisos.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\usuarios\\permisos.py) y [procesos/views.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\views.py).
Calidad
La separación entre liberación intermedia y final es correcta. Las brechas son:
- la solicitud de muestra no es una entidad automática del flujo;
- selección manual del análisis;
- falta distinguir liberación de granel versus liberación comercial;
- rework no tiene suficientemente visible ubicación física segregada, vencimiento, etiqueta y saldo remanente;
- las salidas históricas sin producto explícito pueden evitar la validación contra especificación.
7. Mejoras priorizadas
Críticas
1. Sustituir la ruta universal por rutas reales por producto y bloquear el fallback ambiguo.
2. Crear permisos backend por etapa: descremación, evaporación, secado, mantequilla y envasado.
3. Evitar que una operación avance sin crear su ejecución trazable; permitir contingencia solamente con registro explícito.
4. Separar formatos de envasado por producto: saco 25 kg, caja de mantequilla y otros configurables.
Altas
5. Implementar una corrida especializada de Secado.
6. Separar Calidad de producto a granel y liberación final envasada.
7. Convertir /produccion en entrada por puesto y dejar /procesos para supervisión/trazabilidad.
8. Crear solicitudes automáticas de muestreo asociadas a cada salida.
9. Descontar materiales en la etapa real donde se consumen.
10. Mostrar atribución FIFO cuantificada en la genealogía.
Medias
11. Tablero por equipo con “Disponible / Preparando / Produciendo / Pendiente Calidad / CIP”.
12. Alertas de rendimiento, pérdida de sólidos y tiempos de espera.
13. Flujo guiado con una única acción principal por estado.
14. Mejorar la trazabilidad física y ubicación del rework.
15. Consolidar las lecturas iniciales de Envasado y Calidad en endpoints de bandeja específicos.
Conclusión: CCAA ya tiene una base industrial útil y bastante más avanzada que un CRUD común. La mayor deuda no está en Inventario ni en los movimientos de silo, sino en la coexistencia del lote genérico con corridas especializadas, la ruta universal incorrecta, los permisos demasiado amplios y la falta de una corrida formal de Secado. Conviene corregir primero esas cuatro áreas antes de seguir agregando nuevas pantallas.