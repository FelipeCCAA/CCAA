import TablaRecepciones from "./TablaRecepciones";

/*
  Paso 2: las muestras que Calidad tiene que decidir.

  Incluye las **retenidas**, que no son un caso cerrado: se reanalizan y pueden
  liberarse. Dejarlas en el historial las escondería del único rol que puede
  destrabarlas.
*/
function Calidad() {
  return (
    <TablaRecepciones
      estados="muestreada,retenida"
      titulo="Muestras por decidir"
      descripcion="Muestreadas a la espera de decisión, y retenidas que se pueden reanalizar."
      vacio={{
        titulo: "No hay muestras pendientes",
        detalle: "Nada esperando decisión de Calidad.",
      }}
    />
  );
}

export default Calidad;
