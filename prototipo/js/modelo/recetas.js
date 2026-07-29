/* ============================================================
   Recetas — Gestión Productiva Planta CCAA
   ------------------------------------------------------------
   Transformación de la leche fresca en productos. Funciones PURAS.

   El modelo es MULTINIVEL: la mantequilla lleva crema y la crema lleva
   leche fresca. Preguntar "¿cuánta leche necesito para 1.000 kg de
   mantequilla?" obliga a recorrer la cadena completa, no una tabla plana.

       mantequilla 1 kg ─► crema 2 kg ─► leche fresca 8 L
       crema       1 kg ─► leche fresca 4 L

   Las recetas se versionan igual que las especificaciones: un lote de
   mayo se explica con la receta vigente en mayo.
   ============================================================ */

const Recetas = (() => {

  const numero = v => { const n = Number(v); return isNaN(n) ? 0 : n; };
  const esVacio = v => v === null || v === undefined || v === "";

  const productoDe = (ctx, id) => (ctx.producto || []).find(p => p.id === id) || null;

  /** Receta vigente de un producto en una fecha. */
  function recetaVigente(recetas, productoId, fecha) {
    const candidatas = (recetas || []).filter(r =>
      r.productoId === productoId &&
      r.vigenteDesde <= fecha &&
      (esVacio(r.vigenteHasta) || r.vigenteHasta >= fecha)
    );
    if (!candidatas.length) return null;
    return candidatas.sort((a, b) =>
      String(b.vigenteDesde).localeCompare(String(a.vigenteDesde)) || (b.version || 0) - (a.version || 0)
    )[0];
  }

  /* ============================================================
     Explosión de la receta
     ============================================================ */

  /** Árbol de necesidades para obtener `cantidad` de un producto.
   *  Cada nodo lleva su cantidad ya escalada y su merma aplicada.
   *  `visitados` corta los ciclos: una receta que se necesita a sí misma
   *  colgaría el cálculo, así que se marca y se detiene. */
  function arbol(ctx, productoId, cantidad, fecha, visitados) {
    visitados = visitados || [];
    const producto = productoDe(ctx, productoId);

    const nodo = {
      productoId, producto,
      nombre: producto ? producto.nombre : "(producto desconocido)",
      cantidad: numero(cantidad),
      unidad: producto ? (producto.unidadBase || "kg") : "",
      naturaleza: producto ? (producto.naturaleza || "terminado") : null,
      receta: null, hijos: [], ciclo: false, sinReceta: false
    };

    if (visitados.includes(productoId)) { nodo.ciclo = true; return nodo; }

    const receta = recetaVigente(ctx.receta, productoId, fecha);
    if (!receta) {
      // Hoja del árbol. Si no es materia prima, la cadena queda incompleta.
      nodo.sinReceta = nodo.naturaleza !== "materia_prima";
      return nodo;
    }

    nodo.receta = receta;
    const base = numero(receta.cantidadBase) || 1;
    const factor = nodo.cantidad / base;

    nodo.hijos = (receta.componentes || []).map(componente => {
      const merma = numero(componente.merma);
      const necesario = numero(componente.cantidad) * factor * (1 + merma / 100);
      const hijo = arbol(ctx, componente.productoId, necesario, fecha, visitados.concat(productoId));
      hijo.merma = merma;
      hijo.unidadDeclarada = componente.unidad;
      return hijo;
    });

    return nodo;
  }

  /** Recorre el árbol y acumula totales. */
  function totales(nodo, acumulado) {
    const total = acumulado || { requerimientos: {}, materiaPrima: {}, ciclo: false, sinReceta: [] };

    if (nodo.ciclo) total.ciclo = true;
    if (nodo.sinReceta && !total.sinReceta.includes(nodo.productoId)) total.sinReceta.push(nodo.productoId);

    (nodo.hijos || []).forEach(hijo => {
      total.requerimientos[hijo.productoId] = (total.requerimientos[hijo.productoId] || 0) + hijo.cantidad;
      if (hijo.naturaleza === "materia_prima") {
        total.materiaPrima[hijo.productoId] = (total.materiaPrima[hijo.productoId] || 0) + hijo.cantidad;
      }
      totales(hijo, total);
    });

    return total;
  }

  /** Necesidades totales para producir `cantidad` de un producto. */
  function explosionar(ctx, productoId, cantidad, fecha) {
    const raiz = arbol(ctx, productoId, cantidad, fecha);
    const total = totales(raiz);
    total.arbol = raiz;
    total.totalMateriaPrima = Object.values(total.materiaPrima).reduce((s, v) => s + v, 0);
    return total;
  }

  /** Materia prima por UNA unidad de producto: el número que hace útil al
   *  planificador. Para la crema devuelve 4 (litros de leche por kilo). */
  function insumoPorUnidad(ctx, productoId, fecha) {
    const r = explosionar(ctx, productoId, 1, fecha);
    return {
      porUnidad: r.totalMateriaPrima,
      detalle: r.materiaPrima,
      completa: !r.ciclo && !r.sinReceta.length,
      ciclo: r.ciclo,
      sinReceta: r.sinReceta
    };
  }

  /** Cuánto producto sale de una cantidad de materia prima. Inverso del anterior. */
  function rendimientoDesdeMateriaPrima(ctx, productoId, cantidadMateriaPrima, fecha) {
    const { porUnidad } = insumoPorUnidad(ctx, productoId, fecha);
    if (!porUnidad) return null;
    return numero(cantidadMateriaPrima) / porUnidad;
  }

  /* ============================================================
     Validación
     ============================================================ */

  /** Comprueba una receta antes de guardarla, incluida la que aún no existe.
   *  Devuelve motivos, no un booleano. */
  function validarReceta(receta, ctx) {
    const bloqueos = [];
    const salida = productoDe(ctx, receta.productoId);

    if (!receta.productoId)                bloqueos.push("Indique el producto que produce la receta.");
    if (numero(receta.cantidadBase) <= 0)  bloqueos.push("La cantidad base debe ser mayor que cero.");

    const componentes = receta.componentes || [];
    if (!componentes.length) bloqueos.push("Una receta necesita al menos un componente.");

    const vistos = new Set();
    componentes.forEach((c, i) => {
      const n = i + 1;
      if (!c.productoId) { bloqueos.push(`Componente ${n}: falta el producto.`); return; }
      if (c.productoId === receta.productoId) bloqueos.push(`Componente ${n}: un producto no puede llevarse a sí mismo.`);
      if (vistos.has(c.productoId)) bloqueos.push(`Componente ${n}: está repetido.`);
      vistos.add(c.productoId);

      if (numero(c.cantidad) <= 0) bloqueos.push(`Componente ${n}: la cantidad debe ser mayor que cero.`);

      const producto = productoDe(ctx, c.productoId);
      if (!producto) { bloqueos.push(`Componente ${n}: el producto no existe.`); return; }
      const unidadEsperada = producto.unidadBase || "kg";
      if (c.unidad && c.unidad !== unidadEsperada) {
        bloqueos.push(`Componente ${n} (${producto.nombre}): se mide en ${unidadEsperada}, no en ${c.unidad}.`);
      }
    });

    // Ciclo: se explota con la receta propuesta ya incorporada.
    if (receta.productoId && componentes.length) {
      const recetasProbadas = (ctx.receta || []).filter(r => r.id !== receta.id).concat([
        Object.assign({}, receta, {
          id: receta.id || "__propuesta__",
          vigenteDesde: receta.vigenteDesde || "1900-01-01",
          vigenteHasta: null
        })
      ]);
      const prueba = explosionar({ producto: ctx.producto, receta: recetasProbadas },
                                 receta.productoId, 1, receta.vigenteDesde || "2100-01-01");
      if (prueba.ciclo) {
        bloqueos.push("La receta genera un ciclo: alguno de sus componentes vuelve a necesitar este producto.");
      }
    }

    if (salida && salida.naturaleza === "materia_prima") {
      bloqueos.push("Una materia prima no se fabrica: no lleva receta.");
    }

    return { permitido: bloqueos.length === 0, bloqueos };
  }

  /* ============================================================
     Vistas de apoyo
     ============================================================ */

  /** Tabla de rendimientos de todos los productos que tienen receta. */
  function tablaRendimientos(ctx, fecha) {
    return (ctx.producto || [])
      .filter(p => p.activo !== false && recetaVigente(ctx.receta, p.id, fecha))
      .map(p => {
        const r = insumoPorUnidad(ctx, p.id, fecha);
        return {
          producto: p,
          unidad: p.unidadBase || "kg",
          porUnidad: r.porUnidad,
          completa: r.completa,
          ciclo: r.ciclo,
          detalle: r.detalle
        };
      })
      .sort((a, b) => b.porUnidad - a.porUnidad);
  }

  /** Aplana el árbol para mostrarlo como lista con sangría. */
  function aplanar(nodo, nivel, salida) {
    salida = salida || [];
    nivel = nivel || 0;
    if (nivel > 0) salida.push(Object.assign({ nivel }, nodo));
    (nodo.hijos || []).forEach(h => aplanar(h, nivel + 1, salida));
    return salida;
  }

  return {
    recetaVigente, arbol, totales, explosionar,
    insumoPorUnidad, rendimientoDesdeMateriaPrima,
    validarReceta, tablaRendimientos, aplanar
  };
})();

if (typeof module !== "undefined" && module.exports) module.exports = Recetas;
