import TablaRecepciones from "./TablaRecepciones";

/*
  Lo que ya está en silo. Es la pestaña que se consulta, no la que se trabaja.

  Su búsqueda **pregunta a la base**: es el caso donde el filtro en el cliente
  fallaba de la peor manera, porque buscar una guía vieja respondía «no
  encontramos recepciones» sobre algo que sí existía.
*/
function Historial() {
  return (
    <TablaRecepciones
      estados="descargada,cerrada"
      titulo="Descargadas y cerradas"
      descripcion="Histórico de módulos que ya entraron a silo."
      vacio={{
        titulo: "Sin descargas registradas",
        detalle: "Prueba con otro término de búsqueda.",
      }}
    />
  );
}

export default Historial;
