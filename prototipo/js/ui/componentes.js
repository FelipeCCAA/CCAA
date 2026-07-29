/* ============================================================
   Componentes de interfaz — Gestión Productiva Planta CCAA
   ------------------------------------------------------------
   Piezas reutilizables: avisos, confirmaciones, ventanas modales
   accesibles, tablas con orden/búsqueda/paginación y formularios
   generados a partir del esquema.

   Nada de alert() ni confirm(): bloquean el navegador y no se pueden
   estilar. Todo diálogo aquí atrapa el foco, cierra con Escape y
   devuelve el foco al elemento que lo abrió.
   ============================================================ */

const UI = (() => {

  const $  = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => Array.from(c.querySelectorAll(s));

  const esc = t => (t === null || t === undefined) ? "" : String(t)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

  const num = (n, d = 0) => (n === null || n === undefined || n === "" || isNaN(Number(n)))
    ? "—"
    : Number(n).toLocaleString("es-CL", { minimumFractionDigits: 0, maximumFractionDigits: d });

  const fecha = f => {
    if (!f) return "—";
    const [a, m, d] = String(f).slice(0, 10).split("-");
    return (a && m && d) ? `${d}-${m}-${a}` : String(f);
  };

  const iniciales = nombre => String(nombre || "?").split(/\s+/).slice(0, 2)
    .map(p => p[0] || "").join("").toUpperCase();

  /* Iconos en SVG: monocromos y consistentes. Los emoji se pintan a color
     según el sistema operativo y rompen la sobriedad de la interfaz. */
  const TRAZOS = {
    editar:  '<path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17v3Z"/>',
    borrar:  '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/>',
    analisis:'<path d="M9 3h6M10 3v6l-6 11h16L14 9V3M7.5 15h9"/>',
    cerrar:  '<path d="M18 6 6 18M6 6l12 12"/>',
    buscar:  '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/>',
    aviso:   '<path d="M12 3 2 20h20L12 3ZM12 9v5M12 17.5v.5"/>'
  };

  const icono = (nombre, tam = 15) =>
    `<svg viewBox="0 0 24 24" width="${tam}" height="${tam}" fill="none" stroke="currentColor"
          stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"
          aria-hidden="true" focusable="false">${TRAZOS[nombre] || ""}</svg>`;

  /* ============================================================
     Avisos flotantes
     ============================================================ */

  function contenedorTostadas() {
    let c = $(".tostadas");
    if (!c) {
      c = document.createElement("div");
      c.className = "tostadas";
      c.setAttribute("role", "status");
      c.setAttribute("aria-live", "polite");
      document.body.appendChild(c);
    }
    return c;
  }

  function avisar(mensaje, tono = "ok", ms = 3800) {
    const t = document.createElement("div");
    t.className = `tostada ${tono}`;
    t.innerHTML = `<div>${esc(mensaje)}</div>
      <button class="cerrar" aria-label="Cerrar aviso">×</button>`;
    contenedorTostadas().appendChild(t);

    const quitar = () => {
      t.classList.add("saliendo");
      t.addEventListener("animationend", () => t.remove(), { once: true });
    };
    $(".cerrar", t).addEventListener("click", quitar);
    if (ms) setTimeout(quitar, ms);
    return quitar;
  }

  /* ============================================================
     Ventana modal accesible
     ============================================================ */

  const FOCALIZABLES = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

  /* Los diálogos se apilan: un formulario puede abrir otro encima (crear el
     componente que falta sin salir de la receta). Solo el de arriba responde
     a Escape y atrapa el tabulador; si no, una tecla cerraría los dos. */
  const pilaModales = [];

  /** abrirModal({ titulo, subtitulo, contenido, acciones, ancho, alAbrir })
   *  Devuelve { cerrar, caja }. Las acciones son
   *  [{ texto, clase, alPulsar(cerrar), izquierda, id }]. */
  function abrirModal(opciones) {
    const focoPrevio = document.activeElement;

    const velo = document.createElement("div");
    velo.className = "velo";

    const acciones = (opciones.acciones || []).map((a, i) => `
      <button type="button" class="btn ${a.clase || "btn-sec"} ${a.izquierda ? "a-la-izquierda" : ""}"
              data-accion="${i}" ${a.id ? `id="${esc(a.id)}"` : ""}>${esc(a.texto)}</button>`).join("");

    velo.innerHTML = `
      <div class="modal ${opciones.ancho || ""}" role="dialog" aria-modal="true" aria-labelledby="modal-titulo">
        <div class="modal-head">
          <div>
            <h2 id="modal-titulo">${esc(opciones.titulo || "")}</h2>
            ${opciones.subtitulo ? `<p class="card-sub">${esc(opciones.subtitulo)}</p>` : ""}
          </div>
          <button class="btn-icono" data-cerrar aria-label="Cerrar">${icono("cerrar")}</button>
        </div>
        <div class="modal-cuerpo"></div>
        ${acciones ? `<div class="modal-pie">${acciones}</div>` : ""}
      </div>`;

    const caja = $(".modal", velo);
    const cuerpo = $(".modal-cuerpo", velo);
    if (typeof opciones.contenido === "string") cuerpo.innerHTML = opciones.contenido;
    else if (opciones.contenido) cuerpo.appendChild(opciones.contenido);

    let cerrado = false;
    function cerrar(resultado) {
      if (cerrado) return;
      cerrado = true;
      document.removeEventListener("keydown", alPulsarTecla, true);
      const posicion = pilaModales.indexOf(velo);
      if (posicion >= 0) pilaModales.splice(posicion, 1);
      velo.remove();
      if (focoPrevio && focoPrevio.focus) focoPrevio.focus();
      if (opciones.alCerrar) opciones.alCerrar(resultado);
    }

    function alPulsarTecla(ev) {
      if (pilaModales[pilaModales.length - 1] !== velo) return;   // solo el de arriba
      if (ev.key === "Escape") { ev.preventDefault(); cerrar(); return; }
      if (ev.key !== "Tab") return;
      // Atrapa el foco dentro del diálogo.
      const focos = $$(FOCALIZABLES, caja).filter(e => e.offsetParent !== null);
      if (!focos.length) return;
      const primero = focos[0], ultimo = focos[focos.length - 1];
      if (ev.shiftKey && document.activeElement === primero) { ev.preventDefault(); ultimo.focus(); }
      else if (!ev.shiftKey && document.activeElement === ultimo) { ev.preventDefault(); primero.focus(); }
    }

    $("[data-cerrar]", velo).addEventListener("click", () => cerrar());
    velo.addEventListener("mousedown", ev => { if (ev.target === velo) cerrar(); });
    $$("[data-accion]", velo).forEach(b => b.addEventListener("click", () => {
      const a = opciones.acciones[Number(b.dataset.accion)];
      if (a.alPulsar) a.alPulsar(cerrar, caja); else cerrar();
    }));
    document.addEventListener("keydown", alPulsarTecla, true);

    document.body.appendChild(velo);
    pilaModales.push(velo);

    const inicial = $("[data-foco-inicial]", caja) || $$(FOCALIZABLES, cuerpo)[0] || $("[data-cerrar]", velo);
    if (inicial) inicial.focus();

    if (opciones.alAbrir) opciones.alAbrir(caja, cerrar);
    return { cerrar, caja };
  }

  /** Confirmación no bloqueante. Devuelve Promise<boolean>. */
  function confirmar(opciones) {
    return new Promise(resolver => {
      let respondido = false;
      abrirModal({
        titulo: opciones.titulo || "¿Confirmar?",
        ancho: "angosto",
        contenido: `<p style="font-size:13.5px;color:var(--gris-700)">${esc(opciones.mensaje || "")}</p>`,
        acciones: [
          { texto: opciones.textoCancelar || "Cancelar", clase: "btn-sec",
            alPulsar: cerrar => { respondido = true; resolver(false); cerrar(); } },
          { texto: opciones.textoOk || "Confirmar",
            clase: opciones.peligro ? "btn-peligro" : "btn-pri", id: "confirmar-ok",
            alPulsar: cerrar => { respondido = true; resolver(true); cerrar(); } }
        ],
        alAbrir: caja => { const b = $("#confirmar-ok", caja); if (b) b.focus(); },
        alCerrar: () => { if (!respondido) resolver(false); }
      });
    });
  }

  /* ============================================================
     Tabla con orden, búsqueda y paginación
     ============================================================ */

  const textoDeCelda = (col, fila) => {
    const v = fila[col.clave];
    return (v === null || v === undefined) ? "" : String(v);
  };

  /** tabla(contenedor, config) — vuelve a dibujar conservando orden/página. */
  function tabla(contenedor, config) {
    const estado = contenedor._estadoTabla || { orden: config.ordenInicial || null, dir: config.dirInicial || 1, texto: "", pagina: 1 };
    contenedor._estadoTabla = estado;

    const cols = config.columnas;
    const porPagina = config.porPagina || 25;
    const conAcciones = !!config.acciones;

    function dibujar() {
      let filas = config.filas.slice();

      if (estado.texto) {
        const t = estado.texto.toLowerCase();
        filas = filas.filter(f => cols.some(c => {
          const crudo = c.buscar ? c.buscar(f) : textoDeCelda(c, f);
          return String(crudo).toLowerCase().includes(t);
        }));
      }

      if (estado.orden) {
        const col = cols.find(c => c.clave === estado.orden);
        filas.sort((a, b) => {
          const va = col && col.valor ? col.valor(a) : a[estado.orden];
          const vb = col && col.valor ? col.valor(b) : b[estado.orden];
          if (va === vb) return 0;
          if (va === null || va === undefined || va === "") return 1;
          if (vb === null || vb === undefined || vb === "") return -1;
          const comparacion = (typeof va === "number" && typeof vb === "number")
            ? va - vb
            : String(va).localeCompare(String(vb), "es", { numeric: true });
          return comparacion * estado.dir;
        });
      }

      const total = filas.length;
      const paginas = Math.max(1, Math.ceil(total / porPagina));
      if (estado.pagina > paginas) estado.pagina = paginas;
      const visibles = filas.slice((estado.pagina - 1) * porPagina, estado.pagina * porPagina);

      const barra = (config.buscar === false && !config.barraExtra) ? "" : `
        <div class="tabla-barra">
          ${config.buscar === false ? "" : `
            <div class="buscador">
              <span class="lupa">${icono("buscar", 14)}</span>
              <input type="search" placeholder="${esc(config.placeholderBuscar || "Buscar…")}"
                     value="${esc(estado.texto)}" aria-label="Buscar en la tabla" data-buscar />
            </div>`}
          ${config.barraExtra || ""}
          <span class="tabla-conteo">${total === config.filas.length
            ? `${total} registro${total === 1 ? "" : "s"}`
            : `${total} de ${config.filas.length}`}</span>
        </div>`;

      const encabezado = `<tr>${cols.map(c => {
        const ordenado = estado.orden === c.clave;
        const flecha = ordenado ? (estado.dir === 1 ? "▲" : "▼") : "▲";
        return `<th class="${c.ordenable === false ? "" : "ordenable"} ${ordenado ? "ordenado" : ""} ${c.num ? "der" : ""}"
                    ${c.ordenable === false ? "" : `data-ordenar="${esc(c.clave)}"`}
                    ${c.ancho ? `style="width:${c.ancho}"` : ""}
                    ${ordenado ? `aria-sort="${estado.dir === 1 ? "ascending" : "descending"}"` : ""}>
                  ${esc(c.etiqueta)}${c.ordenable === false ? "" : `<span class="flecha">${flecha}</span>`}
                </th>`;
      }).join("")}${conAcciones ? '<th class="der" style="width:1%"></th>' : ""}</tr>`;

      const cuerpo = visibles.length
        ? visibles.map(f => `
            <tr class="${config.claseFila ? config.claseFila(f) : ""}" data-id="${esc(f.id || "")}">
              ${cols.map(c => `<td class="${c.num ? "num" : ""} ${c.clase || ""}">${c.render ? c.render(f) : esc(textoDeCelda(c, f))}</td>`).join("")}
              ${conAcciones ? `<td><div class="acciones-fila">${config.acciones(f)}</div></td>` : ""}
            </tr>`).join("")
        : `<tr><td colspan="${cols.length + (conAcciones ? 1 : 0)}">
             <div class="vacio">
               <span class="ico" aria-hidden="true">${estado.texto ? "⌕" : (config.vacio && config.vacio.ico) || "▤"}</span>
               <div class="titulo">${esc(estado.texto ? "Sin coincidencias" : (config.vacio && config.vacio.titulo) || "Sin registros")}</div>
               <div class="pista">${esc(estado.texto ? `Nada coincide con "${estado.texto}".` : (config.vacio && config.vacio.pista) || "")}</div>
             </div></td></tr>`;

      const paginacion = paginas > 1 ? `
        <div class="paginacion">
          <span class="pagina">Página ${estado.pagina} de ${paginas}</span>
          <button class="btn btn-sec btn-sm" data-pagina="ant" ${estado.pagina === 1 ? "disabled" : ""}>Anterior</button>
          <button class="btn btn-sec btn-sm" data-pagina="sig" ${estado.pagina === paginas ? "disabled" : ""}>Siguiente</button>
        </div>` : "";

      contenedor.innerHTML = `${barra}<div class="tabla-wrap"><table class="tabla">
        <thead>${encabezado}</thead><tbody>${cuerpo}</tbody></table></div>${paginacion}`;

      $$("[data-ordenar]", contenedor).forEach(th => th.addEventListener("click", () => {
        const clave = th.dataset.ordenar;
        if (estado.orden === clave) estado.dir = -estado.dir;
        else { estado.orden = clave; estado.dir = 1; }
        dibujar();
      }));

      const buscador = $("[data-buscar]", contenedor);
      if (buscador) {
        buscador.addEventListener("input", ev => {
          estado.texto = ev.target.value;
          estado.pagina = 1;
          dibujar();
          const nuevo = $("[data-buscar]", contenedor);
          if (nuevo) { nuevo.focus(); nuevo.setSelectionRange(nuevo.value.length, nuevo.value.length); }
        });
      }

      $$("[data-pagina]", contenedor).forEach(b => b.addEventListener("click", () => {
        estado.pagina += b.dataset.pagina === "sig" ? 1 : -1;
        dibujar();
        contenedor.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }));

      if (config.alPulsarAccion) {
        $$("[data-accion-fila]", contenedor).forEach(b => b.addEventListener("click", ev => {
          ev.stopPropagation();
          const fila = config.filas.find(f => f.id === b.closest("tr").dataset.id);
          config.alPulsarAccion(b.dataset.accionFila, fila);
        }));
      }
    }

    dibujar();
  }

  /* ============================================================
     Formularios generados desde el esquema
     ============================================================ */

  const ETIQUETAS_CAMPO = {
    codigoLote: "Código de lote", kgProducidos: "Kilos producidos", productoId: "Producto",
    mandanteId: "Mandante", siloId: "Silo / estanque", vehiculoId: "Camión",
    operadorId: "Operador", analistaId: "Analista", loteId: "Lote",
    capacidadL: "Capacidad (L)", tipoLeche: "Tipo de leche", vigenteDesde: "Vigente desde",
    vigenteHasta: "Vigente hasta", aplicaA: "Aplica a", horaInicio: "Hora de inicio",
    horaTermino: "Hora de término", choferAM: "Chofer A.M.", choferPM: "Chofer P.M.",
    autorizadaPorId: "Autorizada por", motivoConcesion: "Motivo de la concesión",
    documentoId: "Documento", usuarioId: "Usuario", fechaHora: "Fecha y hora"
  };

  const etiquetaDe = clave => ETIQUETAS_CAMPO[clave] ||
    clave.replace(/([A-Z])/g, " $1").replace(/^./, c => c.toUpperCase()).replace(/ Id$/, "");

  const ETIQUETA_ENUM = {
    polvo: "Polvo", crema: "Crema", liquido: "Líquido", otro: "Otro",
    silo: "Silo", tk_ld: "TK Leche descremada", tk_crema: "TK Crema",
    recepcion: "Recepción", produccion: "Producción", calidad: "Calidad",
    admin: "Administrador", lectura: "Solo lectura",
    en_proceso: "En proceso", producido: "Producido", cerrado: "Cerrado", anulado: "Anulado",
    pendiente: "Pendiente", en_revision: "En revisión", liberado: "Liberado",
    liberado_concesion: "Liberado por concesión", rechazado: "Rechazado",
    registrada: "Registrada", muestreada: "Muestreada", analizada: "Analizada",
    liberada: "Liberada", retenida: "Retenida", descargada: "Descargada", cerrada: "Cerrada",
    borrador: "Borrador", emitido: "Emitido",
    ingreso: "Ingreso", salida: "Salida", ajuste: "Ajuste",
    crear: "Alta", actualizar: "Modificación", eliminar: "Baja"
  };

  const etiquetaEnum = v => ETIQUETA_ENUM[v] || v;

  /** Dibuja un campo del esquema. `refs` mapea entidad → [{id, texto}]. */
  function campo(clave, def, valor, refs) {
    const etq = etiquetaDe(clave);
    const req = def.req ? '<span class="req" aria-hidden="true">*</span>' : "";
    const ayuda = def.nota ? `<span class="ayuda">${esc(def.nota)}</span>` : "";
    const id = `campo-${clave}`;
    const comun = `id="${id}" name="${esc(clave)}" ${def.req ? "required" : ""}`;
    const v = valor === null || valor === undefined ? "" : valor;
    let control;

    switch (def.tipo) {
      case "enum":
        control = `<select ${comun}>
          ${def.req ? "" : '<option value="">— sin definir —</option>'}
          ${def.valores.map(o => `<option value="${esc(o)}" ${o === v ? "selected" : ""}>${esc(etiquetaEnum(o))}</option>`).join("")}
        </select>`;
        break;
      case "ref": {
        const opciones = (refs && refs[def.ref]) || [];
        control = `<select ${comun}>
          <option value="">— sin asignar —</option>
          ${opciones.map(o => `<option value="${esc(o.id)}" ${o.id === v ? "selected" : ""}>${esc(o.texto)}</option>`).join("")}
        </select>`;
        break;
      }
      case "booleano":
        return `<div class="campo"><label class="interruptor">
          <input type="checkbox" id="${id}" name="${esc(clave)}" ${v ? "checked" : ""} /> ${esc(etq)}
        </label>${ayuda}</div>`;
      case "entero":
        control = `<input type="number" step="1" ${def.min !== undefined ? `min="${def.min}"` : ""} ${comun} value="${esc(v)}" />`;
        break;
      case "decimal":
        control = `<input type="number" step="any" ${def.min !== undefined ? `min="${def.min}"` : ""} ${comun} value="${esc(v)}" />`;
        break;
      case "fecha":
        control = `<input type="date" ${comun} value="${esc(String(v).slice(0, 10))}" />`;
        break;
      case "hora":
        control = `<input type="time" ${comun} value="${esc(v)}" />`;
        break;
      case "lista":
        if (def.de === "objeto" && def.campos) return editorFilas(clave, def, v, refs);
        if (def.de === "enum") {
          const sel = Array.isArray(v) ? v : [];
          return `<div class="campo ancho-total"><label>${esc(etq)}${req}</label>
            <div style="display:flex;gap:var(--e4);flex-wrap:wrap">
              ${def.valores.map(o => `<label class="interruptor">
                <input type="checkbox" name="${esc(clave)}" value="${esc(o)}" ${sel.includes(o) ? "checked" : ""} />
                ${esc(etiquetaEnum(o))}</label>`).join("")}
            </div>${ayuda}</div>`;
        }
        control = `<textarea ${comun} rows="3" data-json>${esc(JSON.stringify(v || [], null, 1))}</textarea>`;
        break;
      case "objeto":
        if (def.campos) return grupoObjeto(clave, def, v);
        control = `<textarea ${comun} rows="4" data-json>${esc(JSON.stringify(v || {}, null, 1))}</textarea>`;
        break;
      default:
        control = `<input type="text" ${comun} value="${esc(v)}" />`;
    }

    const ancho = ["objeto", "lista"].includes(def.tipo) || clave === "observacion" ? "ancho-total" : "";
    return `<div class="campo ${ancho}" data-campo="${esc(clave)}">
      <label for="${id}">${esc(etq)}${req}</label>${control}${ayuda}
      <span class="error" hidden></span></div>`;
  }

  /* ============================================================
     Formularios de calidad, generados desde la plantilla del documento
     ============================================================ */

  /** Dibuja un campo de una plantilla de formulario. `soloLectura` se usa para
   *  mostrar un registro ya firmado tal como se completó. */
  function campoPlantilla(campo, valor, soloLectura, prefijo) {
    const nombre = (prefijo || "") + campo.clave;
    const id = `fc-${nombre.replace(/\./g, "-")}`;
    const req = campo.req ? '<span class="req" aria-hidden="true">*</span>' : "";
    const unidad = campo.unidad ? ` <span class="unidad">(${esc(campo.unidad)})</span>` : "";
    const bloqueo = soloLectura ? "disabled" : "";
    const v = valor === null || valor === undefined ? "" : valor;
    const comun = `id="${id}" data-campo-plantilla="${esc(nombre)}" ${bloqueo}`;
    let control;

    switch (campo.tipo) {
      case "booleano":
        return `<div class="campo" data-campo="${esc(nombre)}">
          <label class="interruptor"><input type="checkbox" ${comun} ${v ? "checked" : ""} />
            ${esc(campo.etiqueta)}${req}</label>
          ${campo.ayuda ? `<span class="ayuda">${esc(campo.ayuda)}</span>` : ""}
          <span class="error" hidden></span></div>`;
      case "enum":
        control = `<select ${comun}>
          ${campo.req ? "" : '<option value="">— sin definir —</option>'}
          ${(campo.valores || []).map(o => `<option value="${esc(o)}" ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("")}
        </select>`;
        break;
      case "entero":
        control = `<input type="number" step="1" ${campo.min !== undefined ? `min="${campo.min}"` : ""} ${campo.max !== undefined ? `max="${campo.max}"` : ""} ${comun} value="${esc(v)}" />`;
        break;
      case "decimal":
        control = `<input type="number" step="any" ${campo.min !== undefined ? `min="${campo.min}"` : ""} ${campo.max !== undefined ? `max="${campo.max}"` : ""} ${comun} value="${esc(v)}" />`;
        break;
      case "fecha":
        control = `<input type="date" ${comun} value="${esc(String(v).slice(0, 10))}" />`;
        break;
      case "hora":
        control = `<input type="time" ${comun} value="${esc(v)}" />`;
        break;
      default:
        control = campo.clave === "observacion"
          ? `<textarea rows="2" ${comun}>${esc(v)}</textarea>`
          : `<input type="text" ${comun} value="${esc(v)}" />`;
    }

    const ancho = campo.clave === "observacion" ? "ancho-total" : "";
    return `<div class="campo ${ancho}" data-campo="${esc(nombre)}">
      <label for="${id}">${esc(campo.etiqueta)}${unidad}${req}
        ${campo.origen ? '<span class="chip" title="Se toma del lote">auto</span>' : ""}
        ${campo.parametro ? '<span class="chip" title="Se coteja con el análisis del lote">cotejado</span>' : ""}
      </label>
      ${control}
      ${campo.ayuda ? `<span class="ayuda">${esc(campo.ayuda)}</span>` : ""}
      <span class="error" hidden></span></div>`;
  }

  /** Lee un formulario de plantilla y convierte cada valor según su tipo. */
  function leerPlantilla(plantilla, raiz, prefijo) {
    const valores = {};
    (plantilla || []).forEach(campo => {
      const el = $(`[data-campo-plantilla="${(prefijo || "") + campo.clave}"]`, raiz);
      if (!el) return;
      switch (campo.tipo) {
        case "booleano": valores[campo.clave] = el.checked; break;
        case "entero":   valores[campo.clave] = el.value === "" ? null : parseInt(el.value, 10); break;
        case "decimal":  valores[campo.clave] = el.value === "" ? null : Number(el.value); break;
        default:         valores[campo.clave] = el.value;
      }
    });
    return valores;
  }

  /** Un campo de tipo objeto que declara sus subcampos se dibuja como un
   *  grupo de campos reales. Sin esta rama caía en un cuadro de texto con
   *  JSON crudo: inservible para quien completa el registro en planta. */
  function grupoObjeto(clave, def, valor) {
    const valores = valor || {};
    return `<fieldset class="grupo-objeto ancho-total" data-grupo="${esc(clave)}">
      <legend>${esc(def.etiqueta || etiquetaDe(clave))}</legend>
      ${def.nota ? `<p class="ayuda">${esc(def.nota)}</p>` : ""}
      <div class="form-grid">
        ${def.campos.map(c => campoPlantilla(c, valores[c.clave], false, clave + ".")).join("")}
      </div>
    </fieldset>`;
  }

  /* ---------- Listas de objetos: editor de filas ----------
     Una lista de objetos en JSON es tan inservible como un objeto en JSON.
     Si la lista declara sus `campos`, se dibuja como filas con controles. */

  const VALOR_NUEVO = "__crear_nuevo__";

  function controlSubcampo(campo, valor, refs) {
    const v = valor === null || valor === undefined ? "" : valor;
    const comun = `data-sub="${esc(campo.clave)}" ${campo.req ? "required" : ""}`;
    let control;

    switch (campo.tipo) {
      case "ref": {
        const opciones = (refs && refs[campo.ref]) || [];
        control = `<select ${comun} data-ref="${esc(campo.ref)}">
          <option value="">— elegir —</option>
          ${opciones.map(o => `<option value="${esc(o.id)}" ${o.id === v ? "selected" : ""}>${esc(o.texto)}</option>`).join("")}
          ${campo.permiteCrear ? `<option value="${VALOR_NUEVO}">＋ Crear uno nuevo…</option>` : ""}
        </select>`;
        break;
      }
      case "enum":
        control = `<select ${comun}>
          ${campo.req ? "" : '<option value=""></option>'}
          ${(campo.valores || []).map(o => `<option value="${esc(o)}" ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("")}
        </select>`;
        break;
      case "booleano":
        control = `<input type="checkbox" ${comun} ${v ? "checked" : ""} />`;
        break;
      case "entero":
        control = `<input type="number" step="1" ${comun} value="${esc(v)}" />`;
        break;
      case "decimal":
        control = `<input type="number" step="any" ${comun} value="${esc(v)}" />`;
        break;
      default:
        control = `<input type="text" ${comun} value="${esc(v)}" />`;
    }

    return `<div class="campo">
      <label>${esc(campo.etiqueta)}${campo.unidad ? ` <span class="unidad">(${esc(campo.unidad)})</span>` : ""}</label>
      ${control}
      ${campo.ayuda ? `<span class="ayuda">${esc(campo.ayuda)}</span>` : ""}
    </div>`;
  }

  const filaLista = (campos, valores, refs) => `
    <div class="fila-lista" data-fila>
      ${campos.map(c => controlSubcampo(c, (valores || {})[c.clave], refs)).join("")}
      <button type="button" class="btn-icono peligro" data-quitar
              title="Quitar" aria-label="Quitar de la lista">${icono("cerrar", 14)}</button>
    </div>`;

  function editorFilas(clave, def, valor, refs) {
    const filas = Array.isArray(valor) ? valor : [];
    return `<fieldset class="grupo-objeto ancho-total" data-lista="${esc(clave)}">
      <legend>${esc(def.etiqueta || etiquetaDe(clave))}${def.req ? '<span class="req">*</span>' : ""}</legend>
      ${def.nota ? `<p class="ayuda">${esc(def.nota)}</p>` : ""}
      <div class="filas-lista" data-filas>${filas.map(f => filaLista(def.campos, f, refs)).join("")}</div>
      <button type="button" class="btn btn-sec btn-sm" data-agregar style="margin-top:var(--e3)">+ Agregar</button>
    </fieldset>`;
  }

  /** Enlaza agregar/quitar filas y, si un subcampo lo permite, la creación de
   *  un registro referenciado sin salir del formulario.
   *  `alCrearRef(entidadDestino, devolver)` lo provee quien sabe crear datos. */
  function conectarListas(raiz, entidad, refs, alCrearRef) {
    const def = Esquema.ENTIDADES[entidad];
    if (!def) return;

    $$("[data-lista]", raiz).forEach(caja => {
      const campo = def.campos[caja.dataset.lista];
      if (!campo || !campo.campos) return;
      const contenedor = $("[data-filas]", caja);

      const enlazar = fila => {
        const boton = $("[data-quitar]", fila);
        if (boton) boton.addEventListener("click", () => fila.remove());
        $$("select[data-ref]", fila).forEach(enlazarCreacion);
      };

      function enlazarCreacion(select) {
        if (!$(`option[value="${VALOR_NUEVO}"]`, select)) return;
        select.dataset.previo = select.value;
        select.addEventListener("change", () => {
          if (select.value !== VALOR_NUEVO) { select.dataset.previo = select.value; return; }
          // Se restaura de inmediato: si el usuario cancela, el selector no
          // queda mostrando una opción que no es un valor real.
          select.value = select.dataset.previo || "";
          if (!alCrearRef) { avisar("No se puede crear desde aquí.", "warn"); return; }

          alCrearRef(select.dataset.ref, nuevo => {
            const opcion = document.createElement("option");
            opcion.value = nuevo.id;
            opcion.textContent = nuevo.texto;
            select.insertBefore(opcion, $(`option[value="${VALOR_NUEVO}"]`, select));
            select.value = nuevo.id;
            select.dataset.previo = nuevo.id;
            select.dispatchEvent(new Event("input", { bubbles: true }));
          });
        });
      }

      $$("[data-fila]", contenedor).forEach(enlazar);

      const agregar = $("[data-agregar]", caja);
      if (agregar) agregar.addEventListener("click", () => {
        const temporal = document.createElement("div");
        temporal.innerHTML = filaLista(campo.campos, {}, refs);
        const nueva = temporal.firstElementChild;
        contenedor.appendChild(nueva);
        enlazar(nueva);
        const primero = $("select,input", nueva);
        if (primero) primero.focus();
      });
    });
  }

  function leerFilas(clave, def, raiz) {
    const caja = $(`[data-lista="${clave}"]`, raiz);
    if (!caja) return null;
    return $$("[data-fila]", caja).map(fila => {
      const objeto = {};
      def.campos.forEach(c => {
        const el = $(`[data-sub="${c.clave}"]`, fila);
        if (!el) return;
        switch (c.tipo) {
          case "booleano": objeto[c.clave] = el.checked; break;
          case "entero":   objeto[c.clave] = el.value === "" ? null : parseInt(el.value, 10); break;
          case "decimal":  objeto[c.clave] = el.value === "" ? null : Number(el.value); break;
          default:         objeto[c.clave] = el.value;
        }
      });
      return objeto;
    });
  }

  /** Editor específico para los rangos de una especificación.
   *  Es la regla que decide si un lote se libera: merece un editor propio
   *  y no un cuadro de texto con JSON. */
  function editorRangos(rangos) {
    const params = Esquema.CATALOGOS.parametros;
    return `<div class="rangos" data-editor-rangos>
      ${Object.entries(params).map(([clave, meta]) => {
        const r = (rangos || {})[clave] || {};
        const activo = (rangos || {})[clave] !== undefined;
        return `<div class="rango-fila" data-param="${esc(clave)}">
          <label class="interruptor">
            <input type="checkbox" data-activo ${activo ? "checked" : ""} />
            <span class="etq">${esc(meta.etiqueta)} ${meta.unidad ? `<span class="unidad">(${esc(meta.unidad)})</span>` : ""}</span>
          </label>
          <input type="number" step="any" data-min placeholder="mínimo" value="${r.min ?? ""}" ${activo ? "" : "disabled"} aria-label="Mínimo de ${esc(meta.etiqueta)}" />
          <input type="number" step="any" data-max placeholder="máximo" value="${r.max ?? ""}" ${activo ? "" : "disabled"} aria-label="Máximo de ${esc(meta.etiqueta)}" />
          <label class="interruptor" title="Si es obligatorio, un lote sin este parámetro no puede liberarse">
            <input type="checkbox" data-obligatorio ${r.obligatorio ? "checked" : ""} ${activo ? "" : "disabled"} />
            <span style="font-size:11.5px">Obligatorio</span>
          </label>
        </div>`;
      }).join("")}
    </div>`;
  }

  function conectarEditorRangos(raiz) {
    $$("[data-editor-rangos] .rango-fila", raiz).forEach(fila => {
      const activo = $("[data-activo]", fila);
      const otros = $$("input:not([data-activo])", fila);
      activo.addEventListener("change", () => {
        otros.forEach(i => { i.disabled = !activo.checked; if (!activo.checked) i.value = ""; });
      });
    });
  }

  function leerRangos(raiz) {
    const rangos = {};
    $$("[data-editor-rangos] .rango-fila", raiz).forEach(fila => {
      if (!$("[data-activo]", fila).checked) return;
      const min = $("[data-min]", fila).value;
      const max = $("[data-max]", fila).value;
      const r = { obligatorio: $("[data-obligatorio]", fila).checked };
      if (min !== "") r.min = Number(min);
      if (max !== "") r.max = Number(max);
      rangos[fila.dataset.param] = r;
    });
    return rangos;
  }

  /** Lee un formulario y convierte cada valor según el tipo del esquema. */
  function leerFormulario(entidad, raiz) {
    const def = Esquema.ENTIDADES[entidad];
    const salida = {};

    for (const [clave, campoDef] of Object.entries(def.campos)) {
      if (clave === "id") continue;

      if (clave === "rangos" && $("[data-editor-rangos]", raiz)) { salida.rangos = leerRangos(raiz); continue; }

      // Objeto con subcampos declarados: se lee campo a campo y se descartan
      // los vacíos, para no guardar un montón de null sin significado.
      if (campoDef.tipo === "objeto" && campoDef.campos && $(`[data-grupo="${clave}"]`, raiz)) {
        const leidos = leerPlantilla(campoDef.campos, raiz, clave + ".");
        const limpio = {};
        for (const [k, valor] of Object.entries(leidos)) {
          if (valor !== null && valor !== undefined && valor !== "") limpio[k] = valor;
        }
        salida[clave] = limpio;
        continue;
      }

      if (campoDef.tipo === "lista" && campoDef.de === "objeto" && campoDef.campos) {
        const filas = leerFilas(clave, campoDef, raiz);
        if (filas !== null) { salida[clave] = filas; continue; }
      }

      if (campoDef.tipo === "lista" && campoDef.de === "enum") {
        salida[clave] = $$(`input[name="${clave}"]:checked`, raiz).map(i => i.value);
        continue;
      }

      const el = $(`[name="${clave}"]`, raiz);
      if (!el) continue;

      switch (campoDef.tipo) {
        case "booleano": salida[clave] = el.checked; break;
        case "entero":   salida[clave] = el.value === "" ? null : parseInt(el.value, 10); break;
        case "decimal":  salida[clave] = el.value === "" ? null : Number(el.value); break;
        case "objeto":
        case "lista":
          try { salida[clave] = el.value.trim() ? JSON.parse(el.value) : (campoDef.tipo === "lista" ? [] : {}); }
          catch (e) { salida[clave] = el.value; }   // que la validación del esquema lo rechace
          break;
        default: salida[clave] = el.value;
      }
    }
    return salida;
  }

  /** Pinta los errores de validación junto a cada campo. */
  function mostrarErrores(raiz, errores) {
    $$("[data-campo]", raiz).forEach(c => {
      c.classList.remove("invalido");
      const e = $(".error", c);
      if (e) { e.hidden = true; e.textContent = ""; }
    });
    const sueltos = [];
    errores.forEach(msg => {
      const campo = $$("[data-campo]", raiz).find(c => {
        const etq = $("label", c);
        return etq && msg.startsWith(etq.textContent.replace("*", "").trim() + ":");
      });
      if (campo) {
        campo.classList.add("invalido");
        const e = $(".error", campo);
        if (e) { e.hidden = false; e.textContent = msg.split(":").slice(1).join(":").trim(); }
      } else sueltos.push(msg);
    });
    return sueltos;
  }

  return {
    $, $$, esc, num, fecha, iniciales, icono,
    avisar, abrirModal, confirmar,
    tabla,
    campo, etiquetaDe, etiquetaEnum, editorRangos, conectarEditorRangos, leerRangos,
    campoPlantilla, leerPlantilla, grupoObjeto,
    editorFilas, conectarListas, leerFilas,
    leerFormulario, mostrarErrores
  };
})();
