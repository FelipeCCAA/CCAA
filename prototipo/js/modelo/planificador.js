/* ============================================================
   Planificador — Gestión Productiva Planta CCAA
   ------------------------------------------------------------
   Reglas del programa semanal de planta. Funciones PURAS: reciben
   datos y devuelven datos. Sin DOM, sin almacenamiento, sin red.

   Idea central, heredada del Excel:
     el PROGRAMA HORARIO genera el CONSUMO del BALANCE DE LECHE.
   No son dos tablas independientes. Mover un bloque de evaporador
   recalcula el consumo del día y, por arrastre, el stock de toda la
   semana. Por eso ni el consumo ni los stocks se persisten nunca.
   ============================================================ */

const Planificador = (() => {

  const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
  const DIAS_CORTO = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

  const ETIQUETA_ORIGEN = { ccaa: "CCAA", nestle: "Nestlé", punion: "P. Unión" };

  const catalogos      = () => Esquema.CATALOGOS;
  const categorias     = () => catalogos().categoriasConsumo;
  const evaporadores   = () => catalogos().evaporadores;
  const origenes       = () => catalogos().origenesLeche;

  const numero = v => { const n = Number(v); return isNaN(n) ? 0 : n; };

  /** Familia de un código: los dos primeros caracteres (RC, LN, LU, LC). */
  const familiaDeCodigo = codigo => String(codigo || "").slice(0, 2).toUpperCase();

  /** Fecha de un día de la semana, sin sorpresas de huso horario. */
  function fechaDia(fechaInicio, dia) {
    if (!fechaInicio) return "";
    const [a, m, d] = String(fechaInicio).slice(0, 10).split("-").map(Number);
    if (!a || !m || !d) return "";
    return new Date(Date.UTC(a, m - 1, d + dia)).toISOString().slice(0, 10);
  }

  /* ============================================================
     Consumo derivado del programa horario
     ============================================================ */

  const litrosDeBloque = (bloque, codigo) =>
    Math.max(0, numero(bloque.horaFin) - numero(bloque.horaInicio)) * numero(codigo && codigo.rendimientoLh);

  function consumoVacio() {
    const c = {};
    for (const k of Object.keys(categorias())) c[k] = 0;
    return c;
  }

  /** Consumo de leche de un día, deducido de los bloques programados.
   *
   *  Solo cuentan los bloques en EVAPORADORES: las líneas de secado trabajan
   *  precondensado y la de mantequilla, crema. Un mismo código aparece tanto
   *  en el evaporador como en la línea; sumar ambos contaría la leche dos veces.
   *
   *  «trasvasije» es la excepción: no sale de ningún bloque, se teclea en el
   *  balance del día. */
  function consumoDia(datos, semanaId, dia) {
    const consumo = consumoVacio();
    const codigos = datos.codigoProduccion || [];
    const evap = evaporadores();

    (datos.bloquePlan || [])
      .filter(b => b.semanaId === semanaId && b.dia === dia &&
                   b.tipo === "produccion" && evap.includes(b.equipo))
      .forEach(b => {
        const codigo = codigos.find(c => c.id === b.codigoId);
        if (!codigo || !codigo.categoria) return;
        if (consumo[codigo.categoria] === undefined) consumo[codigo.categoria] = 0;
        consumo[codigo.categoria] += litrosDeBloque(b, codigo);
      });

    const balance = (datos.balanceDia || []).find(x => x.semanaId === semanaId && x.dia === dia);
    consumo.trasvasije = numero(balance && balance.trasvasije);

    consumo.total = Object.keys(categorias()).reduce((s, k) => s + (consumo[k] || 0), 0);
    return consumo;
  }

  /* ============================================================
     Balance de la semana, con arrastre de stock
     ============================================================ */

  /** Litros consumidos que salen de un origen concreto. */
  function consumoDeOrigen(consumo, origen) {
    return Object.entries(categorias())
      .filter(([, meta]) => meta.origen === origen)
      .reduce((s, [clave]) => s + (consumo[clave] || 0), 0);
  }

  /** Balance completo de la semana: una fila por día, con el stock arrastrado.
   *  Nada de esto se guarda: se recalcula en cada lectura. */
  function balanceSemana(datos, semanaId) {
    const semana = (datos.semanaPlan || []).find(s => s.id === semanaId);
    const dias = semana ? (numero(semana.dias) || 6) : 6;

    let stock = null;
    let saldoOrigen = null;
    const filas = [];

    for (let dia = 0; dia < dias; dia++) {
      const registro = (datos.balanceDia || []).find(b => b.semanaId === semanaId && b.dia === dia) || {};

      // El stock de apertura solo se teclea el primer día; después se arrastra.
      if (stock === null) {
        stock = numero(registro.stockInicial);
        const apertura = registro.stockInicialPorOrigen || {};
        saldoOrigen = {};
        for (const o of origenes()) saldoOrigen[o] = numero(apertura[o]);
      }

      const recepciones = {
        ccaa:   numero(registro.recepcionCCAA),
        nestle: numero(registro.recepcionNestle),
        punion: numero(registro.recepcionPUnion)
      };
      const totalRecepciones = origenes().reduce((s, o) => s + recepciones[o], 0);
      const totalDisponible  = stock + totalRecepciones;

      const consumo   = consumoDia(datos, semanaId, dia);
      const stockFinal = totalDisponible - consumo.total;

      const ajustes = registro.ajustes || {};
      const nuevoSaldo = {};
      for (const o of origenes()) {
        nuevoSaldo[o] = saldoOrigen[o] + recepciones[o] - consumoDeOrigen(consumo, o) + numero(ajustes[o]);
      }

      const alertas = [];
      if (stockFinal < 0) alertas.push("El stock proyectado queda negativo: lo programado supera la leche disponible.");
      for (const o of origenes()) {
        if (nuevoSaldo[o] < 0) {
          alertas.push(`Falta leche de ${ETIQUETA_ORIGEN[o]}: saldo ${Math.round(nuevoSaldo[o]).toLocaleString("es-CL")} L.`);
        }
      }

      filas.push({
        dia,
        nombre: DIAS[dia],
        fecha: semana ? fechaDia(semana.fechaInicio, dia) : "",
        registro,
        stockInicial: stock,
        recepciones, totalRecepciones, totalDisponible,
        consumo, totalConsumo: consumo.total,
        stockFinal,
        saldoOrigen: nuevoSaldo,
        cremaDisponibleTon: registro.cremaDisponibleTon === undefined ? null : numero(registro.cremaDisponibleTon),
        alertas
      });

      stock = stockFinal;
      saldoOrigen = nuevoSaldo;
    }

    return filas;
  }

  /** Totales de la semana (la columna final del Excel). */
  function totalesSemana(filas) {
    const total = { recepciones: 0, consumo: consumoVacio(), totalConsumo: 0 };
    total.consumo.total = 0;
    filas.forEach(f => {
      total.recepciones += f.totalRecepciones;
      for (const k of Object.keys(categorias())) total.consumo[k] += f.consumo[k] || 0;
      total.totalConsumo += f.totalConsumo;
    });
    total.consumo.total = total.totalConsumo;
    return total;
  }

  /* ============================================================
     Rendimiento: de litros de leche a kilos de producto
     ------------------------------------------------------------
     `rendimientoLh` dice cuánta leche traga el evaporador por hora.
     La receta dice cuánta leche cuesta un kilo de producto. Dividiendo
     una por otra sale lo que el programa nunca supo decir: cuántos
     KILOS DE PRODUCTO deja cada bloque.
     ============================================================ */

  /** Kilos (o litros) de producto por hora de equipo. null si el producto
   *  no tiene receta completa: es preferible no responder a inventar. */
  function kgPorHora(ctx, codigo, fecha) {
    if (!codigo || !codigo.productoId) return null;
    const insumo = Recetas.insumoPorUnidad(ctx, codigo.productoId, fecha);
    if (!insumo.completa || !insumo.porUnidad) return null;
    return numero(codigo.rendimientoLh) / insumo.porUnidad;
  }

  /** Producción estimada de un bloque, según su receta. */
  function produccionBloque(ctx, bloque, codigo, fecha) {
    const porHora = kgPorHora(ctx, codigo, fecha);
    if (porHora === null) return null;
    const horas = Math.max(0, numero(bloque.horaFin) - numero(bloque.horaInicio));
    return horas * porHora;
  }

  /** Producción estimada del día, por producto. Solo cuenta los bloques de
   *  evaporador, igual que el consumo: las líneas de secado reprocesan lo
   *  que el evaporador ya produjo y volverían a contarse. */
  function produccionDia(datos, semanaId, dia, fecha) {
    const porProducto = {};
    const evap = evaporadores();

    (datos.bloquePlan || [])
      .filter(b => b.semanaId === semanaId && b.dia === dia &&
                   b.tipo === "produccion" && evap.includes(b.equipo))
      .forEach(bloque => {
        const codigo = (datos.codigoProduccion || []).find(c => c.id === bloque.codigoId);
        if (!codigo || !codigo.productoId) return;
        const cantidad = produccionBloque(datos, bloque, codigo, fecha);
        if (cantidad === null) return;
        porProducto[codigo.productoId] = (porProducto[codigo.productoId] || 0) + cantidad;
      });

    return porProducto;
  }

  /* ============================================================
     Calculadora de tiempos de corrida (hoja Base)
     ============================================================ */

  function horasCorrida({ kilosObjetivo, flujo }) {
    const k = numero(kilosObjetivo), f = numero(flujo);
    if (f <= 0) return null;
    return k / f;
  }

  const factorConcentracion = (sg, sng) => (numero(sg) + numero(sng)) / 100;

  /** Hora de término sugerida a partir de un objetivo de kilos. No obliga. */
  function horaFinSugerida(horaInicio, kilosObjetivo, flujo) {
    const horas = horasCorrida({ kilosObjetivo, flujo });
    if (horas === null) return null;
    return Math.min(24, Math.round((numero(horaInicio) + horas) * 2) / 2);   // a media hora
  }

  /* ============================================================
     Validaciones — devuelven motivos, no booleanos
     ============================================================ */

  function validarBloque(bloque, existentes) {
    const bloqueos = [];
    const ini = Number(bloque.horaInicio);
    const fin = Number(bloque.horaFin);

    if (isNaN(ini) || isNaN(fin))      bloqueos.push("Indique la hora de inicio y la de término.");
    else if (fin <= ini)               bloqueos.push("La hora de término debe ser posterior a la de inicio.");

    if (bloque.tipo === "produccion") {
      if (!bloque.codigoId)     bloqueos.push("Un bloque de producción necesita un código de producción.");
      if (bloque.estadoEquipo)  bloqueos.push("Un bloque de producción no lleva estado de equipo.");
    } else if (bloque.tipo === "estado") {
      if (!bloque.estadoEquipo) bloqueos.push("Indique qué ocurre en el equipo (aseo, mantención, PNP…).");
      if (bloque.codigoId)      bloqueos.push("Un bloque de estado no lleva código de producción.");
    }

    const choques = (existentes || []).filter(o =>
      o.id !== bloque.id &&
      o.semanaId === bloque.semanaId &&
      o.equipo === bloque.equipo &&
      o.dia === bloque.dia &&
      Number(o.horaInicio) < fin && ini < Number(o.horaFin)
    );
    if (choques.length) {
      bloqueos.push(`Se solapa con ${choques.length} bloque(s) ya programado(s) en ese equipo y día.`);
    }

    return { permitido: bloqueos.length === 0, bloqueos, choques };
  }

  function puedePublicar(datos, semanaId) {
    const semana = (datos.semanaPlan || []).find(s => s.id === semanaId);
    if (!semana) return { permitido: false, bloqueos: ["No existe la semana."] };

    const bloqueos = [];
    const dias = numero(semana.dias) || 6;

    const bloques = (datos.bloquePlan || []).filter(b => b.semanaId === semanaId);
    if (!bloques.length) bloqueos.push("La semana no tiene ningún bloque programado.");

    const sinBalance = [];
    for (let d = 0; d < dias; d++) {
      if (!(datos.balanceDia || []).some(b => b.semanaId === semanaId && b.dia === d)) sinBalance.push(DIAS[d]);
    }
    if (sinBalance.length) bloqueos.push(`Sin balance de leche: ${sinBalance.join(", ")}.`);

    const filas = balanceSemana(datos, semanaId);
    filas.forEach(f => f.alertas.forEach(a => bloqueos.push(`${f.nombre}: ${a}`)));

    return { permitido: bloqueos.length === 0, bloqueos, filas };
  }

  /* ============================================================
     Ayudas de presentación (sin DOM: solo devuelven datos)
     ============================================================ */

  /** Color y rótulo de un bloque, según sea producción o estado. */
  function aspectoBloque(bloque, codigo) {
    if (bloque.tipo === "estado") {
      const estado = catalogos().estadosEquipo[bloque.estadoEquipo];
      return {
        color: estado ? estado.color : "#b6c5ca",
        trama: !!(estado && estado.trama),
        texto: bloque.estadoEquipo || "?",
        titulo: estado ? estado.etiqueta : "Estado sin definir"
      };
    }
    const familia = catalogos().familiasCodigo[familiaDeCodigo(codigo && codigo.codigo)];
    return {
      color: familia ? familia.color : "#6b7f87",
      trama: false,
      texto: codigo ? codigo.codigo : "—",
      titulo: familia ? familia.etiqueta : "Código sin familia reconocida"
    };
  }

  /** Bloques de un equipo y día, ordenados por hora. */
  function bloquesDe(datos, semanaId, equipo, dia) {
    return (datos.bloquePlan || [])
      .filter(b => b.semanaId === semanaId && b.equipo === equipo && b.dia === dia)
      .sort((a, b) => numero(a.horaInicio) - numero(b.horaInicio));
  }

  /** Horas ocupadas por equipo en la semana: sirve para medir utilización. */
  function utilizacion(datos, semanaId) {
    const uso = {};
    for (const equipo of Object.keys(catalogos().equipos)) uso[equipo] = { produccion: 0, estado: 0 };
    (datos.bloquePlan || [])
      .filter(b => b.semanaId === semanaId)
      .forEach(b => {
        const horas = Math.max(0, numero(b.horaFin) - numero(b.horaInicio));
        if (!uso[b.equipo]) uso[b.equipo] = { produccion: 0, estado: 0 };
        uso[b.equipo][b.tipo === "estado" ? "estado" : "produccion"] += horas;
      });
    return uso;
  }

  return {
    DIAS, DIAS_CORTO, ETIQUETA_ORIGEN,
    familiaDeCodigo, fechaDia, litrosDeBloque,
    consumoDia, consumoDeOrigen, balanceSemana, totalesSemana,
    kgPorHora, produccionBloque, produccionDia,
    horasCorrida, factorConcentracion, horaFinSugerida,
    validarBloque, puedePublicar,
    aspectoBloque, bloquesDe, utilizacion
  };
})();

if (typeof module !== "undefined" && module.exports) module.exports = Planificador;
