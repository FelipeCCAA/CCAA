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
- **Código de lote** (vigente desde 2026-08-20): `CCAA` + último dígito del año + día juliano (3) + **sigla del equipo** + `-` + correlativo del día en esa máquina —p. ej. `CCAA6232E1-01`. El correlativo va siempre desde `-01`. Identifica una corrida, no describe el producto; `Equipo.sigla` es configuración corta y estable del maestro, y `lote_codigo_unico_sucursal` garantiza la unicidad sobre `(sucursal, codigo_lote)`.

- **Dónde termina un lote** (decisión de planta, 2026-08-20): una corrida de torre es un lote aunque cruce turnos o se envase en dos formatos. Solo se parte por un tema de inocuidad mediante `POST lotes/{id}/partir/`, con motivo obligatorio; `Lote.lote_anterior` encadena la continuación.
- `codigo_lote_valido` **avisa, no restringe**: el histórico de planta trae códigos que no siguen el patrón —empezando por todos los del POE anterior— y hay que poder registrarlos. No conectarlo al `clean()` de `Lote`.
- **`Producto.codigo` guarda el SKU** y es parte del código de lote. Un producto sin él no frena nada: `codigo-sugerido/` devuelve `codigo: null` con un motivo que dice qué falta y dónde, y el operador escribe el código a mano. Se carga desde el admin, y conviene componerlo con `generar_sku` en vez de teclearlo.
- **SKU de producto** (`maestros/dominio.py` + `catalogos_sku.py`): 12 dígitos en 6 segmentos, compuestos **solo desde catálogos**. Un valor fuera de catálogo falla en vez de improvisar — un SKU con un segmento inventado se ve igual de válido que uno correcto y termina impreso en un saco. El orden de los segmentos se dedujo de los datos, no de los encabezados de la planilla, que están desalineados; `tests_dominio_sku.py` recompone los 24 productos reales del archivo y es lo que fija ese orden. `sku_valido` comprueba además la regla naturaleza↔cliente, para que el validador no apruebe lo que el generador se niega a componer.
- **Auditoría** (`auditoria`): se captura por señales, no desde las vistas, para cubrir todo lo que escribe en la base —API, admin, scripts, shell— y no solo los caminos instrumentados. Los dos lados del diff se leen **de la base** en `pre_save`/`post_save`: comparar la base contra el objeto en memoria marca como cambiados campos que solo cambiaron de tipo. Todos los cambios tienen la **misma forma** `{campo: [antes, después]}`, también las altas —con `None` delante—: dos formas obligan a cada consumidor a distinguirlas y el que no lo haga revienta. Es **de solo lectura en las tres capas** (viewset, admin y servicio del frontend): un registro que se puede editar no prueba nada.
- **Máquinas** (`maestros.Equipo`): `consume_leche` es una **regla del balance**, no una etiqueta. Un mismo código de producción se programa en el evaporador y en la línea que lo recibe; si ambos restaran, la semana contaría la misma leche dos veces. Solo los evaporadores.
- **Un código de cliente, un mandante** (desde 2026-08-03, restricción `mandante_unico_por_codigo_cliente`). El segmento de cliente del SKU no tiene forma de distinguir dos mandantes que lo compartan: sus productos salen con SKU idénticos. La base llegó a tener «Nestle» y «Nestlé» a la vez y los productos de ese cliente quedaron repartidos entre las dos fichas, sin que nada avisara porque nada lo impedía; la migración `0022` los fusionó. Los mandantes **sin** código sí pueden ser varios: uno sin código es uno que todavía no genera SKU.
- **Una sola representación de «equipo»** (desde 2026-08-03). `maestros.Equipo` es la única: `ControlProceso`, `MonitoreoPPRO`, `CicloCIP`, `BloquePlan` y `RegistroEquipo` lo referencian por clave foránea. Antes había cinco vocabularios para las mismas máquinas —un `TextChoices` en `produccion` («VEB», «SCH2»), el maestro («veb», «scheffers2»), y texto libre en los monitoreos y en el CIP—, y con dos alfabetos un criterio del checklist no se podía comparar contra el registro sin traducir en el medio. `linea1`/`linea2` **eran** las torres Egron: se renombraron a `e1`/`e2`, no se duplicaron. Se agregaron `rovema3` y `rovema4`.
- Los **criterios de evidencia comparan el `codigo` del equipo**, no su nombre ni el objeto. El nombre se edita desde Maestros, y un criterio escrito contra «Torre de secado Egron 1» dejaría de cumplirse el día que alguien le corrija una tilde — en silencio, hasta que un lote no se pudiera liberar. `calidad.dominio._valor_comparable` lo resuelve, y `tests_evidencia` lo fija con un doble cuyo nombre difiere del código.
- **La sucursal dejó de ser una dimensión del negocio** (desde 2026-08-17, `docs/DECISION_MODELO_ORGANIZACIONAL_2026-08-17.md`). CCAA se administra como una sola organización: sucursales o plantas no aparecen en navegación, formularios, perfiles ni contratos del frontend. **Todos los perfiles son de alcance empresa** —`usuarios.0015` los reescribió a `alcance = empresa`, `sucursal = None`— y las altas operacionales reciben su organización de la sesión; el backend ignora cualquier subdivisión que mande un cliente antiguo. Las columnas siguen ahí solo por compatibilidad: `usuarios.tenancy.sucursal_para_escritura` completa la clave foránea con **el registro interno canónico**, y `unica_sucursal_activa` devuelve el primero activo, sin preguntar. Su eliminación física será una migración escalonada, no un `DROP`.

  Esto **deroga** la decisión anterior («una sola planta, y no se nota», 2026-08-10), donde `unica_sucursal_activa` devolvía `None` con dos activas para obligar a elegir. Ese resguardo protegía contra escribir en la planta equivocada; ya no aplica porque la subdivisión dejó de ser algo sobre lo que se elige. **El día que haya una segunda planta hay que reponer esa pregunta**, y no basta con reactivar la función: los perfiles ya no llevan sucursal.

- **Nada de inocuidad se decide comparando sucursales.** Al unificar el modelo hubo un intento de exigir `lote.sucursal_id == equipo.sucursal_id` para registrar un control de proceso, y de filtrar por sucursal los registros periódicos que cubren un lote; con dos fuentes de sucursal conviviendo —la canónica de las escrituras nuevas y la que arrastran las filas sembradas— **el PCC 1 dejaba de poder registrarse y un aseo completado dejaba de cubrir su semana en silencio**. Se quitaron las dos comparaciones (`6707a29`). El aislamiento por empresa lo sigue dando `DocumentoLiberacion`, que se acota a la empresa del lote y por el que pasa la consulta de registros. Si alguien repone una comparación de sucursal ahí, `calidad.tests_api_inocuidad` y `calidad.tests_api_periodicos` vuelven a rojo — que es para lo que están.
- Los **catálogos de opciones** se sirven desde el backend (`/api/maestros/catalogos/`, `/api/planificacion/catalogos/`) y no se escriben en el frontend: una copia ofrece tarde o temprano un valor que el backend rechaza.
- **Una sola receta** (desde 2026-08-03). `maestros.Receta` es el único lugar donde se declara qué lleva un producto. Un `RecetaComponente` es **un producto o un insumo, nunca los dos**: el producto se transforma aquí y la explosión sigue por su receta; el insumo se compra y lo descuenta bodega. Antes había un segundo maestro, `inventario.ConsumoProducto`, plano y sin versión, y era **ese** el que el descuento de bodega consumía — así que un lote de mayo se descontaba con las cantidades de hoy, que es justo lo que `Receta` está versionada para impedir. Los tres caminos que calculan consumo —el descuento del lote, el MRP semanal y el MRP puntual— pasan por `inventario.servicios.insumos_requeridos`; con tres implementaciones, la orden de compra y el descuento podían pedir cantidades distintas para la misma fórmula.
- Las **especificaciones las escribe Calidad**, no Administración (desde 2026-08-06, `EscribeCalidad` en `EspecificacionViewSet`). Misma corrección que el checklist y las recetas: los rangos deciden qué producto sale conforme, y que Administración pudiera moverlos le dejaría cambiar el veredicto de un lote sin medirlo de nuevo. Se editan en **Maestros › Especificaciones**, con una fila por parámetro del catálogo y **no** un textarea de JSON: así no hay forma de escribir una clave que `clean()` rechaza. **Qué versión está vigente lo responde el backend** (`es_vigente`), con la misma función que audita el lote y calculada sobre *todas* las versiones, no sobre la página — con un producto a caballo entre dos páginas, la vieja saldría marcada como vigente.
- La **fórmula la escribe Calidad**, no Bodega. El formulario que había en `/abastecimiento` dejaba que quien descuenta el material redefiniera cuánto material lleva. Se edita en el admin (`Maestros › Recetas`), igual que las especificaciones.
- Una explosión **incompleta no descuenta nada**: si la cadena se corta —un intermedio sin receta, un ciclo— `consumir_receta_produccion` falla en vez de descontar un requerimiento a medias, que se parece demasiado a uno completo y dejaría el saldo de bodega mintiendo. El MRP puntual devuelve `receta_completa` por la misma razón.
- **Declarar el lote producido descuenta su material de bodega** (desde 2026-08-03), y es el único momento en que ocurre: antes hay lote pero no kilos. **No bloquea** — mismo criterio que la leche asignada: detener la producción del día porque bodega no cargó la receta o el material sigue en cuarentena traslada a la línea un problema que no es suyo. Lo que falla queda **pendiente y visible** (`consumo_inventario.pendiente` en la ficha), porque un descuento fallido que no se ve deja el saldo alto sin que nadie lo sepa.
- Atrapar el error del consumo **es seguro solo porque `consumir_receta_produccion` es `@transaction.atomic`**: el servicio alcanza a crear la cabecera y a sacar lo que sí había antes de detectar que falta, y sin esa reversión el lote quedaría con un consumo «registrado» que descontó una fracción. Quitar ese decorador rompe `test_sin_stock_el_lote_igual_se_declara_y_avisa` —verificado por mutación—, no la vista.

- **Estandarización** (`estandarizacion`, desde 2026-08-06): el RC —grasa ÷ SNG— es el cálculo que decide qué producto sale. La matemática vive en `dominio.py` sin ORM, y `ValeEstandarizacion` es el documento con su ciclo. Tres reglas justifican que cada paso sea una acción del servicio y no un `PATCH estado=…`: **muestrear antes de 30 minutos avisa pero no frena** (desde 2026-08-17: antes la mezcla no es homogénea, pero detener la operación lo decide la planta; el vale sella `muestreado_en` y el aviso queda auditable — la hora la pone el servidor), **liberar no se pide sino que se calcula** desde el RC medido, y **corregir reinicia el reloj y borra el análisis** porque agregar leche deshace la mezcla. La composición de las dos leches se congela **en el vale** —el silo cambia con cada ingreso—, y `rc_real` se deriva. `calcular/` responde sin crear: es el paso que el operador repite variando el volumen. Detalle en `docs/REGLAS_DE_PLANTA.md` §3.
- **Una recepción es un camión, no un módulo** (desde 2026-08-19,
  `docs/superpowers/specs/2026-08-19-recepcion-instructivo-design.md`). El formato
  `CCAA.REC.FORM.002.02` pone una fila por camión con las crioscopías M1 a M4, porque un
  camión trae hasta cuatro compartimientos pero **un** silo, **unos** litros y **un**
  destino. `ModuloRecepcion` guarda lo que es propio del compartimiento: la
  crioscopía, y desde la migración `0013` también `carga_recoleccion` —el vínculo con
  la carga que Recolección dejó cerrada en el predio para ese módulo—. No lleva litros,
  silo ni destino: darle litros abriría la puerta a que dos módulos del mismo camión
  declararan silos distintos. La migración `0012` **no colapsó** las filas
  hermanas existentes: sumar litros de filas con silo, estado o veredicto distintos
  habría producido un registro que nadie hizo.
- **Una marca horaria que falta no vale cero.** `recepcion.dominio.permanencia` devuelve
  `None` con su motivo si falta el arribo a portería o el término del CIP. En los 26
  libros de julio de 2026 la hora programa estaba llena en **1 de 603 filas** y la
  planilla calculaba igual: restaba contra cero, así que cada camión «pagaba» la hora del
  reloj a la que terminó el CIP menos dos. El 31-07 el total del día fue de 254 horas que
  no eran sobreestadía. Por eso la permanencia se cuenta desde el **arribo a portería**, y
  `resumen-diario/` informa `camiones_sin_marcas_horarias` en vez de dejar que el total
  parezca completo.
- **El pH del camión no es el pH de la leche.** `ph_camion` (5,5–8,5) es del enjuague y
  vive en su propia columna; `controles["ph"]` (6,5–6,9) es de la leche. Con una sola
  clave, el pH del agua retendría un camión conforme.

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
- **Un autoguardado en vuelo pisaba la confirmación** (corregido el 2026-08-31). Los cuatro formularios con borrador —recepción, análisis de silo, vale y lote— guardan solos cada dos segundos y confirman aparte, así que al pulsar «Confirmar» puede quedar un `guardar-borrador` en camino. Si ese PATCH leía la fila antes de que la confirmación se comprometiera, `serializer.save()` reescribía **todas** las columnas —incluida `estado`— y devolvía a borrador un documento ya confirmado. Las dos peticiones respondían 200 y el operador veía el mensaje de éxito; el fallo aparecía dos pantallas después, al transferir un vale, con «el silo no tiene un análisis confirmado vigente» y sin nada que apuntara a la confirmación perdida. Ahora `_borrador_del_usuario(..., bloquear=True)` toma el candado de fila y las tres acciones que escriben corren en transacción: la que llega segunda relee, ve que ya no es borrador y responde 409. `recepcion.tests_borrador_carrera` lo fija atravesando la vista real —verificado por mutación: sin `bloquear=True` vuelve a rojo—.
- **`select_for_update` sobre una consulta con `select_related` bloquea también las filas unidas.** Los borradores traen silo, vehículo y producto por `select_related`, así que un candado sin acotar dejaría el silo entero bloqueado mientras alguien confirma su análisis. `of=("self",)` lo limita a la fila del documento, que es lo único en disputa.
- Los archivos del Instructivo (`Fabricación/2026/Instructivo/`) están **abiertos por
  OneDrive**: leerlos con `ZipFile::OpenRead` falla con «está siendo utilizado en otro
  proceso». Hay que copiarlos a un directorio temporal primero.
- **`ControlInhibidores.resultado` no dispara nada.** El gatillo del bloqueo de cierre
  (`recepcion.dominio.bloqueos_de_cierre`) sigue siendo
  `Recepcion.controles["delvo"]`/`["inhibidores"]` más el conteo de `BusquedaProveedor`;
  la función nunca lee `ControlInhibidores`. Y `ControlInhibidores` no tiene ViewSet ni
  URL propia —se carga por admin o por ORM—, así que hoy se puede registrar un PPRO N°1
  positivo sin que el cierre se entere: lo único que bloquea es que
  `controles["inhibidores"]` diga `"Positivo"`. Que el control dispare el bloqueo por sí
  mismo es una decisión de Calidad todavía sin tomar, no un descuido del código. Detalle
  en `docs/REGLAS_DE_PLANTA.md` §1.2.

- **El sistema parte en blanco** (desde 2026-08-20). Los libros de `Fabricación/2026` y los
  formatos de `Documentos Planta/` son **referencia de arquitectura, no datos a migrar**: al
  desplegar no se importa nada, y Calidad configura los productos, especificaciones, recetas y
  formularios vigentes. Por eso las plantillas viven en JSONField y los catálogos se sirven desde
  el backend: un formato de planta se carga **configurando, no programando**.

  Lo que se lee en los archivos históricos dice **qué forma tiene el proceso**, no qué filas
  sembrar. Las variantes que solo existen en libros viejos —crema Svelty, crema Champiñones— **no
  se modelan ni se siembran**: son hojas de un formato anterior, y quien las necesite creará la
  suya con el mecanismo de plantillas. Copiarlas al maestro dejaría productos que nadie pidió y
  que alguien tendría que mantener.

  Esto **baja el costo de equivocarse en el modelado**: sin códigos de lote emitidos, una decisión
  que resulte mal se corrige antes del despliegue, sin migración ni reimpresión. No habilita a
  posponer el esquema —igual hay que escribirlo—, pero sí a elegir el camino general y afinarlo
  cuando haya datos reales, en vez de detener el desarrollo esperando una respuesta.

- **El análisis del silo es un registro propio** (desde 2026-08-19, `recepcion.AnalisisSilo`,
  formato `CCAA.REC.FORM.005.01`). No se confunde con `Recepcion.controles`, que son los del
  **camión**: el silo mezcla varios camiones, y es la mezcla —no cada camión— la que alimenta el
  cálculo del RC. Trae los siete parámetros del vale de trazabilidad, incluidas **proteína y
  densidad**, que no existían en ninguna parte del sistema.

  **La vigencia no se guarda: se decide contra el libro de movimientos.** Un análisis deja de
  servir para componer un vale cuando entró un camión después de la muestra —una salida no, porque
  sacar leche no cambia la composición de la que queda, e invalidar por salida obligaría a
  re-muestrear cada vez que una línea consume—. Un campo `vigente` almacenado se desincronizaría al
  corregir la hora de un movimiento, y un vale quedaría compuesto contra leche que ya no está.

  El vale de estandarización **sigue congelando** la composición en sus columnas y solo gana dos
  claves foráneas de **procedencia** (`analisis_entera`, `analisis_descremada`): el análisis se
  puede corregir, y un vale de mayo tiene que auditarse contra lo que se usó en mayo. La captura
  vive en la pantalla de **silos**, no en la del vale: quien mide el silo es Recepción, al
  llenarlo. Que un análisis vencido **impida** crear el vale es decisión de Calidad todavía sin
  tomar; hoy avisa.

- **La organización inicial se busca por el código de su sucursal, no por su RUT** (desde
  2026-08-19). `usuarios.0008` siembra la organización con un RUT distinto en cada rama
  —`TENANT-TEST` bajo `DJANGO_ENV=test`, `TENANT-CI` en CI, y el de
  `CCAA_INITIAL_COMPANY_RUT` en cualquier otro caso—, así que ninguna constante de RUT
  puede acertarle a las tres; `CODIGO_SUCURSAL_INICIAL = "INTERNA"` sí, porque es literal
  en la migración. Antes se buscaba por `rut="RUT-LOCAL-DESARROLLO"`, **un valor que
  ningún camino del código escribe**: la búsqueda no acertaba nunca y los `default` de
  tenant creaban una **segunda** organización.

  El síntoma no se parecía en nada a la causa. Los maestros sembrados quedaban en una
  organización y los perfiles de prueba en la otra, así que todo queryset acotado por
  tenant devolvía vacío: `manage.py test` **sin** `DJANGO_ENV=test` dejaba 20 pruebas en
  rojo repartidas entre `calidad`, `auditoria` y `usuarios`, acusando que «el equipo no
  existe» — y no había nada malo en inocuidad ni en el PCC 1. Con la variable puesta pasaba
  entero, porque el `get_or_create(rut="TENANT-TEST")` de respaldo acertaba por casualidad;
  o sea que la base local y la de CI **no se construían igual**. `usuarios.tests_tenant_sembrado`
  lo fija comprobando la consecuencia y no el RUT: un perfil por defecto tiene que ver los
  equipos que sembró la migración, con y sin la variable.

  Quedan **dos definiciones de «estamos en pruebas»** —`_en_pruebas()` mira `sys.argv` y
  además `settings.DJANGO_ENV`; la migración solo `os.getenv("DJANGO_ENV")`—. Ya no importa,
  porque ambos caminos convergen en la misma organización, pero si alguien vuelve a apoyar
  una decisión en esa detección, que sepa que discrepan.

## El circuito de producción, de punta a punta

`frontend/e2e/circuito-polvo.spec.ts` (desde 2026-08-31) recorre **por pantalla** el turno
completo de leche en polvo: dos camiones —entera y descremada—, decisión de Calidad, descarga,
análisis de los dos estanques, vale de estandarización, lote, kilos y pallet. Se corre con
`npm run circuito` y **escribe** en la base a la que apunta; por eso tiene proyecto propio y
`npm run auditoria` ya no lo incluye. Detalle en `frontend/e2e/README.md`.

Existe porque la cadena ya estaba cubierta por API (`sembrar_flujo_demo`) y por unidad, y ninguna
de las dos comprueba que **alguien pueda recorrerla**: un desplegable vacío o un botón
deshabilitado dejan el backend impecable y la planta detenida. Encontró tres cosas que no se veían
de otro modo: la carrera del autoguardado contra la confirmación (arriba, en las trampas), que el
desplegable de responsables del muestreo salía vacío por perfiles sin área, y que el vale
**no hereda** la composición del `AnalisisSilo` —hay que teclear grasa y SNG que el sistema ya
tiene medidos—.

**Prerrequisitos como configuración, no como sembrado de la prueba:**
`manage.py preparar_circuito_polvo --aplicar` deja las áreas de perfil, la receta del producto y
existencia de embalaje en una ubicación **disponible** —el descuento por FEFO no ve la cuarentena—.
No los crea la prueba a propósito: son configuración de planta, y fabricarlos en cada corrida
escondería justo el caso de que en producción falten. Hacen falta **dos cuentas**
(`crear_usuario_e2e` y `crear_usuario_e2e --usuario e2e_segunda_firma`) porque el análisis de silo
exige dos firmas de personas distintas.

**Consume capacidad de verdad.** Cada corrida mete 25.000 L en un silo y 8.000 en un TK, y deja en
el destino lo que el lote no se lleva. Los estanques se eligen al arrancar entre los que tienen
sitio; cuando no quede, la prueba lo dice con esas palabras y se libera despachando la leche o con
`limpiar_transaccional --aplicar` si la base es de pruebas.

## El flujo de evaporación

`frontend/e2e/evaporacion.spec.ts` (desde 2026-09-01, `npm run evaporacion`) recorre por pantalla
lo que Producción hace con la leche que la estandarización dejó en el silo: abre el lote sobre un
evaporador, prepara la corrida, la inicia y la cierra declarando el precondensado. Los ayudantes
que comparte con el circuito viven en `frontend/e2e/ayudantes.ts`.

**Abrir el lote es iniciar la evaporación**, no son dos cosas. Para la familia `polvo` el
formulario de lote solo ofrece evaporadores —la torre aparece después, cuando Calidad libere el
concentrado— y `_encadenar_con_la_estandarizacion` deduce la etapa del **tipo de máquina**:
evaporador → evaporación, torre → secado. Elegir la máquina equivocada no da error: el lote nace
en otra etapa y no aparece nunca en «Nueva evaporación».

**El silo de origen se analiza después de abrir el lote.** `iniciar_condensacion` exige análisis
confirmado, vigente y con las dos firmas —la misma puerta que la transferencia del vale—. Abrir el
lote genera una **salida**, que no invalida la muestra; un ingreso sí. Analizar antes lo dejaría
vencido si algún vale descargara ahí entremedio.

**Una OP sin leche bloquea igual que ninguna.** El formulario filtra las órdenes por el producto
del vale, así que `preparar_circuito_polvo` programa la OP mirando **qué vales tienen saldo**, y
solo de familias que van a evaporador: una OP de crema deja el desplegable de órdenes lleno y el
de máquinas sin evaporadores, que es el mismo bloqueo movido de sitio.

### La pantalla ofrece lo que el backend va a rechazar

Tres casos del mismo patrón, encontrados por esta prueba. Cuestan caro porque el rechazo llega al
final del formulario —o de la corrida—, cuando ya no dice nada sobre qué elegir distinto:

1. **Vales sin saldo real** (corregido 2026-09-01). El desplegable contaba el consumo uniendo por
   `movimiento.lote`; `litros_ya_tomados` —la regla que bloquea— lo cuenta por `origen_id` y
   acotando al silo del vale. Con un movimiento que tiene `origen_id` y no `lote` —los hay en la
   base— la pantalla ofrecía 20.000 L libres y el formulario, ya completo, respondía «quedan
   0,00 L y se piden 20.000». `_vales_operativos` usa ahora la misma función que la regla: **una
   cantidad, una consulta**.
2. **Silos bloqueados por Calidad como destino del concentrado** (abierto).
   `procesos.opciones_alta` ofrece todos los silos activos sin mirar `estado`; escribe «Bloqueado
   por Calidad» en la opción pero no la deshabilita. El rechazo llega al **cerrar** la corrida,
   con el evaporador ya trabajado.
3. **Máquinas ocupadas por lotes anulados** (abierto). Anular un lote **no cierra su
   `EjecucionProceso`** —solo lo hace declararlo producido—, así que el evaporador queda ocupado
   indefinidamente. Con tres evaporadores, tres corridas abandonadas dejan la planta sin ninguno,
   y el único síntoma es «Máquina ocupada por otra corrida» sobre una máquina que nadie usa.

- **Declarar un lote producido es una sola cola** (desde 2026-09-02,
  `produccion.servicios.cerrar_lote_producido`). Después de que `registrar_produccion` cierra la
  ejecución con sus kilos vienen tres cosas que van siempre juntas: la orden pasa a pendiente de
  Calidad, se descuenta el material de bodega y se avisa al área. Había **tres** caminos que
  declaraban un lote producido —el `PATCH` del lote, `cerrar_mantequilla` y `cerrar_secado`— y cada
  uno traía su propia copia de esa cola. Secado se quedó sin las dos últimas partes, así que el
  polvo salía de la torre **sin descontar sus sacos y sin llegar a la bandeja de Calidad**; y como
  el descuento no fallaba sino que no ocurría, el saldo quedaba alto sin que nada lo delatara.
  Mantequilla adopta solo la cola y no `registrar_produccion`: crea coproductos y merma a mano y
  transiciona a `pendiente_control`, no a `cerrada`; unificar eso sería reescribirlo. Fijado en
  `procesos.tests_secado.CierreSecadoDescuentaMaterialTests`, verificado por mutación.
- **El aviso a un área no llega si nadie tiene esa área cargada.** `_notificar_area` busca
  destinatarios por `PerfilUsuario.area` y crea una fila por persona: sin nadie en Calidad no se
  crea ninguna, y no hay error. Es el hueco 4 de `docs/FLUJO_DEL_SISTEMA.md`. Una prueba que mida
  el aviso tiene que crear el destinatario explícitamente, o estará midiendo la falta de personal.
- **Una corrida cae en una sola bandeja.** `bandejaDeSecado` decide, y la pantalla no vuelve a
  decidir por su cuenta. Había un segundo clasificador para «historial» que rehacía la regla con
  una lista de estados escrita a mano y no coincidía: una corrida `cerrada` aparecía en
  «Terminadas» **y** en «Historial», y los contadores de las tarjetas la sumaban dos veces.
- **El cálculo del cliente nunca es la autoridad.** `calcularBalanceSecado` existe para dibujar el
  balance mientras se teclea, sin viajar al servidor por cada tecla; `rendimiento_recuperacion_pct`
  y `CorridaSecado.clean()` son los que deciden si el cierre se acepta. Lo mismo con el bloqueo de
  envasado: lo informa `lote.bloqueo_envasado`, calculado en el backend **antes** del intento.
  Adivinarlo con un `includes` contra el texto del error —que es lo que había— es una segunda
  fuente para el mismo hecho, y la frágil de las dos.

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

**Resuelto (2026-08-20): el código de lote identifica una corrida** con día, sigla de equipo y
correlativo (`CCAA6232E1-01`), no el SKU del producto. Así un cambio del SKU no altera el
significado de un código ya impreso.

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

Esto ya no afecta al código de lote, que identifica la corrida. `Producto.variante` existe para
desempatar los SKU y `generar_sku` ya lo admite; falta la decisión, no el mecanismo.

**Decisiones abiertas antes de tocar el modelo:**

1. Los cuatro pares de la tabla de arriba: ¿duplicados del archivo o productos distintos? Si son
   distintos, se les asigna `variante` y el SKU pasa a 14 dígitos.
2. Validar con negocio los 16 productos marcados «¿definido correctamente? = False».

**Lo siguiente, en este orden** (revisado el 2026-08-03):

1. ~~Unificar `equipo` en el maestro~~ — hecho.
2. ~~Unificar la receta~~ — hecho.
3. ~~Enganchar el consumo de inventario al ciclo del lote~~ — hecho.
4. ~~Borrar `Insumo.stock_actual`~~ — hecho: lo quitó la migración
   `inventario.0012_remove_insumo_stock_actual`, y `inventario/models.py` deja la nota de que el
   saldo se calcula desde `Existencia`. Esta entrada siguió aquí semanas después de estar resuelta.
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
