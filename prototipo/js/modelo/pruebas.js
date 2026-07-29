/* ============================================================
   Pruebas del modelo — Gestión Productiva Planta CCAA
   ------------------------------------------------------------
   Se ejecutan abriendo pruebas.html en el navegador. No requieren
   Node ni instalación. Cubren las reglas que, si se rompen, dejan
   salir producto que no debería salir.
   ============================================================ */

const Pruebas = (() => {
  const casos = [];
  let grupoActual = "General";

  const grupo  = nombre => { grupoActual = nombre; };
  const prueba = (nombre, fn) => casos.push({ grupo: grupoActual, nombre, fn });

  class FalloAfirmacion extends Error {}

  const repr = v => typeof v === "object" ? JSON.stringify(v) : String(v);

  const afirmar = {
    igual(actual, esperado, msg) {
      const a = typeof actual === "object" ? JSON.stringify(actual) : actual;
      const e = typeof esperado === "object" ? JSON.stringify(esperado) : esperado;
      if (a !== e) throw new FalloAfirmacion(`${msg || "Valores distintos"}\n  esperado: ${repr(esperado)}\n  obtenido: ${repr(actual)}`);
    },
    verdadero(v, msg) {
      if (v !== true) throw new FalloAfirmacion(`${msg || "Se esperaba verdadero"} (obtenido: ${repr(v)})`);
    },
    falso(v, msg) {
      if (v !== false) throw new FalloAfirmacion(`${msg || "Se esperaba falso"} (obtenido: ${repr(v)})`);
    },
    contieneTexto(lista, fragmento, msg) {
      const hallado = (lista || []).some(x => String(x).toLowerCase().includes(fragmento.toLowerCase()));
      if (!hallado) throw new FalloAfirmacion(`${msg || "No se encontró el texto"}: "${fragmento}"\n  en: ${repr(lista)}`);
    },
    async lanza(fn, msg) {
      try { await fn(); }
      catch (e) { return e; }
      throw new FalloAfirmacion(msg || "Se esperaba un error y no ocurrió");
    }
  };

  /* ============================================================
     Datos de prueba
     ============================================================ */

  function escenario() {
    const mandantes = [{ id: "m1", nombre: "CCAA", activo: true }];

    const productos = [
      { id: "p1", nombre: "P. Entero ST 48%", familia: "polvo", mandanteId: "m1", activo: true },
      { id: "p2", nombre: "Crema 42%",        familia: "crema", mandanteId: "m1", activo: true },
      { id: "p3", nombre: "Suero en Polvo",   familia: "polvo", mandanteId: "m1", activo: true }
    ];

    const especificaciones = [
      { id: "e1", productoId: "p1", version: 1, vigenteDesde: "2026-01-01", vigenteHasta: "2026-05-31",
        rangos: { humedad: { max: 4, obligatorio: true }, mg: { min: 26, max: 30 } } },
      { id: "e2", productoId: "p1", version: 2, vigenteDesde: "2026-06-01", vigenteHasta: null,
        rangos: { humedad: { max: 3.5, obligatorio: true }, mg: { min: 26, max: 30 } } },
      { id: "e3", productoId: "p2", version: 1, vigenteDesde: "2026-01-01", vigenteHasta: null,
        rangos: { mg: { min: 40, max: 44 }, ph: { min: 6.4, max: 6.9 } } }
      // p3 (Suero) queda a propósito sin especificación.
    ];

    const documentos = [
      { id: "d1", nombre: "Certificado de análisis", aplicaA: ["polvo", "crema"], orden: 1, activo: true },
      { id: "d2", nombre: "Monitoreo PPRO Rovemas",  aplicaA: ["polvo"],          orden: 2, activo: true },
      { id: "d3", nombre: "Evaluación sensorial",    aplicaA: ["polvo", "crema"], orden: 3, activo: true }
    ];

    const lotes = [
      { id: "l1", codigoLote: "CCAA6140N", productoId: "p1", fecha: "2026-05-20", kgProducidos: 25000, estado: "producido" },
      { id: "l2", codigoLote: "CCAA6140N", productoId: "p2", fecha: "2026-05-20", kgProducidos:  8000, estado: "producido" },
      { id: "l3", codigoLote: "CCAA6141",  productoId: "p3", fecha: "2026-05-21", kgProducidos:  1000, estado: "producido" }
    ];

    const analisis = [
      { id: "a1", loteId: "l1", fecha: "2026-05-20", muestra: "M-1", valores: { humedad: 3.2, mg: 28 } },
      { id: "a2", loteId: "l2", fecha: "2026-05-20", muestra: "M-1", valores: { mg: 42.7, ph: 6.7 } }
    ];

    const usuarios = [
      { id: "u1", nombre: "Camila Rauque",  rol: "calidad",    activo: true },
      { id: "u2", nombre: "Jair Corbari",   rol: "produccion", activo: true }
    ];

    const registrosDe = (loteId, familia) =>
      documentos.filter(d => d.aplicaA.includes(familia)).map(d => ({
        id: `r_${loteId}_${d.id}`, loteId, documentoId: d.id,
        estado: "completado", valores: {}
      }));

    const liberaciones = [
      { id: "lib1", loteId: "l1", estado: "en_revision", concesion: false },
      { id: "lib2", loteId: "l2", estado: "en_revision", concesion: false }
    ];

    const registros = registrosDe("l1", "polvo").concat(registrosDe("l2", "crema"));

    return { mandantes, productos, especificaciones, documentos, lotes, analisis, usuarios, liberaciones, registros };
  }

  /* ============================================================
     ESQUEMA
     ============================================================ */

  grupo("Esquema");

  prueba("rechaza un registro sin campos obligatorios", () => {
    const r = Esquema.validar("lote", { id: "x" });
    afirmar.falso(r.valido, "Un lote sin producto ni fecha no debería validar");
    afirmar.contieneTexto(r.errores, "obligatorio");
  });

  prueba("rechaza valores fuera del enum declarado", () => {
    const r = Esquema.validar("producto", { id: "x", nombre: "X", familia: "queso", mandanteId: "m1" });
    afirmar.falso(r.valido);
    afirmar.contieneTexto(r.errores, "no es un valor admitido");
  });

  prueba("rechaza campos que no existen en el esquema", () => {
    const r = Esquema.validar("mandante", { id: "m9", nombre: "X", inventado: 1 });
    afirmar.falso(r.valido);
    afirmar.contieneTexto(r.errores, "no definidos");
  });

  prueba("rechaza fechas mal formadas", () => {
    const r = Esquema.validar("lote", {
      id: "x", codigoLote: "A", productoId: "p1", fecha: "20/05/2026", kgProducidos: 10
    });
    afirmar.contieneTexto(r.errores, "YYYY-MM-DD");
  });

  prueba("rechaza kilos negativos", () => {
    const r = Esquema.validar("lote", {
      id: "x", codigoLote: "A", productoId: "p1", fecha: "2026-05-20", kgProducidos: -5
    });
    afirmar.contieneTexto(r.errores, "no puede ser menor");
  });

  prueba("un objeto obligatorio vacío no pasa por lleno", () => {
    const r = Esquema.validar("analisis", {
      id: "a", loteId: "l1", fecha: "2026-05-20", valores: {}
    });
    afirmar.falso(r.valido, "Un análisis sin ningún parámetro medido no es un análisis");
    afirmar.contieneTexto(r.errores, "obligatorio");
  });

  prueba("los campos objeto con subcampos declarados se pueden dibujar", () => {
    const controles = Esquema.ENTIDADES.recepcion.campos.controles;
    afirmar.verdadero(Array.isArray(controles.campos),
      "Sin 'campos' la interfaz cae en un cuadro de texto con JSON crudo");
    afirmar.verdadero(controles.campos.some(c => c.clave === "delvo"));
    afirmar.verdadero(Array.isArray(Esquema.ENTIDADES.analisis.campos.valores.campos));
  });

  prueba("acepta transiciones de estado válidas y rechaza las inválidas", () => {
    afirmar.verdadero(Esquema.transicionValida("lote", "en_proceso", "producido"));
    afirmar.falso(Esquema.transicionValida("lote", "en_proceso", "cerrado"),
      "No se puede cerrar un lote que nunca se terminó de producir");
    afirmar.verdadero(Esquema.transicionValida("liberacion", "liberado", "en_revision"),
      "Desmarcar un documento debe poder devolver la liberación a revisión");
  });

  /* ============================================================
     ESPECIFICACIONES VERSIONADAS
     ============================================================ */

  grupo("Especificaciones");

  prueba("un lote se evalúa con la especificación vigente en SU fecha", () => {
    const { especificaciones } = escenario();
    afirmar.igual(Dominio.especificacionVigente(especificaciones, "p1", "2026-05-20").id, "e1",
      "Un lote de mayo debe usar la versión de mayo");
    afirmar.igual(Dominio.especificacionVigente(especificaciones, "p1", "2026-07-10").id, "e2",
      "Un lote de julio debe usar la versión nueva");
  });

  prueba("un producto sin especificación devuelve null", () => {
    const { especificaciones } = escenario();
    afirmar.igual(Dominio.especificacionVigente(especificaciones, "p3", "2026-05-20"), null);
  });

  /* ============================================================
     EVALUACIÓN DE CALIDAD
     ============================================================ */

  grupo("Evaluación de calidad");

  prueba("un análisis dentro de rango es conforme", () => {
    const { especificaciones } = escenario();
    const ev = Dominio.evaluarAnalisis({ valores: { humedad: 3.2, mg: 28 } }, especificaciones[0]);
    afirmar.igual(ev.resultado, Dominio.RESULTADO.CONFORME);
    afirmar.igual(ev.desviaciones.length, 0);
  });

  prueba("un análisis fuera de rango es no conforme e informa el parámetro", () => {
    const { especificaciones } = escenario();
    const ev = Dominio.evaluarAnalisis({ valores: { humedad: 3.2, mg: 35 } }, especificaciones[0]);
    afirmar.igual(ev.resultado, Dominio.RESULTADO.NO_CONFORME);
    afirmar.igual(ev.desviaciones.length, 1);
    afirmar.igual(ev.desviaciones[0].parametro, "mg");
    afirmar.igual(ev.desviaciones[0].desvio, "alto");
  });

  prueba("falta un parámetro obligatorio: no es conforme, es 'sin análisis'", () => {
    const { especificaciones } = escenario();
    const ev = Dominio.evaluarAnalisis({ valores: { mg: 28 } }, especificaciones[0]);
    afirmar.igual(ev.resultado, Dominio.RESULTADO.SIN_ANALISIS,
      "Un parámetro obligatorio sin medir no puede pasar como conforme");
    afirmar.igual(ev.faltantes, ["humedad"]);
  });

  prueba("sin especificación no se inventa un veredicto", () => {
    const ev = Dominio.evaluarAnalisis({ valores: { mg: 28 } }, null);
    afirmar.igual(ev.resultado, Dominio.RESULTADO.SIN_ESPECIFICACION);
  });

  prueba("basta una muestra fuera de rango para que el lote sea no conforme", () => {
    const esc = escenario();
    esc.analisis.push({ id: "a3", loteId: "l1", fecha: "2026-05-20", muestra: "M-2", valores: { humedad: 5.1, mg: 28 } });
    const r = Dominio.resultadoCalidadLote(esc.lotes[0], esc.analisis, esc.especificaciones);
    afirmar.igual(r.resultado, Dominio.RESULTADO.NO_CONFORME,
      "El producto ya está mezclado: no se promedian las muestras");
    afirmar.igual(r.evaluados, 2);
    afirmar.igual(r.desviaciones[0].muestra, "M-2");
  });

  prueba("un lote sin análisis no queda como conforme", () => {
    const esc = escenario();
    const r = Dominio.resultadoCalidadLote(esc.lotes[1], [], esc.especificaciones);
    afirmar.igual(r.resultado, Dominio.RESULTADO.SIN_ANALISIS);
  });

  prueba("el resultado se recalcula: cambiar la especificación cambia el veredicto del histórico", () => {
    const esc = escenario();
    const antes = Dominio.resultadoCalidadLote(esc.lotes[0], esc.analisis, esc.especificaciones);
    afirmar.igual(antes.resultado, Dominio.RESULTADO.CONFORME);

    esc.especificaciones[0].rangos.humedad = { max: 3.0, obligatorio: true }; // se endurece la spec
    const despues = Dominio.resultadoCalidadLote(esc.lotes[0], esc.analisis, esc.especificaciones);
    afirmar.igual(despues.resultado, Dominio.RESULTADO.NO_CONFORME,
      "Al no persistirse el resultado, el histórico se reevalúa solo");
  });

  /* ============================================================
     CHECKLIST DOCUMENTAL
     ============================================================ */

  grupo("Checklist de liberación");

  prueba("a la crema no se le exigen documentos de las líneas de polvo", () => {
    const { documentos, productos } = escenario();
    const dePolvo = Dominio.documentosAplicables(documentos, productos[0]);
    const deCrema = Dominio.documentosAplicables(documentos, productos[1]);
    afirmar.igual(dePolvo.length, 3);
    afirmar.igual(deCrema.length, 2, "Rovemas no aplica a crema");
  });

  prueba("el avance se calcula sobre los documentos exigibles, no sobre los registros", () => {
    const { documentos, productos } = escenario();
    const aplicables = Dominio.documentosAplicables(documentos, productos[0]);
    const av = Dominio.avanceChecklist([{ documentoId: "d1", estado: "completado", valores: {} }], aplicables);
    afirmar.igual(av.completados, 1);
    afirmar.igual(av.total, 3);
    afirmar.igual(av.pct, 33);
    afirmar.falso(av.completo);
  });

  prueba("un formulario de un documento que no aplica no infla el avance", () => {
    const { documentos, productos } = escenario();
    const aplicables = Dominio.documentosAplicables(documentos, productos[1]); // crema: d1 y d3
    const av = Dominio.avanceChecklist([
      { documentoId: "d1", estado: "completado", valores: {} },
      { documentoId: "d2", estado: "completado", valores: {} }
    ], aplicables);
    afirmar.igual(av.completados, 1, "d2 no aplica a crema y no debe contar");
    afirmar.igual(av.total, 2);
  });

  prueba("el formulario de OTRO lote no cuenta para este", () => {
    const { documentos, productos } = escenario();
    const aplicables = Dominio.documentosAplicables(documentos, productos[0]);
    const registros = [
      { loteId: "l1", documentoId: "d1", estado: "completado", valores: {} },
      { loteId: "l9", documentoId: "d2", estado: "completado", valores: {} }
    ];
    const av = Dominio.avanceChecklist(registros, aplicables, "l1");
    afirmar.igual(av.completados, 1, "d2 lo completó otro lote: no cuenta para este");
  });

  prueba("un formulario en borrador no cuenta como cumplido", () => {
    const { documentos, productos } = escenario();
    const aplicables = Dominio.documentosAplicables(documentos, productos[1]);
    const av = Dominio.avanceChecklist([{ documentoId: "d1", estado: "borrador", valores: {} }], aplicables);
    afirmar.igual(av.completados, 0);
  });

  /* ============================================================
     FORMULARIOS DIGITALES DE CALIDAD
     ============================================================ */

  grupo("Formularios de calidad");

  const DOC_FQ = {
    id: "dfq", nombre: "Formulario fisicoquímicos", aplicaA: ["polvo"], orden: 1, activo: true,
    plantilla: [
      { clave: "lote", etiqueta: "Lote", tipo: "texto", req: true, origen: "lote.codigoLote" },
      { clave: "mg", etiqueta: "Materia grasa", tipo: "decimal", req: true, parametro: "mg" },
      { clave: "humedad", etiqueta: "Humedad", tipo: "decimal", parametro: "humedad" },
      { clave: "operador", etiqueta: "Operador", tipo: "texto", req: true }
    ]
  };

  prueba("un formulario al que le faltan campos obligatorios no está completo", () => {
    const registro = { estado: "completado", valores: { lote: "CCAA6140N", mg: 28 } };
    afirmar.falso(Dominio.registroCompleto(registro, DOC_FQ), "falta el operador");
    const v = Dominio.validarRegistro(registro, DOC_FQ);
    afirmar.falso(v.permitido);
    afirmar.contieneTexto(v.bloqueos, "Operador");
  });

  prueba("con todos los campos obligatorios el formulario queda completo", () => {
    const registro = { estado: "completado",
      valores: { lote: "CCAA6140N", mg: 28, operador: "J. Andrade" } };
    afirmar.verdadero(Dominio.registroCompleto(registro, DOC_FQ));
    afirmar.verdadero(Dominio.validarRegistro(registro, DOC_FQ).permitido);
  });

  prueba("los datos que el sistema ya conoce se prellenan solos", () => {
    const valores = Dominio.prellenar(DOC_FQ, { lote: { codigoLote: "CCAA6140N" } });
    afirmar.igual(valores.lote, "CCAA6140N", "no se vuelve a teclear lo que ya está en el lote");
    afirmar.igual(valores.mg, undefined, "solo los campos con origen declarado");
  });

  prueba("el sistema avisa si el formulario discrepa del análisis del lote", () => {
    const esc = escenario();
    const calidad = Dominio.resultadoCalidadLote(esc.lotes[0], esc.analisis, esc.especificaciones);
    const registro = { valores: { mg: 22, operador: "x", lote: "x" } };   // el análisis dice 28
    const d = Dominio.cotejarConAnalisis(registro, DOC_FQ, calidad);
    afirmar.verdadero(d.some(x => x.tipo === "discrepa_del_analisis"),
      "un papel que no cuadra con el laboratorio es justo lo que hay que detectar");
    afirmar.contieneTexto(d.map(x => x.mensaje), "el análisis del lote");
  });

  prueba("si el formulario coincide con el análisis no hay discrepancia", () => {
    const esc = escenario();
    const calidad = Dominio.resultadoCalidadLote(esc.lotes[0], esc.analisis, esc.especificaciones);
    const registro = { valores: { mg: 28, operador: "x", lote: "x" } };
    afirmar.igual(Dominio.cotejarConAnalisis(registro, DOC_FQ, calidad)
      .filter(x => x.tipo === "discrepa_del_analisis").length, 0);
  });

  prueba("el sistema avisa si lo declarado se sale de la especificación", () => {
    const esc = escenario();
    const calidad = Dominio.resultadoCalidadLote(esc.lotes[0], esc.analisis, esc.especificaciones);
    const registro = { valores: { mg: 40, operador: "x", lote: "x" } };   // spec: 26–30
    const d = Dominio.cotejarConAnalisis(registro, DOC_FQ, calidad);
    afirmar.verdadero(d.some(x => x.tipo === "fuera_de_especificacion"));
  });

  prueba("un formulario observado bloquea la liberación aunque esté completo", () => {
    const esc = escenario();
    esc.registros.filter(r => r.loteId === "l1").forEach((r, i) => { if (i === 0) r.estado = "observado"; });
    const r = Dominio.puedeLiberar({
      lote: esc.lotes[0], producto: esc.productos[0], liberacion: esc.liberaciones[0],
      registros: esc.registros, analisis: esc.analisis, especificaciones: esc.especificaciones,
      documentos: esc.documentos, usuario: esc.usuarios[0]
    });
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "observación sin resolver");
  });

  /* ============================================================
     REGLA CENTRAL: LIBERACIÓN
     ============================================================ */

  grupo("Liberación");

  prueba("lote conforme + checklist completo + rol calidad → se libera", () => {
    const esc = escenario();
    const r = Dominio.puedeLiberar({
      lote: esc.lotes[0], producto: esc.productos[0], liberacion: esc.liberaciones[0],
      registros: esc.registros, analisis: esc.analisis, especificaciones: esc.especificaciones,
      documentos: esc.documentos, usuario: esc.usuarios[0]
    });
    afirmar.verdadero(r.permitido);
    afirmar.falso(r.viaConcesion);
  });

  prueba("lote NO conforme con checklist completo → solo por concesión", () => {
    const esc = escenario();
    esc.analisis[0].valores.mg = 35;   // fuera de rango
    const r = Dominio.puedeLiberar({
      lote: esc.lotes[0], producto: esc.productos[0], liberacion: esc.liberaciones[0],
      registros: esc.registros, analisis: esc.analisis, especificaciones: esc.especificaciones,
      documentos: esc.documentos, usuario: esc.usuarios[0]
    });
    afirmar.falso(r.permitido, "Un lote no conforme NUNCA se libera por la vía normal");
    afirmar.verdadero(r.viaConcesion);
    afirmar.contieneTexto(r.bloqueos, "no conforme");
  });

  prueba("checklist incompleto bloquea incluso con calidad conforme", () => {
    const esc = escenario();
    esc.registros = esc.registros.filter(r => r.loteId !== "l1" || r.documentoId === "d1");
    const r = Dominio.puedeLiberar({
      lote: esc.lotes[0], producto: esc.productos[0], liberacion: esc.liberaciones[0],
      registros: esc.registros, analisis: esc.analisis, especificaciones: esc.especificaciones,
      documentos: esc.documentos, usuario: esc.usuarios[0]
    });
    afirmar.falso(r.permitido);
    afirmar.falso(r.viaConcesion, "Sin documentos no hay concesión posible");
    afirmar.contieneTexto(r.bloqueos, "Faltan 2 de 3 formularios");
  });

  prueba("sin especificación no hay liberación, ni siquiera por concesión", () => {
    const esc = escenario();
    const registros = ["d1", "d2", "d3"].map(d => ({
      id: "r3" + d, loteId: "l3", documentoId: d, estado: "completado", valores: {} }));
    const r = Dominio.puedeLiberar({
      lote: esc.lotes[2], producto: esc.productos[2],
      liberacion: { id: "lib3", loteId: "l3", estado: "en_revision" }, registros,
      analisis: esc.analisis, especificaciones: esc.especificaciones,
      documentos: esc.documentos, usuario: esc.usuarios[0]
    });
    afirmar.falso(r.permitido);
    afirmar.falso(r.viaConcesion, "No se concede una excepción sobre algo que nunca se midió");
    afirmar.contieneTexto(r.bloqueos, "no tiene especificación");
  });

  prueba("un usuario de producción no puede autorizar liberaciones", () => {
    const esc = escenario();
    const r = Dominio.puedeLiberar({
      lote: esc.lotes[0], producto: esc.productos[0], liberacion: esc.liberaciones[0],
      analisis: esc.analisis, especificaciones: esc.especificaciones,
      documentos: esc.documentos, usuario: esc.usuarios[1]
    });
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "no puede autorizar");
  });

  prueba("un lote todavía en proceso no se libera", () => {
    const esc = escenario();
    esc.lotes[0].estado = "en_proceso";
    const r = Dominio.puedeLiberar({
      lote: esc.lotes[0], producto: esc.productos[0], liberacion: esc.liberaciones[0],
      registros: esc.registros, analisis: esc.analisis, especificaciones: esc.especificaciones,
      documentos: esc.documentos, usuario: esc.usuarios[0]
    });
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "en proceso");
  });

  prueba("la concesión exige un motivo escrito", () => {
    const esc = escenario();
    esc.analisis[0].valores.mg = 35;
    const ctx = {
      lote: esc.lotes[0], producto: esc.productos[0], liberacion: esc.liberaciones[0],
      registros: esc.registros, analisis: esc.analisis, especificaciones: esc.especificaciones,
      documentos: esc.documentos, usuario: esc.usuarios[0]
    };
    afirmar.falso(Dominio.validarConcesion(ctx, "ok").permitido, "Un motivo de dos letras no es un motivo");
    afirmar.verdadero(Dominio.validarConcesion(ctx, "Aceptado por el mandante según correo del 21-05.").permitido);
  });

  prueba("la concesión exige un usuario identificado", () => {
    const esc = escenario();
    esc.analisis[0].valores.mg = 35;
    const r = Dominio.validarConcesion({
      lote: esc.lotes[0], producto: esc.productos[0], liberacion: esc.liberaciones[0],
      analisis: esc.analisis, especificaciones: esc.especificaciones,
      documentos: esc.documentos, usuario: null
    }, "Aceptado por el mandante según correo del 21-05.");
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "firmada");
  });

  /* ============================================================
     DESPACHO
     ============================================================ */

  grupo("Despacho");

  prueba("no se despacha un lote sin liberar", () => {
    const esc = escenario();
    const r = Dominio.puedeDespachar({
      lote: esc.lotes[0], liberacion: { estado: "en_revision" }, despachos: [], kg: 1000
    });
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "no está liberado");
  });

  prueba("un lote liberado por concesión sí se puede despachar", () => {
    const esc = escenario();
    const r = Dominio.puedeDespachar({
      lote: esc.lotes[0], liberacion: { estado: "liberado_concesion" }, despachos: [], kg: 1000
    });
    afirmar.verdadero(r.permitido);
  });

  prueba("no se puede despachar más kilos de los que el lote produjo", () => {
    const esc = escenario();
    const despachos = [{ id: "de1", loteId: "l1", kg: 20000, estado: "emitido" }];
    const r = Dominio.puedeDespachar({
      lote: esc.lotes[0], liberacion: { estado: "liberado" }, despachos, kg: 8000
    });
    afirmar.falso(r.permitido, "25.000 producidos, 20.000 despachados: no caben 8.000 más");
    afirmar.igual(r.disponibles, 5000);
    afirmar.contieneTexto(r.bloqueos, "disponibles");
  });

  prueba("un despacho anulado devuelve kilos al lote", () => {
    const esc = escenario();
    const despachos = [{ id: "de1", loteId: "l1", kg: 20000, estado: "anulado" }];
    afirmar.igual(Dominio.kgDisponibles(esc.lotes[0], despachos), 25000);
  });

  /* ============================================================
     SILOS
     ============================================================ */

  grupo("Silos");

  prueba("la ocupación descuenta lo consumido (no es el acumulado histórico)", () => {
    const silo = { id: "s1", codigo: "SILO 1", capacidadL: 100000 };
    const mov = [
      { siloId: "s1", tipo: "ingreso", litros: 50000, fechaHora: "2026-05-04T08:00" },
      { siloId: "s1", tipo: "ingreso", litros: 30000, fechaHora: "2026-05-04T14:00" },
      { siloId: "s1", tipo: "salida",  litros: 20000, fechaHora: "2026-05-05T06:00" }
    ];
    const oc = Dominio.ocupacionSilo(silo, mov);
    afirmar.igual(oc.litros, 60000, "80.000 recibidos menos 20.000 consumidos");
    afirmar.igual(oc.pct, 60);
    afirmar.falso(oc.excedido);
  });

  prueba("avisa cuando un silo supera su capacidad", () => {
    const silo = { id: "s1", codigo: "SILO 1", capacidadL: 50000 };
    const oc = Dominio.ocupacionSilo(silo, [{ siloId: "s1", tipo: "ingreso", litros: 60000, fechaHora: "2026-05-04T08:00" }]);
    afirmar.verdadero(oc.excedido);
  });

  prueba("una ocupación negativa delata un descuadre de registro", () => {
    const silo = { id: "s1", codigo: "SILO 1", capacidadL: 50000 };
    const oc = Dominio.ocupacionSilo(silo, [{ siloId: "s1", tipo: "salida", litros: 100, fechaHora: "2026-05-04T08:00" }]);
    afirmar.verdadero(oc.negativo);
  });

  prueba("la trazabilidad del lote llega a las recepciones que había en el silo", () => {
    const mov = [
      { id: "mv1", siloId: "s1", tipo: "ingreso", litros: 50000, fechaHora: "2026-05-04T08:00", origen: { tipo: "recepcion", refId: "r1" } },
      { id: "mv2", siloId: "s1", tipo: "ingreso", litros: 30000, fechaHora: "2026-05-04T14:00", origen: { tipo: "recepcion", refId: "r2" } },
      { id: "mv3", siloId: "s1", tipo: "salida",  litros: 40000, fechaHora: "2026-05-05T06:00", origen: { tipo: "lote", refId: "l1" } },
      { id: "mv4", siloId: "s1", tipo: "ingreso", litros: 10000, fechaHora: "2026-05-06T09:00", origen: { tipo: "recepcion", refId: "r3" } }
    ];
    const recepciones = [{ id: "r1" }, { id: "r2" }, { id: "r3" }];
    const tz = Dominio.trazabilidadLote({ id: "l1" }, mov, recepciones);

    afirmar.igual(tz.length, 1);
    afirmar.igual(tz[0].recepciones.map(r => r.id), ["r1", "r2"]);
  });

  prueba("Delvo positivo retiene el camión automáticamente", () => {
    const r = Dominio.evaluarRecepcion({ controles: { delvo: "Positivo", acidez: 15, ph: 6.7, temperatura: 4 } });
    afirmar.igual(r.estado, "retenida");
    afirmar.contieneTexto(r.motivos, "antibióticos");
  });

  prueba("una recepción con todos los controles en regla se libera", () => {
    const r = Dominio.evaluarRecepcion({ controles: {
      delvo: "Negativo", inhibidores: "Negativo", acidez: 15.5, ph: 6.7, temperatura: 4.2, crioscopia: -0.520
    } });
    afirmar.verdadero(r.conforme);
    afirmar.igual(r.estado, "liberada");
  });

  prueba("la crioscopía sobre el límite señala posible aguado", () => {
    const r = Dominio.evaluarRecepcion({ controles: {
      delvo: "Negativo", inhibidores: "Negativo", acidez: 15.5, ph: 6.7, temperatura: 4.2, crioscopia: -0.505
    } });
    afirmar.falso(r.conforme);
    afirmar.contieneTexto(r.motivos, "aguado");
  });

  /* ============================================================
     PANEL
     ============================================================ */

  grupo("Panel");

  prueba("el cumplimiento informa su cobertura, para no exagerar", () => {
    const esc = escenario();
    esc.analisis[0].valores.mg = 35;   // l1 no conforme, l2 conforme, l3 sin especificación
    const r = Dominio.resumenProduccion(esc.lotes, esc.analisis, esc.especificaciones);

    afirmar.igual(r.conteo.conforme, 1);
    afirmar.igual(r.conteo.no_conforme, 1);
    afirmar.igual(r.conteo.sin_especificacion, 1);
    afirmar.igual(r.pctConformidad, 50, "50% sobre los lotes con veredicto");
    afirmar.igual(r.pctCobertura, 67, "pero solo 2 de 3 lotes fueron evaluables");
  });

  prueba("sin ningún lote evaluable el cumplimiento es null, no 0%", () => {
    const esc = escenario();
    const r = Dominio.resumenProduccion([esc.lotes[2]], [], esc.especificaciones);
    afirmar.igual(r.pctConformidad, null, "0% diría que todo falló; null dice que no se sabe");
  });

  /* ============================================================
     REPOSITORIO
     ============================================================ */

  grupo("Repositorio");

  async function repoLimpio() {
    await Repositorio.iniciar({ adaptador: Repositorio.AdaptadorMemoria() });
    Repositorio.identificarse("u1");
    await Repositorio.crear("mandante", { id: "m1", nombre: "CCAA" });
    await Repositorio.crear("producto", { id: "p1", nombre: "P. Entero ST 48%", familia: "polvo", mandanteId: "m1" });
    return Repositorio;
  }

  prueba("crea un registro válido y le asigna identidad", async () => {
    await repoLimpio();
    const lote = await Repositorio.crear("lote", {
      codigoLote: "CCAA6140N", productoId: "p1", fecha: "2026-05-20", kgProducidos: 25000
    });
    afirmar.verdadero(typeof lote.id === "string" && lote.id.length > 0);
    afirmar.igual(lote.estado, "en_proceso", "El estado inicial sale del esquema");
  });

  prueba("rechaza una referencia a un registro inexistente", async () => {
    await repoLimpio();
    const e = await afirmar.lanza(() => Repositorio.crear("lote", {
      codigoLote: "X", productoId: "no_existe", fecha: "2026-05-20", kgProducidos: 10
    }));
    afirmar.contieneTexto(e.motivos, "no existe");
  });

  prueba("impide duplicar un lote con la misma clave natural", async () => {
    await repoLimpio();
    const datos = { codigoLote: "CCAA6140N", productoId: "p1", fecha: "2026-05-20", kgProducidos: 25000 };
    await Repositorio.crear("lote", datos);
    const e = await afirmar.lanza(() => Repositorio.crear("lote", datos));
    afirmar.contieneTexto(e.motivos, "Ya existe");
  });

  prueba("el mismo código de lote SÍ se admite en otro producto", async () => {
    await repoLimpio();
    await Repositorio.crear("producto", { id: "p2", nombre: "Crema 42%", familia: "crema", mandanteId: "m1" });
    await Repositorio.crear("lote", { codigoLote: "CCAA6140N", productoId: "p1", fecha: "2026-05-20", kgProducidos: 25000 });
    const otro = await Repositorio.crear("lote", { codigoLote: "CCAA6140N", productoId: "p2", fecha: "2026-05-20", kgProducidos: 8000 });
    afirmar.verdadero(!!otro.id, "La planta reutiliza el correlativo entre productos; el modelo lo tolera");
  });

  prueba("bloquea transiciones de estado inválidas", async () => {
    await repoLimpio();
    const lote = await Repositorio.crear("lote", {
      codigoLote: "A", productoId: "p1", fecha: "2026-05-20", kgProducidos: 100
    });
    const e = await afirmar.lanza(() => Repositorio.actualizar("lote", lote.id, { estado: "cerrado" }));
    afirmar.contieneTexto(e.motivos, "no permitida");
    await Repositorio.actualizar("lote", lote.id, { estado: "producido" }); // esta sí
  });

  prueba("no deja borrar algo que está en uso", async () => {
    await repoLimpio();
    await Repositorio.crear("lote", { codigoLote: "A", productoId: "p1", fecha: "2026-05-20", kgProducidos: 100 });
    const e = await afirmar.lanza(() => Repositorio.eliminar("producto", "p1"));
    afirmar.contieneTexto(e.motivos, "referencian");
  });

  prueba("registra en la bitácora quién hizo cada cambio", async () => {
    await repoLimpio();
    const lote = await Repositorio.crear("lote", {
      codigoLote: "A", productoId: "p1", fecha: "2026-05-20", kgProducidos: 100
    });
    await Repositorio.actualizar("lote", lote.id, { kgProducidos: 120 });

    const eventos = await Repositorio.listar("eventoAuditoria", { entidadId: lote.id });
    afirmar.igual(eventos.length, 2);
    afirmar.igual(eventos[1].accion, "actualizar");
    afirmar.igual(eventos[1].usuarioId, "u1");
    afirmar.igual(eventos[1].antes.kgProducidos, 100);
    afirmar.igual(eventos[1].despues.kgProducidos, 120);
  });

  prueba("una importación con errores no toca los datos existentes", async () => {
    await repoLimpio();
    await Repositorio.crear("lote", { codigoLote: "A", productoId: "p1", fecha: "2026-05-20", kgProducidos: 100 });

    const e = await afirmar.lanza(() => Repositorio.importar(JSON.stringify({
      mandante: [{ id: "m9" }]           // le falta 'nombre'
    })));
    afirmar.contieneTexto(e.motivos, "obligatorio");

    const lotes = await Repositorio.listar("lote");
    afirmar.igual(lotes.length, 1, "La base debe quedar intacta tras una importación fallida");
  });

  prueba("no acepta escrituras sobre la bitácora", async () => {
    await repoLimpio();
    await afirmar.lanza(() => Repositorio.crear("eventoAuditoria", {
      entidad: "lote", entidadId: "x", accion: "crear", fechaHora: new Date().toISOString()
    }), "La auditoría debe ser inmutable desde fuera del repositorio");
  });

  /* ============================================================
     SEMILLA — migración de los datos reales al modelo nuevo
     ============================================================ */

  grupo("Semilla");

  prueba("la semilla completa valida contra el esquema", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    const problemas = Semilla.verificar(db);
    afirmar.igual(problemas.length, 0, "Problemas:\n" + problemas.slice(0, 8).join("\n"));
  });

  prueba("las filas del Excel se agrupan: hay menos lotes que filas", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    afirmar.verdadero(db.lote.length < DATOS_SEMILLA.produccion.length,
      "Varias filas con el mismo lote+producto+fecha son despachos de un solo lote");
  });

  prueba("un código de lote compartido genera un lote por producto", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    const conEseCodigo = db.lote.filter(l => l.codigoLote === "CCAA6140N");
    afirmar.igual(conEseCodigo.length, 2, "CCAA6140N es P. Entero y P. Semidescremado a la vez");
    const productos = new Set(conEseCodigo.map(l => l.productoId));
    afirmar.igual(productos.size, 2);
  });

  prueba("los kilos del lote suman los de todos sus despachos", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    const lote = db.lote.find(l => l.codigoLote === "CCAA6135N");
    const suma = db.despacho.filter(d => d.loteId === lote.id).reduce((s, d) => s + d.kg, 0);
    afirmar.igual(lote.kgProducidos, suma, "28.200 + 28.950 kg en dos guías del mismo lote");
    afirmar.igual(lote.kgProducidos, 57150);
  });

  prueba("el semidescremado CCAA queda con especificación (antes no calzaba por el nombre)", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    const producto = db.producto.find(p => p.nombre === "P. Semidescremado ST 45% CCAA");
    const spec = Dominio.especificacionVigente(db.especificacion, producto.id, "2026-05-20");
    afirmar.verdadero(!!spec, "El producto de mayor volumen ya no queda sin evaluar");
  });

  prueba("«semidescremado» no se confunde con «crema»", () => {
    afirmar.igual(Semilla.familiaDe("P. Semidescremado ST 45% CCAA"), "polvo",
      "«semidesCREMAdo» contiene la palabra crema y no es una crema");
    afirmar.igual(Semilla.familiaDe("Crema 42% CCAA"), "crema");
    afirmar.igual(Semilla.familiaDe("P. Entero ST 48%"), "polvo");
    afirmar.igual(Semilla.familiaDe("LEP NESTLÉ"), "polvo");
    afirmar.igual(Semilla.familiaDe("Leche estandarizada - Lácteos Nebe"), "liquido");
  });

  prueba("la familia decide qué documentos exige el checklist", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    const polvo = db.producto.find(p => p.nombre === "P. Semidescremado ST 45% CCAA");
    const crema = db.producto.find(p => p.nombre === "Crema 42% CCAA");
    const dePolvo = Dominio.documentosAplicables(db.documentoLiberacion, polvo);
    const deCrema = Dominio.documentosAplicables(db.documentoLiberacion, crema);
    afirmar.verdadero(dePolvo.length > deCrema.length,
      "Al polvo se le exigen además los documentos de Rovemas, pulverización y evaporadores");
  });

  prueba("todo lote producido tiene expediente de liberación", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    const sinExpediente = db.lote.filter(l => !db.liberacion.some(x => x.loteId === l.id));
    afirmar.igual(sinExpediente.length, 0);
  });

  prueba("solo la leche liberada ingresa al silo", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    const retenidas = db.recepcion.filter(r => r.estado === "retenida");
    afirmar.verdadero(retenidas.length > 0, "La muestra incluye una recepción retenida");
    const conMovimiento = retenidas.filter(r =>
      db.movimientoSilo.some(m => m.origen && m.origen.refId === r.id));
    afirmar.igual(conMovimiento.length, 0, "Una recepción retenida no descarga al silo");
  });

  prueba("la semana W7 se siembra con su catálogo, su balance y sus bloques", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    afirmar.igual(db.codigoProduccion.length, 15, "5 familias × 3 formatos");
    afirmar.igual(db.semanaPlan.length, 1);
    afirmar.igual(db.balanceDia.length, 6, "lunes a sábado");
    afirmar.verdadero(db.bloquePlan.length > 30);
  });

  prueba("el consumo de W7 se deriva del programa y no deja saldos negativos", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    const semana = db.semanaPlan[0];
    const filas = Planificador.balanceSemana(db, semana.id);

    afirmar.igual(filas[0].totalConsumo, 353600, "127.200 + 127.200 + 99.200 del lunes");
    afirmar.igual(filas.length, 6);
    const conAlerta = filas.filter(f => f.alertas.length);
    afirmar.igual(conAlerta.length, 0, "La semana de ejemplo debe cuadrar");
    afirmar.verdadero(Planificador.puedePublicar(db, semana.id).permitido);
  });

  prueba("mover un bloque de evaporador cambia el balance; moverlo en una línea no", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    const semana = db.semanaPlan[0];
    const antes = Planificador.consumoDia(db, semana.id, 0).total;

    const enLinea = db.bloquePlan.find(b => b.dia === 0 && b.equipo === "linea1");
    enLinea.horaFin = 24;
    afirmar.igual(Planificador.consumoDia(db, semana.id, 0).total, antes,
      "Las líneas de secado no consumen leche cruda");

    const enEvaporador = db.bloquePlan.find(b => b.dia === 0 && b.equipo === "scheffers2" && b.horaInicio === 0);
    enEvaporador.horaFin = 10;
    afirmar.verdadero(Planificador.consumoDia(db, semana.id, 0).total > antes,
      "Alargar un bloque de evaporador sí sube el consumo");
  });

  prueba("la semilla trae la cadena leche → crema → mantequilla", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    const crema = db.producto.find(p => p.nombre === "Crema 42% CCAA");
    const manteq = db.producto.find(p => p.nombre === "Mantequilla sin Sal");
    const leche = db.producto.find(p => p.nombre === "Leche fresca");

    afirmar.igual(leche.naturaleza, "materia_prima");
    afirmar.igual(leche.unidadBase, "L");
    afirmar.igual(crema.naturaleza, "intermedio");

    afirmar.igual(Recetas.insumoPorUnidad(db, crema.id, "2026-05-20").porUnidad, 4);
    afirmar.igual(Recetas.insumoPorUnidad(db, manteq.id, "2026-05-20").porUnidad, 8,
      "La mantequilla se explota a través de la crema hasta la leche");
  });

  prueba("todas las recetas de la semilla son válidas", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    const malas = db.receta
      .map(r => ({ r, v: Recetas.validarReceta(r, db) }))
      .filter(x => !x.v.permitido);
    afirmar.igual(malas.length, 0,
      malas.map(x => x.r.id + ": " + x.v.bloqueos.join(" ")).join("\n"));
  });

  prueba("con receta, el programa ya dice cuántos kilos deja cada bloque", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    const semana = db.semanaPlan[0];
    const produccion = Planificador.produccionDia(db, semana.id, 0, "2026-02-09");
    const total = Object.values(produccion).reduce((s, v) => s + v, 0);
    afirmar.verdadero(total > 0, "Antes de las recetas este número no existía");
  });

  prueba("la semilla dota el lunes y deja el martes a medias", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    const semana = db.semanaPlan[0];
    const lunesA = Turnos.coberturaTurno(db, semana.id, 0, "A");
    afirmar.igual(lunesA.estado, "cubierto", "El lunes se sembró completo");
    const martesA = Turnos.coberturaTurno(db, semana.id, 1, "A");
    afirmar.igual(martesA.estado, "parcial", "Al martes le falta un operador a propósito");
  });

  prueba("las asignaciones de la semilla no generan conflictos de descanso", () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    afirmar.igual(Turnos.conflictos(db, db.semanaPlan[0].id).length, 0);
  });

  prueba("la semilla se puede cargar en el repositorio y consultar", async () => {
    const db = Semilla.construir(DATOS_SEMILLA);
    await Repositorio.iniciar({ adaptador: Repositorio.AdaptadorMemoria(), semilla: db });
    const lotes = await Repositorio.listar("lote");
    afirmar.verdadero(lotes.length > 0);
  });

  /* ============================================================
     RECETAS
     ============================================================ */

  grupo("Recetas");

  function cocina(extra) {
    const ctx = {
      producto: [
        { id: "leche",  nombre: "Leche fresca",   familia: "liquido", naturaleza: "materia_prima", unidadBase: "L",  activo: true },
        { id: "crema",  nombre: "Crema 42%",      familia: "crema",   naturaleza: "intermedio",    unidadBase: "kg", activo: true },
        { id: "manteq", nombre: "Mantequilla",    familia: "otro",    naturaleza: "terminado",     unidadBase: "kg", activo: true },
        { id: "polvo",  nombre: "P. Entero",      familia: "polvo",   naturaleza: "terminado",     unidadBase: "kg", activo: true },
        { id: "huerf",  nombre: "Producto huérfano", familia: "otro", naturaleza: "terminado",     unidadBase: "kg", activo: true }
      ],
      receta: [
        { id: "r_crema", productoId: "crema", version: 1, vigenteDesde: "2026-01-01", vigenteHasta: null,
          cantidadBase: 1, componentes: [{ productoId: "leche", cantidad: 4, unidad: "L" }] },
        { id: "r_manteq", productoId: "manteq", version: 1, vigenteDesde: "2026-01-01", vigenteHasta: null,
          cantidadBase: 1, componentes: [{ productoId: "crema", cantidad: 2, unidad: "kg" }] },
        { id: "r_polvo", productoId: "polvo", version: 1, vigenteDesde: "2026-01-01", vigenteHasta: null,
          cantidadBase: 1, componentes: [{ productoId: "leche", cantidad: 8.5, unidad: "L" }] }
      ]
    };
    return Object.assign(ctx, extra || {});
  }

  prueba("un kilo de crema son cuatro litros de leche", () => {
    const r = Recetas.insumoPorUnidad(cocina(), "crema", "2026-05-20");
    afirmar.igual(r.porUnidad, 4);
    afirmar.verdadero(r.completa);
  });

  prueba("la explosión es multinivel: la mantequilla llega hasta la leche", () => {
    const r = Recetas.insumoPorUnidad(cocina(), "manteq", "2026-05-20");
    afirmar.igual(r.porUnidad, 8, "1 kg mantequilla → 2 kg crema → 8 L de leche");
    afirmar.igual(r.detalle.leche, 8);
  });

  prueba("los requerimientos intermedios también quedan a la vista", () => {
    const r = Recetas.explosionar(cocina(), "manteq", 1000, "2026-05-20");
    afirmar.igual(r.requerimientos.crema, 2000, "2.000 kg de crema");
    afirmar.igual(r.requerimientos.leche, 8000, "8.000 L de leche");
    afirmar.igual(r.totalMateriaPrima, 8000);
  });

  prueba("la merma aumenta la cantidad de componente necesaria", () => {
    const ctx = cocina();
    ctx.receta[0].componentes[0].merma = 25;          // 25 % de pérdida
    const r = Recetas.insumoPorUnidad(ctx, "crema", "2026-05-20");
    afirmar.igual(r.porUnidad, 5, "4 L más un 25 % de merma");
  });

  prueba("un producto sin receta no se puede explotar y se dice", () => {
    const r = Recetas.insumoPorUnidad(cocina(), "huerf", "2026-05-20");
    afirmar.falso(r.completa);
    afirmar.igual(r.sinReceta, ["huerf"]);
  });

  prueba("la receta vigente depende de la fecha del lote", () => {
    const ctx = cocina();
    ctx.receta[0].vigenteHasta = "2026-06-30";
    ctx.receta.push({ id: "r_crema2", productoId: "crema", version: 2, vigenteDesde: "2026-07-01",
      vigenteHasta: null, cantidadBase: 1, componentes: [{ productoId: "leche", cantidad: 4.5, unidad: "L" }] });
    afirmar.igual(Recetas.insumoPorUnidad(ctx, "crema", "2026-05-20").porUnidad, 4);
    afirmar.igual(Recetas.insumoPorUnidad(ctx, "crema", "2026-08-10").porUnidad, 4.5);
  });

  prueba("una receta que se lleva a sí misma se rechaza", () => {
    const ctx = cocina();
    const r = Recetas.validarReceta({ id: "x", productoId: "crema", cantidadBase: 1,
      componentes: [{ productoId: "crema", cantidad: 1, unidad: "kg" }] }, ctx);
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "no puede llevarse a sí mismo");
  });

  prueba("se detecta un ciclo indirecto entre recetas", () => {
    const ctx = cocina();
    // La crema pasaría a llevar mantequilla, que ya lleva crema.
    const r = Recetas.validarReceta({ id: "r_crema", productoId: "crema", cantidadBase: 1,
      vigenteDesde: "2026-01-01",
      componentes: [{ productoId: "manteq", cantidad: 1, unidad: "kg" }] }, ctx);
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "ciclo");
  });

  prueba("la unidad del componente debe ser la suya", () => {
    const ctx = cocina();
    const r = Recetas.validarReceta({ id: "x", productoId: "manteq", cantidadBase: 1,
      vigenteDesde: "2026-01-01",
      componentes: [{ productoId: "crema", cantidad: 2, unidad: "L" }] }, ctx);   // la crema va en kg
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "se mide en kg");
  });

  prueba("una materia prima no lleva receta", () => {
    const r = Recetas.validarReceta({ id: "x", productoId: "leche", cantidadBase: 1,
      vigenteDesde: "2026-01-01", componentes: [{ productoId: "crema", cantidad: 1, unidad: "kg" }] }, cocina());
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "no se fabrica");
  });

  prueba("una receta válida pasa la validación", () => {
    const r = Recetas.validarReceta({ id: "nueva", productoId: "polvo", cantidadBase: 1,
      vigenteDesde: "2026-01-01",
      componentes: [{ productoId: "leche", cantidad: 8.5, unidad: "L" }] }, cocina());
    afirmar.verdadero(r.permitido, "Bloqueos: " + r.bloqueos.join(" | "));
  });

  prueba("el rendimiento inverso dice cuánto sale de una cantidad de leche", () => {
    const kg = Recetas.rendimientoDesdeMateriaPrima(cocina(), "crema", 100000, "2026-05-20");
    afirmar.igual(kg, 25000, "100.000 L de leche dan 25.000 kg de crema");
  });

  /* ============================================================
     PLANIFICADOR
     ============================================================ */

  grupo("Planificador");

  function plan(extra) {
    const datos = {
      semanaPlan: [{ id: "sem1", codigo: "W7", anio: 2026, fechaInicio: "2026-02-09", dias: 3, estado: "borrador" }],
      codigoProduccion: [
        { id: "cp1", codigo: "RCSH2N", categoria: "prec_nestle",  rendimientoLh: 15900, formato: "SH2" },
        { id: "cp2", codigo: "RCSH2C", categoria: "prec_ccaa",    rendimientoLh: 15900, formato: "SH2" },
        { id: "cp3", codigo: "LUVEB",  categoria: "secado_colun", rendimientoLh: 12400, formato: "VEB" }
      ],
      bloquePlan: [],
      balanceDia: []
    };
    return Object.assign(datos, extra || {});
  }

  const bloque = (o) => Object.assign(
    { id: "b" + Math.round(o.horaInicio * 100 + o.dia), semanaId: "sem1", tipo: "produccion" }, o);

  prueba("el consumo sale de las horas del bloque por el rendimiento del código", () => {
    const datos = plan({ bloquePlan: [
      bloque({ equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 8, codigoId: "cp1" })
    ] });
    const c = Planificador.consumoDia(datos, "sem1", 0);
    afirmar.igual(c.prec_nestle, 127200, "8 h × 15.900 L/h");
    afirmar.igual(c.total, 127200);
  });

  prueba("cada código suma a su propia categoría de consumo", () => {
    const datos = plan({ bloquePlan: [
      bloque({ equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 8,  codigoId: "cp1" }),
      bloque({ equipo: "scheffers2", dia: 0, horaInicio: 8, horaFin: 16, codigoId: "cp2" }),
      bloque({ equipo: "veb",        dia: 0, horaInicio: 8, horaFin: 16, codigoId: "cp3" })
    ] });
    const c = Planificador.consumoDia(datos, "sem1", 0);
    afirmar.igual(c.prec_nestle, 127200);
    afirmar.igual(c.prec_ccaa, 127200);
    afirmar.igual(c.secado_colun, 99200, "8 h × 12.400 L/h");
    afirmar.igual(c.total, 353600);
  });

  prueba("las líneas de secado NO vuelven a consumir leche (sin doble conteo)", () => {
    const datos = plan({ bloquePlan: [
      bloque({ equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 8, codigoId: "cp1" }),
      bloque({ id: "bl1", equipo: "linea1", dia: 0, horaInicio: 0, horaFin: 8, codigoId: "cp1" }),
      bloque({ id: "bl2", equipo: "linea_mantequilla", dia: 0, horaInicio: 0, horaFin: 8, codigoId: "cp1" })
    ] });
    const c = Planificador.consumoDia(datos, "sem1", 0);
    afirmar.igual(c.prec_nestle, 127200,
      "El mismo código en el evaporador y en la línea debe contarse UNA vez");
  });

  prueba("un bloque de estado no consume leche", () => {
    const datos = plan({ bloquePlan: [
      bloque({ equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 8, tipo: "estado", estadoEquipo: "M", codigoId: null })
    ] });
    afirmar.igual(Planificador.consumoDia(datos, "sem1", 0).total, 0);
  });

  prueba("el trasvasije se toma del balance, no de los bloques", () => {
    const datos = plan({ balanceDia: [{ id: "bd0", semanaId: "sem1", dia: 0, trasvasije: 40000 }] });
    const c = Planificador.consumoDia(datos, "sem1", 0);
    afirmar.igual(c.trasvasije, 40000);
    afirmar.igual(c.total, 40000);
  });

  prueba("el stock se arrastra: el inicial de un día es el final del anterior", () => {
    const datos = plan({
      bloquePlan: [bloque({ equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 8, codigoId: "cp1" })],
      balanceDia: [{ id: "bd0", semanaId: "sem1", dia: 0, stockInicial: 193000 }]
    });
    const filas = Planificador.balanceSemana(datos, "sem1");
    afirmar.igual(filas[0].totalDisponible, 193000);
    afirmar.igual(filas[0].stockFinal, 65800, "193.000 − 127.200");
    afirmar.igual(filas[1].stockInicial, 65800, "se arrastra al día siguiente");
  });

  prueba("las recepciones suman al disponible del día", () => {
    const datos = plan({ balanceDia: [
      { id: "bd0", semanaId: "sem1", dia: 0, stockInicial: 100000,
        recepcionCCAA: 130000, recepcionNestle: 120000, recepcionPUnion: 50000 }
    ] });
    const filas = Planificador.balanceSemana(datos, "sem1");
    afirmar.igual(filas[0].totalRecepciones, 300000);
    afirmar.igual(filas[0].totalDisponible, 400000);
  });

  prueba("el saldo por origen descuenta solo el consumo de ese origen", () => {
    const datos = plan({
      bloquePlan: [bloque({ equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 8, codigoId: "cp1" })],
      balanceDia: [{ id: "bd0", semanaId: "sem1", dia: 0, stockInicial: 200000,
                     stockInicialPorOrigen: { ccaa: 50000, nestle: 100000, punion: 50000 },
                     recepcionNestle: 30000 }]
    });
    const f = Planificador.balanceSemana(datos, "sem1")[0];
    afirmar.igual(f.saldoOrigen.nestle, 2800, "100.000 + 30.000 − 127.200");
    afirmar.igual(f.saldoOrigen.ccaa, 50000, "el consumo Nestlé no toca el saldo CCAA");
  });

  prueba("un saldo negativo por origen se marca como alerta", () => {
    const datos = plan({
      bloquePlan: [bloque({ equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 10, codigoId: "cp1" })],
      balanceDia: [{ id: "bd0", semanaId: "sem1", dia: 0, stockInicial: 500000 }]
    });
    const f = Planificador.balanceSemana(datos, "sem1")[0];
    afirmar.verdadero(f.saldoOrigen.nestle < 0);
    afirmar.contieneTexto(f.alertas, "Falta leche de Nestlé");
  });

  prueba("detecta el solapamiento de dos bloques en el mismo equipo y día", () => {
    const existentes = [bloque({ id: "x1", equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 8, codigoId: "cp1" })];
    const nuevo = bloque({ id: "x2", equipo: "scheffers2", dia: 0, horaInicio: 6, horaFin: 12, codigoId: "cp2" });
    const r = Planificador.validarBloque(nuevo, existentes);
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "solapa");
  });

  prueba("dos bloques contiguos NO se consideran solapados", () => {
    const existentes = [bloque({ id: "x1", equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 8, codigoId: "cp1" })];
    const nuevo = bloque({ id: "x2", equipo: "scheffers2", dia: 0, horaInicio: 8, horaFin: 16, codigoId: "cp2" });
    afirmar.verdadero(Planificador.validarBloque(nuevo, existentes).permitido);
  });

  prueba("el mismo tramo en otro equipo o en otro día es válido", () => {
    const existentes = [bloque({ id: "x1", equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 8, codigoId: "cp1" })];
    afirmar.verdadero(Planificador.validarBloque(
      bloque({ id: "x2", equipo: "veb", dia: 0, horaInicio: 0, horaFin: 8, codigoId: "cp3" }), existentes).permitido);
    afirmar.verdadero(Planificador.validarBloque(
      bloque({ id: "x3", equipo: "scheffers2", dia: 1, horaInicio: 0, horaFin: 8, codigoId: "cp1" }), existentes).permitido);
  });

  prueba("la hora de término debe ser posterior a la de inicio", () => {
    const r = Planificador.validarBloque(
      bloque({ id: "x", equipo: "veb", dia: 0, horaInicio: 12, horaFin: 8, codigoId: "cp3" }), []);
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "posterior");
  });

  prueba("un bloque de producción sin código no es válido, y uno de estado sin estado tampoco", () => {
    afirmar.contieneTexto(
      Planificador.validarBloque(bloque({ id: "x", equipo: "veb", dia: 0, horaInicio: 0, horaFin: 4 }), []).bloqueos,
      "necesita un código");
    afirmar.contieneTexto(
      Planificador.validarBloque({ id: "y", semanaId: "sem1", equipo: "veb", dia: 0,
        horaInicio: 0, horaFin: 4, tipo: "estado" }, []).bloqueos,
      "qué ocurre en el equipo");
  });

  prueba("la receta convierte litros por hora en kilos de producto por hora", () => {
    const ctx = cocina();
    // Un evaporador que traga 15.900 L/h haciendo crema (4 L por kilo).
    const codigo = { id: "c", codigo: "RCSH2C", productoId: "crema", rendimientoLh: 15900 };
    const kgh = Planificador.kgPorHora(ctx, codigo, "2026-05-20");
    afirmar.igual(kgh, 3975, "15.900 L/h ÷ 4 L/kg");

    const bloque = { horaInicio: 0, horaFin: 8 };
    afirmar.igual(Planificador.produccionBloque(ctx, bloque, codigo, "2026-05-20"), 31800,
      "8 h de corrida dejan 31.800 kg de crema");
  });

  prueba("sin receta el planificador no inventa una producción", () => {
    const codigo = { id: "c", codigo: "X", productoId: "huerf", rendimientoLh: 15900 };
    afirmar.igual(Planificador.kgPorHora(cocina(), codigo, "2026-05-20"), null,
      "Es preferible no responder a dar un número falso");
  });

  prueba("la producción estimada del día sale solo de los evaporadores", () => {
    const ctx = cocina();
    const datos = Object.assign({
      semanaPlan: [{ id: "s", codigo: "W1", anio: 2026, fechaInicio: "2026-05-18", dias: 1 }],
      codigoProduccion: [{ id: "cp", codigo: "RCSH2C", productoId: "crema", rendimientoLh: 15900, categoria: "prec_ccaa" }],
      bloquePlan: [
        { id: "b1", semanaId: "s", equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 8, tipo: "produccion", codigoId: "cp" },
        { id: "b2", semanaId: "s", equipo: "linea1",     dia: 0, horaInicio: 0, horaFin: 8, tipo: "produccion", codigoId: "cp" }
      ],
      balanceDia: []
    }, ctx);
    const p = Planificador.produccionDia(datos, "s", 0, "2026-05-20");
    afirmar.igual(p.crema, 31800, "La línea de secado no vuelve a producir la misma crema");
  });

  prueba("la calculadora de tiempos reproduce la hoja Base", () => {
    const h = Planificador.horasCorrida({ kilosObjetivo: 89000, flujo: 15900 });
    afirmar.igual(h.toFixed(1), "5.6", "89.000 kg / 15.900 L·h⁻¹ ≈ 5,6 h");
    afirmar.igual(Planificador.factorConcentracion(8.5, 4.622).toFixed(5), "0.13122");
    afirmar.igual(Planificador.horasCorrida({ kilosObjetivo: 100, flujo: 0 }), null, "sin flujo no hay tiempo");
  });

  prueba("no se publica una semana con saldos negativos", () => {
    const datos = plan({
      bloquePlan: [bloque({ equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 10, codigoId: "cp1" })],
      balanceDia: [0, 1, 2].map(d => ({ id: "bd" + d, semanaId: "sem1", dia: d, stockInicial: d === 0 ? 500000 : 0 }))
    });
    const r = Planificador.puedePublicar(datos, "sem1");
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "Falta leche");
  });

  prueba("no se publica una semana con días sin balance", () => {
    const datos = plan({
      bloquePlan: [bloque({ equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 2, codigoId: "cp1" })],
      balanceDia: [{ id: "bd0", semanaId: "sem1", dia: 0, stockInicial: 900000 }]
    });
    const r = Planificador.puedePublicar(datos, "sem1");
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "Sin balance de leche");
  });

  prueba("una semana cuadrada sí se puede publicar", () => {
    const datos = plan({
      bloquePlan: [bloque({ equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 8, codigoId: "cp1" })],
      balanceDia: [0, 1, 2].map(d => ({
        id: "bd" + d, semanaId: "sem1", dia: d,
        stockInicial: d === 0 ? 200000 : 0,
        stockInicialPorOrigen: d === 0 ? { ccaa: 40000, nestle: 130000, punion: 30000 } : undefined
      }))
    });
    const r = Planificador.puedePublicar(datos, "sem1");
    afirmar.verdadero(r.permitido, "Bloqueos: " + r.bloqueos.join(" | "));
  });

  prueba("la fecha de cada día se calcula desde el lunes de la semana", () => {
    afirmar.igual(Planificador.fechaDia("2026-02-09", 0), "2026-02-09");
    afirmar.igual(Planificador.fechaDia("2026-02-09", 5), "2026-02-14", "sábado de la W7");
  });

  prueba("el color del bloque distingue familia de código y estado de equipo", () => {
    const codigo = { codigo: "RCSH2N" };
    const prod = Planificador.aspectoBloque({ tipo: "produccion" }, codigo);
    afirmar.igual(prod.texto, "RCSH2N", "el código va escrito dentro: el color nunca va solo");
    afirmar.igual(prod.color, Esquema.CATALOGOS.familiasCodigo.RC.color);

    const est = Planificador.aspectoBloque({ tipo: "estado", estadoEquipo: "M" }, null);
    afirmar.verdadero(est.trama, "las paradas planificadas llevan trama además del color");
    afirmar.igual(est.titulo, "Mantenimiento");
  });

  /* ============================================================
     TURNOS DE PERSONAL
     ============================================================ */

  grupo("Turnos");

  function turnos(extra) {
    const datos = {
      semanaPlan: [{ id: "s", codigo: "W1", anio: 2026, fechaInicio: "2026-02-09", dias: 2 }],
      // Lunes: Scheffers 2 produce de 0 a 8 (turno A) y VEB de 8 a 16 (turno B).
      bloquePlan: [
        { id: "b1", semanaId: "s", equipo: "scheffers2", dia: 0, horaInicio: 0, horaFin: 8,  tipo: "produccion", codigoId: "x" },
        { id: "b2", semanaId: "s", equipo: "veb",        dia: 0, horaInicio: 8, horaFin: 16, tipo: "produccion", codigoId: "x" }
      ],
      asignacionTurno: [],
      usuario: [
        { id: "u1", nombre: "Operador Uno",  rol: "produccion", activo: true },
        { id: "u2", nombre: "Operador Dos",  rol: "produccion", activo: true },
        { id: "u3", nombre: "Laboratorista", rol: "calidad",    activo: true },
        { id: "u4", nombre: "Supervisor",    rol: "produccion", activo: true }
      ]
    };
    return Object.assign(datos, extra || {});
  }

  const asignar = (o) => Object.assign({ id: "a" + Math.round(Math.random() * 1e6),
    semanaId: "s", funcion: "operador" }, o);

  prueba("la dotación requerida sale del programa, no de una tabla fija", () => {
    const d = turnos();
    const reqA = Turnos.dotacionRequerida(d, "s", 0, "A");
    afirmar.igual(reqA.operador, 1, "Scheffers 2 produce en turno A");
    afirmar.igual(reqA.laboratorio, 1, "hay un evaporador activo");
    afirmar.igual(reqA.supervisor, 1);
    afirmar.igual(reqA.total, 3);
  });

  prueba("un turno sin equipos programados no necesita a nadie", () => {
    const d = turnos();
    const reqC = Turnos.dotacionRequerida(d, "s", 0, "C");   // nada produce de 16 a 24
    afirmar.igual(reqC.total, 0);
    afirmar.igual(Turnos.coberturaTurno(d, "s", 0, "C").estado, "sin_actividad");
  });

  prueba("un turno con actividad y sin gente queda descubierto", () => {
    const c = Turnos.coberturaTurno(turnos(), "s", 0, "A");
    afirmar.igual(c.estado, "descubierto");
    afirmar.contieneTexto(c.bloqueos, "Falta 1 operador");
  });

  prueba("con la dotación completa el turno queda cubierto", () => {
    const d = turnos({ asignacionTurno: [
      asignar({ dia: 0, turno: "A", usuarioId: "u1", funcion: "operador" }),
      asignar({ dia: 0, turno: "A", usuarioId: "u3", funcion: "laboratorio" }),
      asignar({ dia: 0, turno: "A", usuarioId: "u4", funcion: "supervisor" })
    ] });
    const c = Turnos.coberturaTurno(d, "s", 0, "A");
    afirmar.igual(c.estado, "cubierto");
    afirmar.igual(c.bloqueos.length, 0);
  });

  prueba("mover un bloque en el programa cambia el turno que necesita gente", () => {
    const d = turnos();
    afirmar.igual(Turnos.dotacionRequerida(d, "s", 0, "C").total, 0);
    d.bloquePlan[1].horaInicio = 16;   // el VEB pasa al turno C
    d.bloquePlan[1].horaFin = 24;
    afirmar.igual(Turnos.dotacionRequerida(d, "s", 0, "C").total, 3,
      "Ahora el turno C sí necesita dotación");
  });

  prueba("detecta el solapamiento de una persona en dos turnos", () => {
    const d = turnos({ asignacionTurno: [
      asignar({ id: "x1", dia: 0, turno: "A", usuarioId: "u1" }),
      asignar({ id: "x2", dia: 0, turno: "A", usuarioId: "u1" })   // repetida no; solapada sí en otro
    ] });
    // Mismo turno exacto lo bloquea el índice único; probamos turnos contiguos:
    d.asignacionTurno = [
      asignar({ id: "y1", dia: 0, turno: "A", usuarioId: "u1" }),
      asignar({ id: "y2", dia: 0, turno: "B", usuarioId: "u1" })   // A 0-8, B 8-16: contiguos
    ];
    const p = Turnos.conflictos(d, "s");
    afirmar.verdadero(p.some(x => x.tipo === "descanso_insuficiente"),
      "Turnos contiguos dejan 0 h de descanso");
  });

  prueba("el turno C de un día y el A del siguiente dejan descanso insuficiente", () => {
    const d = turnos({ asignacionTurno: [
      asignar({ id: "z1", dia: 0, turno: "C", usuarioId: "u1" }),   // termina a las 24 h
      asignar({ id: "z2", dia: 1, turno: "A", usuarioId: "u1" })    // empieza a las 24 h (0 del día 1)
    ] });
    const p = Turnos.conflictos(d, "s");
    afirmar.verdadero(p.some(x => x.tipo === "descanso_insuficiente" && x.horas === 0),
      "Sin el cruce de día a día, este caso se escaparía");
  });

  prueba("turnos con descanso suficiente no generan conflicto", () => {
    const d = turnos({ asignacionTurno: [
      asignar({ id: "w1", dia: 0, turno: "A", usuarioId: "u1" }),   // 0-8
      asignar({ id: "w2", dia: 0, turno: "C", usuarioId: "u1" })    // 16-24: 8 h de descanso
    ] });
    afirmar.igual(Turnos.conflictos(d, "s").length, 0, "8 h es justo el mínimo");
  });

  prueba("validar bloquea una asignación que dejaría poco descanso", () => {
    const d = turnos({ asignacionTurno: [
      asignar({ id: "v1", dia: 0, turno: "A", usuarioId: "u1" })
    ] });
    const r = Turnos.validarAsignacion(
      asignar({ id: "v2", dia: 0, turno: "B", usuarioId: "u1" }), d);
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "descanso");
  });

  prueba("no se publica una dotación con turnos descubiertos", () => {
    const r = Turnos.puedePublicar(turnos(), "s");
    afirmar.falso(r.permitido);
    afirmar.contieneTexto(r.bloqueos, "operador");
  });

  prueba("la carga por persona suma las horas de sus turnos", () => {
    const d = turnos({ asignacionTurno: [
      asignar({ dia: 0, turno: "A", usuarioId: "u1" }),
      asignar({ dia: 1, turno: "B", usuarioId: "u1" })
    ] });
    afirmar.igual(Turnos.cargaPorPersona(d, "s").u1, 16, "dos turnos de 8 h");
  });

  /* ============================================================
     Ejecución
     ============================================================ */

  async function correr() {
    const resultados = [];
    for (const caso of casos) {
      try {
        await caso.fn();
        resultados.push({ ...caso, ok: true });
      } catch (e) {
        resultados.push({ ...caso, ok: false, error: e.message, esperada: e instanceof FalloAfirmacion });
      }
    }
    return resultados;
  }

  return { correr, total: () => casos.length };
})();
