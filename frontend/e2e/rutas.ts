/*
  Inventario de pantallas que audita la revisión de accesibilidad.

  Está escrito a mano y no deducido de `app/routes.tsx` a propósito: una lista
  generada del router se mantiene sola, pero también se calla sola. Si alguien
  borra una ruta, la lista generada deja de auditarla sin que nadie se entere;
  esta, en cambio, falla al navegar y obliga a decidir si la pantalla se fue o
  se rompió.

  La aplicación usa `HashRouter`, así que la dirección real es `/#/dashboard`.
  Navegar a `/dashboard` a secas devuelve el mismo `index.html` y la auditoría
  mediría treinta veces el panel de inicio creyendo que recorrió la aplicación.
  De ahí que `abrirRuta` anteponga el `#`.
*/

export interface Pantalla {
  /** Ruta dentro del hash, sin el `#`. */
  ruta: string;
  /** Nombre legible; es lo que sale en el informe. */
  nombre: string;
}

/* Pantallas de acceso: se auditan SIN sesión. Son las únicas que un operario
   ve antes de identificarse, y si el contraste falla ahí no puede ni entrar
   a encontrarse con el resto de los problemas. */
export const PANTALLAS_PUBLICAS: Pantalla[] = [
  { ruta: "/login", nombre: "Iniciar sesión" },
  { ruta: "/recuperar-contrasena", nombre: "Recuperar contraseña" },
  { ruta: "/restablecer-contrasena", nombre: "Restablecer contraseña" },
];

/* Pantallas internas: exigen sesión (ver `RutaProtegida`). */
export const PANTALLAS_PRIVADAS: Pantalla[] = [
  { ruta: "/dashboard", nombre: "Panel" },

  /* Abastecimiento es una sección con pestañas y cada pestaña es una URL.
     Se auditan todas: comparten el marco pero no el contenido, y las tablas
     son justamente donde se esconden los problemas de encabezado y contraste. */
  { ruta: "/abastecimiento", nombre: "Abastecimiento · Panel" },
  { ruta: "/abastecimiento/materiales", nombre: "Abastecimiento · Materiales" },
  { ruta: "/abastecimiento/stock", nombre: "Abastecimiento · Stock" },
  { ruta: "/abastecimiento/bodegas", nombre: "Abastecimiento · Bodegas" },
  { ruta: "/abastecimiento/compras", nombre: "Abastecimiento · Compras" },
  { ruta: "/abastecimiento/proveedores", nombre: "Abastecimiento · Proveedores" },
  { ruta: "/abastecimiento/recepcion", nombre: "Abastecimiento · Recepción" },
  { ruta: "/abastecimiento/calidad", nombre: "Abastecimiento · Calidad" },
  { ruta: "/abastecimiento/pedidos", nombre: "Abastecimiento · Pedidos" },
  { ruta: "/abastecimiento/mrp", nombre: "Abastecimiento · MRP" },

  { ruta: "/procesos", nombre: "Procesos" },
  { ruta: "/mantenimiento", nombre: "Mantenimiento" },
  { ruta: "/inocuidad/aseos", nombre: "Inocuidad · Aseos" },
  { ruta: "/produccion", nombre: "Producción" },

  /* Leche cruda: el viaje del producto, de la ruta de recolección al silo. */
  { ruta: "/leche", nombre: "Leche · Panel" },
  { ruta: "/leche/rutas", nombre: "Leche · Rutas" },
  { ruta: "/leche/en-camino", nombre: "Leche · En camino" },
  { ruta: "/leche/muestreo", nombre: "Leche · Muestreo" },
  { ruta: "/leche/calidad", nombre: "Leche · Calidad" },
  { ruta: "/leche/descarga", nombre: "Leche · Descarga a silo" },
  { ruta: "/leche/silos", nombre: "Leche · Silos" },
  { ruta: "/leche/historial", nombre: "Leche · Historial" },

  { ruta: "/estandarizacion", nombre: "Estandarización" },
  { ruta: "/liberacion", nombre: "Liberación" },
  { ruta: "/planificacion", nombre: "Planificación" },
  { ruta: "/maestros", nombre: "Maestros" },
  { ruta: "/registros", nombre: "Registros" },
  { ruta: "/auditoria", nombre: "Auditoría" },

  /* Exige rol admin (`RutaAdmin`). Con un usuario de otro rol esta pantalla
     redirige y la auditoría mediría el panel: por eso el usuario de la
     auditoría tiene que ser administrador, y `auth.setup.ts` lo comprueba. */
  { ruta: "/administracion", nombre: "Administración" },
];

export const TODAS = [...PANTALLAS_PUBLICAS, ...PANTALLAS_PRIVADAS];
