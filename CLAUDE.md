# CLAUDE.md — CCAA (Gestión Productiva Planta)

Contexto para Claude Code. Lee estos documentos antes de proponer cambios:

- **`DECISIONES.md`** — decisiones de plataforma e infraestructura (PostgreSQL, bloqueo de la firma). Léelo: hay garantías que dependen del motor.
- **`prototipo/MODELO_DATOS.md`** — modelo funcional y decisiones de modelado (veredicto no persistido, especificaciones versionadas, recetas multinivel, checklist por plantilla). Es la referencia de diseño; respétala.
- **`docs/REGLAS_DE_PLANTA.md`** — umbrales, decisiones y fórmulas reales de la fábrica, extraídos de `Flujo Fabrica.md` y **contrastados contra el código**: cada regla dice si está implementada. Ahí está la fórmula RC, la cadena de escalamiento de antibióticos y la discrepancia de crioscopía (el documento dice −0,512 y el código usa −0,510). Léelo antes de tocar recepción, descremación o estandarización.
- **`docs/levantamiento-2026-07/LEVANTAMIENTO_PLANTA.md`** — levantamiento de los procesos reales de planta (HACCP/FSSC) y el **delta de modelo** a integrar (10 modelos nuevos, reglas, plan por archivo, mapeo a apps). **Empieza por aquí para la fase de integración.**
- **`docs/levantamiento-2026-07/SKU_PRODUCTOS.md`** — estructura del **SKU de producto** (12 dígitos, 6 segmentos) y el generador/validador para `maestros`. Distinto del código de lote de `produccion`: el SKU identifica un producto (maestro, estable) y el código de lote una corrida (transaccional). Lee también las salvedades de §4 y la nota de este archivo más abajo.
- **`docs/levantamiento-2026-07/BORRADOR_P0.md`** — código de arranque P0 (código de lote, ControlProceso/MonitoreoPPRO, siembra del Dossier). Ya aplicado; queda como referencia de lo que se pidió.

## Arquitectura

- **Backend:** Django REST + **PostgreSQL**. Apps: `maestros`, `recepcion`, `produccion`, `calidad`, `inocuidad`, `planificacion`, `auditoria`, `usuarios`. Cada app separa:
  - `models.py` — esquema (usa **JSONField** para formularios dinámicos: `plantilla`, `valores`, `rangos`, `controles`).
  - `dominio.py` — reglas puras y testeables (sin ORM/DOM). Toda regla nueva se cubre en `tests_dominio.py`.
  - `views.py` — API; el camino de la **firma de liberación** usa `select_for_update` (no romper, ver `DECISIONES.md` §001).
  - `serializers.py`, `urls.py`, `admin.py`.
- **Frontend:** `frontend/src` (TypeScript): `pages/`, `components/`, `services/` (uno por módulo), `layouts/`.
- **`prototipo/`** — versión HTML/JS previa, archivada. Referencia histórica del modelo; no es el código vivo.

## Decisiones vigentes

- **PostgreSQL** es el motor (no SQLite en producción): protege el bloqueo de fila en la firma. Detalle en `DECISIONES.md` §001.
- Formularios dinámicos en **JSONField**; catálogos simples como `TextChoices`/`CHECK`; detalle repetitivo (lecturas horarias, etapas, muestras) como **modelo hijo con FK**.
- El veredicto de calidad y el avance del checklist **no se persisten**: se recalculan.
- Las decisiones (`puede_liberar` / `puede_despachar`) devuelven motivos de bloqueo, no un booleano.
- Español en UI, datos y comentarios. Fechas ISO `YYYY-MM-DD`. `codigo_lote` como string.
- El diseño manda: extender el modelo, no reescribirlo.
- **Dónde va cada registro:** `produccion` guarda **cómo se produjo** (lote, análisis, control de proceso — el PCC 1 vive ahí como un límite dentro del control). `inocuidad` guarda lo que **solo existe para vigilar un peligro**: PPRO, PCC de detector de metales, y más adelante limpieza CIP/COP, no conformidades y calibraciones. Mover modelos entre apps después obliga a renombrar tablas a mano, así que la separación se decidió con dos modelos y no con seis.
- **Código de lote** (vigente desde 2026-07-31): `CCAA` + último dígito del año + día juliano (3) + **SKU del producto** + `-` + correlativo del día (2) — p. ej. `CCAA6212010102010201-01`. El correlativo va **siempre**, desde `-01`: dos formas conviviendo obligan a conocer la excepción al leer, ordenar y buscar. Reemplaza al esquema del POE.009.02, donde el sufijo codificaba la torre (E1→1, E2→2) y el uso nacional (`N`); eso ahora vive dentro del SKU, que es donde se mantiene una sola vez.
- `codigo_lote_valido` **avisa, no restringe**: el histórico de planta trae códigos que no siguen el patrón —empezando por todos los del POE anterior— y hay que poder registrarlos. No conectarlo al `clean()` de `Lote`.
- **`Producto.codigo` guarda el SKU** y es parte del código de lote. Un producto sin él no frena nada: `codigo-sugerido/` devuelve `codigo: null` con un motivo que dice qué falta y dónde, y el operador escribe el código a mano. Se carga desde el admin, y conviene componerlo con `generar_sku` en vez de teclearlo.
- **SKU de producto** (`maestros/dominio.py` + `catalogos_sku.py`): 12 dígitos en 6 segmentos, compuestos **solo desde catálogos**. Un valor fuera de catálogo falla en vez de improvisar — un SKU con un segmento inventado se ve igual de válido que uno correcto y termina impreso en un saco. El orden de los segmentos se dedujo de los datos, no de los encabezados de la planilla, que están desalineados; `tests_dominio_sku.py` recompone los 24 productos reales del archivo y es lo que fija ese orden. `sku_valido` comprueba además la regla naturaleza↔cliente, para que el validador no apruebe lo que el generador se niega a componer.
- **Auditoría** (`auditoria`): se captura por señales, no desde las vistas, para cubrir todo lo que escribe en la base —API, admin, scripts, shell— y no solo los caminos instrumentados. Los dos lados del diff se leen **de la base** en `pre_save`/`post_save`: comparar la base contra el objeto en memoria marca como cambiados campos que solo cambiaron de tipo. Todos los cambios tienen la **misma forma** `{campo: [antes, después]}`, también las altas —con `None` delante—: dos formas obligan a cada consumidor a distinguirlas y el que no lo haga revienta. Es **de solo lectura en las tres capas** (viewset, admin y servicio del frontend): un registro que se puede editar no prueba nada.
- **Máquinas** (`maestros.Equipo`): `consume_leche` es una **regla del balance**, no una etiqueta. Un mismo código de producción se programa en el evaporador y en la línea que lo recibe; si ambos restaran, la semana contaría la misma leche dos veces. Solo los evaporadores.
- **Un código de cliente, un mandante** (desde 2026-08-03, restricción `mandante_unico_por_codigo_cliente`). El segmento de cliente del SKU no tiene forma de distinguir dos mandantes que lo compartan: sus productos salen con SKU idénticos y —como el código de lote lleva el SKU dentro— también con el mismo código de lote. La base llegó a tener «Nestle» y «Nestlé» a la vez y los productos de ese cliente quedaron repartidos entre las dos fichas, sin que nada avisara porque nada lo impedía; la migración `0022` los fusionó. Los mandantes **sin** código sí pueden ser varios: uno sin código es uno que todavía no genera SKU.
- **Una sola representación de «equipo»** (desde 2026-08-03). `maestros.Equipo` es la única: `ControlProceso`, `MonitoreoPPRO`, `CicloCIP`, `BloquePlan` y `RegistroEquipo` lo referencian por clave foránea. Antes había cinco vocabularios para las mismas máquinas —un `TextChoices` en `produccion` («VEB», «SCH2»), el maestro («veb», «scheffers2»), y texto libre en los monitoreos y en el CIP—, y con dos alfabetos un criterio del checklist no se podía comparar contra el registro sin traducir en el medio. `linea1`/`linea2` **eran** las torres Egron: se renombraron a `e1`/`e2`, no se duplicaron. Se agregaron `rovema3` y `rovema4`.
- Los **criterios de evidencia comparan el `codigo` del equipo**, no su nombre ni el objeto. El nombre se edita desde Maestros, y un criterio escrito contra «Torre de secado Egron 1» dejaría de cumplirse el día que alguien le corrija una tilde — en silencio, hasta que un lote no se pudiera liberar. `calidad.dominio._valor_comparable` lo resuelve, y `tests_evidencia` lo fija con un doble cuyo nombre difiere del código.
- **Una sola planta, y no se nota** (desde 2026-08-10). CCAA no tiene sucursales. El modelo conserva la dimensión —quitarla costaría migrar quince modelos con datos encima, y volvería a costar lo mismo el día que haya una segunda— pero **nadie tiene que verla**: `usuarios.tenancy.unica_sucursal_activa` la resuelve sola cuando hay exactamente una activa, y esa resolución la usan tanto `sucursal_para_escritura` como el alta de personal. **Con dos activas vuelve a pedirse**, y esa mitad importa igual: resolver lo que solo tiene una respuesta es servicial, elegir entre dos es escribir en la planta equivocada sin que nadie lo pida. Una planta desactivada no cuenta.
- Los **perfiles de Administración general son de alcance empresa** (`area = administracion` **y** `nivel = admin`, que es lo que `PerfilUsuario.clean()` ya exigía). Es quien responde por toda la empresa; atarla a una planta —como hizo `usuarios.0008` con todo lo existente— le negaba lo que su propio nivel dice que abarca. `usuarios.0011` sube a los que ya estaban. El alta los crea así sola, y **escribe `sucursal = None` explícitamente**: el campo tiene valor por omisión —la sucursal sembrada en pruebas, y una excepción fuera de ellas—, así que no mandarlo no es lo mismo que mandar nada.
- Los **catálogos de opciones** se sirven desde el backend (`/api/maestros/catalogos/`, `/api/planificacion/catalogos/`) y no se escriben en el frontend: una copia ofrece tarde o temprano un valor que el backend rechaza.
- **Una sola receta** (desde 2026-08-03). `maestros.Receta` es el único lugar donde se declara qué lleva un producto. Un `RecetaComponente` es **un producto o un insumo, nunca los dos**: el producto se transforma aquí y la explosión sigue por su receta; el insumo se compra y lo descuenta bodega. Antes había un segundo maestro, `inventario.ConsumoProducto`, plano y sin versión, y era **ese** el que el descuento de bodega consumía — así que un lote de mayo se descontaba con las cantidades de hoy, que es justo lo que `Receta` está versionada para impedir. Los tres caminos que calculan consumo —el descuento del lote, el MRP semanal y el MRP puntual— pasan por `inventario.servicios.insumos_requeridos`; con tres implementaciones, la orden de compra y el descuento podían pedir cantidades distintas para la misma fórmula.
- Las **especificaciones las escribe Calidad**, no Administración (desde 2026-08-06, `EscribeCalidad` en `EspecificacionViewSet`). Misma corrección que el checklist y las recetas: los rangos deciden qué producto sale conforme, y que Administración pudiera moverlos le dejaría cambiar el veredicto de un lote sin medirlo de nuevo. Se editan en **Maestros › Especificaciones**, con una fila por parámetro del catálogo y **no** un textarea de JSON: así no hay forma de escribir una clave que `clean()` rechaza. **Qué versión está vigente lo responde el backend** (`es_vigente`), con la misma función que audita el lote y calculada sobre *todas* las versiones, no sobre la página — con un producto a caballo entre dos páginas, la vieja saldría marcada como vigente.
- La **fórmula la escribe Calidad**, no Bodega. El formulario que había en `/abastecimiento` dejaba que quien descuenta el material redefiniera cuánto material lleva. Se edita en el admin (`Maestros › Recetas`), igual que las especificaciones.
- Una explosión **incompleta no descuenta nada**: si la cadena se corta —un intermedio sin receta, un ciclo— `consumir_receta_produccion` falla en vez de descontar un requerimiento a medias, que se parece demasiado a uno completo y dejaría el saldo de bodega mintiendo. El MRP puntual devuelve `receta_completa` por la misma razón.
- **Declarar el lote producido descuenta su material de bodega** (desde 2026-08-03), y es el único momento en que ocurre: antes hay lote pero no kilos. **No bloquea** — mismo criterio que la leche asignada: detener la producción del día porque bodega no cargó la receta o el material sigue en cuarentena traslada a la línea un problema que no es suyo. Lo que falla queda **pendiente y visible** (`consumo_inventario.pendiente` en la ficha), porque un descuento fallido que no se ve deja el saldo alto sin que nadie lo sepa.
- Atrapar el error del consumo **es seguro solo porque `consumir_receta_produccion` es `@transaction.atomic`**: el servicio alcanza a crear la cabecera y a sacar lo que sí había antes de detectar que falta, y sin esa reversión el lote quedaría con un consumo «registrado» que descontó una fracción. Quitar ese decorador rompe `test_sin_stock_el_lote_igual_se_declara_y_avisa` —verificado por mutación—, no la vista.

- **Estandarización** (`estandarizacion`, desde 2026-08-06): el RC —grasa ÷ SNG— es el cálculo que decide qué producto sale. La matemática vive en `dominio.py` sin ORM, y `ValeEstandarizacion` es el documento con su ciclo. Tres reglas justifican que cada paso sea una acción del servicio y no un `PATCH estado=…`: **muestrear antes de 30 minutos avisa pero no frena** (desde 2026-08-17: antes la mezcla no es homogénea, pero detener la operación lo decide la planta; el vale sella `muestreado_en` y el aviso queda auditable — la hora la pone el servidor), **liberar no se pide sino que se calcula** desde el RC medido, y **corregir reinicia el reloj y borra el análisis** porque agregar leche deshace la mezcla. La composición de las dos leches se congela **en el vale** —el silo cambia con cada ingreso—, y `rc_real` se deriva. `calcular/` responde sin crear: es el paso que el operador repite variando el volumen. Detalle en `docs/REGLAS_DE_PLANTA.md` §3.

## Trampas conocidas

- El catálogo de `DocumentoLiberacion` se siembra por **migración de datos**, así que también aparece en la base de **pruebas**. Cualquier prueba que arme su propio checklist debe limpiarlo primero (`DocumentoLiberacion.objects.all().delete()` en `setUp`), o medirá el avance contra documentos que no creó.
- El camino de la firma usa `select_for_update`; en SQLite eso **no hace nada** y la garantía desaparece en silencio. De ahí el check `calidad.E001`.
- `frontend/tsconfig.json` es de tipo **solución** (`files: []` + referencias), así que `npx tsc --noEmit` a secas **no comprueba nada** y sale con 0. Usa `npx tsc -b` (es lo que corre `npm run build`).
- El runner de pruebas **migra la base de pruebas solo**, así que una migración generada y no aplicada deja la suite entera en verde y revienta en el navegador con un `IntegrityError`. Después de `makemigrations`, correr `migrate`.
- Las **migraciones de datos siembran también la base de pruebas** (documentos de liberación, equipos). Un `create()` en `setUp` choca con la unicidad: usar `update_or_create`.
- En una pantalla que carga varias fuentes con `Promise.all`, **un endpoint caído las vacía todas**. Los datos auxiliares —catálogos de desplegables— van aparte y degradan solos.
- **No reescribas archivos con acentos usando `Get-Content | … | Set-Content`**: PowerShell 5.1 lee en ANSI y escribe en UTF-8, así que un reemplazo masivo convierte cada `ó` en `Ã³` en todo el archivo. Usa Edit, o restaura con `git checkout --` y reaplica a mano.
- Un **`default` de campo que lanza una excepción rompe la página «Añadir» del admin**, no solo el guardado: Django pide el `default` de cada campo al construir el modelo vacío del formulario. Los defaults de tenant (`empresa_predeterminada_pruebas`, `sucursal_predeterminada_pruebas`, en dos docenas de campos) lanzaban `ImproperlyConfigured` fuera de pruebas y dejaban **22 de 72 modelos** con «Añadir» en error 500. Ahora devuelven `None` fuera de pruebas: no se inventa tenant y el campo obligatorio lo exige el formulario. `usuarios.tests_admin_alta` recorre el registro entero del admin —no una lista de 22— y corre con `@override_settings(DJANGO_ENV="development")`, porque **bajo `test` el defecto no existe** y la prueba pasaría sin comprobar nada.
- Dentro de `transaction.atomic()`, **salir con `return` confirma la transacción**: solo una excepción revierte. Un `return Response(...)` de validación a mitad de un lote de escrituras deja media operación guardada.

## Tarea de integración en curso

Integrar el delta del levantamiento (`LEVANTAMIENTO_PLANTA.md` §2–§5) siguiendo el backlog
`docs/levantamiento-2026-07/Backlog_Mejoras_App_CCAA.md`.

**P0 aplicado** (2026-07-30): campo `area` en `DocumentoLiberacion`, siembra de los registros
del Dossier, `generar_codigo_lote` con sus pruebas, `ControlProceso`+`ControlProcesoLectura` con
el PCC 1, y la app `inocuidad` con `MonitoreoPPRO`+`PproLectura`.

**Ciclo de vida del lote** (cambiado el 2026-07-31): un lote **se abre al empezar la corrida**,
con su leche asignada y **sin kilos** — `kg_producidos` es nulable. Los kilos se declaran al
pasar a `producido`, que es cuando se saben; la regla vive en
`produccion.dominio.puede_declarar_producido`, no en el esquema, para que un lote histórico se
pueda cargar completo de una vez. La leche asignada **avisa pero no bloquea** ese paso: exigirla
detendría la producción del día por un dato completable, y endurecerlo es decisión de Calidad
sobre esa misma función. El código se propone con `codigo-sugerido/` y queda editable, por la
misma razón que `codigo_lote_valido` avisa y no restringe.

**Codificador de SKU** (2026-07-31): completo. Dominio puro en `maestros/catalogos_sku.py` +
`maestros/dominio.py`, y el maestro en `Producto` (`naturaleza_comercial`, `categoria`, `tipo`,
`formato`, `mercado`, `variante`) más `Mandante.codigo_cliente`.

**El SKU se deriva, no se teclea.** `Producto.save()` lo recalcula desde los atributos cada vez;
en el admin el campo es de solo lectura y al lado va «Cómo se lee el SKU», que lo descompone de
vuelta. Dejarlo escribible invitaría a teclear un código que contradiga los atributos del mismo
producto — que es exactamente el defecto que trae el archivo de origen (§4.2). Un producto sin los
atributos cargados conserva el código que tenga: el histórico está lleno de códigos a mano.

**Dónde se crea un producto:** pantalla **Maestros** (`/maestros`), pestaña Productos — o el admin
de Django. El mandante necesita su `codigo_cliente` cargado o sus productos no generan SKU.

**Maestros** cubre seis pestañas: productos, mandantes, máquinas, silos, camiones y códigos de
producción. Los tres últimos comparten `FormularioMaestro`, un formulario descrito por datos; los
tres primeros tienen el suyo porque muestran reglas propias (el SKU derivado, el cliente que
aporta el mandante, la advertencia del balance). Faltan **especificaciones**, **documentos de
liberación** y **recetas**: sus formularios son plantillas JSON y quien decide sobre ellos es
Calidad, así que siguen en el admin.

**Auditoría** vive en `/auditoria`, visible para todos los roles.

**Inocuidad aplicada** (2026-07-31): las dos reglas de bloqueo están y funcionan de punta a punta.
Una lectura fuera del límite del **PCC 1** de uperización, o un **PPRO** con lecturas No-OK sin
acción correctiva, impiden liberar el lote — y **no admiten concesión**: una concesión asume un
riesgo conocido y medido sobre la calidad, y aquí lo que falló es la barrera que hace seguro el
producto. El mecanismo no es una rama aparte: sus motivos entran en `bloqueos` y eso ya anula las
dos vías; si alguien los saca de esa lista, tiene que reponer la exclusión a mano.

Los límites del PCC viven **en cada `ControlProceso`** y no en un maestro: cambian por equipo —VEB
80,0 °C / 14.175 kg·h; Scheffers 2 81,2 °C / 17.100— y un control de mayo se audita contra el
límite que regía en mayo. Las claves que el PCC vigila dentro de `valores` (`t_dsi`,
`flujo_entrada`) se sirven en `/api/produccion/catalogos-inocuidad/` para que la pantalla las
rotule igual que el dominio las evalúa: si divergieran, el PCC dejaría de vigilar en silencio.

La captura está en el **panel de inocuidad de la ficha del lote**.

**Documentos que cumple el propio dato** (2026-07-31). Once de los diecinueve registros del
Dossier son datos que la aplicación ya captura, y pedir además una casilla es doble digitación —
peor aún: la casilla puede decir «cumplido» sobre un PCC 1 incumplido.
`DocumentoLiberacion.evidencia` declara qué registro lo cumple, y
`calidad.dominio.documentos_con_evidencia` lo resuelve.

**Siete están atados** (2026-08-03), y el resto sigue manual a propósito: un documento cumplido
*de más* deja salir producto.

| Documento | Lo cumple |
|---|---|
| `CCAA.REC.FORM.005` Trazabilidad | la asignación de silos del lote |
| `CCAA.Cond.FORM.010` PCC 1 | un `ControlProceso` en `veb`, `scheffers2` o `scheffers3` |
| `CCAA.Sec.FORM.025` Pulverización | un `ControlProceso` en `e1` o `e2` |
| `CCAA.Sec.FORM.001` Fisicoquímico | un `Analisis` del lote |
| `CCAA.ENV.FORM.001` Detector de metales | un `MonitoreoPPRO` de ese tipo |
| `CCAA.Sec.FORM.022` PPRO 3 · E1-E2 | un `MonitoreoPPRO` de aire/roce en `e1` o `e2` |
| `CCAA.Sec.FORM.005` PPRO 4 · Rovemas | un `MonitoreoPPRO` de aire/roce en `rovema3` o `rovema4` |

Los dos últimos exigen **equipo y tipo juntos**. Solo la máquina no basta: el checklist de cuerpos
extraños de esa misma torre es otro documento, y sin el tipo lo daría por cumplido — mientras que
el PPRO vigila presión de aire y roce de válvulas, que nadie habría mirado.

El expediente **distingue** el cumplimiento por dato del visto manual: no es lo mismo «hay control
de proceso» que «alguien lo marcó».

**El checklist tiene 21 documentos, no 19.** El Dossier lista el checklist de cuerpos extraños
como un solo registro (`Cond.FORM.005/014/016`), pero en planta son tres formatos con **piezas
distintas**: el Scheffers 2 tiene pulmones y coil, el Scheffers 3 tapas por efecto, y el VEB
cuatro efectos. Una plantilla única pediría el estado de piezas que ese evaporador no tiene, y el
checklist se marcaría igual sin decir qué se revisó.

**Plantillas cargadas** (desde `Documentos Planta/`, no inventadas): los cuatro checklists de
cuerpos extraños —Scheffers 2, Scheffers 3, VEB y Rovemas 3-4— y la **inspección pre-operativa
E1-E2** (`Sec.FORM.003`, cargada el 2026-08-03). `maestros.tests` exige que solo tengan plantilla
los documentos declarados en `PLANTILLAS_DE_UN_FORMATO_REAL` junto a su formato de origen:
agregar una obliga a decir de dónde salió.

**Los nombres de archivo de `Documentos Planta/` no son fiables.** `CCAA.Sec.FORM.020.01.xlsx`
contiene en su encabezado el código `CCAA.Sec.FORM.021.01`, y el formato de la inspección en
operación de las Rovemas se llama `Inspeccion operativa Rov 3 4.xlsx` —sin número—. Los formatos
se buscan **por el código que llevan dentro**, abriendo el archivo; buscar por nombre da falsos
negativos y, peor, falsos positivos.

Tres documentos **no llevan plantilla aunque su formato ya se revisó**, y `maestros.tests`
(`REVISADOS_Y_SIN_PLANTILLA`) lo fija para que el próximo que los encuentre no los cargue creyendo
que faltaban: el PPRO E1-E2 (`Sec.FORM.022`) son lecturas horarias OK/No-OK de tres tipos que
`MonitoreoPPRO` ya modela; la dosificación de lecitina (`Sec.FORM.021`) son lecturas horarias, o
sea `ControlProcesoLectura`; y la inspección en operación de Rovemas (`Sec.FORM.024`) es una
**grilla de 24 horas** — su mitad «al inicio de la operación» sí sería un checklist, pero
aplanar la mitad «cada 1 hora» a un campo por ítem daría un formulario que se completa entero
habiendo registrado una de las veinticuatro lecturas que el formato pide. Partir un formato de
planta en dos registros lo decide Calidad.

**Los cinco documentos que siguen en `por_lote` sin formato que lo diga se quedan ahí.** El
control maestro (`12.- Control de Documentos`) no trae columna de frecuencia utilizable, y
`por_lote` es el valor seguro: pasarse de frecuencia solo molesta, quedarse corto deja que un
registro cubra lotes que nunca revisó.

**Ojo con el tipo `lista`**: está en el contrato de la plantilla pero `FormularioDinamico` no lo
dibuja — cae al campo de texto por defecto, sin avisar. Hay una prueba que impide usarlo hasta que
se implemente.

**Los registros que no son por lote viven en el equipo y su período** (2026-07-31). En el catálogo
de planta **solo 12 de 204 documentos son por lote**; el resto son aseos por ciclo, monitoreos por
turno y programas. `DocumentoLiberacion.frecuencia` decide dónde vive el dato, y `RegistroEquipo`
—hermano de `RegistroCalidad`, mismo contrato de plantilla— cuelga del equipo y su fecha. El
checklist del lote lo **consume**: un aseo semanal se llena una vez y cubre todos los lotes de esa
semana.

La ventana se deduce de la frecuencia y **no se guarda**: un `vigente_hasta` almacenado se
desincroniza al corregir la fecha del registro, y un lote quedaría cubierto por un aseo que ya no
lo alcanza. La excepción es `segun_programa`, sin período deducible: ahí el registro declara su
vigencia y sin ella **no cubre nada**.

La captura vive en **`/registros`**, organizada por equipo y fecha — quien asea una torre no
piensa en lotes. Los campos los dibuja `components/CampoDePlantilla`, el mismo componente que el
expediente: un solo renderizador para un solo contrato.

**La frecuencia es un dato configurable, no una constante del código.** Se edita en la pestaña
**Documentos de liberación** de Maestros —o en el admin—, y la escribe **Calidad**, no
Administración: es quien responde por el checklist, y que Producción pudiera bajar la frecuencia
de un documento le dejaría reducir lo que se le exige. Cambiarla mueve el formulario entre el
expediente del lote y `/registros`, sin desplegar.

**Las frecuencias sembradas se cargan solo cuando el formato las declara.** El catálogo del levantamiento
tiene una columna de frecuencia que **no coincide** con los formularios: clasifica los checklists
de cuerpos extraños como «Según programa» mientras el formato dice «Al inicio del ciclo de
producción». Manda el formato. El resto se queda en `por_lote`, que además es el valor seguro:
pasarse de frecuencia solo molesta, quedarse corto deja que un registro cubra lotes que nunca
revisó.

La pantalla cubre productos, mandantes y silos (estos últimos de solo lectura: su ocupación es un
saldo del libro de movimientos, y un formulario invitaría a «corregirlo» escribiéndolo). Las
**especificaciones** y el **catálogo de documentos** siguen en el admin: sus formularios son JSON
y quien decide sobre ellos es Calidad, no Administración.

Los catálogos de los desplegables se sirven en `/api/maestros/catalogos-sku/` en vez de escribirse
en el frontend, y el SKU **no se previsualiza en el cliente**: reproducir el generador allí crea
una segunda implementación que puede diferir de la que manda, justo en el dato que se imprime en
el saco. Lo que sí se anticipa es qué falta para poder componerlo.

**Salvedades sobre `SKU_PRODUCTOS.md`** (verificadas contra el Excel fuente):

- §4.2 concluye que el generador «corrige automáticamente» las filas mal codificadas. **No las
  corrige.** *Leche Entera Estándar 28% NE* trae la **columna Categoría = "Crema"**, no solo el
  SKU; el generador compone desde atributos, así que de un atributo malo sale el mismo SKU malo.
  Hay que arreglar el dato.
- §4.2 sospecha de *Leche Entera Instantánea 27% CN*: está bien, es Colun (`02`). Sin acción.
- §4.1 atribuye las colisiones a falta de estructura. **Parte era carga inconsistente, y ya está
  medido** (2026-08-03): aplicar la categoría `11` donde corresponde baja las colisiones de seis
  grupos a cuatro. O sea que el 7.º segmento sí hace falta —pero para cuatro pares, no para el
  desorden entero—, y solo si negocio confirma que no son duplicados del archivo.
- §4.3 dice 17 productos sin validar; en la hoja son **16**.
- §7 da `Receta` por «pendiente de portar del prototipo»: **ya está** (`maestros/recetas.py`, con
  explosión multinivel y pruebas). Lo que sigue vigente de §7 es que las hojas de recetas del
  mismo Excel son la BOM por 100 kg y pueden sembrarla.

**Resuelto (2026-07-31): el código de lote lleva el SKU completo de 12 dígitos**, o sea 23
caracteres —`CCAA6212010102010201-01`—. Se planteó la alternativa de un código corto por producto
(el Excel trae `Cód. CeGe` 101–123 y `Cód. Patricio R.` 5001–7004, que darían `CCAA6197101-01`) y
se descartó a favor de que el código cargue toda la información del producto. Si en planta el
largo resulta impracticable al imprimirlo o transcribirlo, el cambio es de una línea en
`generar_codigo_lote` — pero invalida los códigos ya emitidos.

**Maestro de productos cargado** (2026-08-03): los **23** del Excel, con
`python manage.py cargar_productos` (`--aplicar` para escribir; sin eso simula recorriendo el
mismo camino y revirtiendo, no calculando aparte lo que pasaría).

El comando **ignora la columna «SKU» del archivo** y compone cada código con `generar_sku`:
copiarla metería en el maestro el mismo defecto que `Producto.save()` existe para evitar, un
código que contradice los atributos del propio producto. Las tres correcciones al archivo están
declaradas en `CORRECCIONES`, con su motivo, para que se vea qué se cambió: la *Leche Entera
Estándar 28% NE* venía con Categoría = Crema (§4.2), y los dos productos *c/LdS* venían con
categoría `02` en vez de la `11` que ya existe.

Es un **comando y no una migración de datos** porque los productos son datos de negocio: una
migración los sembraría también en la base de pruebas, donde no pintan nada y solo abren la puerta
a que una prueba pase por un producto que no creó.

**Medido (2026-08-03): aplicar la categoría `11` baja las colisiones de seis grupos a cuatro.**
Eso es lo que faltaba para decidir el 7.º segmento. Los cuatro pares que quedan comparten los seis
segmentos y hay que preguntarle a negocio si son el mismo producto repetido en el archivo o dos
distintos:

| SKU | Productos que lo comparten |
|---|---|
| `010302010201` | Leche Entera Estándar 27% SP · Leche Entera en Polvo Regular |
| `010302030201` | Leche Descremada MH SP · Leche en Polvo Descremada Regular |
| `010311030201` | Leche Descremada c/LdS MH SP · Leche Descremada en Polvo c/Lec |
| `020003020101` | Precondensado SemiDescremado Rc0.201 · P. Semidescremado ST 45% CCAA |

Ojo: **el código de lote lleva el SKU**, así que mientras esos pares compartan código, dos lotes de
productos distintos del mismo día pueden salir con el mismo código de lote. `Producto.variante`
existe para desempatarlos y `generar_sku` ya lo admite; falta la decisión, no el mecanismo.

**Decisiones abiertas antes de tocar el modelo:**

1. Los cuatro pares de la tabla de arriba: ¿duplicados del archivo o productos distintos? Si son
   distintos, se les asigna `variante` y el SKU pasa a 14 dígitos.
2. Validar con negocio los 16 productos marcados «¿definido correctamente? = False».

**Lo siguiente, en este orden** (revisado el 2026-08-03):

1. ~~Unificar `equipo` en el maestro~~ — hecho.
2. ~~Unificar la receta~~ — hecho.
3. ~~Enganchar el consumo de inventario al ciclo del lote~~ — hecho.
4. Borrar `Insumo.stock_actual`: saldo huérfano, visible en el admin, que ya no lee nadie.
5. ~~Las plantillas de `Sec.FORM.003` y `Sec.FORM.024`~~ — hecho: la primera cargada, la segunda
   revisada y deliberadamente sin plantilla (ver arriba).
6. ~~Cargar el maestro de productos completo~~ — hecho (23/23). Quedan las decisiones del SKU,
   que son de negocio.
7. ~~Especificaciones en Maestros~~ — hecha (2026-08-06). Faltan **recetas**; la plantilla JSON de los documentos sigue en el admin a propósito.
8. **`Sec.FORM.024` con Calidad**: decidir si se parte en un checklist de inicio de operación y un
   registro de lecturas horarias, o si se modela como un `MonitoreoPPRO` con más tipos.

**Pendiente con Calidad:** los 19 se sembraron con `aplica_a = ["polvo"]`. Cuáles exigen además
crema o mantequilla sigue abierto (`MODELO_DATOS.md` §8.3) y se responde editando el catálogo,
no migrando.
