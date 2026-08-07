import TablaRecepciones from "./TablaRecepciones";

/*
  Paso 1: los módulos que llegaron y esperan que alguien tome la muestra.

  Es la pantalla del turno de recepción. Antes esta lista estaba al final de un
  scroll de dos pantallas, debajo de diecinueve tarjetas de silo.
*/
function Muestreo() {
  return (
    <TablaRecepciones
      estados="registrada"
      titulo="Por muestrear"
      descripcion="Módulos recibidos que todavía no tienen muestra tomada."
      vacio={{
        titulo: "No hay módulos esperando muestra",
        detalle: "Cuando se registre una llegada aparecerá aquí.",
      }}
    />
  );
}

export default Muestreo;
