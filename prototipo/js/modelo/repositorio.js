/* ============================================================
   Repositorio — Gestión Productiva Planta CCAA
   ------------------------------------------------------------
   Única capa que sabe DÓNDE viven los datos. El dominio y la interfaz
   nunca tocan el almacenamiento directamente.

   TODA la API es asíncrona (Promesas) aunque hoy el adaptador sea
   localStorage, que es síncrono. Es deliberado: cuando los datos se
   muevan a una API, SharePoint o una base de datos, cambia UN archivo
   —el adaptador— y ni el dominio ni la UI se enteran. Si la API
   naciera síncrona, esa migración obligaría a reescribir la app entera.

   Responsabilidades:
     · validar contra el esquema        · integridad referencial
     · índices únicos                   · bitácora de auditoría
     · asignación de identidad
   ============================================================ */

const Repositorio = (() => {

  const CLAVE = "gpccaa_v2";
  let db = null;              // instantánea en memoria
  let adaptador = null;
  let sesion = { usuarioId: null };

  const clonar = o => JSON.parse(JSON.stringify(o));
  const ahora  = () => new Date().toISOString();

  /* ============================================================
     Adaptadores de almacenamiento
     Contrato: leerTodo() -> Promise<objeto|null>, escribirTodo(obj) -> Promise<void>
     ============================================================ */

  const AdaptadorLocalStorage = (clave = CLAVE) => ({
    nombre: "localStorage",
    async leerTodo() {
      const crudo = localStorage.getItem(clave);
      return crudo ? JSON.parse(crudo) : null;
    },
    async escribirTodo(datos) {
      localStorage.setItem(clave, JSON.stringify(datos));
    }
  });

  /** Adaptador en memoria: para pruebas y para prototipar sin ensuciar el navegador. */
  const AdaptadorMemoria = (inicial = null) => {
    let contenido = inicial ? clonar(inicial) : null;
    return {
      nombre: "memoria",
      async leerTodo() { return contenido ? clonar(contenido) : null; },
      async escribirTodo(datos) { contenido = clonar(datos); }
    };
  };

  /* ============================================================
     Errores de negocio: llevan la lista de motivos legible
     ============================================================ */

  class ErrorRepositorio extends Error {
    constructor(mensaje, motivos = []) {
      super(mensaje);
      this.name = "ErrorRepositorio";
      this.motivos = motivos;
    }
  }

  /* ============================================================
     Ciclo de vida
     ============================================================ */

  function baseVacia() {
    const vacia = {};
    for (const nombre of Esquema.nombres) vacia[nombre] = [];
    vacia._meta = { version: Esquema.version, creada: ahora() };
    return vacia;
  }

  /** Inicializa el repositorio. `semilla` solo se aplica si no hay datos previos. */
  async function iniciar(opciones = {}) {
    adaptador = opciones.adaptador || AdaptadorLocalStorage();
    const guardado = await adaptador.leerTodo();

    if (guardado) {
      db = guardado;
      // Actualización de esquema: una colección que NO existía en los datos
      // guardados es una entidad nueva, así que se rellena desde la semilla.
      // Una que existe se respeta aunque esté vacía: el usuario pudo vaciarla.
      const semilla = opciones.semilla || {};
      const incorporadas = [];
      for (const nombre of Esquema.nombres) {
        if (Array.isArray(db[nombre])) continue;
        db[nombre] = Array.isArray(semilla[nombre]) ? clonar(semilla[nombre]) : [];
        if (db[nombre].length) incorporadas.push(nombre);
      }
      // Migraciones de forma: convierten datos de un esquema anterior.
      const migrado = opciones.migrar ? !!opciones.migrar(db) : false;

      // Y por último se descartan los campos que el esquema ya no declara,
      // para que un registro viejo no haga fallar su propia validación.
      let depurados = 0;
      for (const nombre of Esquema.nombres) {
        const campos = Esquema.ENTIDADES[nombre].campos;
        for (const registro of db[nombre]) {
          for (const clave of Object.keys(registro)) {
            if (!campos[clave]) { delete registro[clave]; depurados++; }
          }
        }
      }

      if (incorporadas.length || migrado || depurados) {
        db._meta = Object.assign({}, db._meta, { actualizado: ahora(), incorporadas, depurados });
        await adaptador.escribirTodo(db);
      }
    } else {
      db = opciones.semilla ? clonar(opciones.semilla) : baseVacia();
      for (const nombre of Esquema.nombres) if (!Array.isArray(db[nombre])) db[nombre] = [];
      db._meta = { version: Esquema.version, creada: ahora() };
      await adaptador.escribirTodo(db);
    }
    return db;
  }

  function identificarse(usuarioId) { sesion.usuarioId = usuarioId; }
  function usuarioActual() { return sesion.usuarioId; }

  function exigirInicio() {
    if (!db) throw new ErrorRepositorio("El repositorio no está iniciado. Llame a Repositorio.iniciar() primero.");
  }

  async function persistir() { await adaptador.escribirTodo(db); }

  /* ============================================================
     Identidad
     ============================================================ */

  let contador = 0;
  function nuevoId(entidad) {
    contador += 1;
    const marca = Date.now().toString(36);
    return `${entidad}_${marca}${contador.toString(36).padStart(2, "0")}`;
  }

  /* ============================================================
     Integridad
     ============================================================ */

  function verificarReferencias(entidad, obj) {
    const motivos = [];
    for (const [campo, destino] of Object.entries(Esquema.referencias(entidad))) {
      const valor = obj[campo];
      if (valor === null || valor === undefined || valor === "") continue;
      if (!(db[destino] || []).some(r => r.id === valor)) {
        motivos.push(`${campo}: no existe ${Esquema.ENTIDADES[destino].etiqueta} con id "${valor}".`);
      }
    }
    return motivos;
  }

  function verificarUnicos(entidad, obj, idExcluido) {
    const motivos = [];
    const indices = (Esquema.ENTIDADES[entidad].indices || []).filter(i => i.unico);
    for (const indice of indices) {
      const choque = (db[entidad] || []).some(r =>
        r.id !== idExcluido && indice.campos.every(c => r[c] === obj[c])
      );
      if (choque) {
        const detalle = indice.campos.map(c => `${c}="${obj[c]}"`).join(", ");
        motivos.push(`Ya existe un registro con ${detalle}.`);
      }
    }
    return motivos;
  }

  /** Entidades que apuntan a este registro. Impide borrar algo en uso. */
  function dependientes(entidad, id) {
    const encontrados = [];
    for (const otra of Esquema.nombres) {
      for (const [campo, destino] of Object.entries(Esquema.referencias(otra))) {
        if (destino !== entidad) continue;
        const cuantos = (db[otra] || []).filter(r => r[campo] === id).length;
        if (cuantos) encontrados.push({ entidad: otra, campo, cuantos });
      }
    }
    return encontrados;
  }

  /* ============================================================
     Auditoría
     ============================================================ */

  function auditar(entidad, entidadId, accion, antes, despues) {
    if (entidad === "eventoAuditoria") return;   // no se audita la auditoría
    db.eventoAuditoria.push({
      id: nuevoId("aud"),
      entidad, entidadId, accion,
      usuarioId: sesion.usuarioId,
      fechaHora: ahora(),
      antes: antes ? clonar(antes) : null,
      despues: despues ? clonar(despues) : null
    });
  }

  /* ============================================================
     Operaciones
     ============================================================ */

  async function listar(entidad, filtro) {
    exigirInicio();
    const todos = clonar(db[entidad] || []);
    if (!filtro) return todos;
    if (typeof filtro === "function") return todos.filter(filtro);
    return todos.filter(r => Object.entries(filtro).every(([k, v]) => r[k] === v));
  }

  async function obtener(entidad, id) {
    exigirInicio();
    const hallado = (db[entidad] || []).find(r => r.id === id);
    return hallado ? clonar(hallado) : null;
  }

  async function crear(entidad, datos) {
    exigirInicio();
    if (!Esquema.ENTIDADES[entidad]) throw new ErrorRepositorio(`Entidad desconocida: ${entidad}`);
    if (Esquema.ENTIDADES[entidad].soloLectura) throw new ErrorRepositorio(`${entidad} es de solo lectura.`);

    const registro = Esquema.conDefectos(entidad, Object.assign({}, datos));
    if (!registro.id) registro.id = nuevoId(entidad);

    const { valido, errores } = Esquema.validar(entidad, registro);
    const motivos = errores
      .concat(valido ? verificarReferencias(entidad, registro) : [])
      .concat(valido ? verificarUnicos(entidad, registro, null) : []);

    if (motivos.length) throw new ErrorRepositorio(`No se pudo crear ${entidad}.`, motivos);

    db[entidad].push(registro);
    auditar(entidad, registro.id, "crear", null, registro);
    await persistir();
    return clonar(registro);
  }

  async function actualizar(entidad, id, cambios) {
    exigirInicio();
    if (Esquema.ENTIDADES[entidad].soloLectura) throw new ErrorRepositorio(`${entidad} es de solo lectura.`);

    const indice = (db[entidad] || []).findIndex(r => r.id === id);
    if (indice < 0) throw new ErrorRepositorio(`No existe ${entidad} con id "${id}".`);

    const antes = db[entidad][indice];
    const despues = Object.assign({}, antes, cambios, { id });

    const { errores } = Esquema.validar(entidad, despues);
    const motivos = errores
      .concat(verificarReferencias(entidad, despues))
      .concat(verificarUnicos(entidad, despues, id));

    // Si la entidad declara máquina de estados, la transición debe ser válida.
    const maquina = Esquema.ESTADOS[entidad];
    if (maquina && cambios.estado && cambios.estado !== antes.estado &&
        !Esquema.transicionValida(entidad, antes.estado, cambios.estado)) {
      motivos.push(`Transición de estado no permitida: "${antes.estado}" → "${cambios.estado}".`);
    }

    if (motivos.length) throw new ErrorRepositorio(`No se pudo actualizar ${entidad}.`, motivos);

    db[entidad][indice] = despues;
    auditar(entidad, id, "actualizar", antes, despues);
    await persistir();
    return clonar(despues);
  }

  async function eliminar(entidad, id) {
    exigirInicio();
    const indice = (db[entidad] || []).findIndex(r => r.id === id);
    if (indice < 0) throw new ErrorRepositorio(`No existe ${entidad} con id "${id}".`);

    const enUso = dependientes(entidad, id);
    if (enUso.length) {
      throw new ErrorRepositorio(`No se puede eliminar ${entidad}: está en uso.`,
        enUso.map(d => `${Esquema.ENTIDADES[d.entidad].etiqueta}: ${d.cuantos} registro(s) lo referencian.`));
    }

    const antes = db[entidad][indice];
    db[entidad].splice(indice, 1);
    auditar(entidad, id, "eliminar", antes, null);
    await persistir();
    return true;
  }

  /** Instantánea completa. El dominio trabaja sobre datos en memoria,
   *  así que la interfaz la pide una vez y evalúa todo sin más lecturas. */
  async function instantanea() {
    exigirInicio();
    return clonar(db);
  }

  /* ============================================================
     Respaldo y traspaso
     ============================================================ */

  function exportar() {
    exigirInicio();
    return JSON.stringify(db, null, 2);
  }

  /** Importa un volcado validando ANTES de tocar los datos actuales.
   *  Si algo falla, la base queda intacta. */
  async function importar(texto) {
    exigirInicio();
    let entrante;
    try { entrante = JSON.parse(texto); }
    catch (e) { throw new ErrorRepositorio("El archivo no es JSON válido.", [e.message]); }

    const motivos = [];
    const colecciones = [];
    for (const nombre of Esquema.nombres) {
      if (entrante[nombre] === undefined) continue;
      if (!Array.isArray(entrante[nombre])) { motivos.push(`"${nombre}" debería ser una lista.`); continue; }
      entrante[nombre].forEach((r, i) => {
        const { valido, errores } = Esquema.validar(nombre, r);
        if (!valido) motivos.push(`${nombre}[${i}]: ${errores.join(" ")}`);
      });
      colecciones.push(nombre);
    }
    if (!colecciones.length) motivos.push("El archivo no contiene ninguna colección reconocida.");
    if (motivos.length) throw new ErrorRepositorio("El archivo tiene errores; no se importó nada.", motivos.slice(0, 20));

    const respaldo = clonar(db);
    for (const nombre of colecciones) db[nombre] = entrante[nombre];
    db._meta = Object.assign({}, db._meta, { importado: ahora(), respaldoPrevio: respaldo._meta });
    auditar("_sistema", "importacion", "actualizar", null, { colecciones });
    await persistir();
    return { colecciones, respaldo };
  }

  async function restablecer(semilla) {
    exigirInicio();
    db = semilla ? clonar(semilla) : baseVacia();
    for (const nombre of Esquema.nombres) if (!Array.isArray(db[nombre])) db[nombre] = [];
    await persistir();
    return db;
  }

  return {
    AdaptadorLocalStorage, AdaptadorMemoria, ErrorRepositorio,
    iniciar, identificarse, usuarioActual,
    listar, obtener, crear, actualizar, eliminar,
    instantanea, exportar, importar, restablecer,
    dependientes
  };
})();

if (typeof module !== "undefined" && module.exports) module.exports = Repositorio;
