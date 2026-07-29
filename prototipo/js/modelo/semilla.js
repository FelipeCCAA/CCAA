/* ============================================================
   Semilla — traduce los datos de ejemplo al modelo nuevo
   ------------------------------------------------------------
   Toma DATOS_SEMILLA (formato plano, derivado de los Excel) y lo
   convierte en las entidades del esquema. Es, en pequeño, el mismo
   trabajo que hará el importador de Produccion.xlsx: sirve de
   plantilla y prueba que el modelo aguanta los datos reales.

   Conversión clave: una fila del Excel NO es un lote, es un DESPACHO.
   Las filas se agrupan por (codigoLote + producto + fecha) para formar
   el lote, y cada fila origina su propio despacho y su propio análisis.
   ============================================================ */

const Semilla = (() => {

  const slug = t => String(t).toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")   // quita tildes
    .replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 40);

  const numeroONulo = v => {
    if (v === null || v === undefined || v === "") return null;
    const n = Number(v);
    return isNaN(n) ? null : n;
  };
  const enteroONulo = v => {
    const n = numeroONulo(v);
    return n === null ? null : Math.round(n);
  };
  const textoOVacio = v => (v === null || v === undefined) ? "" : String(v);

  /* ---------- Clasificaciones ---------- */

  function familiaDe(nombreProducto) {
    const p = nombreProducto.toUpperCase();
    // El polvo se comprueba primero y "CREMA" exige límites de palabra:
    // "SEMIDESCREMADO" contiene "CREMA" y no es una crema.
    if (p.startsWith("P. ") || /\b(POLVO|LEP|RWK|SUERO)\b/.test(p)) return "polvo";
    if (/\bCREMAS?\b/.test(p))                                      return "crema";
    if (p.includes("MANTEQUILLA"))                                  return "otro";
    if (p.includes("LECHE ESTANDARIZADA"))                          return "liquido";
    return "otro";
  }

  function mandanteDe(nombreProducto) {
    const p = nombreProducto.toUpperCase();
    if (p.includes("NESTL")) return "Nestlé";
    if (p.includes("COLUN")) return "Colun";
    if (p.includes("NEBE"))  return "Lácteos Nebe";
    return "CCAA";
  }

  /** Capacidades provisorias por tipo de contenedor.
   *  No vienen de los Excel: hay que confirmarlas con planta.
   *  Ahora son editables desde la pantalla de Administración. */
  function perfilSilo(codigo) {
    if (codigo.startsWith("TK CREMA")) return { tipo: "tk_crema", capacidadL: 30000 };
    if (codigo.startsWith("TK LD"))    return { tipo: "tk_ld",    capacidadL: 100000 };
    return { tipo: "silo", capacidadL: 150000 };
  }

  /** Documentos que solo aplican a las líneas de polvo.
   *  Pendiente de confirmar con Calidad; el campo existe para eso. */
  const SOLO_POLVO = /rovema|pulverizaci|uperizaci|evaporador|detector de metales|hermeticidad/i;

  /* ---------- Plantillas de los formularios de liberación ----------
     PROVISORIAS: reproducen lo que el nombre del documento deja suponer,
     no los formularios oficiales de planta. Son editables desde
     Administración → Documento de liberación, sin tocar código.

     `origen`    rellena el campo desde el lote (no se vuelve a teclear).
     `parametro` permite cotejar lo escrito contra el análisis y la
                 especificación vigente. Ahí está el valor de digitalizar. */

  const SI_NO = { tipo: "enum", valores: ["Conforme", "No conforme"], req: true };
  const OBS   = { clave: "observacion", etiqueta: "Observaciones", tipo: "texto" };

  const PLANTILLAS = [
    { patron: /planilla de instructivo/i, campos: [
      { clave: "lote", etiqueta: "Lote", tipo: "texto", req: true, origen: "lote.codigoLote" },
      { clave: "turnoRecepcion", etiqueta: "Turno de recepción", tipo: "enum", valores: ["A", "B", "C"], req: true },
      Object.assign({ clave: "verificado", etiqueta: "Verificación documental" }, SI_NO), OBS ] },

    { patron: /control de proceso \(PCC\)/i, campos: [
      { clave: "tempPasteurizacion", etiqueta: "Temperatura de pasteurización", tipo: "decimal", unidad: "°C", req: true, min: 60, max: 120 },
      { clave: "tiempoRetencion", etiqueta: "Tiempo de retención", tipo: "decimal", unidad: "s", req: true, min: 0 },
      Object.assign({ clave: "resultado", etiqueta: "Resultado del PCC" }, SI_NO), OBS ] },

    { patron: /cuerpos extra.os evaporadores/i, campos: [
      Object.assign({ clave: "inspeccion", etiqueta: "Inspección visual" }, SI_NO),
      { clave: "hallazgos", etiqueta: "Hallazgos", tipo: "texto" }, OBS ] },

    { patron: /pulverizaci.n/i, campos: [
      { clave: "presionBomba", etiqueta: "Presión de bomba", tipo: "decimal", unidad: "bar", req: true, min: 0 },
      { clave: "tempEntrada", etiqueta: "Temperatura de aire de entrada", tipo: "decimal", unidad: "°C", req: true },
      { clave: "tempSalida", etiqueta: "Temperatura de aire de salida", tipo: "decimal", unidad: "°C", req: true }, OBS ] },

    { patron: /disco de uperizaci.n/i, campos: [
      { clave: "tempMaxima", etiqueta: "Temperatura máxima registrada", tipo: "decimal", unidad: "°C", req: true },
      { clave: "discoArchivado", etiqueta: "Disco archivado", tipo: "booleano", req: true }, OBS ] },

    { patron: /inspecci.n preoperativa/i, campos: [
      { clave: "linea", etiqueta: "Línea", tipo: "enum", valores: ["E1", "E2", "Ambas"], req: true },
      Object.assign({ clave: "resultado", etiqueta: "Resultado de la inspección" }, SI_NO), OBS ] },

    { patron: /conexi.n de tierra/i, campos: [
      { clave: "resistencia", etiqueta: "Resistencia medida", tipo: "decimal", unidad: "Ω", req: true, min: 0, max: 100 },
      Object.assign({ clave: "continuidad", etiqueta: "Continuidad" }, SI_NO), OBS ] },

    // El más valioso: sus campos se cotejan contra el análisis del lote.
    { patron: /fisicoqu.micos/i, campos: [
      { clave: "humedad", etiqueta: "Humedad", tipo: "decimal", unidad: "%", parametro: "humedad" },
      { clave: "mg", etiqueta: "Materia grasa", tipo: "decimal", unidad: "%", req: true, parametro: "mg" },
      { clave: "st", etiqueta: "Sólidos totales", tipo: "decimal", unidad: "%", parametro: "st" },
      { clave: "acidez", etiqueta: "Acidez", tipo: "decimal", unidad: "°D", parametro: "acidez" },
      { clave: "ph", etiqueta: "pH", tipo: "decimal", parametro: "ph" }, OBS ] },

    { patron: /filtros de limpieza/i, campos: [
      { clave: "filtrosRevisados", etiqueta: "Filtros revisados", tipo: "entero", req: true, min: 0 },
      Object.assign({ clave: "estado", etiqueta: "Estado de los filtros" }, SI_NO), OBS ] },

    { patron: /PPRO E1 y E2/i, campos: [
      Object.assign({ clave: "resultado", etiqueta: "Monitoreo de PPRO" }, SI_NO),
      { clave: "desviaciones", etiqueta: "Desviaciones detectadas", tipo: "entero", min: 0 }, OBS ] },

    { patron: /PPRO Rovemas/i, campos: [
      Object.assign({ clave: "rovema3", etiqueta: "Rovema 3" }, SI_NO),
      Object.assign({ clave: "rovema4", etiqueta: "Rovema 4" }, SI_NO), OBS ] },

    { patron: /cuerpos extra.os Rovema/i, campos: [
      Object.assign({ clave: "inspeccion", etiqueta: "Inspección de envasadoras" }, SI_NO), OBS ] },

    { patron: /FEFO/i, campos: [
      { clave: "loteMasAntiguo", etiqueta: "Lote más antiguo en bodega", tipo: "texto", req: true },
      { clave: "cumpleFEFO", etiqueta: "Se respeta el orden FEFO", tipo: "booleano", req: true }, OBS ] },

    { patron: /detector de metales/i, campos: [
      { clave: "patronFe", etiqueta: "Patrón Fe detectado", tipo: "booleano", req: true },
      { clave: "patronNoFe", etiqueta: "Patrón No-Fe detectado", tipo: "booleano", req: true },
      { clave: "patronSS", etiqueta: "Patrón acero inoxidable detectado", tipo: "booleano", req: true },
      { clave: "rechazoVerificado", etiqueta: "Sistema de rechazo verificado", tipo: "booleano", req: true }, OBS ] },

    { patron: /consumo de materiales/i, campos: [
      { clave: "bolsasUsadas", etiqueta: "Bolsas utilizadas", tipo: "entero", req: true, min: 0 },
      { clave: "merma", etiqueta: "Merma", tipo: "decimal", unidad: "%", min: 0, max: 100 }, OBS ] },

    { patron: /hermeticidad y peso neto/i, campos: [
      { clave: "muestras", etiqueta: "Muestras controladas", tipo: "entero", req: true, min: 1 },
      { clave: "pesoNetoPromedio", etiqueta: "Peso neto promedio", tipo: "decimal", unidad: "kg", req: true, min: 0 },
      Object.assign({ clave: "hermeticidad", etiqueta: "Hermeticidad" }, SI_NO), OBS ] },

    { patron: /evaluaci.n sensorial/i, campos: [
      { clave: "olor", etiqueta: "Olor", tipo: "enum", valores: ["Característico", "Extraño"], req: true },
      { clave: "sabor", etiqueta: "Sabor", tipo: "enum", valores: ["Característico", "Extraño"], req: true },
      { clave: "color", etiqueta: "Color", tipo: "enum", valores: ["Característico", "Anormal"], req: true },
      { clave: "aspecto", etiqueta: "Aspecto", tipo: "enum", valores: ["Homogéneo", "Grumoso"], req: true },
      Object.assign({ clave: "veredicto", etiqueta: "Veredicto sensorial" }, SI_NO), OBS ] },

    { patron: /laboratorio externo/i, campos: [
      { clave: "laboratorio", etiqueta: "Laboratorio", tipo: "texto", req: true },
      { clave: "numeroInforme", etiqueta: "N.º de informe", tipo: "texto", req: true },
      { clave: "fechaInforme", etiqueta: "Fecha del informe", tipo: "fecha", req: true },
      Object.assign({ clave: "resultado", etiqueta: "Resultado microbiológico" }, SI_NO), OBS ] },

    { patron: /certificado de an.lisis/i, campos: [
      { clave: "lote", etiqueta: "Lote", tipo: "texto", req: true, origen: "lote.codigoLote" },
      { clave: "producto", etiqueta: "Producto", tipo: "texto", req: true, origen: "producto.nombre" },
      { clave: "fechaElaboracion", etiqueta: "Fecha de elaboración", tipo: "fecha", req: true, origen: "lote.fecha" },
      { clave: "numeroCertificado", etiqueta: "N.º de certificado", tipo: "texto", req: true },
      { clave: "mg", etiqueta: "Materia grasa declarada", tipo: "decimal", unidad: "%", req: true, parametro: "mg" }, OBS ] }
  ];

  function plantillaPara(nombre) {
    const encontrada = PLANTILLAS.find(p => p.patron.test(nombre));
    return encontrada ? encontrada.campos : [
      Object.assign({ clave: "verificado", etiqueta: "Verificación" }, SI_NO),
      { clave: "referencia", etiqueta: "Referencia del documento físico", tipo: "texto" }, OBS
    ];
  }

  /* ============================================================
     Construcción
     ============================================================ */

  function construir(origen) {
    const d = origen || (typeof DATOS_SEMILLA !== "undefined" ? DATOS_SEMILLA : null);
    if (!d) throw new Error("No hay datos de origen para construir la semilla.");

    const db = {};
    for (const nombre of Esquema.nombres) db[nombre] = [];
    db._meta = { version: Esquema.version, origen: "DATOS_SEMILLA", nota: "Datos de ejemplo reales (parciales)." };

    /* ---------- Mandantes ---------- */
    const nombresMandante = new Set(d.catalogos.mandantes || []);
    (d.produccion || []).forEach(r => nombresMandante.add(mandanteDe(r.producto)));
    const mandantePorNombre = {};
    for (const nombre of nombresMandante) {
      const id = "man_" + slug(nombre);
      mandantePorNombre[nombre] = id;
      db.mandante.push({ id, nombre, activo: true });
    }

    /* ---------- Productos ----------
       Se añaden la materia prima y los intermedios que la cadena de recetas
       necesita nombrar: sin «Leche fresca» no hay de qué partir. */
    const LECHE = "Leche fresca";
    const PRECONDENSADO = "Precondensado";
    const MANTEQUILLA = "Mantequilla sin Sal";

    const nombresProducto = new Set(d.catalogos.productos || []);
    (d.produccion || []).forEach(r => nombresProducto.add(r.producto));
    [LECHE, PRECONDENSADO, MANTEQUILLA].forEach(n => nombresProducto.add(n));

    const naturalezaDe = nombre => {
      if (nombre === LECHE) return "materia_prima";
      if (nombre === PRECONDENSADO || familiaDe(nombre) === "crema") return "intermedio";
      return "terminado";
    };
    const unidadBaseDe = nombre => (nombre === LECHE ? "L" : "kg");

    const productoPorNombre = {};
    for (const nombre of nombresProducto) {
      const id = "pro_" + slug(nombre);
      productoPorNombre[nombre] = id;
      db.producto.push({
        id, codigo: "", nombre,
        familia: familiaDe(nombre),
        naturaleza: naturalezaDe(nombre),
        unidadBase: unidadBaseDe(nombre),
        mandanteId: mandantePorNombre[mandanteDe(nombre)],
        activo: true
      });
    }

    /* ---------- Recetas ----------
       Solo las dos primeras vienen dadas por Producción. Las de polvo y
       precondensado son estimaciones de orden de magnitud y van marcadas
       como provisorias: se corrigen desde Administración → Recetas. */
    const RECETAS = [
      { producto: "Crema 42% CCAA", cantidadBase: 1,
        componentes: [{ producto: LECHE, cantidad: 4, unidad: "L" }],
        fuente: "Indicada por Producción: 4 L de leche fresca por kilo de crema" },

      { producto: MANTEQUILLA, cantidadBase: 1,
        componentes: [{ producto: "Crema 42% CCAA", cantidad: 2, unidad: "kg" }],
        fuente: "Indicada por Producción: 2 kg de crema por kilo de mantequilla" },

      { producto: PRECONDENSADO, cantidadBase: 1,
        componentes: [{ producto: LECHE, cantidad: 3.7, unidad: "L" }],
        fuente: "PROVISORIA — confirmar con Producción" },

      { producto: "P. Entero ST 48%", cantidadBase: 1,
        componentes: [{ producto: LECHE, cantidad: 8.5, unidad: "L" }],
        fuente: "PROVISORIA — confirmar con Producción" },

      { producto: "P. Semidescremado ST 45% CCAA", cantidadBase: 1,
        componentes: [{ producto: LECHE, cantidad: 9.5, unidad: "L" }],
        fuente: "PROVISORIA — confirmar con Producción" },

      { producto: "LEP NESTLÉ", cantidadBase: 1,
        componentes: [{ producto: LECHE, cantidad: 8.5, unidad: "L" }],
        fuente: "PROVISORIA — confirmar con Producción" }
    ];

    RECETAS.forEach(r => {
      const productoId = productoPorNombre[r.producto];
      if (!productoId) return;
      db.receta.push({
        id: "rec_" + slug(r.producto) + "_v1",
        productoId,
        version: 1,
        vigenteDesde: "2025-01-01",
        vigenteHasta: null,
        cantidadBase: r.cantidadBase,
        componentes: r.componentes
          .filter(c => productoPorNombre[c.producto])
          .map(c => ({ productoId: productoPorNombre[c.producto], cantidad: c.cantidad, unidad: c.unidad, merma: 0 })),
        fuente: r.fuente,
        observacion: ""
      });
    });

    /* ---------- Especificaciones ----------
       Las claves antiguas eran nombres de producto y no siempre calzaban
       (existía "P. Semidescremado ST 45%" cuando el producto real es
       "...45% CCAA"). Aquí se asignan por coincidencia laxa, de modo que
       ninguna especificación quede huérfana ni ningún producto sin evaluar
       por una diferencia de texto. */
    const specs = d.catalogos.especificaciones || {};
    let nSpec = 0;
    for (const [claveSpec, rangosViejos] of Object.entries(specs)) {
      const objetivo = Object.keys(productoPorNombre).find(n =>
        n === claveSpec || n.startsWith(claveSpec) || claveSpec.startsWith(n)
      );
      if (!objetivo) continue;

      const rangos = {};
      for (const [param, par] of Object.entries(rangosViejos)) {
        if (!Array.isArray(par)) continue;
        rangos[param] = { min: par[0], max: par[1], obligatorio: false };
      }
      db.especificacion.push({
        id: "esp_" + slug(objetivo) + "_v1",
        productoId: productoPorNombre[objetivo],
        version: 1,
        vigenteDesde: "2025-01-01",
        vigenteHasta: null,
        rangos,
        fuente: "Referencial — pendiente de validar con Calidad"
      });
      nSpec++;
    }

    /* ---------- Silos ---------- */
    const siloPorCodigo = {};
    (d.catalogos.silos || []).forEach(codigo => {
      const id = "sil_" + slug(codigo);
      siloPorCodigo[codigo] = id;
      db.silo.push(Object.assign({ id, codigo, activo: true }, perfilSilo(codigo)));
    });

    /* ---------- Vehículos ---------- */
    const vehiculoPorPlaca = {};
    (d.maestros || []).forEach((m, i) => {
      const placa = textoOVacio(m.placa).trim() || `SIN-PLACA-${i + 1}`;
      const id = "veh_" + slug(placa);
      vehiculoPorPlaca[placa.replace(/\s/g, "")] = id;
      db.vehiculo.push({
        id,
        numero: textoOVacio(m.vehiculo),
        placa,
        tipo: m.tipo || "Camión",
        capacidadL: numeroONulo(m.capacidad),
        transportista: textoOVacio(m.transportista),
        choferAM: textoOVacio(m.choferAM),
        choferPM: textoOVacio(m.choferPM),
        activo: true
      });
    });

    /* ---------- Usuarios ---------- */
    const usuarioPorNombre = {};
    const agregarUsuario = (nombre, rol) => {
      if (!nombre) return null;
      if (usuarioPorNombre[nombre]) return usuarioPorNombre[nombre];
      const id = "usu_" + slug(nombre);
      usuarioPorNombre[nombre] = id;
      db.usuario.push({ id, nombre, rol, activo: true });
      return id;
    };
    (d.catalogos.operadores || []).forEach(n => agregarUsuario(n, "recepcion"));
    (d.liberaciones || []).forEach(l => agregarUsuario(l.especialista, "calidad"));
    agregarUsuario("Soporte TI", "admin");
    agregarUsuario("Programación de planta", "produccion");

    /* ---------- Documentos de liberación ---------- */
    const documentoPorNombre = {};
    (d.catalogos.documentosLiberacion || []).forEach((nombre, i) => {
      const id = "doc_" + slug(nombre);
      documentoPorNombre[nombre] = id;
      const codigo = (nombre.match(/^[A-Z0-9.]+FORM[0-9.]*/i) || [""])[0];
      db.documentoLiberacion.push({
        id, codigo, nombre,
        aplicaA: SOLO_POLVO.test(nombre) ? ["polvo"] : ["polvo", "crema", "liquido", "otro"],
        instruccion: "",
        plantilla: plantillaPara(nombre),
        fuente: "Plantilla provisoria — reemplazar por el formulario oficial de Calidad",
        orden: i + 1,
        activo: true
      });
    });

    /* ---------- Producción: lotes + análisis + despachos ---------- */
    const PARAMETROS = ["humedad", "mg", "sng", "st", "acidez", "ph", "temperatura", "pesoEsp", "proteina"];
    const lotePorClave = {};

    (d.produccion || []).forEach((fila, i) => {
      const productoId = productoPorNombre[fila.producto];
      if (!productoId) return;

      const codigoLote = textoOVacio(fila.lote).trim() || `S/C-${fila.fecha}`;
      const clave = `${codigoLote}|${productoId}|${fila.fecha}`;

      let lote = lotePorClave[clave];
      if (!lote) {
        lote = {
          id: "lot_" + slug(clave) + "_" + i,
          codigoLote,
          op: textoOVacio(fila.op),
          productoId,
          fecha: fila.fecha,
          linea: fila.linea || "",
          turno: "",
          kgProducidos: 0,
          bultos: null,
          horaInicio: fila.horaInicio || "",
          horaTermino: fila.horaTermino || "",
          vencimiento: fila.vencimiento || "",
          estado: "producido",
          observacion: textoOVacio(fila.observacion)
        };
        lotePorClave[clave] = lote;
        db.lote.push(lote);
      }

      // Cada fila aporta sus kilos al lote…
      lote.kgProducidos += numeroONulo(fila.kg) || 0;
      const bultos = enteroONulo(fila.bolsas);
      if (bultos !== null) lote.bultos = (lote.bultos || 0) + bultos;

      // …su análisis, si trae parámetros…
      const valores = {};
      PARAMETROS.forEach(p => { const v = numeroONulo(fila[p]); if (v !== null) valores[p] = v; });
      if (Object.keys(valores).length) {
        db.analisis.push({
          id: "ana_" + lote.id + "_" + i,
          loteId: lote.id,
          fecha: fila.fecha,
          muestra: fila.gd ? `GD ${fila.gd}` : `Muestra ${i + 1}`,
          analistaId: null,
          valores,
          especificacionId: null,
          observacion: ""
        });
      }

      // …y su despacho, si salió efectivamente de planta.
      const kg = numeroONulo(fila.kg);
      if (fila.gd && kg && textoOVacio(fila.destino).trim()) {
        db.despacho.push({
          id: "des_" + lote.id + "_" + i,
          loteId: lote.id,
          gd: textoOVacio(fila.gd),
          oc: textoOVacio(fila.oc),
          fecha: fila.fecha,
          destino: fila.destino,
          kg,
          bultos: enteroONulo(fila.bolsas),
          vehiculoId: null,
          estado: "emitido",
          observacion: ""
        });
      }
    });

    /* ---------- Recepciones + movimientos de silo ---------- */
    (d.recepcion || []).forEach((r, i) => {
      const siloId = siloPorCodigo[r.silo] || null;
      const id = "rec_" + slug(r.id || `r${i}`);
      const litros = numeroONulo(r.litros) || 0;

      db.recepcion.push({
        id,
        fecha: r.fecha,
        hora: "",
        guia: textoOVacio(r.id),
        vehiculoId: vehiculoPorPlaca[textoOVacio(r.camion).replace(/\s/g, "")] || null,
        procedencia: r.procedencia === "P Unión" ? "P. Unión" : r.procedencia,
        tipoLeche: r.tipoLeche,
        litros,
        siloId,
        operadorId: usuarioPorNombre[r.operador] || null,
        turno: r.turno,
        controles: {
          temperatura: numeroONulo(r.temperatura),
          acidez: numeroONulo(r.acidez),
          ph: numeroONulo(r.ph),
          delvo: r.delvoTest,
          inhibidores: r.inhibidores,
          crioscopia: numeroONulo(r.crioscopia)
        },
        estado: r.estado === "Retenida" ? "retenida" : "descargada",
        motivo: r.estado === "Retenida" ? "Inhibidores positivos en el control de camión." : "",
        observacion: ""
      });

      // Solo la leche liberada entra físicamente al silo.
      if (siloId && r.estado !== "Retenida") {
        db.movimientoSilo.push({
          id: "mov_" + id,
          siloId,
          tipo: "ingreso",
          litros,
          fechaHora: `${r.fecha}T08:00`,
          origen: { tipo: "recepcion", refId: id },
          motivo: ""
        });
      }
    });

    /* ---------- Liberaciones y registros de calidad ---------- */

    const TEXTO_POR_CLAVE = {
      laboratorio:       () => "Laboratorio externo Osorno",
      numeroInforme:     ctx => "INF-" + ctx.lote.codigoLote,
      numeroCertificado: ctx => "CA-" + ctx.lote.codigoLote,
      loteMasAntiguo:    ctx => ctx.lote.codigoLote,
      hallazgos:         () => "Sin hallazgos",
      referencia:        ctx => "REG-" + ctx.lote.codigoLote
    };

    /** Rellena un formulario de ejemplo. Los campos ligados a un parámetro
     *  toman el valor real del análisis del lote, de modo que el cotejo del
     *  sistema no arroje discrepancias falsas en los datos de muestra. */
    function valoresDemo(documento, contexto) {
      const valores = Object.assign({}, Dominio.prellenar(documento, contexto));

      (documento.plantilla || []).forEach(campo => {
        if (valores[campo.clave] !== undefined) return;

        if (campo.parametro && contexto.analisis) {
          const medido = numeroONulo(contexto.analisis.valores[campo.parametro]);
          if (medido !== null) { valores[campo.clave] = medido; return; }
        }
        if (!campo.req) return;

        if (TEXTO_POR_CLAVE[campo.clave]) { valores[campo.clave] = TEXTO_POR_CLAVE[campo.clave](contexto); return; }

        switch (campo.tipo) {
          case "booleano": valores[campo.clave] = true; break;
          case "enum":     valores[campo.clave] = campo.valores[0]; break;
          case "entero":   valores[campo.clave] = campo.min !== undefined ? Math.max(1, campo.min) : 12; break;
          case "decimal":
            valores[campo.clave] = (campo.min !== undefined && campo.max !== undefined)
              ? (campo.min + campo.max) / 2
              : (campo.min !== undefined ? campo.min + 1 : 1);
            break;
          case "fecha":    valores[campo.clave] = contexto.lote.fecha; break;
          default:         valores[campo.clave] = "Conforme";
        }
      });
      return valores;
    }

    function crearRegistros(lote, documentosCumplidos, especialistaId, fecha) {
      const producto = db.producto.find(p => p.id === lote.productoId);
      const analisis = db.analisis.find(a => a.loteId === lote.id) || null;
      const aplicables = Dominio.documentosAplicables(db.documentoLiberacion, producto);

      aplicables.forEach(documento => {
        if (!documentosCumplidos.has(documento.id)) return;
        db.registroCalidad.push({
          id: `rcal_${lote.id}_${documento.id}`,
          loteId: lote.id,
          documentoId: documento.id,
          estado: "completado",
          valores: valoresDemo(documento, { lote, producto, analisis }),
          referencia: "",
          completadoPorId: especialistaId,
          completadoEn: `${fecha}T12:00`,
          observacion: ""
        });
      });
    }

    (d.liberaciones || []).forEach(l => {
      const productoId = productoPorNombre[l.producto];
      const lote = db.lote.find(x => x.codigoLote === l.lote && x.productoId === productoId) ||
                   db.lote.find(x => x.codigoLote === l.lote);
      if (!lote) return;

      const especialistaId = usuarioPorNombre[l.especialista] || null;
      const cumplidos = new Set((l.checklist || [])
        .filter(c => c.completado && documentoPorNombre[c.documento])
        .map(c => documentoPorNombre[c.documento]));

      crearRegistros(lote, cumplidos, especialistaId, l.fecha);

      db.liberacion.push({
        id: "lib_" + slug(l.id),
        loteId: lote.id,
        estado: l.estado === "Liberado" ? "liberado"
              : l.estado === "En revisión" ? "en_revision" : "pendiente",
        autorizadaPorId: l.estado === "Liberado" ? especialistaId : null,
        autorizadaEn: l.estado === "Liberado" ? `${l.fecha}T12:00` : "",
        concesion: false,
        motivoConcesion: "",
        observacion: ""
      });
    });

    // Todo lote producido necesita su expediente, aunque esté vacío.
    db.lote.forEach(lote => {
      if (db.liberacion.some(l => l.loteId === lote.id)) return;
      db.liberacion.push({
        id: "lib_" + lote.id,
        loteId: lote.id,
        estado: "pendiente",
        autorizadaPorId: null,
        autorizadaEn: "",
        concesion: false,
        motivoConcesion: "",
        observacion: ""
      });
    });

    /* ============================================================
       Planificación — catálogo BD y semana W7
       ------------------------------------------------------------
       Los códigos siguen la matriz familia × formato de la hoja BD.
       Los rendimientos (15.900 / 11.000 / 12.400 L·h⁻¹) son los del Excel.
       `productoId` queda sin asignar a propósito: el enlace código→producto
       no está en la hoja y hay que completarlo desde Administración.
       ============================================================ */

    const RENDIMIENTO = { SH2: 15900, SH3: 11000, VEB: 12400 };
    const FAMILIAS = [
      { prefijo: "RC", sufijo: "N", categoria: "prec_nestle",   mandante: "Nestlé" },
      { prefijo: "RC", sufijo: "C", categoria: "prec_ccaa",     mandante: "CCAA" },
      { prefijo: "LN", sufijo: "",  categoria: "secado_nestle", mandante: "Nestlé" },
      { prefijo: "LU", sufijo: "",  categoria: "secado_colun",  mandante: "Colun" },
      { prefijo: "LC", sufijo: "",  categoria: "secado_ccaa",   mandante: "CCAA" }
    ];

    // Qué produce cada familia de código. Sin esto el planificador no puede
    // traducir litros por hora en kilos de producto. Lo que no está claro
    // queda sin asignar a propósito: se completa desde Administración.
    const PRODUCTO_POR_FAMILIA = {
      RC: PRECONDENSADO,
      LN: "LEP NESTLÉ",
      LC: "P. Semidescremado ST 45% CCAA",
      LU: null                       // no hay producto Colun en el catálogo
    };

    const codigoPorNombre = {};
    FAMILIAS.forEach(f => {
      Object.keys(RENDIMIENTO).forEach(formato => {
        const codigo = `${f.prefijo}${formato}${f.sufijo}`;
        const id = "cpr_" + slug(codigo);
        codigoPorNombre[codigo] = id;
        const nombreProducto = PRODUCTO_POR_FAMILIA[f.prefijo];
        db.codigoProduccion.push({
          id, codigo,
          productoId: nombreProducto ? (productoPorNombre[nombreProducto] || null) : null,
          mandanteId: mandantePorNombre[f.mandante] || null,
          formato,
          categoria: f.categoria,
          rendimientoLh: RENDIMIENTO[formato],
          activo: true
        });
      });
    });

    // Semana W7: lunes 9 al sábado 14 de febrero de 2026.
    const SEMANA = "sem_w7_2026";
    db.semanaPlan.push({
      id: SEMANA, codigo: "W7", anio: 2026,
      fechaInicio: "2026-02-09", dias: 6, estado: "borrador",
      observacion: "Semana de ejemplo. Las recepciones diarias son provisorias: " +
                   "no se dispuso del Excel original para cargarlas."
    });

    const CREMA_TON = [12, 6, 6, 24, 12, 8];
    for (let dia = 0; dia < 6; dia++) {
      db.balanceDia.push({
        id: `bal_w7_${dia}`,
        semanaId: SEMANA,
        dia,
        stockInicial: dia === 0 ? 193000 : null,
        stockInicialPorOrigen: dia === 0 ? { ccaa: 80000, nestle: 80000, punion: 33000 } : null,
        recepcionCCAA: 130000,
        recepcionNestle: 130000,
        recepcionPUnion: 100000,
        trasvasije: 0,
        cremaDisponibleTon: CREMA_TON[dia],
        ajustes: null,
        observacion: ""
      });
    }

    const nuevoBloque = (dia, equipo, horaInicio, horaFin, opciones) => {
      db.bloquePlan.push(Object.assign({
        id: `blq_w7_${dia}_${equipo}_${String(horaInicio).replace(".", "_")}`,
        semanaId: SEMANA, equipo, dia, horaInicio, horaFin,
        tipo: "produccion", codigoId: null, estadoEquipo: null,
        cantidadKg: null, observacion: ""
      }, opciones || {}));
    };

    for (let dia = 0; dia < 6; dia++) {
      // Evaporadores: lo único que alimenta el balance de leche.
      nuevoBloque(dia, "scheffers2", 0, 8,  { codigoId: codigoPorNombre.RCSH2N });
      nuevoBloque(dia, "scheffers2", 8, 16, { codigoId: codigoPorNombre.RCSH2C });
      nuevoBloque(dia, "veb",        8, 16, { codigoId: codigoPorNombre.LUVEB });

      // Líneas de secado: se programan, pero NO vuelven a consumir leche cruda.
      nuevoBloque(dia, "linea1", 8, 20, { codigoId: codigoPorNombre.LNSH2 });
      nuevoBloque(dia, "linea2", 0, 12, { codigoId: codigoPorNombre.LCSH3 });
      nuevoBloque(dia, "carga_precondensado", 4, 8, { codigoId: codigoPorNombre.RCSH3C });
    }

    // Paradas y anomalías repartidas en la semana.
    nuevoBloque(0, "veb",         6, 8,  { tipo: "estado", estadoEquipo: "X" });
    nuevoBloque(2, "scheffers3",  0, 24, { tipo: "estado", estadoEquipo: "M" });
    nuevoBloque(3, "veb",        16, 18, { tipo: "estado", estadoEquipo: "P",
                                           observacion: "Corte de vapor." });
    nuevoBloque(4, "scheffers2", 16, 17, { tipo: "estado", estadoEquipo: "A" });
    nuevoBloque(5, "linea1",     20, 21, { tipo: "estado", estadoEquipo: "AP" });

    /* ---------- Asignaciones de turno ----------
       La dotación se deduce del programa recién sembrado. Se cubre el lunes
       completo y el martes a medias, y el resto de la semana queda sin dotar:
       así la cuadrícula de cobertura muestra los tres estados de verdad. */
    const operadores = (d.catalogos.operadores || []).map(n => usuarioPorNombre[n]).filter(Boolean);
    const laboratoristas = (d.liberaciones || [])
      .map(l => usuarioPorNombre[l.especialista]).filter(Boolean);
    let cursorOp = 0, cursorLab = 0;
    const tomarOperador = () => operadores.length ? operadores[cursorOp++ % operadores.length] : null;
    const tomarLab = () => laboratoristas.length ? laboratoristas[cursorLab++ % laboratoristas.length] : null;

    const asignar = (dia, turno, usuarioId, funcion) => {
      if (!usuarioId) return;
      const yaEsta = db.asignacionTurno.some(a =>
        a.semanaId === SEMANA && a.dia === dia && a.turno === turno && a.usuarioId === usuarioId);
      if (yaEsta) return;
      db.asignacionTurno.push({
        id: `asg_w7_${dia}_${turno}_${slug(usuarioId)}`,
        semanaId: SEMANA, dia, turno, usuarioId, funcion, equipo: "", observacion: ""
      });
    };

    // El supervisor y el laboratorista se toman del pool para no chocar reglas.
    const dotarTurno = (dia, turno, recorte) => {
      const req = Turnos.dotacionRequerida(db, SEMANA, dia, turno);
      if (!req.total) return;
      const nOperadores = Math.max(0, req.operador - (recorte || 0));
      for (let i = 0; i < nOperadores; i++) asignar(dia, turno, tomarOperador(), "operador");
      if (req.laboratorio && !recorte) asignar(dia, turno, tomarLab(), "laboratorio");
      if (req.supervisor && !recorte)  asignar(dia, turno, tomarOperador(), "supervisor");
    };

    ["A", "B", "C"].forEach(t => dotarTurno(0, t, 0));   // lunes: cubierto
    dotarTurno(1, "A", 1);                                // martes turno A: falta un operador

    db._meta.resumen = {
      productos: db.producto.length, especificaciones: nSpec,
      lotes: db.lote.length, analisis: db.analisis.length,
      despachos: db.despacho.length, recepciones: db.recepcion.length,
      liberaciones: db.liberacion.length
    };
    return db;
  }

  /** Comprueba la semilla contra el esquema. Devuelve los problemas encontrados. */
  function verificar(db) {
    const problemas = [];
    for (const entidad of Esquema.nombres) {
      (db[entidad] || []).forEach((registro, i) => {
        const { valido, errores } = Esquema.validar(entidad, registro);
        if (!valido) problemas.push(`${entidad}[${i}] (${registro.id}): ${errores.join(" ")}`);
      });
    }
    return problemas;
  }

  /** Migra datos guardados con un esquema anterior.
   *  Hoy: el checklist que vivía dentro de `liberacion` pasa a ser
   *  `registroCalidad`, un formulario por documento cumplido. */
  function migrar(db) {
    if (!Array.isArray(db.liberacion)) return false;
    let cambios = 0;
    db.registroCalidad = db.registroCalidad || [];

    db.liberacion.forEach(liberacion => {
      if (!Array.isArray(liberacion.checklist)) return;
      liberacion.checklist.forEach(item => {
        if (!item.completado || !item.documentoId) return;
        const yaEsta = db.registroCalidad.some(r =>
          r.loteId === liberacion.loteId && r.documentoId === item.documentoId);
        if (yaEsta) return;
        db.registroCalidad.push({
          id: `rcal_${liberacion.loteId}_${item.documentoId}`,
          loteId: liberacion.loteId,
          documentoId: item.documentoId,
          estado: "completado",
          valores: {},
          referencia: "",
          completadoPorId: item.usuarioId || null,
          completadoEn: item.fechaHora || "",
          observacion: "Migrado del checklist anterior: sin datos de formulario."
        });
        cambios++;
      });
      delete liberacion.checklist;
      cambios++;
    });
    return cambios > 0;
  }

  return { construir, verificar, migrar, familiaDe, mandanteDe };
})();

if (typeof module !== "undefined" && module.exports) module.exports = Semilla;
