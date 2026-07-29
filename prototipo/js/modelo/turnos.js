/* ============================================================
   Turnos de personal — Gestión Productiva Planta CCAA
   ------------------------------------------------------------
   Dotación de personal ACOPLADA al programa de producción. Funciones
   PURAS: sin DOM, sin almacenamiento, sin red.

   Idea central, igual que el consumo de leche:
     la DOTACIÓN REQUERIDA se deduce del PROGRAMA HORARIO.
   Donde no hay equipos programados en un turno, no hace falta gente.
   Mover un bloque en el planificador cambia la dotación que ese turno
   necesita. Por eso el requerimiento no se persiste: se recalcula.
   ============================================================ */

const Turnos = (() => {

  const numero = v => { const n = Number(v); return isNaN(n) ? 0 : n; };

  const cat          = () => Esquema.CATALOGOS;
  const horarios     = () => cat().horariosTurno;
  const funciones    = () => cat().funcionesTurno;
  const dotEquipo    = () => cat().dotacionEquipo || {};
  const evaporadores = () => cat().evaporadores || [];
  const minDescanso  = () => numero(cat().minDescansoHoras) || 8;

  const ETIQUETA_FUNCION = clave => (funciones()[clave] || {}).etiqueta || clave;

  /** Tramo horario de un turno: { desde, hasta }. */
  function horarioTurno(turno) {
    const h = horarios()[turno];
    return h ? { desde: numero(h.desde), hasta: numero(h.hasta) } : null;
  }

  /** ¿El bloque [ini, fin) pisa el tramo del turno? */
  function bloqueEnTurno(bloque, turno) {
    const h = horarioTurno(turno);
    if (!h) return false;
    return numero(bloque.horaInicio) < h.hasta && h.desde < numero(bloque.horaFin);
  }

  /* ============================================================
     Dotación requerida, derivada del programa
     ============================================================ */

  /** Equipos con producción programada que pisan un turno de un día. */
  function equiposActivos(datos, semanaId, dia, turno) {
    const vistos = {};
    (datos.bloquePlan || [])
      .filter(b => b.semanaId === semanaId && b.dia === dia &&
                   b.tipo === "produccion" && bloqueEnTurno(b, turno))
      .forEach(b => { vistos[b.equipo] = true; });
    return Object.keys(vistos);
  }

  /** Dotación que ese turno necesita, deducida de los equipos activos.
   *  - operador: uno por equipo activo (o lo que diga dotacionEquipo)
   *  - laboratorio: uno si hay algún evaporador activo (muestreo)
   *  - supervisor: uno si hay actividad */
  function dotacionRequerida(datos, semanaId, dia, turno) {
    const activos = equiposActivos(datos, semanaId, dia, turno);
    const dot = dotEquipo();
    const operador = activos.reduce((s, e) => s + (dot[e] === undefined ? 1 : numero(dot[e])), 0);
    const hayEvaporador = activos.some(e => evaporadores().includes(e));

    const req = {
      operador,
      laboratorio: hayEvaporador ? 1 : 0,
      supervisor: activos.length ? 1 : 0
    };
    req.total = req.operador + req.laboratorio + req.supervisor;
    req.activos = activos;
    return req;
  }

  /* ============================================================
     Dotación asignada
     ============================================================ */

  function asignacionesDe(datos, semanaId, dia, turno) {
    return (datos.asignacionTurno || [])
      .filter(a => a.semanaId === semanaId && a.dia === dia && a.turno === turno);
  }

  function dotacionAsignada(datos, semanaId, dia, turno) {
    const asignaciones = asignacionesDe(datos, semanaId, dia, turno);
    const por = { operador: 0, laboratorio: 0, supervisor: 0 };
    asignaciones.forEach(a => { por[a.funcion] = (por[a.funcion] || 0) + 1; });
    por.total = asignaciones.length;
    por.personas = asignaciones;
    return por;
  }

  /* ============================================================
     Cobertura: requerido vs asignado
     ============================================================ */

  /** Cobertura de un turno. Devuelve motivos, no un booleano. */
  function coberturaTurno(datos, semanaId, dia, turno) {
    const requerido = dotacionRequerida(datos, semanaId, dia, turno);
    const asignado  = dotacionAsignada(datos, semanaId, dia, turno);

    const faltantes = {}, sobrantes = {};
    const bloqueos = [];
    for (const f of Object.keys(funciones())) {
      const falta = (requerido[f] || 0) - (asignado[f] || 0);
      if (falta > 0) {
        faltantes[f] = falta;
        bloqueos.push(`Falta${falta > 1 ? "n" : ""} ${falta} ${ETIQUETA_FUNCION(f).toLowerCase()}${falta > 1 ? "es" : ""}.`);
      } else if (falta < 0 && (requerido.total > 0)) {
        sobrantes[f] = -falta;
      }
    }

    let estado;
    if (!requerido.total)                        estado = "sin_actividad";
    else if (!asignado.total)                    estado = "descubierto";
    else if (Object.keys(faltantes).length)      estado = "parcial";
    else                                         estado = "cubierto";

    return {
      dia, turno, requerido, asignado, faltantes, sobrantes, estado,
      cubierto: estado === "cubierto" || estado === "sin_actividad",
      bloqueos
    };
  }

  /** Cobertura de toda la semana: una entrada por día × turno. */
  function coberturaSemana(datos, semanaId) {
    const semana = (datos.semanaPlan || []).find(s => s.id === semanaId);
    const dias = semana ? (numero(semana.dias) || 6) : 6;
    const turnos = cat().turnos;
    const celdas = [];
    for (let dia = 0; dia < dias; dia++) {
      for (const turno of turnos) celdas.push(coberturaTurno(datos, semanaId, dia, turno));
    }
    return celdas;
  }

  /* ============================================================
     Conflictos de la persona
     ============================================================ */

  /** Intervalo absoluto de una asignación, en horas desde el lunes 0 h. */
  function intervaloAbsoluto(asignacion) {
    const h = horarioTurno(asignacion.turno);
    if (!h) return null;
    const base = numero(asignacion.dia) * 24;
    return { inicio: base + h.desde, fin: base + h.hasta, asignacion };
  }

  /** Choques de una semana: solapamientos y descansos insuficientes.
   *  Recorre los intervalos de cada persona en horas absolutas, así el salto
   *  de un día a otro (turno C de un día, turno A del siguiente) se detecta
   *  sin casos especiales. */
  function conflictos(datos, semanaId) {
    const porPersona = {};
    (datos.asignacionTurno || [])
      .filter(a => a.semanaId === semanaId)
      .forEach(a => {
        const it = intervaloAbsoluto(a);
        if (!it) return;
        (porPersona[a.usuarioId] = porPersona[a.usuarioId] || []).push(it);
      });

    const problemas = [];
    for (const [usuarioId, intervalos] of Object.entries(porPersona)) {
      intervalos.sort((x, y) => x.inicio - y.inicio);
      for (let i = 1; i < intervalos.length; i++) {
        const prev = intervalos[i - 1], act = intervalos[i];
        if (act.inicio < prev.fin) {
          problemas.push({ tipo: "solapamiento", usuarioId,
            a: prev.asignacion, b: act.asignacion,
            mensaje: "Está asignada a dos turnos que se solapan." });
        } else {
          const descanso = act.inicio - prev.fin;
          if (descanso < minDescanso()) {
            problemas.push({ tipo: "descanso_insuficiente", usuarioId, horas: descanso,
              a: prev.asignacion, b: act.asignacion,
              mensaje: `Solo ${descanso} h de descanso entre turnos (mínimo ${minDescanso()} h).` });
          }
        }
      }
    }
    return problemas;
  }

  /* ============================================================
     Validación y publicación
     ============================================================ */

  /** ¿Se puede asignar a esta persona a este turno sin romper reglas? */
  function validarAsignacion(asignacion, datos) {
    const bloqueos = [];
    if (!asignacion.usuarioId) bloqueos.push("Indique la persona.");
    if (!asignacion.turno)     bloqueos.push("Indique el turno.");

    const yaEsta = (datos.asignacionTurno || []).some(a =>
      a.id !== asignacion.id &&
      a.semanaId === asignacion.semanaId && a.dia === asignacion.dia &&
      a.turno === asignacion.turno && a.usuarioId === asignacion.usuarioId);
    if (yaEsta) bloqueos.push("Esa persona ya está asignada a ese turno.");

    // Descanso: se prueba incorporando la asignación propuesta.
    const it = intervaloAbsoluto(asignacion);
    if (it) {
      (datos.asignacionTurno || [])
        .filter(a => a.id !== asignacion.id && a.semanaId === asignacion.semanaId &&
                     a.usuarioId === asignacion.usuarioId)
        .forEach(otra => {
          const io = intervaloAbsoluto(otra);
          if (!io) return;
          if (it.inicio < io.fin && io.inicio < it.fin) {
            bloqueos.push("Se solapa con otro turno de esa persona el mismo día.");
          } else {
            const descanso = Math.abs(it.inicio < io.inicio ? io.inicio - it.fin : it.inicio - io.fin);
            if (descanso < minDescanso()) {
              bloqueos.push(`Quedaría con ${descanso} h de descanso (mínimo ${minDescanso()} h).`);
            }
          }
        });
    }

    return { permitido: bloqueos.length === 0, bloqueos };
  }

  function puedePublicar(datos, semanaId) {
    const bloqueos = [];
    coberturaSemana(datos, semanaId).forEach(c => {
      if (c.estado === "descubierto" || c.estado === "parcial") {
        bloqueos.push(`${DIAS[c.dia]} · turno ${c.turno}: ${c.bloqueos.join(" ")}`);
      }
    });
    conflictos(datos, semanaId).forEach(p => bloqueos.push(p.mensaje));
    return { permitido: bloqueos.length === 0, bloqueos };
  }

  /* ============================================================
     Resumen
     ============================================================ */

  const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

  /** Horas asignadas a cada persona en la semana, para repartir carga. */
  function cargaPorPersona(datos, semanaId) {
    const carga = {};
    (datos.asignacionTurno || [])
      .filter(a => a.semanaId === semanaId)
      .forEach(a => {
        const h = horarioTurno(a.turno);
        if (!h) return;
        carga[a.usuarioId] = (carga[a.usuarioId] || 0) + (h.hasta - h.desde);
      });
    return carga;
  }

  function resumenSemana(datos, semanaId) {
    const celdas = coberturaSemana(datos, semanaId);
    const conProblema = celdas.filter(c => c.estado === "descubierto" || c.estado === "parcial");
    const activas = celdas.filter(c => c.estado !== "sin_actividad");
    const requeridoTotal = celdas.reduce((s, c) => s + c.requerido.total, 0);
    const asignadoTotal  = celdas.reduce((s, c) => s + c.asignado.total, 0);
    return {
      celdas,
      turnosActivos: activas.length,
      turnosDescubiertos: conProblema.length,
      requeridoTotal, asignadoTotal,
      conflictos: conflictos(datos, semanaId),
      personas: Object.keys(cargaPorPersona(datos, semanaId)).length
    };
  }

  return {
    DIAS, ETIQUETA_FUNCION,
    horarioTurno, bloqueEnTurno,
    equiposActivos, dotacionRequerida, asignacionesDe, dotacionAsignada,
    coberturaTurno, coberturaSemana,
    intervaloAbsoluto, conflictos,
    validarAsignacion, puedePublicar,
    cargaPorPersona, resumenSemana
  };
})();

if (typeof module !== "undefined" && module.exports) module.exports = Turnos;
