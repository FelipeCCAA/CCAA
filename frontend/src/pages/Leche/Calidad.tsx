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
      descripcion="Completa una vez los controles del camión y registra únicamente la crioscopía propia de cada módulo."
      vacio={{
        titulo: "No hay muestras pendientes",
        detalle: "Nada esperando decisión de Calidad.",
      }}
    />
  );
}

export default Calidad;
