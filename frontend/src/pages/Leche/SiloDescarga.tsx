import TablaRecepciones from "./TablaRecepciones";

/*
  Paso 3: aprobadas por Calidad. Falta asignarles silo, o descargarlas.

  Los dos trabajos comparten estado —`liberada`— y se distinguen por si el
  silo ya está asignado; el botón de cada fila ya lo resuelve. Por eso van
  juntos en una pestaña y no en dos: es la misma persona, en la misma vuelta.
*/
function SiloDescarga() {
  return (
    <TablaRecepciones
      estados="liberada"
      titulo="Aprobadas por Calidad"
      descripcion="Asigna el silo de destino y registra la descarga. La descarga mueve el saldo del silo."
      vacio={{
        titulo: "Nada aprobado esperando descarga",
        detalle: "Las cargas aparecen aquí cuando Calidad las libera.",
      }}
    />
  );
}

export default SiloDescarga;
