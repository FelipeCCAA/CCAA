Primer bloque React terminado: rutas productivas obligatorias y errores operacionales claros.
Implementé:
- Diagnóstico bajo demanda de productos sin ruta activa en [DiagnosticoRutas.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Procesos\\DiagnosticoRutas.tsx).
- Contrato TypeScript para GET /api/procesos/rutas-producto/diagnostico/.
- Mensajes legibles para errores ruta_producto, equipo y etapa.
- Integración en apertura de lotes, continuación de procesos y ejecución de corridas.
- Sin llamadas GET adicionales al entrar: el diagnóstico solo se consulta al presionar el botón.
- No modifiqué Django ni implementé funciones pendientes del backend.
Archivos principales:
- [procesos.service.ts](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\services\\procesos.service.ts)
- [errores-proceso.ts](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\services\\errores-proceso.ts)
- [Procesos.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Procesos\\Procesos.tsx)
- [FormularioLote.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Produccion\\FormularioLote.tsx)
- [SalidasIntermedias.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Produccion\\SalidasIntermedias.tsx)
Verificación:
- 3 pruebas específicas aprobadas.
- ESLint aprobado únicamente sobre los archivos modificados.
- git diff --check sin errores.
- No ejecuté la suite completa.
Pendiente antes de probar en el sistema real: aplicar las migraciones backend Procesos 0014–0016 y Calidad 0006.
El siguiente bloque es manejar conflictos de equipos ocupados: mostrar el conflicto y actualizar solamente la disponibilidad afectada. Después seguirían Calidad de mantequilla y el puesto independiente de Secado.

Segundo bloque terminado. No modifiqué Django ni avancé a Calidad o Secado.
Cambios principales:
- Estados visuales:
  - preparacion → Reservado.
  - ejecucion, pausada, bloqueada → Ocupado.
  - pendiente_control y demás → Disponible.
- Los selectores deshabilitan equipos reservados u ocupados e indican la ejecución responsable.
- Los errores equipo muestran el mensaje completo entregado por Django.
- Los botones quedan bloqueados mientras existe un POST pendiente, junto con una protección adicional dentro del handler.
- No existen reintentos automáticos de POST/PATCH.
- Un fallo del GET posterior ya no hace creer que el POST falló.
Archivos principales:
- [EstadoEquipo.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\components\\EstadoEquipo\\EstadoEquipo.tsx)
- [disponibilidad-equipos.ts](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\services\\disponibilidad-equipos.ts)
- [errores-proceso.ts](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\services\\errores-proceso.ts)
- [Procesos.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Procesos\\Procesos.tsx)
- [EvaporadoresProduccion.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Produccion\\EvaporadoresProduccion.tsx)
- [FormularioLote.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Produccion\\FormularioLote.tsx)
- [SalidasIntermedias.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Produccion\\SalidasIntermedias.tsx)
- Formularios de descremación, condensación y mantequilla.
Refrescos después de operar:
- Ejecuciones: solo GET /api/procesos/ejecuciones/operativas/.
- Evaporadores: solo condensaciones y ejecuciones operativas.
- Continuación intermedia: solo salidas disponibles y ejecuciones operativas.
- No se recargan Producción completa, Calidad, rutas ni el listado general de lotes.
Verificación:
- 7 pruebas específicas aprobadas.
- ESLint aprobado en los archivos modificados.
- TypeScript aprobado.
- git diff --check aprobado; solo advertencias normales LF/CRLF.
Incompatibilidades backend encontradas:
- Algunos endpoints de opciones consideran ocupado únicamente ejecucion, omitiendo preparacion, pausada y bloqueada.
- La bandeja de mantequilla no entrega disponibilidad.
- ejecuciones/operativas/ entrega el nombre del equipo, pero no su ID; React debe relacionarlo temporalmente por nombre.
- avance-frontend-produccion.md está vacío.
Para mantener la exactitud, React utiliza las ejecuciones operativas reales como fuente de verdad, sin inventar un estado adicional.




## bloque 3 - calidad de mantequilla
Bloque 3 terminado. No modifiqué Django ni avancé a Secado.
Cambios principales
- Disponibilidad ahora relaciona equipos exclusivamente mediante equipo_id.
- equipo_nombre quedó solo para visualización.
- Nueva sección “Mantequilla a granel pendiente” en Calidad.
- Separación real entre:
  - análisis de silo;
  - análisis de lote.
- Rangos de especificación junto a los resultados medidos.
- Estados textuales: Pendiente de Calidad, Liberada y Rechazada.
- Protección contra doble envío y sin reintentos automáticos.
Contratos utilizados
Liberación de mantequilla:
{
  "analisis_lote_id": 123,
  "observacion": "Resultado conforme"
}
Liberación de material en silo conserva:
{
  "analisis_id": 45,
  "observacion": "Conforme"
}
Rechazo:
{
  "motivo": "Humedad fuera de especificación"
}
El botón de mantequilla dice explícitamente Liberar para Envasado. El rechazo solicita el motivo dentro de la tarjeta.
Envasado
Cuando Django devuelve que la mantequilla sigue pendiente:
- se muestra Esperando aprobación de Calidad;
- se conserva el mensaje operacional completo;
- se oculta el formulario para ese lote;
- no se reintenta el POST.
Limitación backend detectada: el listado de lotes de Envasado no expone anticipadamente la liberación intermedia. Por eso React puede mostrar el bloqueo después de la validación del POST, pero no conocerlo preventivamente sin un campo o endpoint backend adicional.
También detecté que Calidad devuelve para ciertas mantequillas el código/nombre de la ejecución como lote_codigo/producto_nombre, en lugar de los datos directos de salida.lote. No modifiqué Django por restricción del alcance.
Refrescos
- Liberar/rechazar: solamente GET /api/calidad/expedientes/?incluir_procesos=1.
- Envasado bloqueado: actualización local, sin GET adicional.
- Los POST invalidan la caché; Envasado obtendrá información fresca al volver a cargar.
- Sin polling y sin recargar Producción completa.
Archivos principales
- [CentroCalidad.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Calidad\\CentroCalidad.tsx)
- [ResultadoProcesoCalidadCard.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Calidad\\ResultadoProcesoCalidadCard.tsx)
- [calidad.service.ts](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\services\\calidad.service.ts)
- [calidad-proceso.ts](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\services\\calidad-proceso.ts)
- [Envasado.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Envasado\\Envasado.tsx)
- [FormularioEnvase.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Produccion\\FormularioEnvase.tsx)
- [disponibilidad-equipos.ts](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\services\\disponibilidad-equipos.ts)
- [procesos.service.ts](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\services\\procesos.service.ts)
Además se actualizaron los cinco consumidores de disponibilidad para buscar por ID.
Verificación
- 6 pruebas específicas: aprobadas.
- TypeScript: aprobado.
- ESLint sobre archivos modificados: aprobado.
- git diff --check: aprobado.
- No se ejecutó la suite completa.

Edited 15 files+469-135Review changesUndoReview

frontend/src/pages/Calidad/CentroCalidad.tsxfrontend/src/pages/Calidad/CentroCalidad.tsx+105-89
frontend/src/pages/Calidad/ResultadoProcesoCalidadCard.tsxfrontend/src/pages/Calidad/ResultadoProcesoCalidadCard.tsx+218-0
frontend/src/pages/Envasado/Envasado.tsxfrontend/src/pages/Envasado/Envasado.tsx+8-2
Show 12 more files

