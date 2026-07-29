/* ============================================================
   Dominio — Gestión Productiva Planta CCAA
   ------------------------------------------------------------
   Reglas de negocio del proceso productivo. Funciones PURAS:
   sin DOM, sin localStorage, sin fetch. Reciben datos y devuelven
   resultados. Por eso son testeables y sobreviven a cualquier
   cambio de plataforma (cliente, API, Power Platform).

   Regla central del sistema:
     Un despacho exige un lote liberado.
     Un lote se libera si su checklist está completo Y su calidad es
     conforme. Si no es conforme, solo puede salir como CONCESIÓN,
     con motivo y autorizador registrados.

   Las funciones de decisión nunca devuelven un booleano suelto:
   devuelven { permitido, bloqueos[] } para que la interfaz pueda
   explicarle al usuario por qué no puede avanzar.
   ============================================================ */

const Dominio = (() => {

  const RESULTADO = {
    CONFORME:           "conforme",
    NO_CONFORME:        "no_conforme",
    SIN_ANALISIS:       "sin_analisis",
    SIN_ESPECIFICACION: "sin_especificacion"
  };

  const ETIQUETA_RESULTADO = {
    conforme:           "Conforme",
    no_conforme:        "No conforme",
    sin_analisis:       "Sin análisis",
    sin_especificacion: "Sin especificación"
  };

  const LIBERACION = {
    PENDIENTE:  "pendiente",
    EN_REVISION:"en_revision",
    LIBERADO:   "liberado",
    CONCESION:  "liberado_concesion",
    RECHAZADO:  "rechazado"
  };

  const ROLES_AUTORIZADORES = ["calidad", "admin"];

  const esVacio = v => v === null || v === undefined || v === "";
  const numero  = v => (esVacio(v) ? null : Number(v));

  /* ============================================================
     Especificaciones
     ============================================================ */

  /** Especificación vigente para un producto en una fecha dada.
   *  Permite auditar un lote de mayo contra la spec de mayo, aunque hoy sea otra. */
  function especificacionVigente(especificaciones, productoId, fecha) {
    const candidatas = (especificaciones || []).filter(e =>
      e.productoId === productoId &&
      e.vigenteDesde <= fecha &&
      (esVacio(e.vigenteHasta) || e.vigenteHasta >= fecha)
    );
    if (!candidatas.length) return null;
    // Si se solaparan versiones, gana la de vigencia más reciente.
    return candidatas.sort((a, b) =>
      b.vigenteDesde.localeCompare(a.vigenteDesde) || (b.version || 0) - (a.version || 0)
    )[0];
  }

  /* ============================================================
     Evaluación de calidad
     ============================================================ */

  /** Evalúa un análisis contra una especificación.
   *  Devuelve el resultado y el detalle de cada parámetro, para que
   *  la UI pueda mostrar exactamente qué se salió de rango. */
  function evaluarAnalisis(analisis, especificacion) {
    if (!especificacion) {
      return { resultado: RESULTADO.SIN_ESPECIFICACION, detalle: [], desviaciones: [] };
    }

    const detalle = [];
    const valores = (analisis && analisis.valores) || {};

    for (const [parametro, rango] of Object.entries(especificacion.rangos || {})) {
      const valor = numero(valores[parametro]);

      if (valor === null || isNaN(valor)) {
        detalle.push({ parametro, valor: null, min: rango.min, max: rango.max,
                       estado: rango.obligatorio ? "faltante" : "no_medido" });
        continue;
      }

      const bajo  = !esVacio(rango.min) && valor < Number(rango.min);
      const alto  = !esVacio(rango.max) && valor > Number(rango.max);
      detalle.push({ parametro, valor, min: rango.min, max: rango.max,
                     estado: (bajo || alto) ? "fuera_de_rango" : "en_rango",
                     desvio: bajo ? "bajo" : (alto ? "alto" : null) });
    }

    const faltantesObligatorios = detalle.filter(d => d.estado === "faltante");
    const fueraDeRango          = detalle.filter(d => d.estado === "fuera_de_rango");
    const medidos               = detalle.filter(d => d.valor !== null);

    let resultado;
    if (fueraDeRango.length)                       resultado = RESULTADO.NO_CONFORME;
    else if (faltantesObligatorios.length)         resultado = RESULTADO.SIN_ANALISIS;
    else if (!medidos.length)                      resultado = RESULTADO.SIN_ANALISIS;
    else                                           resultado = RESULTADO.CONFORME;

    return {
      resultado,
      detalle,
      desviaciones: fueraDeRango,
      faltantes: faltantesObligatorios.map(d => d.parametro)
    };
  }

  /** Veredicto de calidad de un lote a partir de todos sus análisis.
   *
   *  Agregación: manda el peor resultado. Si cualquier muestra del lote
   *  está fuera de especificación, el lote entero es no conforme —
   *  no se promedia, porque el producto físico ya está mezclado y no
   *  se puede separar la fracción defectuosa.
   *
   *  NUNCA se persiste: se recalcula siempre. Así, al corregir una
   *  especificación, todo el histórico queda evaluado con el criterio nuevo. */
  function resultadoCalidadLote(lote, analisis, especificaciones) {
    const delLote = (analisis || []).filter(a => a.loteId === lote.id);
    const spec = especificacionVigente(especificaciones, lote.productoId, lote.fecha);

    if (!spec)          return { resultado: RESULTADO.SIN_ESPECIFICACION, desviaciones: [], evaluados: 0, spec: null };
    if (!delLote.length) return { resultado: RESULTADO.SIN_ANALISIS,      desviaciones: [], evaluados: 0, spec };

    const evaluaciones = delLote.map(a => ({ analisis: a, ev: evaluarAnalisis(a, spec) }));
    const desviaciones = evaluaciones.flatMap(e =>
      e.ev.desviaciones.map(d => Object.assign({ analisisId: e.analisis.id, muestra: e.analisis.muestra }, d))
    );

    let resultado = RESULTADO.CONFORME;
    if (evaluaciones.some(e => e.ev.resultado === RESULTADO.NO_CONFORME))      resultado = RESULTADO.NO_CONFORME;
    else if (evaluaciones.some(e => e.ev.resultado === RESULTADO.SIN_ANALISIS)) resultado = RESULTADO.SIN_ANALISIS;

    return { resultado, desviaciones, evaluados: delLote.length, spec, evaluaciones };
  }

  /* ============================================================
     Checklist de liberación
     ============================================================ */

  /** Documentos exigibles a un lote, según la familia de su producto.
   *  A la crema no se le piden los documentos de las líneas de polvo. */
  function documentosAplicables(documentos, producto) {
    if (!producto) return [];
    return (documentos || [])
      .filter(d => d.activo !== false && (d.aplicaA || []).includes(producto.familia))
      .sort((a, b) => (a.orden || 0) - (b.orden || 0));
  }

  /* ---------- Formularios digitales ---------- */

  const plantillaDe = documento => (documento && documento.plantilla) || [];

  /** Campos obligatorios de la plantilla que el registro dejó vacíos. */
  function camposFaltantes(registro, documento) {
    const valores = (registro && registro.valores) || {};
    return plantillaDe(documento).filter(campo => campo.req && esVacio(valores[campo.clave]));
  }

  /** Un documento cuenta como cumplido solo si su formulario está completado
   *  y no le falta ningún campo obligatorio. Marcar una casilla ya no basta. */
  function registroCompleto(registro, documento) {
    if (!registro || registro.estado !== "completado") return false;
    return camposFaltantes(registro, documento).length === 0;
  }

  function validarRegistro(registro, documento) {
    const bloqueos = [];
    const faltantes = camposFaltantes(registro, documento);
    if (faltantes.length) {
      bloqueos.push(`Faltan ${faltantes.length} campo(s) obligatorio(s): ` +
                    faltantes.map(c => c.etiqueta).join(", ") + ".");
    }
    for (const campo of plantillaDe(documento)) {
      const valor = (registro.valores || {})[campo.clave];
      if (esVacio(valor)) continue;
      if (campo.min !== undefined && Number(valor) < campo.min) bloqueos.push(`${campo.etiqueta}: no puede ser menor que ${campo.min}.`);
      if (campo.max !== undefined && Number(valor) > campo.max) bloqueos.push(`${campo.etiqueta}: no puede ser mayor que ${campo.max}.`);
    }
    return { permitido: bloqueos.length === 0, bloqueos, faltantes };
  }

  /** Valores que el sistema ya conoce y no hay que volver a teclear.
   *  Un campo de plantilla con `origen: "lote.codigoLote"` se rellena solo. */
  function prellenar(documento, contexto) {
    const valores = {};
    for (const campo of plantillaDe(documento)) {
      if (!campo.origen) continue;
      const valor = String(campo.origen).split(".").reduce((o, k) => (o == null ? o : o[k]), contexto);
      if (!esVacio(valor)) valores[campo.clave] = valor;
    }
    return valores;
  }

  /** Coteja lo escrito en un formulario contra los análisis del lote.
   *
   *  Un campo de plantilla con `parametro: "humedad"` se compara con el valor
   *  medido y con la especificación vigente. Es la ventaja de tener el
   *  formulario dentro del sistema: el dato se contrasta solo, en vez de
   *  quedar en un papel que nadie vuelve a cruzar. */
  function cotejarConAnalisis(registro, documento, calidadLote) {
    const discrepancias = [];
    const valores = (registro && registro.valores) || {};
    const spec = calidadLote && calidadLote.spec;

    for (const campo of plantillaDe(documento)) {
      if (!campo.parametro) continue;
      const declarado = numero(valores[campo.clave]);
      if (declarado === null || isNaN(declarado)) continue;

      // ¿Se sale de la especificación vigente?
      const rango = spec && spec.rangos && spec.rangos[campo.parametro];
      if (rango) {
        const bajo = !esVacio(rango.min) && declarado < Number(rango.min);
        const alto = !esVacio(rango.max) && declarado > Number(rango.max);
        if (bajo || alto) {
          discrepancias.push({
            tipo: "fuera_de_especificacion", parametro: campo.parametro, etiqueta: campo.etiqueta,
            declarado, min: rango.min, max: rango.max,
            mensaje: `${campo.etiqueta}: ${declarado} está fuera de la especificación (${rango.min ?? "—"} a ${rango.max ?? "—"}).`
          });
        }
      }

      // ¿Coincide con lo que dice el análisis de laboratorio?
      const medidos = ((calidadLote && calidadLote.evaluaciones) || [])
        .map(e => numero(e.analisis.valores[campo.parametro]))
        .filter(v => v !== null && !isNaN(v));
      if (medidos.length) {
        const cerca = medidos.some(v => Math.abs(v - declarado) <= (campo.tolerancia !== undefined ? campo.tolerancia : 0.05));
        if (!cerca) {
          discrepancias.push({
            tipo: "discrepa_del_analisis", parametro: campo.parametro, etiqueta: campo.etiqueta,
            declarado, medidos,
            mensaje: `${campo.etiqueta}: el formulario dice ${declarado} y el análisis del lote, ${medidos.join(" / ")}.`
          });
        }
      }
    }
    return discrepancias;
  }

  /** Avance documental de un lote, derivado de sus registros de calidad.
   *  No se persiste: cambiar la plantilla de un documento recalcula el avance.
   *
   *  `loteId` es opcional pero conviene pasarlo: sin él, quien llame debe
   *  haber filtrado ya los registros de ESE lote. Un registro de otro lote
   *  colándose aquí daría por cumplido un documento que nadie completó. */
  function avanceChecklist(registros, documentosAplicables, loteId) {
    const exigibles = documentosAplicables || [];
    const porDocumento = {};
    (registros || [])
      .filter(r => !loteId || r.loteId === loteId)
      .forEach(r => { porDocumento[r.documentoId] = r; });

    const detalle = exigibles.map(documento => {
      const registro = porDocumento[documento.id] || null;
      return {
        documento, registro,
        completo: registroCompleto(registro, documento),
        observado: !!(registro && registro.estado === "observado"),
        iniciado: !!registro,
        faltantes: camposFaltantes(registro, documento)
      };
    });

    const completados = detalle.filter(d => d.completo);
    const observados  = detalle.filter(d => d.observado);
    const faltantes   = detalle.filter(d => !d.completo);

    return {
      detalle,
      completados: completados.length,
      total: exigibles.length,
      pct: exigibles.length ? Math.round(completados.length / exigibles.length * 100) : 0,
      completo: exigibles.length > 0 && faltantes.length === 0,
      faltantes: faltantes.map(d => d.documento),
      observados: observados.map(d => d.documento)
    };
  }

  /* ============================================================
     Reglas de liberación y despacho
     ============================================================ */

  /** ¿Se puede liberar este lote?
   *
   *  ctx = { lote, producto, liberacion, analisis[], especificaciones[], documentos[], usuario }
   *
   *  Devuelve:
   *    permitido  — liberación normal disponible
   *    viaConcesion — solo puede salir como concesión (calidad no conforme,
   *                   pero el resto de las condiciones se cumplen)
   *    bloqueos[] — motivos legibles, para mostrarlos en pantalla */
  function puedeLiberar(ctx) {
    const bloqueos = [];
    const { lote, producto, usuario } = ctx;

    if (!lote) return { permitido: false, viaConcesion: false, bloqueos: ["No existe el lote."] };

    if (lote.estado === "anulado")     bloqueos.push("El lote está anulado.");
    if (lote.estado === "en_proceso")  bloqueos.push("El lote aún está en proceso: primero hay que cerrar la producción.");

    const aplicables = documentosAplicables(ctx.documentos, producto);
    const avance = avanceChecklist(ctx.registros, aplicables, lote.id);
    if (!avance.total)      bloqueos.push("No hay documentos configurados para esta familia de producto.");
    else if (!avance.completo) {
      bloqueos.push(`Faltan ${avance.faltantes.length} de ${avance.total} formularios por completar.`);
    }
    if (avance.observados.length) {
      bloqueos.push(`${avance.observados.length} formulario(s) marcados con observación sin resolver.`);
    }

    if (usuario && !ROLES_AUTORIZADORES.includes(usuario.rol)) {
      bloqueos.push(`El rol "${usuario.rol}" no puede autorizar liberaciones.`);
    }

    const calidad = resultadoCalidadLote(lote, ctx.analisis, ctx.especificaciones);
    const bloqueosCalidad = [];
    if (calidad.resultado === RESULTADO.SIN_ESPECIFICACION) {
      bloqueosCalidad.push("El producto no tiene especificación de calidad vigente a la fecha del lote.");
    } else if (calidad.resultado === RESULTADO.SIN_ANALISIS) {
      bloqueosCalidad.push("El lote no tiene análisis de calidad completos.");
    }

    // Sin especificación o sin análisis no hay liberación posible, ni siquiera por concesión:
    // no se puede conceder una excepción sobre algo que nunca se midió.
    if (bloqueosCalidad.length) {
      return { permitido: false, viaConcesion: false, calidad,
               bloqueos: bloqueos.concat(bloqueosCalidad) };
    }

    const noConforme = calidad.resultado === RESULTADO.NO_CONFORME;
    const restoOk = bloqueos.length === 0;

    return {
      permitido:    restoOk && !noConforme,
      viaConcesion: restoOk && noConforme,
      calidad,
      avance,
      bloqueos: noConforme
        ? bloqueos.concat([`Calidad no conforme: ${calidad.desviaciones.length} parámetro(s) fuera de rango. Requiere liberación bajo concesión.`])
        : bloqueos
    };
  }

  /** Valida una liberación por concesión: exige motivo y rol autorizado. */
  function validarConcesion(ctx, motivo) {
    const evaluacion = puedeLiberar(ctx);
    const bloqueos = [];

    if (!evaluacion.viaConcesion && !evaluacion.permitido) {
      bloqueos.push(...evaluacion.bloqueos);
    }
    if (esVacio(motivo) || String(motivo).trim().length < 10) {
      bloqueos.push("La concesión exige un motivo escrito de al menos 10 caracteres.");
    }
    if (!ctx.usuario) {
      bloqueos.push("La concesión debe quedar firmada por un usuario identificado.");
    }
    return { permitido: bloqueos.length === 0, bloqueos, calidad: evaluacion.calidad };
  }

  /** Kilos ya comprometidos en despachos emitidos de un lote. */
  function kgDespachados(loteId, despachos) {
    return (despachos || [])
      .filter(d => d.loteId === loteId && d.estado !== "anulado")
      .reduce((s, d) => s + (Number(d.kg) || 0), 0);
  }

  function kgDisponibles(lote, despachos) {
    return (Number(lote.kgProducidos) || 0) - kgDespachados(lote.id, despachos);
  }

  /** ¿Se puede emitir este despacho?
   *  ctx = { lote, liberacion, despachos[], kg } */
  function puedeDespachar(ctx) {
    const bloqueos = [];
    const { lote, liberacion, despachos } = ctx;
    const kg = Number(ctx.kg) || 0;

    if (!lote) return { permitido: false, bloqueos: ["No existe el lote."] };

    const liberado = liberacion &&
      (liberacion.estado === LIBERACION.LIBERADO || liberacion.estado === LIBERACION.CONCESION);

    if (!liberado) bloqueos.push("El lote no está liberado por Calidad.");
    if (lote.estado === "anulado") bloqueos.push("El lote está anulado.");

    const disponibles = kgDisponibles(lote, despachos);
    if (kg <= 0) bloqueos.push("Los kilos del despacho deben ser mayores que cero.");
    else if (kg > disponibles) {
      bloqueos.push(`Solo quedan ${disponibles.toLocaleString("es-CL")} kg disponibles en el lote.`);
    }

    return { permitido: bloqueos.length === 0, bloqueos, disponibles };
  }

  /* ============================================================
     Silos: ocupación y trazabilidad
     ============================================================ */

  /** Ocupación real de un silo: suma de su libro de movimientos.
   *  No es el acumulado histórico de recepciones — descuenta lo consumido. */
  function ocupacionSilo(silo, movimientos, hasta) {
    const propios = (movimientos || []).filter(m =>
      m.siloId === silo.id && (!hasta || m.fechaHora <= hasta)
    );
    const litros = propios.reduce((s, m) => {
      const v = Number(m.litros) || 0;
      if (m.tipo === "ingreso") return s + v;
      if (m.tipo === "salida")  return s - v;
      return s + v; // ajuste: puede ser negativo
    }, 0);

    const capacidad = Number(silo.capacidadL) || 0;
    return {
      siloId: silo.id,
      codigo: silo.codigo,
      litros,
      capacidad,
      pct: capacidad ? Math.round(litros / capacidad * 100) : 0,
      excedido: capacidad > 0 && litros > capacidad,
      negativo: litros < 0   // señal de descuadre en el registro
    };
  }

  /** Trazabilidad hacia atrás de un lote: de qué silos consumió y qué
   *  recepciones habían ingresado a esos silos antes del consumo.
   *
   *  La leche se mezcla dentro del silo, así que la respuesta honesta es
   *  un conjunto de recepciones candidatas, no una cadena uno a uno.
   *  Así funciona la trazabilidad en lácteos. */
  function trazabilidadLote(lote, movimientos, recepciones) {
    const consumos = (movimientos || []).filter(m =>
      m.tipo === "salida" && m.origen && m.origen.tipo === "lote" && m.origen.refId === lote.id
    );

    return consumos.map(consumo => {
      const ingresos = (movimientos || []).filter(m =>
        m.siloId === consumo.siloId && m.tipo === "ingreso" && m.fechaHora <= consumo.fechaHora
      );
      const idsRecepcion = ingresos
        .filter(m => m.origen && m.origen.tipo === "recepcion")
        .map(m => m.origen.refId);

      return {
        siloId: consumo.siloId,
        litros: Number(consumo.litros) || 0,
        fechaHora: consumo.fechaHora,
        recepciones: (recepciones || []).filter(r => idsRecepcion.includes(r.id))
      };
    });
  }

  /** ¿La recepción cumple los controles para liberarse al silo?
   *  Delvo o inhibidores positivos retienen el camión de forma automática. */
  function evaluarRecepcion(recepcion, limites) {
    const c = (recepcion && recepcion.controles) || {};
    const lim = limites || { acidezMax: 18, phMin: 6.5, phMax: 6.9, temperaturaMax: 8, crioscopiaMax: -0.510 };
    const motivos = [];

    if (c.delvo === "Positivo")       motivos.push("Delvo Test positivo (presencia de antibióticos).");
    if (c.inhibidores === "Positivo") motivos.push("Inhibidores positivos.");

    const acidez = numero(c.acidez);
    if (acidez !== null && acidez > lim.acidezMax) motivos.push(`Acidez ${acidez} °D sobre el máximo (${lim.acidezMax} °D).`);

    const ph = numero(c.ph);
    if (ph !== null && (ph < lim.phMin || ph > lim.phMax)) motivos.push(`pH ${ph} fuera del rango ${lim.phMin}–${lim.phMax}.`);

    const t = numero(c.temperatura);
    if (t !== null && t > lim.temperaturaMax) motivos.push(`Temperatura ${t} °C sobre el máximo (${lim.temperaturaMax} °C).`);

    // La crioscopía detecta aguado: menos negativa que el límite = sospecha.
    const cr = numero(c.crioscopia);
    if (cr !== null && cr > lim.crioscopiaMax) motivos.push(`Crioscopía ${cr} indica posible aguado.`);

    return { conforme: motivos.length === 0, estado: motivos.length ? "retenida" : "liberada", motivos };
  }

  /* ============================================================
     Agregaciones para el panel
     ============================================================ */

  function resumenProduccion(lotes, analisis, especificaciones) {
    const conteo = { conforme: 0, no_conforme: 0, sin_analisis: 0, sin_especificacion: 0 };
    let kgTotal = 0;

    const evaluados = (lotes || []).map(l => {
      const r = resultadoCalidadLote(l, analisis, especificaciones);
      conteo[r.resultado]++;
      kgTotal += Number(l.kgProducidos) || 0;
      return { lote: l, calidad: r };
    });

    const conVeredicto = conteo.conforme + conteo.no_conforme;
    return {
      lotes: (lotes || []).length,
      kgTotal,
      conteo,
      conVeredicto,
      // Porcentaje sobre lotes efectivamente evaluados. La cobertura se
      // informa aparte: un cumplimiento alto sobre pocos lotes no es una
      // buena noticia, y el panel debe poder decirlo.
      pctConformidad: conVeredicto ? Math.round(conteo.conforme / conVeredicto * 100) : null,
      pctCobertura: (lotes || []).length ? Math.round(conVeredicto / lotes.length * 100) : 0,
      evaluados
    };
  }

  return {
    RESULTADO, ETIQUETA_RESULTADO, LIBERACION, ROLES_AUTORIZADORES,
    especificacionVigente, evaluarAnalisis, resultadoCalidadLote,
    documentosAplicables, avanceChecklist,
    plantillaDe, camposFaltantes, registroCompleto, validarRegistro,
    prellenar, cotejarConAnalisis,
    puedeLiberar, validarConcesion,
    kgDespachados, kgDisponibles, puedeDespachar,
    ocupacionSilo, trazabilidadLote, evaluarRecepcion,
    resumenProduccion
  };
})();

if (typeof module !== "undefined" && module.exports) module.exports = Dominio;
