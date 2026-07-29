/* ============================================================
   Esquema de datos — Gestión Productiva Planta CCAA
   ------------------------------------------------------------
   Definición declarativa de las entidades del proceso productivo.
   Es el contrato del sistema: de aquí salen la validación, el DDL
   de una base futura y el esquema de una API. No contiene lógica
   de negocio (eso vive en dominio.js) ni acceso a datos (repositorio.js).

   Modela el PROCESO, no la planilla. Los códigos de lote de la planta
   se reutilizan entre productos y entre días, por lo que aquí son un
   atributo descriptivo, nunca una clave.
   ============================================================ */

const Esquema = (() => {

  /* ---------- Tipos admitidos por los campos ---------- */
  const TIPOS = ["id", "texto", "entero", "decimal", "fecha", "fechaHora", "hora",
                 "booleano", "enum", "ref", "lista", "objeto"];

  /* ---------- Catálogos simples (listas de valores, sin entidad propia) ---------- */
  const CATALOGOS = {
    familias:     ["polvo", "crema", "liquido", "otro"],
    /* Dónde está cada producto en la cadena de transformación.
       La leche fresca es materia prima; la crema y el precondensado son
       intermedios que además se venden; el polvo y la mantequilla, terminados. */
    naturalezas:  ["materia_prima", "intermedio", "terminado"],
    unidades:     ["kg", "L"],
    lineas:       ["E1", "E2"],
    turnos:       ["A", "B", "C"],
    tiposLeche:   ["Entera", "Descremada"],
    procedencias: ["Nestlé", "P. Unión"],
    tiposSilo:    ["silo", "tk_ld", "tk_crema"],
    roles:        ["recepcion", "produccion", "calidad", "admin", "lectura"],
    /* ---- Planificación de producción ---- */
    equipos: {
      carga_precondensado: { etiqueta: "Carga de precondensado", etapa: "Apronte" },
      scheffers2:          { etiqueta: "Evaporador Scheffers 2", etapa: "Evaporación" },
      scheffers3:          { etiqueta: "Evaporador Scheffers 3", etapa: "Evaporación" },
      veb:                 { etiqueta: "Evaporador VEB",         etapa: "Evaporación" },
      linea1:              { etiqueta: "Línea 1 · Secado E1",    etapa: "Secado" },
      linea2:              { etiqueta: "Línea 2 · Secado E2",    etapa: "Secado" },
      linea_mantequilla:   { etiqueta: "Línea de mantequilla",   etapa: "Batido" }
    },
    // Solo estos consumen leche cruda y alimentan el balance. Las líneas de
    // secado trabajan precondensado y la de mantequilla, crema: incluirlas
    // contaría la misma leche dos veces.
    evaporadores: ["scheffers2", "scheffers3", "veb"],

    formatos: ["SH2", "SH3", "VEB"],

    /* Estados de equipo. Deliberadamente NO usan los colores de serie:
       las paradas planificadas van en gris con trama y las anomalías en la
       paleta de estado reservada. Cada bloque muestra además su letra y su
       etiqueta, así el color nunca carga solo el significado. */
    estadosEquipo: {
      A:  { etiqueta: "Aseo",              color: "#8b9da4", trama: true },
      X:  { etiqueta: "Preparación",       color: "#b6c5ca", trama: true },
      M:  { etiqueta: "Mantenimiento",     color: "#6b7f87", trama: true },
      P:  { etiqueta: "PNP",               color: "#d03b3b" },
      AP: { etiqueta: "Atraso de partida", color: "#fab219" }
    },

    /* Familias de código de producción. Paleta categórica validada con el
       verificador de la skill dataviz sobre superficie #ffffff y pairlist
       "all" (en una carta Gantt cualquier par puede quedar contiguo):
       peor par CVD ΔE 9.2, visión normal ΔE 16.3. El aqua queda en 2.82:1,
       bajo 3:1, por lo que el código va SIEMPRE escrito dentro del bloque. */
    familiasCodigo: {
      RC: { etiqueta: "Precondensado", color: "#2a78d6" },
      LN: { etiqueta: "Secado Nestlé", color: "#eb6834" },
      LU: { etiqueta: "Secado Colun",  color: "#1baf7a" },
      LC: { etiqueta: "Secado CCAA",   color: "#4a3aa7" }
    },

    categoriasConsumo: {
      prec_nestle:   { etiqueta: "Prec. Nestlé", origen: "nestle", derivada: true },
      prec_ccaa:     { etiqueta: "Prec. CCAA",   origen: "ccaa",   derivada: true },
      secado_ccaa:   { etiqueta: "Secado CCAA",  origen: "ccaa",   derivada: true },
      secado_nestle: { etiqueta: "Secado Nestlé",origen: "nestle", derivada: true },
      // Supuesto a confirmar con Producción: el secado Colun se abastece de
      // la leche recibida de P. Unión. Es el único origen sin fórmula explícita.
      secado_colun:  { etiqueta: "Secado Colun", origen: "punion", derivada: true },
      // No sale de ningún bloque: se teclea en el balance del día.
      trasvasije:    { etiqueta: "Trasvasije",   origen: "nestle", derivada: false }
    },

    origenesLeche: ["ccaa", "nestle", "punion"],

    /* ---- Turnos de personal ----
       Los tramos horarios son provisorios; se confirman con planta y son
       editables. Cubren las 24 h en tres turnos de 8 h. */
    horariosTurno: {
      A: { etiqueta: "A · 00–08", desde: 0,  hasta: 8 },
      B: { etiqueta: "B · 08–16", desde: 8,  hasta: 16 },
      C: { etiqueta: "C · 16–24", desde: 16, hasta: 24 }
    },

    /* Funciones que se cubren en cada turno. La dotación de operadores y de
       laboratorio se deduce del programa; el supervisor es uno por turno activo. */
    funcionesTurno: {
      operador:    { etiqueta: "Operador",            derivada: true },
      laboratorio: { etiqueta: "Laboratorio",         derivada: true },
      supervisor:  { etiqueta: "Supervisor de turno", derivada: true }
    },

    // Operadores que necesita cada equipo cuando está produciendo. Editable.
    dotacionEquipo: {
      scheffers2: 1, scheffers3: 1, veb: 1,
      linea1: 1, linea2: 1, linea_mantequilla: 1, carga_precondensado: 1
    },

    // Horas mínimas de descanso entre dos turnos de una misma persona.
    minDescansoHoras: 8,

    parametros: {
      humedad:     { etiqueta: "Humedad",         unidad: "%" },
      mg:          { etiqueta: "Materia grasa",   unidad: "%" },
      sng:         { etiqueta: "Sólidos no grasos", unidad: "%" },
      st:          { etiqueta: "Sólidos totales", unidad: "%" },
      acidez:      { etiqueta: "Acidez",          unidad: "°D" },
      ph:          { etiqueta: "pH",              unidad: "" },
      temperatura: { etiqueta: "Temperatura",     unidad: "°C" },
      pesoEsp:     { etiqueta: "Peso específico", unidad: "g/mL" },
      proteina:    { etiqueta: "Proteína",        unidad: "%" }
    }
  };

  /* ---------- Estados ----------
     Se declaran con sus transiciones válidas para que la UI y el dominio
     compartan una sola definición de qué movimiento está permitido. */
  const ESTADOS = {
    recepcion: {
      inicial: "registrada",
      valores: ["registrada", "muestreada", "analizada", "liberada", "retenida", "descargada", "cerrada"],
      transiciones: {
        registrada:  ["muestreada", "cerrada"],
        muestreada:  ["analizada"],
        analizada:   ["liberada", "retenida"],
        liberada:    ["descargada"],
        retenida:    ["liberada", "cerrada"],   // se libera tras reanálisis o se rechaza
        descargada:  ["cerrada"],
        cerrada:     []
      }
    },
    lote: {
      inicial: "en_proceso",
      valores: ["en_proceso", "producido", "cerrado", "anulado"],
      transiciones: {
        en_proceso: ["producido", "anulado"],
        producido:  ["cerrado", "anulado"],
        cerrado:    [],
        anulado:    []
      }
    },
    liberacion: {
      inicial: "pendiente",
      valores: ["pendiente", "en_revision", "liberado", "liberado_concesion", "rechazado"],
      transiciones: {
        pendiente:          ["en_revision", "rechazado"],
        en_revision:        ["liberado", "liberado_concesion", "rechazado", "pendiente"],
        liberado:           ["en_revision"],          // al desmarcar un documento vuelve a revisión
        liberado_concesion: ["en_revision"],
        rechazado:          ["en_revision"]
      }
    },
    despacho: {
      inicial: "borrador",
      valores: ["borrador", "emitido", "anulado"],
      transiciones: { borrador: ["emitido", "anulado"], emitido: ["anulado"], anulado: [] }
    },
    semanaPlan: {
      inicial: "borrador",
      valores: ["borrador", "publicada", "cerrada"],
      transiciones: {
        borrador:  ["publicada"],
        publicada: ["borrador", "cerrada"],   // se puede devolver a borrador para corregir
        cerrada:   []
      }
    }
  };

  /* ---------- Entidades ---------- */
  const ENTIDADES = {

    /* ===== Maestros ===== */

    mandante: {
      etiqueta: "Mandante", grupo: "maestro", rotulo: "nombre",
      descripcion: "Empresa dueña del producto elaborado (incluye la marca propia CCAA).",
      campos: {
        id:     { tipo: "id" },
        nombre: { tipo: "texto", req: true },
        activo: { tipo: "booleano", def: true }
      }
    },

    producto: {
      etiqueta: "Producto", grupo: "maestro", rotulo: "nombre",
      descripcion: "Producto terminado. El mandante es un campo propio, no se deduce del nombre.",
      campos: {
        id:         { tipo: "id" },
        codigo:     { tipo: "texto" },
        nombre:     { tipo: "texto", req: true },
        familia:    { tipo: "enum", valores: CATALOGOS.familias, req: true },
        naturaleza: { tipo: "enum", valores: CATALOGOS.naturalezas, def: "terminado",
                      nota: "Dónde está en la cadena: materia prima, intermedio o terminado" },
        unidadBase: { tipo: "enum", valores: CATALOGOS.unidades, def: "kg",
                      nota: "Unidad en que se mide: la leche en litros, el polvo y la crema en kilos" },
        mandanteId: { tipo: "ref", ref: "mandante", req: true },
        activo:     { tipo: "booleano", def: true }
      },
      indices: [{ campos: ["nombre", "mandanteId"], unico: true }]
    },

    especificacion: {
      etiqueta: "Especificación de calidad", grupo: "maestro",
      descripcion: "Rangos aceptables por producto, versionados en el tiempo. Un lote se " +
                   "audita contra la versión vigente en su fecha de producción, no contra la actual.",
      campos: {
        id:            { tipo: "id" },
        productoId:    { tipo: "ref", ref: "producto", req: true },
        version:       { tipo: "entero", req: true, def: 1 },
        vigenteDesde:  { tipo: "fecha", req: true },
        vigenteHasta:  { tipo: "fecha", nulo: true, nota: "null = vigente indefinidamente" },
        rangos:        { tipo: "objeto", req: true,
                         nota: "{ parametro: { min, max, obligatorio } }" },
        fuente:        { tipo: "texto", nota: "Documento o acuerdo que respalda la especificación" }
      },
      indices: [{ campos: ["productoId", "version"], unico: true }]
    },

    receta: {
      etiqueta: "Receta de producto", grupo: "maestro",
      descripcion: "Qué se necesita para obtener una cantidad de producto. Es multinivel: la " +
                   "mantequilla lleva crema y la crema lleva leche fresca, así que el consumo " +
                   "de materia prima se deduce recorriendo la cadena completa.",
      campos: {
        id:           { tipo: "id" },
        productoId:   { tipo: "ref", ref: "producto", req: true, nota: "El producto que sale" },
        version:      { tipo: "entero", req: true, def: 1 },
        vigenteDesde: { tipo: "fecha", req: true },
        vigenteHasta: { tipo: "fecha", nota: "Vacío = vigente indefinidamente" },
        cantidadBase: { tipo: "decimal", req: true, def: 1, min: 0,
                        nota: "Cuánto produce esta receta, en la unidad base del producto" },
        componentes:  { tipo: "lista", de: "objeto", req: true,
                        etiqueta: "Componentes",
                        nota: "Lo que entra para obtener la cantidad base. La unidad debe " +
                              "coincidir con la unidad base de cada componente.",
                        campos: [
                          { clave: "productoId", etiqueta: "Componente", tipo: "ref", ref: "producto",
                            req: true, permiteCrear: true,
                            ayuda: "Si el componente aún no existe, se crea desde aquí" },
                          { clave: "cantidad",   etiqueta: "Cantidad",   tipo: "decimal", req: true, min: 0 },
                          { clave: "unidad",     etiqueta: "Unidad",     tipo: "enum", valores: CATALOGOS.unidades, req: true },
                          { clave: "merma",      etiqueta: "Merma",      tipo: "decimal", unidad: "%", min: 0, max: 100,
                            ayuda: "Pérdida del componente en el proceso; aumenta la cantidad necesaria" }
                        ] },
        fuente:       { tipo: "texto", nota: "De dónde salió la receta; marque las provisorias" },
        observacion:  { tipo: "texto" }
      },
      indices: [{ campos: ["productoId", "version"], unico: true }],
      derivados: {
        insumoPorUnidad: "Recetas.explosionar() — materia prima total por unidad de producto"
      }
    },

    silo: {
      etiqueta: "Silo / estanque", grupo: "maestro", rotulo: "codigo",
      descripcion: "Contenedor de leche o crema. La capacidad permite calcular ocupación real.",
      campos: {
        id:         { tipo: "id" },
        codigo:     { tipo: "texto", req: true },
        tipo:       { tipo: "enum", valores: CATALOGOS.tiposSilo, req: true },
        capacidadL: { tipo: "decimal", req: true, min: 0 },
        activo:     { tipo: "booleano", def: true }
      },
      indices: [{ campos: ["codigo"], unico: true }]
    },

    vehiculo: {
      etiqueta: "Camión", grupo: "maestro", rotulo: "placa",
      campos: {
        id:            { tipo: "id" },
        numero:        { tipo: "texto" },
        placa:         { tipo: "texto", req: true },
        tipo:          { tipo: "texto", def: "Camión" },
        capacidadL:    { tipo: "decimal", min: 0 },
        transportista: { tipo: "texto" },
        choferAM:      { tipo: "texto" },
        choferPM:      { tipo: "texto" },
        activo:        { tipo: "booleano", def: true }
      }
    },

    documentoLiberacion: {
      etiqueta: "Documento de liberación", grupo: "maestro", rotulo: "nombre",
      descripcion: "Catálogo de documentos obligatorios y, en 'plantilla', los campos del " +
                   "formulario digital. Cambiar la plantilla cambia el formulario: no hay " +
                   "formularios escritos a mano.",
      campos: {
        id:          { tipo: "id" },
        codigo:      { tipo: "texto", nota: "Ej: CCAA.Calidad.FORM.016.02" },
        nombre:      { tipo: "texto", req: true },
        aplicaA:     { tipo: "lista", de: "enum", valores: CATALOGOS.familias, req: true },
        instruccion: { tipo: "texto", nota: "Qué debe verificar quien lo completa" },
        plantilla:   { tipo: "lista", de: "objeto",
                       nota: "Campos del formulario: [{ clave, etiqueta, tipo, req, unidad, " +
                             "valores, min, max, parametro, origen }]. Vacío = solo atestación." },
        fuente:      { tipo: "texto", nota: "De dónde salió la plantilla; marque las provisorias" },
        orden:       { tipo: "entero", def: 0 },
        activo:      { tipo: "booleano", def: true }
      }
    },

    usuario: {
      etiqueta: "Usuario", grupo: "maestro", rotulo: "nombre",
      descripcion: "Personas que operan el sistema. Los operadores de planta se registran " +
                   "aquí aunque todavía no tengan credenciales.",
      campos: {
        id:     { tipo: "id" },
        nombre: { tipo: "texto", req: true },
        rol:    { tipo: "enum", valores: CATALOGOS.roles, req: true, def: "lectura" },
        activo: { tipo: "booleano", def: true }
      }
    },

    /* ===== Transaccional ===== */

    recepcion: {
      etiqueta: "Recepción de leche", grupo: "transaccional",
      descripcion: "Llegada de un camión. Los controles deciden si la leche se libera al silo o se retiene.",
      campos: {
        id:          { tipo: "id" },
        fecha:       { tipo: "fecha", req: true },
        hora:        { tipo: "hora" },
        guia:        { tipo: "texto" },
        vehiculoId:  { tipo: "ref", ref: "vehiculo" },
        procedencia: { tipo: "enum", valores: CATALOGOS.procedencias },
        tipoLeche:   { tipo: "enum", valores: CATALOGOS.tiposLeche, req: true },
        litros:      { tipo: "decimal", req: true, min: 0 },
        siloId:      { tipo: "ref", ref: "silo", nota: "Destino de descarga" },
        operadorId:  { tipo: "ref", ref: "usuario" },
        turno:       { tipo: "enum", valores: CATALOGOS.turnos },
        // Los subcampos se declaran para que la interfaz dibuje campos reales
        // y no un cuadro de texto con JSON. Son los que decide evaluarRecepcion().
        controles:   { tipo: "objeto", etiqueta: "Controles del camión",
                       nota: "Deciden si la leche se libera al silo o se retiene",
                       campos: [
                         { clave: "temperatura",   etiqueta: "Temperatura",   tipo: "decimal", unidad: "°C" },
                         { clave: "acidez",        etiqueta: "Acidez",        tipo: "decimal", unidad: "°D" },
                         { clave: "ph",            etiqueta: "pH",            tipo: "decimal" },
                         { clave: "crioscopia",    etiqueta: "Crioscopía",    tipo: "decimal", unidad: "°C",
                           ayuda: "Menos negativa que −0,510 sugiere aguado" },
                         { clave: "delvo",         etiqueta: "Delvo Test",    tipo: "enum", valores: ["Negativo", "Positivo"] },
                         { clave: "inhibidores",   etiqueta: "Inhibidores",   tipo: "enum", valores: ["Negativo", "Positivo"] },
                         { clave: "organoleptico", etiqueta: "Organoléptico", tipo: "enum", valores: ["Conforme", "No conforme"] }
                       ] },
        estado:      { tipo: "enum", valores: ESTADOS.recepcion.valores, def: ESTADOS.recepcion.inicial },
        motivo:      { tipo: "texto", nota: "Obligatorio si el estado es 'retenida'" },
        observacion: { tipo: "texto" }
      }
    },

    movimientoSilo: {
      etiqueta: "Movimiento de silo", grupo: "transaccional",
      descripcion: "Libro mayor de cada silo. Un ingreso viene de una recepción; una salida, " +
                   "del consumo de un lote. La ocupación es la suma, nunca un campo editable.",
      campos: {
        id:        { tipo: "id" },
        siloId:    { tipo: "ref", ref: "silo", req: true },
        tipo:      { tipo: "enum", valores: ["ingreso", "salida", "ajuste"], req: true },
        litros:    { tipo: "decimal", req: true, min: 0 },
        fechaHora: { tipo: "fechaHora", req: true },
        origen:    { tipo: "objeto", etiqueta: "Origen del movimiento",
                     nota: "Qué provocó el movimiento: una recepción, el consumo de un lote o un ajuste",
                     campos: [
                       { clave: "tipo",  etiqueta: "Tipo",  tipo: "enum", valores: ["recepcion", "lote", "ajuste"] },
                       { clave: "refId", etiqueta: "Identificador del registro de origen", tipo: "texto" }
                     ] },
        motivo:    { tipo: "texto", nota: "Obligatorio en ajustes" }
      }
    },

    lote: {
      etiqueta: "Lote de producción", grupo: "transaccional",
      descripcion: "Unidad de producción y de liberación. Su identidad la asigna el sistema: " +
                   "'codigoLote' es el correlativo de planta y se repite entre productos y días.",
      campos: {
        id:            { tipo: "id" },
        codigoLote:    { tipo: "texto", req: true, nota: "Correlativo de planta. NO es único." },
        op:            { tipo: "texto", nota: "Orden de producción, si existe" },
        productoId:    { tipo: "ref", ref: "producto", req: true },
        fecha:         { tipo: "fecha", req: true },
        linea:         { tipo: "enum", valores: CATALOGOS.lineas },
        turno:         { tipo: "enum", valores: CATALOGOS.turnos },
        kgProducidos:  { tipo: "decimal", req: true, min: 0 },
        bultos:        { tipo: "entero", min: 0, nota: "Bolsas o cajas" },
        horaInicio:    { tipo: "hora" },
        horaTermino:   { tipo: "hora" },
        vencimiento:   { tipo: "fecha" },
        estado:        { tipo: "enum", valores: ESTADOS.lote.valores, def: ESTADOS.lote.inicial },
        observacion:   { tipo: "texto" }
      },
      indices: [{ campos: ["codigoLote", "productoId", "fecha"], unico: true }],
      derivados: {
        resultadoCalidad: "Dominio.resultadoCalidadLote() — nunca se persiste",
        kgDisponibles:    "kgProducidos menos lo despachado"
      }
    },

    analisis: {
      etiqueta: "Análisis de calidad", grupo: "transaccional",
      descripcion: "Medición fisicoquímica de un lote. Puede haber varias por lote (una por " +
                   "muestra o por despacho); el veredicto del lote las agrega.",
      campos: {
        id:               { tipo: "id" },
        loteId:           { tipo: "ref", ref: "lote", req: true },
        fecha:            { tipo: "fecha", req: true },
        muestra:          { tipo: "texto", nota: "Identificador de la muestra o del despacho analizado" },
        analistaId:       { tipo: "ref", ref: "usuario" },
        valores:          { tipo: "objeto", req: true, etiqueta: "Parámetros medidos",
                            nota: "Se evalúan contra la especificación vigente del producto",
                            campos: Object.entries(CATALOGOS.parametros).map(([clave, meta]) => ({
                              clave, etiqueta: meta.etiqueta, tipo: "decimal", unidad: meta.unidad
                            })) },
        especificacionId: { tipo: "ref", ref: "especificacion",
                            nota: "Versión usada al evaluar. Se congela para auditoría." },
        observacion:      { tipo: "texto" }
      }
    },

    registroCalidad: {
      etiqueta: "Registro de calidad", grupo: "transaccional",
      descripcion: "Un formulario del checklist, ya completado para un lote concreto. Es el " +
                   "documento digitalizado: guarda los valores tal como se ingresaron, quién " +
                   "los firmó y cuándo.",
      campos: {
        id:              { tipo: "id" },
        loteId:          { tipo: "ref", ref: "lote", req: true },
        documentoId:     { tipo: "ref", ref: "documentoLiberacion", req: true },
        estado:          { tipo: "enum", valores: ["borrador", "completado", "observado"], def: "borrador" },
        valores:         { tipo: "objeto", nota: "{ clave del campo de la plantilla: valor }" },
        referencia:      { tipo: "texto", nota: "N.º del documento físico o externo, si lo hay" },
        completadoPorId: { tipo: "ref", ref: "usuario" },
        completadoEn:    { tipo: "fechaHora" },
        observacion:     { tipo: "texto" }
      },
      indices: [{ campos: ["loteId", "documentoId"], unico: true }],
      derivados: {
        completo: "Dominio.registroCompleto() — todos los campos obligatorios de la plantilla"
      }
    },

    liberacion: {
      etiqueta: "Liberación de producto", grupo: "transaccional",
      descripcion: "Autorización de Calidad para despachar un lote. El avance documental ya no " +
                   "vive aquí: se deriva de los registros de calidad del lote.",
      campos: {
        id:              { tipo: "id" },
        loteId:          { tipo: "ref", ref: "lote", req: true },
        estado:          { tipo: "enum", valores: ESTADOS.liberacion.valores, def: ESTADOS.liberacion.inicial },
        autorizadaPorId: { tipo: "ref", ref: "usuario", nota: "Rol calidad o admin" },
        autorizadaEn:    { tipo: "fechaHora" },
        concesion:       { tipo: "booleano", def: false },
        motivoConcesion: { tipo: "texto", nota: "Obligatorio si concesion = true" },
        observacion:     { tipo: "texto" }
      },
      indices: [{ campos: ["loteId"], unico: true }]
    },

    despacho: {
      etiqueta: "Despacho", grupo: "transaccional",
      descripcion: "Salida física de producto. Solo se emite contra un lote liberado y " +
                   "por kilos que el lote todavía tenga disponibles.",
      campos: {
        id:            { tipo: "id" },
        loteId:        { tipo: "ref", ref: "lote", req: true },
        gd:            { tipo: "texto", nota: "Guía de despacho. Texto: puede llevar ceros a la izquierda." },
        oc:            { tipo: "texto" },
        fecha:         { tipo: "fecha", req: true },
        destino:       { tipo: "texto", req: true },
        kg:            { tipo: "decimal", req: true, min: 0 },
        bultos:        { tipo: "entero", min: 0 },
        vehiculoId:    { tipo: "ref", ref: "vehiculo" },
        estado:        { tipo: "enum", valores: ESTADOS.despacho.valores, def: ESTADOS.despacho.inicial },
        observacion:   { tipo: "texto" }
      }
    },

    /* ===== Planificación ===== */

    codigoProduccion: {
      etiqueta: "Código de producción", grupo: "maestro", rotulo: "codigo",
      descripcion: "Receta programable: qué se produce, en qué evaporador, para qué mandante " +
                   "y cuántos litros de leche consume por hora. Origen: hoja BD del Excel.",
      campos: {
        id:            { tipo: "id" },
        codigo:        { tipo: "texto", req: true, nota: "Ej: RCSH2N" },
        productoId:    { tipo: "ref", ref: "producto", nota: "Enlaza con el catálogo real de productos" },
        mandanteId:    { tipo: "ref", ref: "mandante" },
        formato:       { tipo: "enum", valores: CATALOGOS.formatos },
        categoria:     { tipo: "enum", valores: Object.keys(CATALOGOS.categoriasConsumo),
                         req: true, nota: "A qué fila de CONSUMO del balance suma" },
        rendimientoLh: { tipo: "decimal", req: true, min: 0, nota: "Litros de leche por hora de proceso" },
        activo:        { tipo: "booleano", def: true }
      },
      indices: [{ campos: ["codigo"], unico: true }]
    },

    semanaPlan: {
      etiqueta: "Semana de planificación", grupo: "transaccional", rotulo: "codigo",
      descripcion: "Cabecera de una semana programada. Agrupa los bloques del programa horario " +
                   "y el balance de leche de cada día.",
      campos: {
        id:          { tipo: "id" },
        codigo:      { tipo: "texto", req: true, nota: "Ej: W7" },
        anio:        { tipo: "entero", req: true },
        fechaInicio: { tipo: "fecha", req: true, nota: "Lunes de la semana" },
        dias:        { tipo: "entero", def: 6, min: 1, max: 7, nota: "6 = lunes a sábado" },
        estado:      { tipo: "enum", valores: ESTADOS.semanaPlan.valores, def: ESTADOS.semanaPlan.inicial },
        observacion: { tipo: "texto" }
      },
      indices: [{ campos: ["codigo", "anio"], unico: true }]
    },

    bloquePlan: {
      etiqueta: "Bloque de programa", grupo: "transaccional",
      descripcion: "Un tramo de horas ocupado en un equipo. Sustituye a las celdas pintadas del " +
                   "Excel por un intervalo explícito.",
      campos: {
        id:           { tipo: "id" },
        semanaId:     { tipo: "ref", ref: "semanaPlan", req: true },
        equipo:       { tipo: "enum", valores: Object.keys(CATALOGOS.equipos), req: true },
        dia:          { tipo: "entero", req: true, min: 0, max: 6, nota: "0 = lunes" },
        horaInicio:   { tipo: "decimal", req: true, min: 0, max: 24, nota: "Admite medias horas: 8.5" },
        horaFin:      { tipo: "decimal", req: true, min: 0, max: 24 },
        tipo:         { tipo: "enum", valores: ["produccion", "estado"], req: true, def: "produccion" },
        codigoId:     { tipo: "ref", ref: "codigoProduccion", nota: "Obligatorio si el tipo es producción" },
        estadoEquipo: { tipo: "enum", valores: Object.keys(CATALOGOS.estadosEquipo),
                        nota: "Obligatorio si el tipo es estado" },
        cantidadKg:   { tipo: "decimal", min: 0, nota: "Objetivo de kilos, opcional" },
        observacion:  { tipo: "texto" }
      },
      derivados: {
        litrosConsumidos: "horas × rendimiento del código, solo si el equipo es un evaporador"
      }
    },

    balanceDia: {
      etiqueta: "Balance de leche del día", grupo: "transaccional",
      descripcion: "Guarda únicamente lo que se ingresa a mano. El consumo y los saldos son " +
                   "derivados del programa horario y nunca se persisten.",
      campos: {
        id:                    { tipo: "id" },
        semanaId:              { tipo: "ref", ref: "semanaPlan", req: true },
        dia:                   { tipo: "entero", req: true, min: 0, max: 6 },
        stockInicial:          { tipo: "decimal", min: 0, nota: "Solo el del primer día; el resto se arrastra" },
        stockInicialPorOrigen: { tipo: "objeto", etiqueta: "Stock de apertura por origen",
                                 nota: "Solo el primer día; después se arrastra",
                                 campos: [
                                   { clave: "ccaa",   etiqueta: "CCAA",     tipo: "decimal", unidad: "L" },
                                   { clave: "nestle", etiqueta: "Nestlé",   tipo: "decimal", unidad: "L" },
                                   { clave: "punion", etiqueta: "P. Unión", tipo: "decimal", unidad: "L" }
                                 ] },
        recepcionCCAA:         { tipo: "decimal", def: 0 },
        recepcionNestle:       { tipo: "decimal", def: 0 },
        recepcionPUnion:       { tipo: "decimal", def: 0 },
        trasvasije:            { tipo: "decimal", def: 0, nota: "Manual: no sale de ningún bloque" },
        cremaDisponibleTon:    { tipo: "decimal", min: 0 },
        ajustes:               { tipo: "objeto", etiqueta: "Ajustes por origen",
                                 nota: "Correcciones puntuales en litros; admiten valores negativos",
                                 campos: [
                                   { clave: "ccaa",   etiqueta: "CCAA",     tipo: "decimal", unidad: "L" },
                                   { clave: "nestle", etiqueta: "Nestlé",   tipo: "decimal", unidad: "L" },
                                   { clave: "punion", etiqueta: "P. Unión", tipo: "decimal", unidad: "L" }
                                 ] },
        observacion:           { tipo: "texto" }
      },
      indices: [{ campos: ["semanaId", "dia"], unico: true }],
      derivados: {
        consumoPorCategoria: "Planificador.consumoDia() — desde los bloques de evaporadores",
        totalDisponible:     "stock inicial + recepciones",
        totalConsumo:        "suma de las categorías",
        stockFinal:          "disponible − consumo; se arrastra al día siguiente"
      }
    },

    asignacionTurno: {
      etiqueta: "Asignación de turno", grupo: "transaccional",
      descripcion: "Una persona asignada a un turno de un día de la semana. La dotación " +
                   "necesaria se deduce del programa de producción: sin equipos programados " +
                   "en un turno, no hace falta gente.",
      campos: {
        id:          { tipo: "id" },
        semanaId:    { tipo: "ref", ref: "semanaPlan", req: true },
        dia:         { tipo: "entero", req: true, min: 0, max: 6, nota: "0 = lunes" },
        turno:       { tipo: "enum", valores: CATALOGOS.turnos, req: true },
        usuarioId:   { tipo: "ref", ref: "usuario", req: true },
        funcion:     { tipo: "enum", valores: Object.keys(CATALOGOS.funcionesTurno), req: true, def: "operador" },
        equipo:      { tipo: "enum", valores: Object.keys(CATALOGOS.equipos),
                       nota: "Equipo a cargo, si aplica" },
        observacion: { tipo: "texto" }
      },
      indices: [{ campos: ["semanaId", "dia", "turno", "usuarioId"], unico: true }]
    },

    /* ===== Sistema ===== */

    eventoAuditoria: {
      etiqueta: "Evento de auditoría", grupo: "sistema", soloLectura: true,
      descripcion: "Registro inmutable de cambios. Lo escribe el repositorio, nunca la UI.",
      campos: {
        id:        { tipo: "id" },
        entidad:   { tipo: "texto", req: true },
        entidadId: { tipo: "texto", req: true },
        accion:    { tipo: "enum", valores: ["crear", "actualizar", "eliminar"], req: true },
        usuarioId: { tipo: "ref", ref: "usuario" },
        fechaHora: { tipo: "fechaHora", req: true },
        antes:     { tipo: "objeto", nulo: true },
        despues:   { tipo: "objeto", nulo: true }
      }
    }
  };

  /* ============================================================
     Validación de instancias contra el esquema
     ============================================================ */

  const esVacio = v => v === null || v === undefined || v === "";

  function validarCampo(nombre, def, valor) {
    const errores = [];
    const etq = def.etiqueta || nombre;

    if (esVacio(valor)) {
      if (def.req && def.def === undefined) errores.push(`${etq}: es obligatorio.`);
      return errores;
    }

    switch (def.tipo) {
      case "entero":
        if (!Number.isInteger(Number(valor))) errores.push(`${etq}: debe ser un número entero.`);
        break;
      case "decimal":
        if (isNaN(Number(valor))) errores.push(`${etq}: debe ser numérico.`);
        break;
      case "fecha":
        if (!/^\d{4}-\d{2}-\d{2}$/.test(String(valor))) errores.push(`${etq}: use formato YYYY-MM-DD.`);
        break;
      case "hora":
        if (!/^\d{2}:\d{2}(:\d{2})?$/.test(String(valor))) errores.push(`${etq}: use formato HH:MM.`);
        break;
      case "booleano":
        if (typeof valor !== "boolean") errores.push(`${etq}: debe ser verdadero o falso.`);
        break;
      case "enum":
        if (!def.valores.includes(valor)) errores.push(`${etq}: "${valor}" no es un valor admitido.`);
        break;
      case "lista":
        if (!Array.isArray(valor)) errores.push(`${etq}: debe ser una lista.`);
        break;
      case "objeto":
        if (typeof valor !== "object" || Array.isArray(valor)) errores.push(`${etq}: debe ser un objeto.`);
        // Un objeto obligatorio sin ninguna clave está tan vacío como un campo
        // en blanco: un análisis sin parámetros o una especificación sin rangos
        // no significan nada.
        else if (def.req && Object.keys(valor).length === 0) errores.push(`${etq}: es obligatorio.`);
        break;
    }

    if (def.min !== undefined && Number(valor) < def.min) errores.push(`${etq}: no puede ser menor que ${def.min}.`);
    if (def.max !== undefined && Number(valor) > def.max) errores.push(`${etq}: no puede ser mayor que ${def.max}.`);

    return errores;
  }

  /** Valida un objeto contra su entidad. Devuelve { valido, errores[] }.
   *  No consulta la base: las referencias se verifican en el repositorio. */
  function validar(entidad, obj) {
    const def = ENTIDADES[entidad];
    if (!def) return { valido: false, errores: [`Entidad desconocida: ${entidad}`] };

    const errores = [];
    for (const [nombre, campo] of Object.entries(def.campos)) {
      errores.push(...validarCampo(nombre, campo, obj[nombre]));
    }
    const desconocidos = Object.keys(obj).filter(k => !def.campos[k]);
    if (desconocidos.length) errores.push(`Campos no definidos en el esquema: ${desconocidos.join(", ")}.`);

    return { valido: errores.length === 0, errores };
  }

  /** Rellena los valores por defecto declarados en el esquema. */
  function conDefectos(entidad, obj) {
    const def = ENTIDADES[entidad];
    if (!def) return obj;
    const salida = Object.assign({}, obj);
    for (const [nombre, campo] of Object.entries(def.campos)) {
      if (esVacio(salida[nombre]) && campo.def !== undefined) salida[nombre] = campo.def;
    }
    return salida;
  }

  /** ¿Es válido pasar de un estado a otro, según las transiciones declaradas? */
  function transicionValida(maquina, desde, hasta) {
    const m = ESTADOS[maquina];
    if (!m) return false;
    if (desde === hasta) return true;
    return (m.transiciones[desde] || []).includes(hasta);
  }

  /** Referencias salientes de una entidad: { campo: entidadDestino } */
  function referencias(entidad) {
    const def = ENTIDADES[entidad];
    if (!def) return {};
    const refs = {};
    for (const [nombre, campo] of Object.entries(def.campos)) {
      if (campo.tipo === "ref") refs[nombre] = campo.ref;
    }
    return refs;
  }

  return {
    version: "1.0.0",
    TIPOS, CATALOGOS, ESTADOS, ENTIDADES,
    nombres: Object.keys(ENTIDADES),
    validar, conDefectos, transicionValida, referencias
  };
})();

if (typeof module !== "undefined" && module.exports) module.exports = Esquema;
