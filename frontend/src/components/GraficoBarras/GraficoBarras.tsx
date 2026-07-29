/*
  Barras horizontales para comparar magnitudes entre categorías.

  Horizontales y no verticales porque los nombres ("Leche semidescremada en
  polvo") no caben rotados bajo un eje.

  Una sola serie: no lleva leyenda —el título dice qué se está midiendo— y
  cada barra lleva su valor escrito al lado, que con pocas categorías se lee
  mejor que un eje con marcas. Los números van en color de texto, no en el
  color de la barra: el color identifica la marca, no el dato.
*/

interface Dato {
  nombre: string;
  kg: number;
}

interface Props {
  titulo: string;
  subtitulo?: string;
  datos: Dato[];
  unidad?: string;
}


const formato = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });


function GraficoBarras({ titulo, subtitulo, datos, unidad = "kg" }: Props) {

  // La escala se ancla al mayor valor, no a la suma: comparar alturas
  // relativas es lo que se quiere leer aquí.
  const maximo = Math.max(...datos.map((d) => d.kg), 0);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6">

      <h2 className="text-lg font-semibold text-slate-800">

        {titulo}

      </h2>

      {subtitulo && (

        <p className="mt-1 text-sm text-slate-400">

          {subtitulo}

        </p>

      )}

      {datos.length === 0 ? (

        <p className="mt-6 text-sm text-slate-400">

          Sin datos en el periodo.

        </p>

      ) : (

        <ul className="mt-6 space-y-5">

          {datos.map((dato) => {

            const porcentaje = maximo > 0 ? (dato.kg / maximo) * 100 : 0;

            return (

              <li key={dato.nombre}>

                <div className="mb-2 flex items-baseline justify-between gap-4">

                  <span className="truncate text-sm text-slate-600">

                    {dato.nombre}

                  </span>

                  <span className="shrink-0 text-sm font-medium text-slate-800">

                    {formato.format(dato.kg)}

                    <span className="ml-1 text-xs font-normal text-slate-400">

                      {unidad}

                    </span>

                  </span>

                </div>

                <div
                  className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100"
                  title={`${dato.nombre}: ${formato.format(dato.kg)} ${unidad}`}
                >

                  <div
                    className="h-full rounded-full bg-green-600"
                    style={{ width: `${porcentaje}%` }}
                  />

                </div>

              </li>

            );

          })}

        </ul>

      )}

    </section>
  );
}


export default GraficoBarras;
