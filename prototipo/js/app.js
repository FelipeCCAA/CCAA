/* ============================================================
   Aplicación — Gestión Productiva Planta CCAA
   ------------------------------------------------------------
   Interfaz sobre el modelo (esquema + dominio + repositorio).
   No contiene reglas de negocio: las consulta al dominio y muestra
   sus motivos. Los formularios se generan desde el esquema, así que
   agregar un campo al esquema lo hace aparecer en pantalla.
   ============================================================ */

const App = (() => {

  const { $, $$, esc, num, fecha, iniciales, avisar, abrirModal, confirmar } = UI;

  let db = null;              // instantánea de datos
  let usuario = null;         // usuario que opera
  let vistaActual = "panel";
  const expandidos = new Set();   // liberaciones con el checklist abierto
  const CLAVE_USUARIO = "gpccaa_usuario";

  /* ============================================================
     Acceso a datos
     ============================================================ */

  async function recargar() {
    db = await Repositorio.instantanea();
  }

  const buscar   = (entidad, id) => (db[entidad] || []).find(r => r.id === id) || null;
  const productoDe = lote => buscar("producto", lote.productoId);
  const mandanteDe = producto => producto ? buscar("mandante", producto.mandanteId) : null;
  const nombreProducto = id => { const p = buscar("producto", id); return p ? p.nombre : "—"; };
  const nombreUsuario  = id => { const u = buscar("usuario", id); return u ? u.nombre : "—"; };

  const liberacionDe = loteId => (db.liberacion || []).find(l => l.loteId === loteId) || null;

  const calidadDe = lote => Dominio.resultadoCalidadLote(lote, db.analisis, db.especificacion);

  /** Nombre correcto de un parámetro fisicoquímico («pH», no «Ph»). */
  const etiquetaParametro = clave => {
    const meta = Esquema.CATALOGOS.parametros[clave];
    return meta ? meta.etiqueta : UI.etiquetaDe(clave);
  };

  /** Etiquetas y tono de cada resultado de calidad. */
  const TONO_CALIDAD = { conforme: "ok", no_conforme: "bad", sin_analisis: "warn", sin_especificacion: "muted" };
  const insigniaCalidad = r => `<span class="badge ${TONO_CALIDAD[r] || "muted"}">${esc(Dominio.ETIQUETA_RESULTADO[r] || r)}</span>`;

  const TONO_LIBERACION = { liberado: "ok", liberado_concesion: "warn", en_revision: "info", pendiente: "muted", rechazado: "bad" };
  const insigniaLiberacion = e => `<span class="badge ${TONO_LIBERACION[e] || "muted"}">${esc(UI.etiquetaEnum(e))}</span>`;

  const TONO_RECEPCION = { descargada: "ok", liberada: "ok", retenida: "bad", analizada: "info", muestreada: "info", registrada: "muted", cerrada: "muted" };

  /* ============================================================
     Opciones para los campos de referencia
     ============================================================ */

  const ROTULOS = {
    mandante:  m => m.nombre,
    producto:  p => p.nombre,
    silo:      s => `${s.codigo} · ${num(s.capacidadL)} L`,
    vehiculo:  v => `${v.placa}${v.transportista ? " · " + v.transportista : ""}`,
    usuario:   u => `${u.nombre} (${UI.etiquetaEnum(u.rol)})`,
    documentoLiberacion: d => d.nombre,
    especificacion: e => `${nombreProducto(e.productoId)} · v${e.version}`,
    receta: r => `${nombreProducto(r.productoId)} · v${r.version}`,
    lote:      l => `${l.codigoLote} · ${nombreProducto(l.productoId)} · ${fecha(l.fecha)}`,
    recepcion: r => `${r.guia || r.id} · ${fecha(r.fecha)}`,
    liberacion:r => `Liberación de ${r.loteId}`,
    analisis:  a => `${a.muestra || a.id}`,
    despacho:  d => `GD ${d.gd || "—"}`,
    movimientoSilo: m => `${UI.etiquetaEnum(m.tipo)} ${num(m.litros)} L`,
    eventoAuditoria: e => e.id,
    semanaPlan: s => `${s.codigo} · ${fecha(s.fechaInicio)}`,
    codigoProduccion: c => `${c.codigo} · ${num(c.rendimientoLh)} L/h`,
    bloquePlan: b => {
      const equipo = Esquema.CATALOGOS.equipos[b.equipo];
      return `${equipo ? equipo.etiqueta : b.equipo} · ${Planificador.DIAS[b.dia] || "?"} ${b.horaInicio}–${b.horaFin} h`;
    },
    balanceDia: b => `Balance · ${Planificador.DIAS[b.dia] || "?"}`,
    asignacionTurno: a => `${Turnos.DIAS[a.dia] || "?"} · turno ${a.turno} · ${nombreUsuario(a.usuarioId)}`,
    registroCalidad: r => {
      const documento = buscar("documentoLiberacion", r.documentoId);
      const lote = buscar("lote", r.loteId);
      return `${lote ? lote.codigoLote : "?"} · ${documento ? documento.nombre : "?"}`;
    }
  };

  function opcionesRef() {
    const refs = {};
    for (const entidad of Esquema.nombres) {
      const rotulo = ROTULOS[entidad] || (r => r.id);
      refs[entidad] = (db[entidad] || [])
        .filter(r => r.activo !== false)
        .map(r => ({ id: r.id, texto: rotulo(r) }))
        .sort((a, b) => a.texto.localeCompare(b.texto, "es"));
    }
    return refs;
  }

  /* ============================================================
     Formularios genéricos por entidad
     ============================================================ */

  // Orden y agrupación de campos. Lo que no aparezca va a "Otros datos".
  const FORMULARIOS = {
    lote: [
      { titulo: "Identificación", campos: ["codigoLote", "productoId", "fecha", "op"] },
      { titulo: "Producción",     campos: ["linea", "turno", "kgProducidos", "bultos", "horaInicio", "horaTermino"] },
      { titulo: "Seguimiento",    campos: ["vencimiento", "estado", "observacion"] }
    ],
    recepcion: [
      { titulo: "Recepción", campos: ["fecha", "hora", "guia", "vehiculoId", "procedencia", "tipoLeche", "litros"] },
      { titulo: "Descarga",  campos: ["siloId", "operadorId", "turno", "estado", "motivo"] },
      { titulo: "Controles", campos: ["controles"] },
      { titulo: "Notas",     campos: ["observacion"] }
    ],
    despacho: [
      { titulo: "Despacho", campos: ["loteId", "fecha", "gd", "oc", "destino"] },
      { titulo: "Carga",    campos: ["kg", "bultos", "vehiculoId", "estado", "observacion"] }
    ],
    especificacion: [
      { titulo: "Alcance",  campos: ["productoId", "version", "vigenteDesde", "vigenteHasta", "fuente"] },
      { titulo: "Rangos",   campos: ["rangos"] }
    ]
  };

  function armarFormulario(entidad, registro, refs) {
    const def = Esquema.ENTIDADES[entidad];
    const secciones = FORMULARIOS[entidad];
    const usados = new Set(["id"]);

    const pintar = clave => {
      if (!def.campos[clave] || usados.has(clave)) return "";
      usados.add(clave);
      if (clave === "rangos") return `<div class="ancho-total">${UI.editorRangos(registro.rangos)}</div>`;
      return UI.campo(clave, def.campos[clave], registro[clave], refs);
    };

    let html = "";
    if (secciones) {
      html += secciones.map(s => `
        <div class="form-seccion">
          <h4>${esc(s.titulo)}</h4>
          <div class="form-grid">${s.campos.map(pintar).join("")}</div>
        </div>`).join("");
    }
    const restantes = Object.keys(def.campos).filter(c => !usados.has(c));
    if (restantes.length) {
      html += `<div class="form-seccion">
        ${secciones ? "<h4>Otros datos</h4>" : ""}
        <div class="form-grid">${restantes.map(pintar).join("")}</div>
      </div>`;
    }
    return `<form id="form-entidad" novalidate>${html}</form>`;
  }

  /** Abre el formulario de alta o edición de cualquier entidad del esquema.
   *  opciones = { iniciales, validar }  — `validar` es la comprobación de dominio
   *  que el esquema no puede hacer (solapamientos, coherencia entre campos). */
  function editar(entidad, id, alGuardar, opciones) {
    opciones = opciones || {};
    const def = Esquema.ENTIDADES[entidad];
    const refs = opcionesRef();
    const registro = id ? buscar(entidad, id)
                        : Esquema.conDefectos(entidad, Object.assign({}, opciones.iniciales));
    if (id && !registro) { avisar("El registro ya no existe.", "bad"); return; }

    abrirModal({
      titulo: `${id ? "Editar" : "Nuevo"} · ${def.etiqueta}`,
      subtitulo: def.descripcion,
      ancho: entidad === "especificacion" ? "ancho" : "",
      contenido: armarFormulario(entidad, registro, refs),
      acciones: [
        { texto: "Cancelar", clase: "btn-sec", alPulsar: cerrar => cerrar() },
        { texto: id ? "Guardar cambios" : "Crear", clase: "btn-pri", alPulsar: async (cerrar, caja) => {
            const form = $("#form-entidad", caja);
            const datos = UI.leerFormulario(entidad, form);

            const validar = opciones.validar || VALIDACION_DOMINIO[entidad];
            if (validar) {
              const v = validar(Object.assign({ id }, datos));
              if (!v.permitido) {
                UI.mostrarErrores(form, []);
                avisar(v.bloqueos[0], "bad", 6000);
                return;
              }
            }
            try {
              const guardado = id ? await Repositorio.actualizar(entidad, id, datos)
                                  : await Repositorio.crear(entidad, datos);
              await recargar();
              avisar(`${def.etiqueta} ${id ? "actualizado" : "creado"}.`, "ok");
              cerrar();
              // Se devuelve el registro guardado: quien abrió el formulario
              // desde otro (crear un componente sin salir de la receta) lo necesita.
              if (alGuardar) alGuardar(guardado); else renderVista();
            } catch (e) {
              const sueltos = UI.mostrarErrores(form, e.motivos || [e.message]);
              avisar(sueltos.length ? sueltos[0] : "Revise los campos marcados.", "bad", 5000);
            }
          } }
      ],
      alAbrir: caja => {
        UI.conectarEditorRangos(caja);
        UI.conectarListas(caja, entidad, refs, crearReferenciaAlVuelo);
      }
    });
  }

  /** Permite crear un registro referenciado sin abandonar el formulario actual.
   *  En una receta, el componente que falta se da de alta ahí mismo y queda
   *  seleccionado: así el árbol se construye de arriba hacia abajo. */
  function crearReferenciaAlVuelo(entidadDestino, devolver) {
    editar(entidadDestino, null, creado => {
      if (!creado) return;
      const rotulo = (ROTULOS[entidadDestino] || (r => r.id))(creado);
      devolver({ id: creado.id, texto: rotulo });
    });
  }

  /** Comprobaciones de dominio que el esquema no puede hacer por sí solo. */
  const VALIDACION_DOMINIO = {
    receta: datos => Recetas.validarReceta(datos, db)
  };

  async function borrar(entidad, id, alBorrar) {
    const def = Esquema.ENTIDADES[entidad];
    const registro = buscar(entidad, id);
    const rotulo = (ROTULOS[entidad] || (r => r.id))(registro);

    const ok = await confirmar({
      titulo: `Eliminar ${def.etiqueta.toLowerCase()}`,
      mensaje: `Se eliminará «${rotulo}». La acción queda registrada en la bitácora, pero el dato no se recupera.`,
      textoOk: "Eliminar", peligro: true
    });
    if (!ok) return;

    try {
      await Repositorio.eliminar(entidad, id);
      await recargar();
      avisar(`${def.etiqueta} eliminado.`, "ok");
      if (alBorrar) alBorrar(); else renderVista();
    } catch (e) {
      abrirModal({
        titulo: "No se puede eliminar", ancho: "angosto",
        contenido: `<p style="font-size:13px;margin-bottom:var(--e3)">${esc(e.message)}</p>
          <ul class="bloqueos">${(e.motivos || []).map(m => `<li>${esc(m)}</li>`).join("")}</ul>`,
        acciones: [{ texto: "Entendido", clase: "btn-sec" }]
      });
    }
  }

  const botonesFila = () => `
    <button class="btn-icono" data-accion-fila="editar" title="Editar" aria-label="Editar">${UI.icono("editar")}</button>
    <button class="btn-icono peligro" data-accion-fila="borrar" title="Eliminar" aria-label="Eliminar">${UI.icono("borrar")}</button>`;

  /* ============================================================
     Panel general
     ============================================================ */

  function renderPanel() {
    const resumen = Dominio.resumenProduccion(db.lote, db.analisis, db.especificacion);

    const retenidas = db.recepcion.filter(r => r.estado === "retenida").length;
    const litros = db.recepcion.filter(r => r.estado !== "retenida").reduce((s, r) => s + (r.litros || 0), 0);
    const pendientes = db.liberacion.filter(l => !["liberado", "liberado_concesion"].includes(l.estado)).length;
    const concesiones = db.liberacion.filter(l => l.estado === "liberado_concesion").length;

    const kpis = [
      { etq: "Kilos producidos", val: num(resumen.kgTotal), unidad: "kg",
        det: `${resumen.lotes} lotes registrados`, tono: "info" },
      { etq: "Cumplimiento de calidad",
        val: resumen.pctConformidad === null ? "—" : resumen.pctConformidad, unidad: resumen.pctConformidad === null ? "" : "%",
        det: `sobre ${resumen.conVeredicto} de ${resumen.lotes} lotes evaluables (${resumen.pctCobertura}%)`,
        tono: resumen.conteo.no_conforme ? "warn" : "ok" },
      { etq: "Lotes no conformes", val: resumen.conteo.no_conforme, unidad: "",
        det: concesiones ? `${concesiones} liberado(s) por concesión` : "ninguno liberado por concesión",
        tono: resumen.conteo.no_conforme ? "bad" : "ok" },
      { etq: "Litros recepcionados", val: num(litros), unidad: "L",
        det: `${retenidas} recepción(es) retenida(s)`, tono: retenidas ? "warn" : "info" },
      { etq: "Liberaciones pendientes", val: pendientes, unidad: "",
        det: `de ${db.liberacion.length} expedientes`, tono: pendientes ? "warn" : "ok" }
    ];

    $("#kpis").innerHTML = kpis.map(k => `
      <div class="kpi kpi-${k.tono}">
        <div class="kpi-valor">${esc(k.val)}${k.unidad ? `<span class="unidad">${esc(k.unidad)}</span>` : ""}</div>
        <div class="kpi-etiqueta">${esc(k.etq)}</div>
        <div class="kpi-detalle">${esc(k.det)}</div>
      </div>`).join("");

    // Aviso honesto sobre la calidad del dato que sostiene los indicadores
    const referenciales = db.especificacion.filter(e => /referencial/i.test(e.fuente || "")).length;
    const sinSpec = resumen.conteo.sin_especificacion;
    const avisos = [];
    if (referenciales) avisos.push(`${referenciales} especificación(es) marcadas como <strong>referenciales</strong>, sin validar con Calidad`);
    if (sinSpec) avisos.push(`<strong>${sinSpec} lote(s)</strong> sin especificación vigente: no se evalúan`);
    $("#aviso-panel").innerHTML = avisos.length ? `
      <div class="aviso aviso-warn">
        <span class="ico" aria-hidden="true">⚠</span>
        <div>Los indicadores de calidad son provisorios: ${avisos.join(" y ")}.
        Ajústelas en <button class="btn btn-sm btn-sec" data-ir-admin="especificacion">Administración → Especificaciones</button></div>
      </div>` : "";
    const irSpec = $("[data-ir-admin]");
    if (irSpec) irSpec.addEventListener("click", () => { irA("admin"); adminEntidad = "especificacion"; renderAdmin(); });

    // Kilos por producto y por mandante
    const porProducto = {}, porMandante = {};
    db.lote.forEach(l => {
      const p = productoDe(l);
      const kg = l.kgProducidos || 0;
      porProducto[p ? p.nombre : "—"] = (porProducto[p ? p.nombre : "—"] || 0) + kg;
      const m = mandanteDe(p);
      porMandante[m ? m.nombre : "—"] = (porMandante[m ? m.nombre : "—"] || 0) + kg;
    });
    barras("#grafico-productos", porProducto, " kg");
    barras("#grafico-mandantes", porMandante, " kg");
  }

  function barras(selector, objeto, sufijo, maximos) {
    const entradas = Object.entries(objeto).sort((a, b) => b[1] - a[1]).slice(0, 8);
    const tope = Math.max(1, ...entradas.map(e => e[1]));
    $(selector).innerHTML = entradas.length ? entradas.map(([k, v]) => {
      const limite = maximos && maximos[k];
      const excedido = limite && v > limite;
      const ancho = Math.min(100, v / tope * 100);
      return `<div class="barra-fila">
        <div class="barra-etq" title="${esc(k)}">${esc(k)}</div>
        <div class="barra-pista"><div class="barra ${excedido ? "excedido" : ""}" style="width:${ancho.toFixed(1)}%"></div></div>
        <div class="barra-val">${num(v)}${sufijo}</div>
      </div>`;
    }).join("") : `<div class="vacio"><span class="ico">▤</span><div class="titulo">Sin datos</div></div>`;
  }

  /* ============================================================
     Producción
     ============================================================ */

  function renderProduccion() {
    const filtroCalidad = $("#filtro-calidad") ? $("#filtro-calidad").value : "todos";
    const filtroProducto = $("#filtro-producto") ? $("#filtro-producto").value : "todos";

    let filas = db.lote.map(l => {
      const calidad = calidadDe(l);
      const lib = liberacionDe(l);
      return {
        id: l.id, lote: l,
        codigoLote: l.codigoLote,
        producto: nombreProducto(l.productoId),
        productoId: l.productoId,
        fecha: l.fecha,
        kg: l.kgProducidos,
        linea: l.linea,
        calidad: calidad.resultado,
        desviaciones: calidad.desviaciones.length,
        analisis: calidad.evaluados,
        liberacion: lib ? lib.estado : "pendiente"
      };
    });

    if (filtroCalidad !== "todos")  filas = filas.filter(f => f.calidad === filtroCalidad);
    if (filtroProducto !== "todos") filas = filas.filter(f => f.productoId === filtroProducto);

    UI.tabla($("#tabla-produccion"), {
      filas,
      ordenInicial: "fecha", dirInicial: -1,
      placeholderBuscar: "Buscar lote, producto…",
      columnas: [
        { clave: "fecha", etiqueta: "Fecha", render: f => fecha(f.fecha), ancho: "100px" },
        { clave: "codigoLote", etiqueta: "Lote", clase: "mono" },
        { clave: "producto", etiqueta: "Producto" },
        { clave: "kg", etiqueta: "Kilos", num: true, render: f => num(f.kg) },
        { clave: "linea", etiqueta: "Línea", render: f => f.linea || "—" },
        { clave: "analisis", etiqueta: "Análisis", num: true,
          render: f => f.analisis ? `<span class="chip">${f.analisis}</span>` : `<span class="chip">0</span>` },
        { clave: "calidad", etiqueta: "Calidad", render: f => insigniaCalidad(f.calidad) +
          (f.desviaciones ? ` <span class="mono" title="Parámetros fuera de rango">${f.desviaciones}↯</span>` : "") },
        { clave: "liberacion", etiqueta: "Liberación", render: f => insigniaLiberacion(f.liberacion) }
      ],
      claseFila: f => f.calidad === "no_conforme" ? "fila-alerta" : "",
      acciones: f => `
        <button class="btn-icono" data-accion-fila="analisis" title="Análisis del lote" aria-label="Análisis">${UI.icono("analisis")}</button>
        ${botonesFila()}`,
      alPulsarAccion: (accion, fila) => {
        if (accion === "editar")   editar("lote", fila.id);
        if (accion === "borrar")   borrar("lote", fila.id);
        if (accion === "analisis") abrirAnalisis(fila.lote);
      },
      vacio: { ico: "⧉", titulo: "Sin lotes", pista: "Registre el primer lote con «+ Nuevo lote»." }
    });
  }

  /** Análisis de un lote: alta, edición y detalle de desviaciones. */
  function abrirAnalisis(lote) {
    const dibujar = (caja) => {
      const calidad = calidadDe(lote);
      const propios = db.analisis.filter(a => a.loteId === lote.id);
      const spec = calidad.spec;

      const filaDesviacion = d => `<li>${esc(etiquetaParametro(d.parametro))}: ${d.valor}
        (esperado ${d.min ?? "—"} a ${d.max ?? "—"}) en ${esc(d.muestra || "—")}</li>`;

      $(".contenido-analisis", caja).innerHTML = `
        <div class="entre" style="margin-bottom:var(--e3)">
          <div>
            ${insigniaCalidad(calidad.resultado)}
            <span class="card-sub" style="margin-left:var(--e2)">
              ${spec ? `Especificación v${spec.version} · ${esc(spec.fuente || "")}` : "Sin especificación vigente para este producto"}
            </span>
          </div>
          <button class="btn btn-pri btn-sm" data-nuevo-analisis>+ Nuevo análisis</button>
        </div>
        ${calidad.desviaciones.length ? `
          <div class="aviso aviso-bad"><span class="ico">⚠</span>
            <div><strong>Parámetros fuera de rango</strong>
              <ul class="bloqueos" style="margin-top:var(--e1)">${calidad.desviaciones.map(filaDesviacion).join("")}</ul>
            </div></div>` : ""}
        <div class="tabla-wrap"><table class="tabla">
          <thead><tr><th>Muestra</th><th>Fecha</th><th>Parámetros</th><th></th></tr></thead>
          <tbody>${propios.length ? propios.map(a => `
            <tr>
              <td class="mono">${esc(a.muestra || "—")}</td>
              <td>${fecha(a.fecha)}</td>
              <td>${Object.entries(a.valores || {}).map(([k, v]) =>
                    `<span class="chip">${esc(etiquetaParametro(k))} ${v}</span>`).join(" ") || "—"}</td>
              <td><div class="acciones-fila">
                <button class="btn-icono" data-editar-analisis="${esc(a.id)}" aria-label="Editar análisis">${UI.icono("editar")}</button>
                <button class="btn-icono peligro" data-borrar-analisis="${esc(a.id)}" aria-label="Eliminar análisis">${UI.icono("borrar")}</button>
              </div></td>
            </tr>`).join("") : `<tr><td colspan="4"><div class="vacio">
                <span class="ico">${UI.icono("analisis", 26)}</span><div class="titulo">Sin análisis</div>
                <div class="pista">Un lote sin análisis no se puede liberar.</div></div></td></tr>`}
          </tbody></table></div>`;

      $("[data-nuevo-analisis]", caja).addEventListener("click", () =>
        editar("analisis", null, () => dibujar(caja)));
      $$("[data-editar-analisis]", caja).forEach(b => b.addEventListener("click", () =>
        editar("analisis", b.dataset.editarAnalisis, () => dibujar(caja))));
      $$("[data-borrar-analisis]", caja).forEach(b => b.addEventListener("click", () =>
        borrar("analisis", b.dataset.borrarAnalisis, () => dibujar(caja))));
    };

    abrirModal({
      titulo: `Análisis · ${lote.codigoLote}`,
      subtitulo: `${nombreProducto(lote.productoId)} · ${fecha(lote.fecha)}`,
      ancho: "ancho",
      contenido: `<div class="contenido-analisis"></div>`,
      acciones: [{ texto: "Cerrar", clase: "btn-sec" }],
      alAbrir: caja => dibujar(caja),
      alCerrar: () => renderVista()
    });
  }

  /* ============================================================
     Recepción y silos
     ============================================================ */

  function renderRecepcion() {
    // Ocupación real por silo (saldo de movimientos), no acumulado histórico
    const ocupaciones = db.silo
      .map(s => Dominio.ocupacionSilo(s, db.movimientoSilo))
      .filter(o => o.litros !== 0)
      .sort((a, b) => b.litros - a.litros);

    const porSilo = {}, capacidades = {};
    ocupaciones.forEach(o => { porSilo[o.codigo] = o.litros; capacidades[o.codigo] = o.capacidad; });
    barras("#grafico-silos", porSilo, " L", capacidades);

    const excedidos = ocupaciones.filter(o => o.excedido);
    $("#aviso-silos").innerHTML = excedidos.length ? `
      <div class="aviso aviso-bad"><span class="ico">⚠</span>
        <div><strong>${excedidos.length} silo(s) sobre su capacidad declarada:</strong>
        ${esc(excedidos.map(o => o.codigo).join(", "))}. Revise la capacidad en Administración o los movimientos registrados.</div>
      </div>` : "";

    const filas = db.recepcion.map(r => ({
      id: r.id, rec: r,
      guia: r.guia || r.id,
      fecha: r.fecha,
      silo: (buscar("silo", r.siloId) || {}).codigo || "—",
      procedencia: r.procedencia,
      tipoLeche: r.tipoLeche,
      litros: r.litros,
      camion: (buscar("vehiculo", r.vehiculoId) || {}).placa || "—",
      operador: nombreUsuario(r.operadorId),
      turno: r.turno,
      estado: r.estado,
      controles: r.controles || {}
    }));

    UI.tabla($("#tabla-recepcion"), {
      filas, ordenInicial: "fecha", dirInicial: -1,
      placeholderBuscar: "Buscar guía, camión, silo…",
      columnas: [
        { clave: "guia", etiqueta: "Guía", clase: "mono" },
        { clave: "fecha", etiqueta: "Fecha", render: f => fecha(f.fecha) },
        { clave: "silo", etiqueta: "Silo / TK" },
        { clave: "procedencia", etiqueta: "Procedencia" },
        { clave: "tipoLeche", etiqueta: "Tipo" },
        { clave: "litros", etiqueta: "Litros", num: true, render: f => num(f.litros) },
        { clave: "camion", etiqueta: "Camión", clase: "mono" },
        { clave: "turno", etiqueta: "Turno", render: f => f.turno || "—" },
        { clave: "controles", etiqueta: "Controles", ordenable: false, render: f => {
            const c = f.controles;
            const pastilla = (etq, val, malo) => val === undefined || val === null || val === ""
              ? "" : `<span class="badge ${malo ? "bad" : "ok"}">${esc(etq)}</span>`;
            return [
              pastilla("Delvo", c.delvo, c.delvo === "Positivo"),
              pastilla("Inhib.", c.inhibidores, c.inhibidores === "Positivo")
            ].filter(Boolean).join(" ") || "—";
          } },
        { clave: "estado", etiqueta: "Estado", render: f =>
            `<span class="badge ${TONO_RECEPCION[f.estado] || "muted"}">${esc(UI.etiquetaEnum(f.estado))}</span>` }
      ],
      claseFila: f => f.estado === "retenida" ? "fila-alerta" : "",
      acciones: f => botonesFila("recepcion", f.id),
      alPulsarAccion: (accion, fila) => {
        if (accion === "editar") editar("recepcion", fila.id);
        if (accion === "borrar") borrar("recepcion", fila.id);
      },
      vacio: { ico: "▤", titulo: "Sin recepciones", pista: "Registre la primera con «+ Nueva recepción»." }
    });
  }

  /* ============================================================
     Calidad — bandeja, expediente del lote y formularios digitales
     ------------------------------------------------------------
     Dos niveles en vez de una lista plana: primero una bandeja
     priorizada, después el expediente de un lote concreto. Con 22
     lotes y 19 documentos cada uno, la lista plana era inoperable.
     ============================================================ */

  let expedienteActual = null;

  function contextoLiberacion(lote) {
    return {
      lote,
      producto: productoDe(lote),
      liberacion: liberacionDe(lote.id),
      registros: db.registroCalidad.filter(r => r.loteId === lote.id),
      analisis: db.analisis,
      especificaciones: db.especificacion,
      documentos: db.documentoLiberacion,
      usuario
    };
  }

  const puedeFirmarCalidad = () => usuario && Dominio.ROLES_AUTORIZADORES.includes(usuario.rol);

  function diasDesde(fechaISO) {
    if (!fechaISO) return 0;
    const dias = Math.round((Date.now() - new Date(String(fechaISO).slice(0, 10) + "T00:00:00")) / 86400000);
    return Math.max(0, dias);
  }

  const registroDe = (loteId, documentoId) =>
    db.registroCalidad.find(r => r.loteId === loteId && r.documentoId === documentoId) || null;

  /** Estado de un lote a ojos de Calidad, con todo lo necesario para decidir. */
  function expedienteDe(lote) {
    const ctx = contextoLiberacion(lote);
    const aplicables = Dominio.documentosAplicables(db.documentoLiberacion, ctx.producto);
    const avance = Dominio.avanceChecklist(ctx.registros, aplicables, lote.id);
    const evaluacion = Dominio.puedeLiberar(ctx);
    const calidad = evaluacion.calidad || Dominio.resultadoCalidadLote(lote, db.analisis, db.especificacion);

    const discrepancias = aplicables.flatMap(documento => {
      const registro = registroDe(lote.id, documento.id);
      if (!registro) return [];
      return Dominio.cotejarConAnalisis(registro, documento, calidad)
        .map(d => Object.assign({ documento }, d));
    });

    return { ctx, aplicables, avance, evaluacion, calidad, discrepancias, lote,
             dias: diasDesde(lote.fecha) };
  }

  function renderCalidad() {
    const lote = expedienteActual ? buscar("lote", expedienteActual) : null;
    if (lote) renderExpediente(lote);
    else { expedienteActual = null; renderBandeja(); }
  }

  /* ---------- Bandeja ---------- */

  function renderBandeja() {
    const filtro = $("#filtro-calidad-estado") ? $("#filtro-calidad-estado").value : "pendientes";

    const todos = db.lote.map(expedienteDe);
    const liberado = e => ["liberado", "liberado_concesion"].includes(e.ctx.liberacion ? e.ctx.liberacion.estado : "");

    let filas = todos;
    if (filtro === "pendientes")   filas = todos.filter(e => !liberado(e));
    else if (filtro === "liberados") filas = todos.filter(e => liberado(e));
    else if (filtro === "atencion")  filas = todos.filter(e =>
      !liberado(e) && (e.calidad.resultado === "no_conforme" || e.discrepancias.length || e.avance.observados.length));

    const pendientes = todos.filter(e => !liberado(e));
    const kgRetenidos = pendientes.reduce((s, e) => s + (e.lote.kgProducidos || 0), 0);
    const conDiscrepancia = todos.filter(e => e.discrepancias.length).length;
    // Un formulario que no cuadra con el laboratorio es más grave que uno que
    // simplemente declara un valor fuera de rango: eso ya lo dice la calidad del lote.
    const desajustados = todos.filter(e =>
      e.discrepancias.some(d => d.tipo === "discrepa_del_analisis")).length;
    const noConformes = pendientes.filter(e => e.calidad.resultado === "no_conforme").length;

    $("#calidad-contenido").innerHTML = `
      <div class="kpis">
        <div class="kpi kpi-${pendientes.length ? "warn" : "ok"}">
          <div class="kpi-valor">${pendientes.length}</div>
          <div class="kpi-etiqueta">Lotes por liberar</div>
          <div class="kpi-detalle">de ${todos.length} expedientes</div></div>
        <div class="kpi kpi-info">
          <div class="kpi-valor">${num(kgRetenidos)}<span class="unidad">kg</span></div>
          <div class="kpi-etiqueta">Producto retenido</div>
          <div class="kpi-detalle">sin autorización de despacho</div></div>
        <div class="kpi kpi-${noConformes ? "bad" : "ok"}">
          <div class="kpi-valor">${noConformes}</div>
          <div class="kpi-etiqueta">No conformes pendientes</div>
          <div class="kpi-detalle">solo salen por concesión</div></div>
        <div class="kpi kpi-${conDiscrepancia ? "bad" : "ok"}">
          <div class="kpi-valor">${conDiscrepancia}</div>
          <div class="kpi-etiqueta">Con avisos de cotejo</div>
          <div class="kpi-detalle">${desajustados
            ? `${desajustados} con datos distintos del análisis`
            : "valores fuera de rango en un formulario"}</div></div>
      </div>

      <div class="card">
        <div class="card-head">
          <div><h2>Bandeja de Calidad</h2>
            <p class="card-sub">Ordenada por antigüedad: arriba, lo que lleva más tiempo esperando.</p></div>
          <div class="filtros">
            <div class="campo">
              <label for="filtro-calidad-estado">Mostrar</label>
              <select id="filtro-calidad-estado">
                <option value="pendientes" ${filtro === "pendientes" ? "selected" : ""}>Por liberar</option>
                <option value="atencion" ${filtro === "atencion" ? "selected" : ""}>Requieren atención</option>
                <option value="liberados" ${filtro === "liberados" ? "selected" : ""}>Ya liberados</option>
                <option value="todos" ${filtro === "todos" ? "selected" : ""}>Todos</option>
              </select>
            </div>
          </div>
        </div>
        <div id="tabla-calidad"></div>
      </div>`;

    $("#filtro-calidad-estado").addEventListener("change", renderBandeja);

    UI.tabla($("#tabla-calidad"), {
      filas: filas.map(e => ({
        id: e.lote.id, exp: e,
        codigoLote: e.lote.codigoLote,
        producto: nombreProducto(e.lote.productoId),
        fecha: e.lote.fecha,
        dias: e.dias,
        kg: e.lote.kgProducidos,
        calidad: e.calidad.resultado,
        avance: e.avance.pct,
        estado: e.ctx.liberacion ? e.ctx.liberacion.estado : "pendiente",
        alertas: e.discrepancias.length + e.avance.observados.length
      })),
      ordenInicial: "fecha", dirInicial: 1,
      placeholderBuscar: "Buscar lote o producto…",
      columnas: [
        { clave: "codigoLote", etiqueta: "Lote", clase: "mono" },
        { clave: "producto", etiqueta: "Producto" },
        { clave: "fecha", etiqueta: "Elaborado", render: f => fecha(f.fecha) },
        { clave: "dias", etiqueta: "Días", num: true,
          render: f => `<span class="${f.dias > 7 ? "chip-alerta" : ""}">${f.dias}</span>` },
        { clave: "kg", etiqueta: "Kilos", num: true, render: f => num(f.kg) },
        { clave: "calidad", etiqueta: "Calidad", render: f => insigniaCalidad(f.calidad) },
        { clave: "avance", etiqueta: "Formularios", num: true, render: f => `
            <div class="avance-celda">
              <div class="mini-pista"><div class="mini-barra" style="width:${f.avance}%"></div></div>
              <span>${f.exp.avance.completados}/${f.exp.avance.total}</span>
            </div>` },
        { clave: "alertas", etiqueta: "Avisos", num: true,
          render: f => f.alertas ? `<span class="badge bad">${f.alertas}</span>` : `<span class="mono">—</span>` },
        { clave: "estado", etiqueta: "Estado", render: f => insigniaLiberacion(f.estado) }
      ],
      claseFila: f => f.calidad === "no_conforme" ? "fila-alerta" : "",
      acciones: () => `<button class="btn btn-sec btn-sm" data-accion-fila="abrir">Abrir expediente</button>`,
      alPulsarAccion: (accion, fila) => {
        if (accion !== "abrir") return;
        irA("calidad/" + fila.id);
      },
      vacio: { ico: "✔", titulo: "Nada pendiente", pista: "No hay lotes que coincidan con el filtro." }
    });
  }

  /* ---------- Expediente de un lote ---------- */

  function renderExpediente(lote) {
    const e = expedienteDe(lote);
    const lib = e.ctx.liberacion;
    const editable = puedeFirmarCalidad() && !["liberado", "liberado_concesion"].includes(lib ? lib.estado : "");

    const siguiente = e.avance.detalle.find(d => !d.completo);

    const filaDocumento = d => {
      const registro = d.registro;
      const estado = d.completo ? `<span class="badge ok">Completado</span>`
                   : d.observado ? `<span class="badge bad">Observado</span>`
                   : registro ? `<span class="badge warn">Borrador</span>`
                              : `<span class="badge muted">Pendiente</span>`;
      const firma = registro && registro.completadoPorId
        ? `<span class="firma">${esc(nombreUsuario(registro.completadoPorId))}${registro.completadoEn ? " · " + fecha(registro.completadoEn) : ""}</span>`
        : "";
      const discrepa = e.discrepancias.filter(x => x.documento.id === d.documento.id).length;

      return `<li class="doc-fila ${d.completo ? "hecho" : ""} ${d.observado ? "observado" : ""}">
        <div class="doc-info">
          <button type="button" class="doc-nombre" data-abrir-doc="${esc(d.documento.id)}">
            ${esc(d.documento.nombre)}</button>
          ${d.documento.codigo ? `<span class="mono">${esc(d.documento.codigo)}</span>` : ""}
          ${firma}
          ${discrepa ? `<span class="badge bad">${discrepa} discrepancia(s)</span>` : ""}
        </div>
        <div class="doc-estado">${estado}
          <button class="btn btn-sec btn-sm" data-abrir-doc="${esc(d.documento.id)}">
            ${d.completo ? "Ver" : "Completar"}</button></div>
      </li>`;
    };

    $("#calidad-contenido").innerHTML = `
      <button class="btn btn-fantasma btn-sm" id="volver-bandeja" style="margin-bottom:var(--e3)">← Volver a la bandeja</button>

      <div class="card">
        <div class="lib-head">
          <div>
            <h2 class="lib-titulo">${esc(lote.codigoLote)} ${insigniaCalidad(e.calidad.resultado)}</h2>
            <p class="card-sub">${esc(nombreProducto(lote.productoId))} · ${fecha(lote.fecha)} ·
              ${num(lote.kgProducidos)} kg · ${e.dias} día(s) en espera</p>
          </div>
          <div class="lib-derecha">
            ${insigniaLiberacion(lib ? lib.estado : "pendiente")}
            <span class="lib-pct">${e.avance.completados}/${e.avance.total} formularios · ${e.avance.pct}%</span>
            ${lib && lib.autorizadaPorId ? `<span class="lib-pct">Autorizó ${esc(nombreUsuario(lib.autorizadaPorId))}</span>` : ""}
          </div>
        </div>
        <div class="progreso"><div class="relleno ${e.avance.completo ? "completo" : ""}" style="width:${e.avance.pct}%"></div></div>
        <div class="card-cuerpo">
          ${e.calidad.desviaciones.length ? `
            <div class="aviso aviso-bad"><span class="ico">⚠</span>
              <div><strong>Parámetros fuera de especificación:</strong>
                ${esc(e.calidad.desviaciones.map(d =>
                  `${etiquetaParametro(d.parametro)} ${d.valor} (esperado ${d.min ?? "—"} a ${d.max ?? "—"})`).join(" · "))}</div></div>` : ""}
          ${e.discrepancias.length ? `
            <div class="aviso aviso-bad"><span class="ico">⚠</span>
              <div><strong>El formulario no cuadra con el análisis del lote:</strong>
                <ul class="bloqueos" style="margin-top:var(--e1)">
                  ${e.discrepancias.map(d => `<li>${esc(d.documento.nombre)} — ${esc(d.mensaje)}</li>`).join("")}
                </ul></div></div>` : ""}
          <div class="entre">
            <button class="btn btn-sec btn-sm" id="ver-analisis">Ver análisis del lote (${e.calidad.evaluados})</button>
            ${editable && siguiente
              ? `<button class="btn btn-pri btn-sm" id="siguiente-pendiente">Completar siguiente pendiente →</button>` : ""}
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <div><h2>Formularios de liberación</h2>
            <p class="card-sub">Cada documento abre su registro tal como se completó.</p></div>
        </div>
        <ul class="doc-lista">${e.avance.detalle.map(filaDocumento).join("")}</ul>
      </div>

      <div class="card">
        <div class="card-cuerpo">
          ${e.evaluacion.bloqueos.length
            ? `<ul class="bloqueos">${e.evaluacion.bloqueos.map(b => `<li>${esc(b)}</li>`).join("")}</ul>` : ""}
          <div class="lib-acciones">
            <button class="btn btn-pri btn-sm" id="autorizar" ${e.evaluacion.permitido && puedeFirmarCalidad() ? "" : "disabled"}>
              Autorizar despacho</button>
            ${e.evaluacion.viaConcesion && puedeFirmarCalidad()
              ? `<button class="btn btn-sec btn-sm" id="conceder">Liberar bajo concesión…</button>` : ""}
            ${!puedeFirmarCalidad()
              ? `<span class="nota-inline">Solo Calidad o Administración pueden autorizar.</span>` : ""}
          </div>
        </div>
      </div>`;

    $("#volver-bandeja").addEventListener("click", () => irA("calidad"));
    $("#ver-analisis").addEventListener("click", () => abrirAnalisis(lote));
    const btnSiguiente = $("#siguiente-pendiente");
    if (btnSiguiente) btnSiguiente.addEventListener("click", () => abrirFormulario(lote, siguiente.documento));

    $$("[data-abrir-doc]").forEach(b => b.addEventListener("click", () => {
      const documento = buscar("documentoLiberacion", b.dataset.abrirDoc);
      if (documento) abrirFormulario(lote, documento);
    }));

    const btnAutorizar = $("#autorizar");
    if (btnAutorizar) btnAutorizar.addEventListener("click", () => autorizar(lote.id, false));
    const btnConceder = $("#conceder");
    if (btnConceder) btnConceder.addEventListener("click", () => autorizar(lote.id, true));
  }

  /* ---------- El formulario digital ---------- */

  function abrirFormulario(lote, documento) {
    const registro = registroDe(lote.id, documento.id);
    const producto = productoDe(lote);
    const calidad = Dominio.resultadoCalidadLote(lote, db.analisis, db.especificacion);
    const plantilla = Dominio.plantillaDe(documento);

    // Lo que el sistema ya sabe no se vuelve a teclear.
    const prellenado = Dominio.prellenar(documento, { lote, producto, mandante: mandanteDe(producto) });
    const valores = Object.assign({}, prellenado, (registro && registro.valores) || {});

    const firmado = !!(registro && registro.estado === "completado");
    const editable = puedeFirmarCalidad() &&
      !["liberado", "liberado_concesion"].includes((liberacionDe(lote.id) || {}).estado);
    const soloLectura = firmado || !editable;

    const cuerpo = `
      ${documento.instruccion ? `<p class="card-sub">${esc(documento.instruccion)}</p>` : ""}
      ${documento.fuente && /provisoria/i.test(documento.fuente) ? `
        <div class="aviso aviso-warn"><span class="ico">⚠</span>
          <div>${esc(documento.fuente)}. Ajuste los campos en
            Administración → Documento de liberación.</div></div>` : ""}
      ${registro && registro.completadoPorId ? `
        <div class="aviso aviso-info"><span class="ico">◔</span>
          <div>Completado por <strong>${esc(nombreUsuario(registro.completadoPorId))}</strong>
            ${registro.completadoEn ? "el " + fecha(registro.completadoEn) : ""}.
            ${firmado ? "Para modificarlo hay que reabrirlo, y el cambio queda en la bitácora." : ""}</div></div>` : ""}
      <form id="form-calidad" novalidate>
        <div class="form-grid">
          ${plantilla.length
            ? plantilla.map(c => UI.campoPlantilla(c, valores[c.clave], soloLectura)).join("")
            : `<p class="card-sub ancho-total">Este documento no tiene campos: basta con dejar constancia
                 de su verificación y, si aplica, la referencia del papel.</p>`}
          <div class="campo ancho-total">
            <label for="ref-doc">Referencia del documento físico o externo</label>
            <input type="text" id="ref-doc" value="${esc((registro && registro.referencia) || "")}" ${soloLectura ? "disabled" : ""} />
          </div>
        </div>
        <div id="cotejo-vivo"></div>
      </form>`;

    const acciones = [];
    if (soloLectura) {
      acciones.push({ texto: "Cerrar", clase: "btn-sec" });
      if (firmado && editable) {
        acciones.push({ texto: "Reabrir", clase: "btn-sec", izquierda: true, alPulsar: async cerrar => {
          const ok = await confirmar({
            titulo: "Reabrir el formulario",
            mensaje: "El documento volverá a borrador y el lote dejará de contarlo como cumplido. " +
                     "La reapertura queda registrada en la bitácora.",
            textoOk: "Reabrir"
          });
          if (!ok) return;
          await Repositorio.actualizar("registroCalidad", registro.id, { estado: "borrador" });
          await recargar(); cerrar(); renderCalidad();
          avisar("Formulario reabierto.", "warn");
        } });
      }
    } else {
      acciones.push({ texto: "Cancelar", clase: "btn-sec" });
      acciones.push({ texto: "Marcar con observación", clase: "btn-sec", izquierda: true,
        alPulsar: (cerrar, caja) => guardarFormulario(lote, documento, registro, caja, "observado", cerrar) });
      acciones.push({ texto: "Guardar borrador", clase: "btn-sec",
        alPulsar: (cerrar, caja) => guardarFormulario(lote, documento, registro, caja, "borrador", cerrar) });
      acciones.push({ texto: "Completar y firmar", clase: "btn-pri",
        alPulsar: (cerrar, caja) => guardarFormulario(lote, documento, registro, caja, "completado", cerrar) });
    }

    abrirModal({
      titulo: documento.nombre,
      subtitulo: `${lote.codigoLote} · ${nombreProducto(lote.productoId)} · ${fecha(lote.fecha)}`,
      contenido: cuerpo,
      acciones,
      alAbrir: caja => {
        if (soloLectura) return;
        const revisar = () => {
          const provisional = { valores: UI.leerPlantilla(plantilla, caja) };
          const discrepancias = Dominio.cotejarConAnalisis(provisional, documento, calidad);
          $("#cotejo-vivo", caja).innerHTML = discrepancias.length ? `
            <div class="aviso aviso-warn" style="margin:var(--e3) 0 0"><span class="ico">⚠</span>
              <div><strong>Revise antes de firmar:</strong>
                <ul class="bloqueos" style="margin-top:var(--e1)">
                  ${discrepancias.map(d => `<li>${esc(d.mensaje)}</li>`).join("")}</ul></div></div>` : "";
        };
        $$("[data-campo-plantilla]", caja).forEach(el => el.addEventListener("change", revisar));
        revisar();
      }
    });
  }

  async function guardarFormulario(lote, documento, registro, caja, estado, cerrar) {
    const plantilla = Dominio.plantillaDe(documento);
    const valores = UI.leerPlantilla(plantilla, caja);
    const referencia = $("#ref-doc", caja).value.trim();

    if (estado === "completado") {
      const validacion = Dominio.validarRegistro({ valores }, documento);
      if (!validacion.permitido) {
        UI.mostrarErrores($("#form-calidad", caja), validacion.bloqueos);
        avisar(validacion.bloqueos[0], "bad", 6000);
        return;
      }
    }

    const datos = {
      loteId: lote.id, documentoId: documento.id,
      estado, valores, referencia,
      completadoPorId: estado === "completado" ? (usuario ? usuario.id : null) : (registro ? registro.completadoPorId : null),
      completadoEn: estado === "completado" ? new Date().toISOString() : (registro ? registro.completadoEn : ""),
      observacion: registro ? registro.observacion : ""
    };

    try {
      if (registro) await Repositorio.actualizar("registroCalidad", registro.id, datos);
      else          await Repositorio.crear("registroCalidad", datos);
      await recargar();

      // Desmarcar un documento de un lote ya liberado lo devuelve a revisión.
      const lib = liberacionDe(lote.id);
      if (lib && estado !== "completado" && ["liberado", "liberado_concesion"].includes(lib.estado)) {
        await Repositorio.actualizar("liberacion", lib.id, {
          estado: "en_revision", autorizadaPorId: null, autorizadaEn: "", concesion: false });
        await recargar();
      } else if (lib && lib.estado === "pendiente") {
        await Repositorio.actualizar("liberacion", lib.id, { estado: "en_revision" });
        await recargar();
      }

      cerrar();
      renderCalidad();
      avisar(estado === "completado" ? "Formulario firmado."
           : estado === "observado" ? "Formulario marcado con observación."
           : "Borrador guardado.", estado === "observado" ? "warn" : "ok");
    } catch (e) {
      avisar((e.motivos && e.motivos[0]) || e.message, "bad", 6000);
    }
  }

  /* ---------- Autorización ---------- */

  async function autorizar(loteId, porConcesion) {
    const lote = buscar("lote", loteId);
    const ctx = contextoLiberacion(lote);

    if (!usuario) { avisar("Seleccione con qué usuario está operando.", "warn"); return; }

    if (!porConcesion) {
      const evaluacion = Dominio.puedeLiberar(ctx);
      if (!evaluacion.permitido) { avisar(evaluacion.bloqueos[0] || "No se puede liberar.", "bad", 5000); return; }
      const ok = await confirmar({
        titulo: "Autorizar despacho",
        mensaje: `Se autorizará el despacho del lote ${lote.codigoLote} (${nombreProducto(lote.productoId)}). ` +
                 `Quedará registrado a su nombre: ${usuario.nombre}.`,
        textoOk: "Autorizar"
      });
      if (!ok) return;
      await guardarLiberacion(ctx.liberacion, "liberado", false, "");
      avisar("Lote liberado para despacho.", "ok");
      renderCalidad(); renderPanel();
      return;
    }

    abrirModal({
      titulo: "Liberar bajo concesión",
      subtitulo: `${lote.codigoLote} · ${nombreProducto(lote.productoId)}`,
      ancho: "angosto",
      contenido: `
        <div class="aviso aviso-warn"><span class="ico">⚠</span>
          <div>Este lote <strong>no cumple</strong> la especificación vigente. La concesión queda
          registrada de forma permanente con su nombre y no se puede borrar de la bitácora.</div></div>
        <div class="campo">
          <label for="motivo-concesion">Motivo de la concesión<span class="req">*</span></label>
          <textarea id="motivo-concesion" rows="4" data-foco-inicial
            placeholder="Ej.: Aceptado por el mandante según correo del 21-05; destino reproceso."></textarea>
          <span class="ayuda">Mínimo 10 caracteres. Describa quién aceptó la desviación y con qué respaldo.</span>
        </div>`,
      acciones: [
        { texto: "Cancelar", clase: "btn-sec" },
        { texto: "Liberar bajo concesión", clase: "btn-peligro", alPulsar: async (cerrar, caja) => {
            const motivo = $("#motivo-concesion", caja).value.trim();
            const validacion = Dominio.validarConcesion(ctx, motivo);
            if (!validacion.permitido) { avisar(validacion.bloqueos[0], "bad", 5000); return; }
            await guardarLiberacion(ctx.liberacion, "liberado_concesion", true, motivo);
            cerrar();
            avisar("Lote liberado bajo concesión.", "warn", 5000);
            renderCalidad(); renderPanel();
          } }
      ]
    });
  }

  async function guardarLiberacion(lib, estado, concesion, motivo) {
    try {
      await Repositorio.actualizar("liberacion", lib.id, {
        estado, concesion, motivoConcesion: motivo,
        autorizadaPorId: usuario ? usuario.id : null,
        autorizadaEn: new Date().toISOString()
      });
      await recargar();
    } catch (e) { avisar(e.message, "bad", 5000); }
  }

  /* ============================================================
     Despachos
     ============================================================ */

  function renderDespachos() {
    const filas = db.despacho.map(d => {
      const lote = buscar("lote", d.loteId);
      return {
        id: d.id,
        gd: d.gd || "—", fecha: d.fecha, destino: d.destino, kg: d.kg,
        lote: lote ? lote.codigoLote : "—",
        producto: lote ? nombreProducto(lote.productoId) : "—",
        estado: d.estado
      };
    });

    UI.tabla($("#tabla-despachos"), {
      filas, ordenInicial: "fecha", dirInicial: -1,
      placeholderBuscar: "Buscar guía, destino, lote…",
      columnas: [
        { clave: "gd", etiqueta: "Guía", clase: "mono" },
        { clave: "fecha", etiqueta: "Fecha", render: f => fecha(f.fecha) },
        { clave: "lote", etiqueta: "Lote", clase: "mono" },
        { clave: "producto", etiqueta: "Producto" },
        { clave: "destino", etiqueta: "Destino" },
        { clave: "kg", etiqueta: "Kilos", num: true, render: f => num(f.kg) },
        { clave: "estado", etiqueta: "Estado", render: f =>
            `<span class="badge ${f.estado === "emitido" ? "ok" : f.estado === "anulado" ? "muted" : "info"}">${esc(UI.etiquetaEnum(f.estado))}</span>` }
      ],
      acciones: f => botonesFila("despacho", f.id),
      alPulsarAccion: (accion, fila) => {
        if (accion === "editar") editar("despacho", fila.id);
        if (accion === "borrar") borrar("despacho", fila.id);
      },
      vacio: { ico: "⇥", titulo: "Sin despachos", pista: "Solo se puede despachar desde un lote liberado." }
    });

    // Resumen de kilos disponibles por lote liberado
    const liberados = db.lote.filter(l => {
      const x = liberacionDe(l.id);
      return x && ["liberado", "liberado_concesion"].includes(x.estado);
    });
    const disponibles = {};
    liberados.forEach(l => {
      const d = Dominio.kgDisponibles(l, db.despacho);
      if (d > 0) disponibles[`${l.codigoLote} · ${nombreProducto(l.productoId)}`] = d;
    });
    barras("#grafico-disponible", disponibles, " kg");
  }

  /** Alta de despacho: valida contra el dominio antes de permitir guardar. */
  function nuevoDespacho() {
    const liberados = db.lote.filter(l => {
      const x = liberacionDe(l.id);
      return x && ["liberado", "liberado_concesion"].includes(x.estado)
             && Dominio.kgDisponibles(l, db.despacho) > 0;
    });

    if (!liberados.length) {
      abrirModal({
        titulo: "No hay lotes disponibles", ancho: "angosto",
        contenido: `<p style="font-size:13px">Para emitir un despacho se necesita un lote
          <strong>liberado por Calidad</strong> y con kilos sin comprometer.
          Revise el módulo de Liberación.</p>`,
        acciones: [{ texto: "Entendido", clase: "btn-sec" }]
      });
      return;
    }
    editar("despacho", null);
  }

  /* ============================================================
     Planificador de producción
     ============================================================ */

  let semanaActual = null;

  const CLAVE_SEMANA = "gpccaa_semana";
  const puedeEditarPlan = () => usuario && ["produccion", "admin"].includes(usuario.rol);

  /** Mezcla un color con blanco: el relleno del bloque queda claro y el texto
   *  puede ir en tinta oscura. El color a plena fuerza se conserva en la barra
   *  lateral y en la leyenda, que es donde la separación de la paleta importa. */
  function tinte(hex, proporcion) {
    const n = parseInt(String(hex).replace("#", ""), 16);
    const mezcla = c => Math.round(c * proporcion + 255 * (1 - proporcion));
    const r = mezcla((n >> 16) & 255), g = mezcla((n >> 8) & 255), b = mezcla(n & 255);
    return "#" + [r, g, b].map(c => c.toString(16).padStart(2, "0")).join("");
  }

  function semanasOrdenadas() {
    return db.semanaPlan.slice().sort((a, b) => String(b.fechaInicio).localeCompare(String(a.fechaInicio)));
  }

  function renderPlanificador() {
    const semanas = semanasOrdenadas();
    if (!semanas.length) {
      $("#plan-barra").innerHTML = "";
      $("#plan-contenido").innerHTML = `<div class="card"><div class="vacio">
        <span class="ico">▦</span><div class="titulo">Sin semanas programadas</div>
        <div class="pista">Cree la primera con «+ Nueva semana».</div></div></div>`;
      return;
    }
    if (!semanaActual || !buscar("semanaPlan", semanaActual)) {
      semanaActual = localStorage.getItem(CLAVE_SEMANA);
      if (!buscar("semanaPlan", semanaActual)) semanaActual = semanas[0].id;
    }

    const semana = buscar("semanaPlan", semanaActual);
    const evaluacion = Planificador.puedePublicar(db, semana.id);
    const editable = puedeEditarPlan() && semana.estado !== "cerrada";

    const TONO_SEMANA = { borrador: "muted", publicada: "ok", cerrada: "info" };
    $("#plan-barra").innerHTML = `
      <div class="card" style="margin-bottom:var(--e3)">
        <div class="card-head">
          <div class="filtros">
            <div class="campo">
              <label for="sel-semana">Semana</label>
              <select id="sel-semana">
                ${semanas.map(s => `<option value="${esc(s.id)}" ${s.id === semana.id ? "selected" : ""}>
                  ${esc(s.codigo)} · ${fecha(s.fechaInicio)}</option>`).join("")}
              </select>
            </div>
            <div class="campo">
              <label>Estado</label>
              <div>${`<span class="badge ${TONO_SEMANA[semana.estado] || "muted"}">${esc(UI.etiquetaEnum(semana.estado))}</span>`}</div>
            </div>
          </div>
          <div class="topbar-acciones">
            ${editable ? `<button class="btn btn-sec btn-sm" data-editar-semana>Editar semana</button>` : ""}
            ${editable && semana.estado === "borrador"
              ? `<button class="btn btn-pri btn-sm" data-publicar ${evaluacion.permitido ? "" : "disabled"}>Publicar programa</button>` : ""}
            ${editable && semana.estado === "publicada"
              ? `<button class="btn btn-sec btn-sm" data-reabrir>Volver a borrador</button>` : ""}
          </div>
        </div>
      </div>`;

    $("#sel-semana").addEventListener("change", ev => {
      semanaActual = ev.target.value;
      localStorage.setItem(CLAVE_SEMANA, semanaActual);
      renderPlanificador();
    });
    const btnEditar = $("[data-editar-semana]");
    if (btnEditar) btnEditar.addEventListener("click", () => editar("semanaPlan", semana.id, renderPlanificador));
    const btnPublicar = $("[data-publicar]");
    if (btnPublicar) btnPublicar.addEventListener("click", () => publicarSemana(semana));
    const btnReabrir = $("[data-reabrir]");
    if (btnReabrir) btnReabrir.addEventListener("click", async () => {
      await Repositorio.actualizar("semanaPlan", semana.id, { estado: "borrador" });
      await recargar(); renderPlanificador();
      avisar("La semana vuelve a borrador.", "ok");
    });

    $("#plan-contenido").innerHTML = `
      ${!editable ? `
        <div class="aviso aviso-info"><span class="ico">◔</span>
          <div>Está viendo el programa en <strong>modo lectura</strong>.
            ${semana.estado === "cerrada"
              ? "La semana está cerrada y ya no admite cambios."
              : `Programar es tarea de Producción: cambie el usuario a un rol de
                 <strong>producción</strong> o <strong>administrador</strong> para editar.`}</div></div>` : ""}
      ${!evaluacion.permitido && semana.estado === "borrador" ? `
        <div class="aviso aviso-warn"><span class="ico">⚠</span>
          <div><strong>El programa todavía no se puede publicar:</strong>
            <ul class="bloqueos" style="margin-top:var(--e1)">
              ${evaluacion.bloqueos.slice(0, 6).map(b => `<li>${esc(b)}</li>`).join("")}
            </ul></div></div>` : ""}
      <div class="card">
        <div class="card-head">
          <div><h2>Programa horario</h2>
            <p class="card-sub">Solo los evaporadores consumen leche cruda: sus bloques son los que alimentan el balance.
              ${editable ? "Pulse una pista vacía para programar." : "Está en modo lectura."}</p></div>
          <div id="plan-leyenda"></div>
        </div>
        <div id="plan-gantt"></div>
      </div>
      <div class="card">
        <div class="card-head">
          <div><h2>Balance de leche</h2>
            <p class="card-sub">Las celdas en blanco se ingresan; el consumo y los stocks se derivan del programa.</p></div>
        </div>
        <div id="plan-balance"></div>
      </div>`;

    renderLeyenda();
    renderGantt(semana, editable);
    renderBalance(semana, editable);
  }

  function renderLeyenda() {
    const fam = Esquema.CATALOGOS.familiasCodigo;
    const est = Esquema.CATALOGOS.estadosEquipo;
    const muestra = (color, texto, trama) =>
      `<span class="leyenda-item"><span class="leyenda-color ${trama ? "trama" : ""}" style="--c:${color}"></span>${esc(texto)}</span>`;
    $("#plan-leyenda").innerHTML = `<div class="leyenda">
      ${Object.values(fam).map(f => muestra(f.color, f.etiqueta, false)).join("")}
      ${Object.entries(est).map(([k, e]) => muestra(e.color, `${k} · ${e.etiqueta}`, e.trama)).join("")}
    </div>`;
  }

  function renderGantt(semana, editable) {
    const dias = semana.dias || 6;
    const equipos = Esquema.CATALOGOS.equipos;
    const evaporadores = Esquema.CATALOGOS.evaporadores;
    const indices = Array.from({ length: dias }, (_, i) => i);

    const cabecera = `
      <div class="gantt-fila gantt-cabecera">
        <div class="gantt-eq"></div>
        ${indices.map(d => `
          <div class="gantt-dia-cab">
            <div class="gantt-dia-nombre">${esc(Planificador.DIAS_CORTO[d])}
              <span>${fecha(Planificador.fechaDia(semana.fechaInicio, d))}</span></div>
            <div class="gantt-horas">${[0, 6, 12, 18].map(h => `<span>${h}</span>`).join("")}</div>
          </div>`).join("")}
      </div>`;

    const filas = Object.entries(equipos).map(([clave, meta]) => {
      const esEvaporador = evaporadores.includes(clave);
      const pistas = indices.map(d => {
        const bloques = Planificador.bloquesDe(db, semana.id, clave, d);
        return `<div class="gantt-pista ${editable ? "editable" : ""}" data-equipo="${esc(clave)}" data-dia="${d}">
          ${bloques.map(b => barraBloque(b)).join("")}
        </div>`;
      }).join("");

      return `<div class="gantt-fila">
        <div class="gantt-eq ${esEvaporador ? "evaporador" : ""}">
          <span class="gantt-eq-nombre">${esc(meta.etiqueta)}</span>
          <span class="gantt-eq-etapa">${esc(meta.etapa)}${esEvaporador ? " · consume leche" : ""}</span>
        </div>${pistas}</div>`;
    }).join("");

    $("#plan-gantt").innerHTML = `<div class="gantt-wrap"><div class="gantt" style="--dias:${dias}">
      ${cabecera}${filas}</div></div>`;

    $$("#plan-gantt [data-bloque]").forEach(b => b.addEventListener("click", ev => {
      ev.stopPropagation();
      abrirBloque(b.dataset.bloque, semana, editable);
    }));

    if (!editable) return;
    $$("#plan-gantt .gantt-pista.editable").forEach(p => p.addEventListener("click", ev => {
      if (ev.target.closest("[data-bloque]")) return;
      const caja = p.getBoundingClientRect();
      const hora = Math.max(0, Math.min(23, Math.floor((ev.clientX - caja.left) / caja.width * 24)));
      nuevoBloque(semana, p.dataset.equipo, Number(p.dataset.dia), hora);
    }));
  }

  function barraBloque(bloque) {
    const codigo = buscar("codigoProduccion", bloque.codigoId);
    const aspecto = Planificador.aspectoBloque(bloque, codigo);
    const izquierda = (bloque.horaInicio / 24 * 100);
    const ancho = ((bloque.horaFin - bloque.horaInicio) / 24 * 100);
    const horas = (bloque.horaFin - bloque.horaInicio);
    const litros = (codigo && Esquema.CATALOGOS.evaporadores.includes(bloque.equipo))
      ? Planificador.litrosDeBloque(bloque, codigo) : 0;

    const semana = buscar("semanaPlan", bloque.semanaId);
    const fechaBloque = semana ? Planificador.fechaDia(semana.fechaInicio, bloque.dia) : "";
    const kg = codigo ? Planificador.produccionBloque(db, bloque, codigo, fechaBloque) : null;
    const producto = codigo ? buscar("producto", codigo.productoId) : null;

    const titulo = `${aspecto.titulo} · ${bloque.horaInicio}–${bloque.horaFin} h (${horas} h)` +
                   (litros ? ` · ${num(litros)} L de leche` : "") +
                   (kg !== null && producto
                     ? ` · ≈ ${num(kg)} ${producto.unidadBase || "kg"} de ${producto.nombre}`
                     : "");

    return `<button type="button" class="gantt-bloque ${aspecto.trama ? "trama" : ""}"
      style="left:${izquierda.toFixed(3)}%;width:${ancho.toFixed(3)}%;--c:${aspecto.color};--relleno:${tinte(aspecto.color, 0.18)}"
      data-bloque="${esc(bloque.id)}" title="${esc(titulo)}">
      <span class="gantt-bloque-texto">${esc(aspecto.texto)}</span></button>`;
  }

  function opcionesBloque(semana) {
    return {
      iniciales: { semanaId: semana.id },
      validar: b => Planificador.validarBloque(Object.assign({ semanaId: semana.id }, b), db.bloquePlan)
    };
  }

  function nuevoBloque(semana, equipo, dia, hora) {
    editar("bloquePlan", null, renderPlanificador, {
      iniciales: {
        semanaId: semana.id, equipo, dia,
        horaInicio: hora, horaFin: Math.min(24, hora + 4), tipo: "produccion"
      },
      validar: opcionesBloque(semana).validar
    });
  }

  function abrirBloque(id, semana, editable) {
    const bloque = buscar("bloquePlan", id);
    if (!bloque) return;
    if (!editable) {
      const codigo = buscar("codigoProduccion", bloque.codigoId);
      const aspecto = Planificador.aspectoBloque(bloque, codigo);
      abrirModal({
        titulo: aspecto.texto, subtitulo: aspecto.titulo, ancho: "angosto",
        contenido: `<div class="ficha">
          <div class="dato"><div class="etq">Equipo</div><div class="val">${esc(Esquema.CATALOGOS.equipos[bloque.equipo].etiqueta)}</div></div>
          <div class="dato"><div class="etq">Día</div><div class="val">${esc(Planificador.DIAS[bloque.dia])}</div></div>
          <div class="dato"><div class="etq">Tramo</div><div class="val">${bloque.horaInicio}–${bloque.horaFin} h</div></div>
        </div>`,
        acciones: [{ texto: "Cerrar", clase: "btn-sec" }]
      });
      return;
    }
    editar("bloquePlan", id, renderPlanificador, {
      validar: opcionesBloque(semana).validar
    });
  }

  function renderBalance(semana, editable) {
    const filas = Planificador.balanceSemana(db, semana.id);
    const totales = Planificador.totalesSemana(filas);
    const cats = Esquema.CATALOGOS.categoriasConsumo;
    const origenes = Esquema.CATALOGOS.origenesLeche;

    const celdaEditable = (f, campo, deshabilitado) => {
      if (!editable || deshabilitado) return `<td class="num derivado">${num(f.registro[campo])}</td>`;
      const id = f.registro.id;
      if (!id) return `<td class="num derivado">—</td>`;
      return `<td class="num"><input type="number" step="any" class="celda-num"
        data-balance="${esc(id)}" data-campo="${esc(campo)}"
        value="${f.registro[campo] === null || f.registro[campo] === undefined ? "" : f.registro[campo]}"
        aria-label="${esc(UI.etiquetaDe(campo))} de ${esc(f.nombre)}" /></td>`;
    };

    const filaTexto = (etiqueta, valores, clase, total) => `
      <tr class="${clase || ""}">
        <th scope="row">${esc(etiqueta)}</th>
        ${valores.join("")}
        <td class="num total">${total === undefined ? "" : num(total)}</td>
      </tr>`;

    const html = `
      <div class="tabla-wrap"><table class="tabla tabla-balance">
        <thead><tr><th scope="col">Concepto</th>
          ${filas.map(f => `<th scope="col">${esc(f.nombre)}<span class="sub">${fecha(f.fecha)}</span></th>`).join("")}
          <th scope="col" class="der">Semana</th></tr></thead>
        <tbody>
          ${filaTexto("Stock 8 AM", filas.map((f, i) =>
            i === 0 ? celdaEditable(f, "stockInicial", false)
                    : `<td class="num derivado">${num(f.stockInicial)}</td>`), "fila-fuerte")}

          ${filaTexto("Recepción CCAA",     filas.map(f => celdaEditable(f, "recepcionCCAA")),   "", totales.recepciones ? filas.reduce((s, f) => s + f.recepciones.ccaa, 0) : 0)}
          ${filaTexto("Recepción Nestlé",   filas.map(f => celdaEditable(f, "recepcionNestle")), "", filas.reduce((s, f) => s + f.recepciones.nestle, 0))}
          ${filaTexto("Recepción P. Unión", filas.map(f => celdaEditable(f, "recepcionPUnion")), "", filas.reduce((s, f) => s + f.recepciones.punion, 0))}

          ${filaTexto("Total disponible", filas.map(f => `<td class="num derivado">${num(f.totalDisponible)}</td>`),
            "fila-fuerte", filas.reduce((s, f) => s + f.totalDisponible, 0))}

          <tr class="fila-seccion"><th scope="row" colspan="${filas.length + 2}">Consumo</th></tr>
          ${Object.entries(cats).map(([clave, meta]) => filaTexto(
            "· " + meta.etiqueta,
            filas.map(f => meta.derivada
              ? `<td class="num derivado">${num(f.consumo[clave])}</td>`
              : celdaEditable(f, "trasvasije")),
            "", totales.consumo[clave])).join("")}

          ${filaTexto("Total consumo", filas.map(f => `<td class="num derivado">${num(f.totalConsumo)}</td>`),
            "fila-fuerte", totales.totalConsumo)}

          <tr class="fila-seccion"><th scope="row" colspan="${filas.length + 2}">Saldo por origen</th></tr>
          ${origenes.map(o => filaTexto("· " + Planificador.ETIQUETA_ORIGEN[o],
            filas.map(f => `<td class="num derivado ${f.saldoOrigen[o] < 0 ? "negativo" : ""}">${num(f.saldoOrigen[o])}</td>`))).join("")}

          ${filaTexto("Stock 8 AM día siguiente",
            filas.map(f => `<td class="num derivado ${f.stockFinal < 0 ? "negativo" : ""}">${num(f.stockFinal)}</td>`), "fila-fuerte")}

          ${filaTexto("Crema disponible (t)", filas.map(f => celdaEditable(f, "cremaDisponibleTon")))}

          ${(() => {
            // Producción estimada según receta: lo que el programa deja en
            // producto, no solo lo que consume en leche.
            const porDia = filas.map(f =>
              Planificador.produccionDia(db, semana.id, f.dia, f.fecha));
            const productos = Array.from(new Set(porDia.flatMap(p => Object.keys(p))));
            if (!productos.length) return "";
            return `<tr class="fila-seccion"><th scope="row" colspan="${filas.length + 2}">
                      Producción estimada según receta</th></tr>` +
              productos.map(pid => {
                const producto = buscar("producto", pid);
                const unidad = producto ? (producto.unidadBase || "kg") : "kg";
                const total = porDia.reduce((s, p) => s + (p[pid] || 0), 0);
                return filaTexto(`· ${producto ? producto.nombre : "—"} (${unidad})`,
                  porDia.map(p => `<td class="num derivado">${num(p[pid] || 0)}</td>`), "", total);
              }).join("");
          })()}
        </tbody>
      </table></div>`;

    $("#plan-balance").innerHTML = html;

    $$("#plan-balance .celda-num").forEach(input => input.addEventListener("change", async ev => {
      const valor = ev.target.value === "" ? null : Number(ev.target.value);
      try {
        await Repositorio.actualizar("balanceDia", ev.target.dataset.balance,
          { [ev.target.dataset.campo]: valor });
        await recargar();
        renderPlanificador();
        avisar("Balance actualizado.", "ok", 1800);
      } catch (e) {
        avisar((e.motivos && e.motivos[0]) || e.message, "bad", 5000);
      }
    }));
  }

  async function publicarSemana(semana) {
    const evaluacion = Planificador.puedePublicar(db, semana.id);
    if (!evaluacion.permitido) { avisar(evaluacion.bloqueos[0], "bad", 6000); return; }
    const ok = await confirmar({
      titulo: "Publicar el programa",
      mensaje: `El programa de la semana ${semana.codigo} quedará publicado para la planta.`,
      textoOk: "Publicar"
    });
    if (!ok) return;
    await Repositorio.actualizar("semanaPlan", semana.id, { estado: "publicada" });
    await recargar(); renderPlanificador();
    avisar("Programa publicado.", "ok");
  }

  /** Crea la semana siguiente clonando la estructura y arrastrando el stock. */
  async function nuevaSemana() {
    const semanas = semanasOrdenadas();
    const ultima = semanas[0] || null;

    let fechaInicio = new Date().toISOString().slice(0, 10);
    let stock = 0, porOrigen = { ccaa: 0, nestle: 0, punion: 0 };
    let codigo = "W1", anio = Number(fechaInicio.slice(0, 4));

    if (ultima) {
      const dias = ultima.dias || 6;
      fechaInicio = Planificador.fechaDia(ultima.fechaInicio, 7);
      anio = Number(fechaInicio.slice(0, 4));
      const filas = Planificador.balanceSemana(db, ultima.id);
      const cierre = filas[filas.length - 1];
      if (cierre) { stock = cierre.stockFinal; porOrigen = cierre.saldoOrigen; }
      const n = parseInt(String(ultima.codigo).replace(/\D/g, ""), 10);
      codigo = isNaN(n) ? "W1" : "W" + (n + 1);
      var diasNueva = dias;
    }

    try {
      const semana = await Repositorio.crear("semanaPlan", {
        codigo, anio, fechaInicio, dias: ultima ? (ultima.dias || 6) : 6, estado: "borrador",
        observacion: ultima ? `Continúa a ${ultima.codigo}. Stock arrastrado del cierre anterior.` : ""
      });
      for (let dia = 0; dia < (semana.dias || 6); dia++) {
        await Repositorio.crear("balanceDia", {
          semanaId: semana.id, dia,
          stockInicial: dia === 0 ? Math.max(0, Math.round(stock)) : null,
          stockInicialPorOrigen: dia === 0 ? porOrigen : null,
          recepcionCCAA: 0, recepcionNestle: 0, recepcionPUnion: 0,
          trasvasije: 0, cremaDisponibleTon: null, ajustes: null, observacion: ""
        });
      }
      await recargar();
      semanaActual = semana.id;
      localStorage.setItem(CLAVE_SEMANA, semanaActual);
      renderPlanificador();
      avisar(`Semana ${semana.codigo} creada con el stock arrastrado.`, "ok", 5000);
    } catch (e) {
      avisar((e.motivos && e.motivos[0]) || e.message, "bad", 6000);
    }
  }

  /* ============================================================
     Turnos de personal — dotación acoplada al programa
     ============================================================ */

  const ESTADO_CELDA = {
    sin_actividad: { clase: "celda-inactiva", etq: "Sin actividad" },
    descubierto:   { clase: "celda-descubierta", etq: "Sin dotación" },
    parcial:       { clase: "celda-parcial", etq: "Incompleto" },
    cubierto:      { clase: "celda-cubierta", etq: "Cubierto" }
  };

  function renderTurnos() {
    const semanas = semanasOrdenadas();
    if (!semanas.length) {
      $("#turnos-barra").innerHTML = "";
      $("#turnos-contenido").innerHTML = `<div class="card"><div class="vacio">
        <span class="ico">▦</span><div class="titulo">Sin semanas programadas</div>
        <div class="pista">La dotación se arma sobre una semana del planificador. Cree una primero.</div></div></div>`;
      return;
    }
    if (!semanaActual || !buscar("semanaPlan", semanaActual)) {
      semanaActual = localStorage.getItem(CLAVE_SEMANA);
      if (!buscar("semanaPlan", semanaActual)) semanaActual = semanas[0].id;
    }

    const semana = buscar("semanaPlan", semanaActual);
    const editable = puedeEditarPlan();
    const resumen = Turnos.resumenSemana(db, semana.id);

    $("#turnos-barra").innerHTML = `
      <div class="card" style="margin-bottom:var(--e3)">
        <div class="card-head">
          <div class="filtros">
            <div class="campo">
              <label for="sel-semana-turnos">Semana</label>
              <select id="sel-semana-turnos">
                ${semanas.map(s => `<option value="${esc(s.id)}" ${s.id === semana.id ? "selected" : ""}>
                  ${esc(s.codigo)} · ${fecha(s.fechaInicio)}</option>`).join("")}
              </select>
            </div>
          </div>
          <div class="card-sub">${editable
            ? "Pulse una celda para asignar personal a ese turno."
            : "Modo lectura: cambie a un rol de producción o administrador para editar."}</div>
        </div>
      </div>`;

    $("#sel-semana-turnos").addEventListener("change", ev => {
      semanaActual = ev.target.value;
      localStorage.setItem(CLAVE_SEMANA, semanaActual);
      renderTurnos();
    });

    $("#turnos-contenido").innerHTML = `
      <div class="kpis">
        <div class="kpi kpi-info">
          <div class="kpi-valor">${resumen.turnosActivos}</div>
          <div class="kpi-etiqueta">Turnos con actividad</div>
          <div class="kpi-detalle">según el programa de la semana</div></div>
        <div class="kpi kpi-${resumen.turnosDescubiertos ? "bad" : "ok"}">
          <div class="kpi-valor">${resumen.turnosDescubiertos}</div>
          <div class="kpi-etiqueta">Turnos sin cubrir</div>
          <div class="kpi-detalle">requieren más personal</div></div>
        <div class="kpi kpi-info">
          <div class="kpi-valor">${resumen.asignadoTotal}<span class="unidad">/${resumen.requeridoTotal}</span></div>
          <div class="kpi-etiqueta">Dotación asignada</div>
          <div class="kpi-detalle">${resumen.personas} personas en la semana</div></div>
        <div class="kpi kpi-${resumen.conflictos.length ? "bad" : "ok"}">
          <div class="kpi-valor">${resumen.conflictos.length}</div>
          <div class="kpi-etiqueta">Conflictos</div>
          <div class="kpi-detalle">solapes y descansos insuficientes</div></div>
      </div>

      ${resumen.conflictos.length ? `
        <div class="aviso aviso-bad"><span class="ico">⚠</span>
          <div><strong>Conflictos de personal:</strong>
            <ul class="bloqueos" style="margin-top:var(--e1)">
              ${resumen.conflictos.map(c => `<li>${esc(nombreUsuario(c.usuarioId))}: ${esc(c.mensaje)}</li>`).join("")}
            </ul></div></div>` : ""}

      <div class="card">
        <div class="card-head">
          <div><h2>Cobertura de la semana</h2>
            <p class="card-sub">La dotación necesaria de cada turno se deduce de los equipos que el
              programa tiene corriendo en esas horas.</p></div>
        </div>
        <div id="turnos-grilla"></div>
      </div>`;

    renderGrillaTurnos(semana, editable);
  }

  function renderGrillaTurnos(semana, editable) {
    const dias = semana.dias || 6;
    const indices = Array.from({ length: dias }, (_, i) => i);
    const turnos = Esquema.CATALOGOS.turnos;

    const celda = (dia, turno) => {
      const c = Turnos.coberturaTurno(db, semana.id, dia, turno);
      const info = ESTADO_CELDA[c.estado];
      const detalle = c.requerido.total
        ? `${c.asignado.total}/${c.requerido.total}`
        : "—";
      return `<td class="celda-turno ${info.clase} ${editable && c.estado !== "sin_actividad" ? "editable" : ""}"
                  ${editable ? `data-celda="${dia}:${turno}"` : ""}
                  title="${esc(ESTADO_CELDA[c.estado].etq)}">
        <div class="celda-cifra">${detalle}</div>
        ${c.requerido.total ? `<div class="celda-nota">${esc(info.etq)}</div>` : ""}
      </td>`;
    };

    $("#turnos-grilla").innerHTML = `<div class="tabla-wrap"><table class="tabla tabla-turnos">
      <thead><tr><th>Turno</th>
        ${indices.map(d => `<th>${esc(Turnos.DIAS[d])}<span class="sub">${fecha(Planificador.fechaDia(semana.fechaInicio, d))}</span></th>`).join("")}
      </tr></thead>
      <tbody>
        ${turnos.map(t => {
          const h = Esquema.CATALOGOS.horariosTurno[t];
          return `<tr><th scope="row">${esc(t)}<span class="sub">${h ? `${h.desde}–${h.hasta} h` : ""}</span></th>
            ${indices.map(d => celda(d, t)).join("")}</tr>`;
        }).join("")}
      </tbody></table></div>`;

    if (!editable) return;
    $$("#turnos-grilla [data-celda]").forEach(td => td.addEventListener("click", () => {
      const [dia, turno] = td.dataset.celda.split(":");
      gestionarCelda(semana, Number(dia), turno);
    }));
  }

  function gestionarCelda(semana, dia, turno) {
    const dibujar = (caja) => {
      const req = Turnos.dotacionRequerida(db, semana.id, dia, turno);
      const asignaciones = Turnos.asignacionesDe(db, semana.id, dia, turno);
      const cobertura = Turnos.coberturaTurno(db, semana.id, dia, turno);

      const candidatos = db.usuario.filter(u => u.activo !== false)
        .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
      const funciones = Esquema.CATALOGOS.funcionesTurno;

      const chip = a => `<li class="asig-chip">
        <span>${esc(nombreUsuario(a.usuarioId))} · ${esc(Turnos.ETIQUETA_FUNCION(a.funcion))}</span>
        <button class="btn-icono peligro" data-quitar-asig="${esc(a.id)}" aria-label="Quitar">${UI.icono("cerrar", 13)}</button>
      </li>`;

      const filaReq = f => {
        const r = req[f] || 0, a = cobertura.asignado[f] || 0;
        if (!r && !a) return "";
        return `<li class="${a < r ? "req-falta" : "req-ok"}">
          ${esc(Turnos.ETIQUETA_FUNCION(f))}: <strong>${a}/${r}</strong></li>`;
      };

      $(".contenido-celda", caja).innerHTML = `
        <div class="ficha" style="margin-bottom:var(--e4)">
          <div class="dato"><div class="etq">Requerido según el programa</div>
            <div class="val"><ul class="req-lista">${Object.keys(funciones).map(filaReq).join("") || "Sin actividad programada"}</ul></div></div>
          <div class="dato"><div class="etq">Equipos activos</div>
            <div class="val">${req.activos.length
              ? esc(req.activos.map(e => Esquema.CATALOGOS.equipos[e].etiqueta).join(", "))
              : "—"}</div></div>
        </div>

        <h4 style="margin-bottom:var(--e2)">Personal asignado (${asignaciones.length})</h4>
        <ul class="asig-lista">${asignaciones.map(chip).join("") ||
          '<li class="card-sub">Nadie asignado todavía.</li>'}</ul>

        <div class="asig-alta">
          <div class="campo"><label>Persona</label>
            <select id="asig-usuario">
              ${candidatos.map(u => `<option value="${esc(u.id)}">${esc(u.nombre)} · ${esc(UI.etiquetaEnum(u.rol))}</option>`).join("")}
            </select></div>
          <div class="campo"><label>Función</label>
            <select id="asig-funcion">
              ${Object.entries(funciones).map(([k, v]) => `<option value="${esc(k)}">${esc(v.etiqueta)}</option>`).join("")}
            </select></div>
          <button class="btn btn-pri" id="asig-agregar">Asignar</button>
        </div>`;

      $$("[data-quitar-asig]", caja).forEach(b => b.addEventListener("click", async () => {
        await Repositorio.eliminar("asignacionTurno", b.dataset.quitarAsig);
        await recargar(); dibujar(caja); renderGrillaTurnos(semana, true);
      }));

      $("#asig-agregar", caja).addEventListener("click", async () => {
        const propuesta = {
          semanaId: semana.id, dia, turno,
          usuarioId: $("#asig-usuario", caja).value,
          funcion: $("#asig-funcion", caja).value,
          equipo: "", observacion: ""
        };
        const v = Turnos.validarAsignacion(propuesta, db);
        if (!v.permitido) { avisar(v.bloqueos[0], "bad", 6000); return; }
        try {
          await Repositorio.crear("asignacionTurno", propuesta);
          await recargar(); dibujar(caja); renderGrillaTurnos(semana, true);
          avisar("Persona asignada.", "ok", 2000);
        } catch (e) {
          avisar((e.motivos && e.motivos[0]) || e.message, "bad", 6000);
        }
      });
    };

    abrirModal({
      titulo: `${Turnos.DIAS[dia]} · Turno ${turno}`,
      subtitulo: `${semana.codigo} · ${fecha(Planificador.fechaDia(semana.fechaInicio, dia))}`,
      contenido: `<div class="contenido-celda"></div>`,
      acciones: [{ texto: "Cerrar", clase: "btn-sec" }],
      alAbrir: caja => dibujar(caja),
      alCerrar: () => renderTurnos()
    });
  }

  /* ============================================================
     Administración (CRUD de todas las entidades)
     ============================================================ */

  let adminEntidad = "producto";

  const GRUPOS_ADMIN = [
    { titulo: "Catálogos", entidades: ["producto", "receta", "mandante", "especificacion", "documentoLiberacion"] },
    { titulo: "Planta",    entidades: ["silo", "vehiculo", "usuario"] },
    { titulo: "Planificación", entidades: ["codigoProduccion", "semanaPlan", "bloquePlan", "balanceDia", "asignacionTurno"] },
    { titulo: "Registros", entidades: ["lote", "analisis", "recepcion", "movimientoSilo",
                                       "registroCalidad", "liberacion", "despacho"] },
    { titulo: "Sistema",   entidades: ["eventoAuditoria"] }
  ];

  function renderAdmin() {
    const def = Esquema.ENTIDADES[adminEntidad];

    $("#admin-menu").innerHTML = GRUPOS_ADMIN.map(g => `
      <div class="grupo">${esc(g.titulo)}</div>
      ${g.entidades.map(e => `
        <button class="admin-item ${e === adminEntidad ? "activo" : ""}" data-entidad="${esc(e)}">
          ${esc(Esquema.ENTIDADES[e].etiqueta)}
          <span class="cuenta">${(db[e] || []).length}</span>
        </button>`).join("")}`).join("");

    $$("#admin-menu [data-entidad]").forEach(b => b.addEventListener("click", () => {
      adminEntidad = b.dataset.entidad;
      renderAdmin();
    }));

    // Columnas derivadas del esquema: los primeros campos simples de la entidad
    const columnas = Object.entries(def.campos)
      .filter(([clave, c]) => clave !== "id" && !["objeto", "lista"].includes(c.tipo))
      .slice(0, 7)
      .map(([clave, c]) => ({
        clave,
        etiqueta: UI.etiquetaDe(clave),
        num: ["entero", "decimal"].includes(c.tipo),
        valor: fila => fila[clave],
        render: fila => {
          const v = fila[clave];
          if (c.tipo === "ref") {
            const destino = buscar(c.ref, v);
            return destino ? esc((ROTULOS[c.ref] || (r => r.id))(destino)) : '<span class="mono">—</span>';
          }
          if (c.tipo === "booleano") return v ? '<span class="badge ok">Sí</span>' : '<span class="badge muted">No</span>';
          if (c.tipo === "enum")     return `<span class="badge muted sin-punto">${esc(UI.etiquetaEnum(v))}</span>`;
          if (c.tipo === "fecha")    return fecha(v);
          if (["entero", "decimal"].includes(c.tipo)) return num(v, 2);
          return esc(v === null || v === undefined || v === "" ? "—" : v);
        }
      }));

    const soloLectura = !!def.soloLectura;

    $("#admin-titulo").textContent = def.etiqueta;
    $("#admin-descripcion").textContent = def.descripcion || "";
    $("#admin-nuevo").hidden = soloLectura;
    $("#admin-nuevo").textContent = `+ Nuevo · ${def.etiqueta}`;

    UI.tabla($("#admin-tabla"), {
      filas: (db[adminEntidad] || []).slice().reverse(),
      placeholderBuscar: `Buscar en ${def.etiqueta.toLowerCase()}…`,
      columnas,
      acciones: soloLectura ? null : () => botonesFila(adminEntidad),
      alPulsarAccion: (accion, fila) => {
        if (accion === "editar") editar(adminEntidad, fila.id, renderAdmin);
        if (accion === "borrar") borrar(adminEntidad, fila.id, renderAdmin);
      },
      vacio: { titulo: `Sin ${def.etiqueta.toLowerCase()}`,
               pista: soloLectura ? "Aún no hay eventos registrados." : "Cree el primer registro." }
    });
  }

  /* ============================================================
     Navegación
     ============================================================ */

  const VISTAS = {
    panel:      { titulo: "Panel general", sub: "Estado de la producción, la calidad y las liberaciones" },
    planificador: { titulo: "Planificador de producción",
                    sub: "Programa horario de planta y balance de leche de la semana" },
    turnos:     { titulo: "Turnos de personal",
                  sub: "Dotación de cada turno, deducida del programa de producción" },
    produccion: { titulo: "Producción", sub: "Lotes elaborados, análisis y resultado de calidad" },
    recepcion:  { titulo: "Recepción y silos", sub: "Leche recibida, controles de camión y ocupación de estanques" },
    calidad:    { titulo: "Calidad", sub: "Formularios de liberación, cotejo con los análisis y autorización de despacho" },
    despachos:  { titulo: "Despachos", sub: "Salidas de producto contra lotes liberados" },
    admin:      { titulo: "Administración", sub: "Catálogos, especificaciones, maestros y bitácora" }
  };

  const ACCION_VISTA = {
    planificador: { texto: "+ Nueva semana",  accion: () => nuevaSemana() },
    produccion: { texto: "+ Nuevo lote",      accion: () => editar("lote", null) },
    recepcion:  { texto: "+ Nueva recepción", accion: () => editar("recepcion", null) },
    despachos:  { texto: "+ Nuevo despacho",  accion: () => nuevoDespacho() }
  };

  function irA(ruta, sinTocarHash) {
    // Las vistas admiten un parámetro: «calidad/<idLote>» abre ese expediente,
    // de modo que se puede enlazar directamente al lote en revisión.
    const [vista, parametro] = String(ruta || "").split("/");
    if (!VISTAS[vista]) return irA("panel", sinTocarHash);
    if (vista === "calidad") expedienteActual = parametro || null;
    vistaActual = vista;
    // La vista queda en la URL: se puede enlazar y el botón «atrás» funciona.
    if (!sinTocarHash && location.hash.slice(1) !== ruta) location.hash = ruta;
    $$(".vista").forEach(v => v.classList.toggle("activa", v.id === "vista-" + vista));
    $$(".nav-item").forEach(n => n.classList.toggle("activo", n.dataset.modulo === vista));
    $("#titulo-vista").textContent = VISTAS[vista].titulo;
    $("#sub-vista").textContent = VISTAS[vista].sub;

    const boton = $("#btn-accion");
    const config = ACCION_VISTA[vista];
    boton.hidden = !config;
    if (config) { boton.textContent = config.texto; boton.onclick = config.accion; }

    renderVista();
    window.scrollTo(0, 0);
  }

  function renderVista() {
    if (vistaActual === "panel")        renderPanel();
    if (vistaActual === "planificador") renderPlanificador();
    if (vistaActual === "turnos")       renderTurnos();
    if (vistaActual === "produccion")   renderProduccion();
    if (vistaActual === "recepcion")  renderRecepcion();
    if (vistaActual === "calidad")    renderCalidad();
    if (vistaActual === "despachos")  renderDespachos();
    if (vistaActual === "admin")      renderAdmin();
    actualizarContadores();
  }

  function actualizarContadores() {
    const pendientes = db.liberacion.filter(l => !["liberado", "liberado_concesion"].includes(l.estado)).length;
    const retenidas = db.recepcion.filter(r => r.estado === "retenida").length;
    const marca = (modulo, n, alerta) => {
      const boton = $(`.nav-item[data-modulo="${modulo}"] .cuenta`);
      if (!boton) return;
      boton.textContent = n || "";
      boton.hidden = !n;
      boton.classList.toggle("alerta", !!alerta);
    };
    marca("calidad", pendientes, false);
    marca("recepcion", retenidas, true);
  }

  /* ============================================================
     Sesión, datos y arranque
     ============================================================ */

  function renderSesion() {
    const candidatos = db.usuario.filter(u => u.activo !== false)
      .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));

    $("#sesion").innerHTML = `
      <div class="avatar" aria-hidden="true">${esc(iniciales(usuario ? usuario.nombre : "?"))}</div>
      <select id="selector-usuario" aria-label="Usuario que opera">
        ${candidatos.map(u => `<option value="${esc(u.id)}" ${usuario && u.id === usuario.id ? "selected" : ""}>
          ${esc(u.nombre)} · ${esc(UI.etiquetaEnum(u.rol))}</option>`).join("")}
      </select>`;

    $("#selector-usuario").addEventListener("change", ev => {
      usuario = buscar("usuario", ev.target.value);
      localStorage.setItem(CLAVE_USUARIO, usuario.id);
      Repositorio.identificarse(usuario.id);
      renderSesion();
      renderVista();
      avisar(`Operando como ${usuario.nombre} · ${UI.etiquetaEnum(usuario.rol)}.`, "ok", 2500);
    });
  }

  function exportar() {
    const blob = new Blob([Repositorio.exportar()], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `gestion-productiva-ccaa-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    avisar("Datos exportados.", "ok");
  }

  async function importar(archivo) {
    const texto = await archivo.text();
    try {
      const { colecciones } = await Repositorio.importar(texto);
      await recargar();
      renderSesion(); renderVista();
      avisar(`Importado: ${colecciones.join(", ")}.`, "ok", 5000);
    } catch (e) {
      abrirModal({
        titulo: "No se pudo importar",
        subtitulo: "No se modificó ningún dato existente.",
        contenido: `<p style="font-size:13px;margin-bottom:var(--e3)">${esc(e.message)}</p>
          <ul class="bloqueos">${(e.motivos || []).map(m => `<li>${esc(m)}</li>`).join("")}</ul>`,
        acciones: [{ texto: "Cerrar", clase: "btn-sec" }]
      });
    }
  }

  async function restablecer() {
    const ok = await confirmar({
      titulo: "Restablecer datos",
      mensaje: "Se descartarán todos los cambios locales y se volverá a los datos de ejemplo. " +
               "Exporte antes si quiere conservarlos.",
      textoOk: "Restablecer", peligro: true
    });
    if (!ok) return;
    await Repositorio.restablecer(Semilla.construir(DATOS_SEMILLA));
    await recargar();
    renderSesion(); renderVista();
    avisar("Datos restablecidos.", "ok");
  }

  async function arrancar() {
    await Repositorio.iniciar({
      adaptador: Repositorio.AdaptadorLocalStorage(),
      semilla: Semilla.construir(DATOS_SEMILLA),
      migrar: Semilla.migrar
    });
    await recargar();

    const guardado = localStorage.getItem(CLAVE_USUARIO);
    usuario = buscar("usuario", guardado) ||
              db.usuario.find(u => u.rol === "calidad") ||
              db.usuario[0] || null;
    if (usuario) Repositorio.identificarse(usuario.id);

    // Filtros que dependen de los datos
    $("#filtro-producto").innerHTML = '<option value="todos">Todos los productos</option>' +
      db.producto.slice().sort((a, b) => a.nombre.localeCompare(b.nombre, "es"))
        .map(p => `<option value="${esc(p.id)}">${esc(p.nombre)}</option>`).join("");

    $$(".nav-item").forEach(b => b.addEventListener("click", () => irA(b.dataset.modulo)));
    $("#filtro-producto").addEventListener("change", renderProduccion);
    $("#filtro-calidad").addEventListener("change", renderProduccion);
    $("#admin-nuevo").addEventListener("click", () => editar(adminEntidad, null, renderAdmin));

    $("#btn-exportar").addEventListener("click", exportar);
    $("#btn-importar").addEventListener("click", () => $("#input-importar").click());
    $("#input-importar").addEventListener("change", ev => {
      const a = ev.target.files[0];
      if (a) importar(a);
      ev.target.value = "";
    });
    $("#btn-restablecer").addEventListener("click", restablecer);

    window.addEventListener("hashchange", () => irA(location.hash.slice(1), true));

    renderSesion();
    irA(location.hash.slice(1) || "panel", true);
  }

  return { arrancar, irA };
})();

document.addEventListener("DOMContentLoaded", () => {
  App.arrancar().catch(e => {
    document.body.innerHTML = `<div style="padding:40px;font-family:system-ui">
      <h1>No se pudo iniciar la aplicación</h1>
      <pre style="color:#a52626;white-space:pre-wrap">${e.stack || e.message}</pre></div>`;
  });
});
