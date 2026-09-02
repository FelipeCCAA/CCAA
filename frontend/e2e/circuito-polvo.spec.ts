/*
  El circuito completo de leche en polvo, por pantalla.

  Recorre lo que hace un turno entero: llegan dos camiones —entera y
  descremada—, Calidad los decide, se descargan en sus estanques, se analiza el
  silo, se compone y libera un vale de estandarización, se abre el lote, se
  declaran los kilos y se arma el pallet.

  Por qué por pantalla y no por API
  ---------------------------------
  La cadena ya está cubierta por API en `sembrar_flujo_demo` y por unidad en
  cada `tests_dominio`. Lo que ninguna de las dos comprueba es que un operador
  pueda recorrerla: un desplegable que sale vacío, un botón que queda
  deshabilitado o una pantalla que no ofrece el paso siguiente dejan el backend
  impecable y la planta detenida. Eso es exactamente lo que pasó con el
  responsable del muestreo, que se llena con los usuarios del área Recepción y
  salía vacío porque ningún perfil tenía área.

  Prerrequisitos
  --------------
  Áreas de perfil, receta del producto y existencia de embalaje los deja
  `python manage.py preparar_circuito_polvo --aplicar`. No se siembran desde
  aquí a propósito: son configuración de planta, y una prueba que la fabrica
  cada vez esconde justo el caso de que en producción falte.

  Es una sola prueba y no nueve, porque son nueve pasos del mismo hecho: el
  lote no existe sin su vale, y el vale no existe sin sus recepciones. Nueve
  pruebas independientes tendrían que sembrar cada una el estado de la anterior
  —o sea, dejar de recorrer el circuito—. Cada `test.step` dice en qué eslabón
  se rompió, que es lo que se quiere saber cuando falla.
*/

import { test, expect, type Page } from "@playwright/test";

import {
  analizarSilo, campo, cerrarSegundaFirma, descartarPendiente, elegirOpcion,
  irA, rechazos, trasGuardar, vigilar,
} from "./ayudantes";
import { API } from "./constantes";

/* Cada corrida escribe códigos nuevos. Reutilizarlos chocaría con la unicidad
   de guía, vale, lote y pallet a la segunda vuelta, y el fallo parecería del
   circuito en vez del sembrado. */
const SELLO = Date.now().toString().slice(-6);

const HOY = new Date().toISOString().slice(0, 10);

/* Leche que pasa los cinco controles del dominio: acidez ≤ 18, pH 6,5–6,9,
   temperatura ≤ 8, crioscopía ≤ −0,510 y pH de camión 5,5–8,5. Los valores no
   son redondos porque una lectura de planta tampoco lo es. */
const ENTERA = {
  guia: `GR-ENT-${SELLO}`,
  litros: "25000",
  crioscopia: "-0.521",
  grasa: "3.62",
  sng: "8.61",
};

const DESCREMADA = {
  guia: `GR-DES-${SELLO}`,
  litros: "8000",
  crioscopia: "-0.518",
  grasa: "0.05",
  sng: "8.88",
};

/*
  El vale prepara menos litros de los recibidos: sobra leche en el silo, que es
  la situación normal, y no la que deja el saldo en cero justo.

  El RC objetivo es 0,3000 y no el de la leche entera (3,62/8,61 = 0,4204)
  **para que la descremada haga falta**. Con un objetivo cercano al de la
  entera, la mezcla sale con veinte litros de descremada y el circuito da por
  buena una estandarización que en realidad no estandarizó nada. Con 0,3000 la
  mezcla pide ~14.300 L de entera y ~5.700 de descremada.
*/
const VALE = {
  codigo: `VE-${SELLO}`,
  volumen: "20000",
  rcObjetivo: "0.3000",
};

/*
  Los estanques se eligen al empezar, no se fijan aquí.

  El circuito **escribe leche de verdad**: cada corrida deja litros en el silo
  que usó, y con estanques fijos la tercera vuelta choca contra «no tiene
  capacidad suficiente» — un fallo que parece del circuito y es del sitio.
  Se piden los tres con sitio de sobra al arrancar, que además es lo que hace
  el operador: mira la ocupación y elige.
*/
const ESTANQUES = { entera: "", descremada: "", destino: "" };

/*
  La muestra tras agitar. `decidir` no acepta una decisión: compara el RC medido
  con el objetivo y admite ±0,005. 2,61/8,70 = 0,3000 clavado, así que el vale
  sale liberado y el circuito sigue. Un valor fuera de tolerancia lo mandaría a
  «corrigiendo», que es correcto pero no es el camino que esta prueba recorre.
*/
const MUESTRA = { grasa: "2.61", sng: "8.70" };

const LOTE = { codigo: `CCAA-CIR-${SELLO}`, litros: "6000", kg: "500" };

const PALLET = { codigo: `PAL-${SELLO}`, sacos: "20" };










/*
  Registra la llegada de un camión y lo deja descargado en su estanque.

  Los cuatro pasos —llegada, muestra, calidad, silo y descarga— van juntos
  porque son el mismo camión; separarlos obligaría a buscar la fila por guía
  cuatro veces en cuatro pantallas para no ganar nada.
*/
async function recibirCamion(
  pagina: Page,
  leche: typeof ENTERA,
  tipo: "Entera" | "Descremada",
  estanque: string,
) {
  await irA(pagina, "/leche");
  await pagina.getByRole("button", { name: "Registrar llegada" }).click();

  const formulario = pagina.getByRole("dialog").or(pagina.locator("form")).first();
  await expect(pagina.getByText("Registrar llegada del camión")).toBeVisible();

  await descartarPendiente(pagina);

  await campo(pagina, "Fecha *").fill(HOY);
  await campo(pagina, "Guía / recepción").fill(leche.guia);

  /* Cualquier camión con patente sirve; la patente concreta es dato de planta
     y escribirla aquí ataría la prueba a una fila de la base. Lo que sí se
     exige es que **tenga** patente: el maestro trae una ficha con la placa
     vacía, y elegirla por posición dejaba la recepción como «Sin camión». */
  await elegirOpcion(campo(pagina, "Camión *"), /^[A-Z]{2}/);
  await campo(pagina, "Tipo de leche *").selectOption(tipo);
  await campo(pagina, "Litros *").fill(leche.litros);
  await campo(pagina, "Crioscopía (°C)").fill(leche.crioscopia);

  /* Sin arribo a portería la permanencia no se puede calcular y el resumen
     diario cuenta el camión como «sin marcas horarias». */
  await campo(pagina, "Arribo a portería").fill("07:10");
  await campo(pagina, "Hora de ingreso").fill("07:25");

  /* Se espera `confirmar-borrador` y no cualquier petición de recepción: el
     formulario autoguarda un borrador mientras se teclea, y engancharse a esa
     respuesta daba la llegada por registrada cuando todavía no lo estaba. La
     pantalla siguiente cargaba su lista antes de que la confirmación llegara
     al servidor, mostraba «0 registros» y ya no vuelve a consultar. */
  await trasGuardar(pagina, "confirmar-borrador", async () => {
    await formulario.getByRole("button", { name: "Confirmar llegada" }).click();
  });

  // -- Muestreo -----------------------------------------------------------
  await irA(pagina, "/leche/muestreo");
  const filaMuestreo = pagina.getByRole("row", { name: new RegExp(leche.guia) });
  await expect(filaMuestreo).toBeVisible({ timeout: 15_000 });
  await filaMuestreo.getByRole("button", { name: /Tomar muestra|Muestrear/ }).click();

  const responsable = pagina.getByLabel("Responsable de la prueba");
  await expect(
    responsable.locator("option"),
    "El desplegable de responsables salió vacío: ningún perfil activo tiene " +
      "área Recepción. Corre «manage.py preparar_circuito_polvo --aplicar».",
  ).not.toHaveCount(1);
  await responsable.selectOption({ index: 1 });

  await trasGuardar(pagina, "tomar-muestra", async () => {
    await pagina.getByRole("button", { name: "Confirmar muestra" }).click();
  });

  // -- Decisión de Calidad ------------------------------------------------
  await irA(pagina, "/leche/calidad");
  const filaCalidad = pagina.getByRole("row", { name: new RegExp(leche.guia) });
  await expect(filaCalidad).toBeVisible({ timeout: 15_000 });
  await filaCalidad.getByRole("button", { name: /Evaluar|Reanalizar/ }).click();

  await pagina.getByLabel("pH de enjuague del camión").fill("7.05");
  await pagina.getByLabel("Temperatura", { exact: true }).fill("4.2");
  await pagina.getByLabel("Acidez", { exact: true }).fill("15.4");
  await pagina.getByLabel("pH", { exact: true }).fill("6.72");
  await pagina.getByLabel("Grasa", { exact: true }).fill(leche.grasa);
  await pagina.getByLabel("SNG", { exact: true }).fill(leche.sng);
  await pagina.getByLabel("Delvo Test").selectOption("Negativo");
  await pagina.getByLabel("Inhibidores").selectOption("Negativo");
  for (const item of ["Sangre", "Pus", "Materias extrañas", "Aroma"]) {
    await pagina.getByLabel(item).selectOption("Conforme");
  }

  /* El pH del camión se acaba de escribir, así que el formulario pide motivo
     de corrección: es la regla de auditoría, no un estorbo de la prueba. */
  const motivoPh = pagina.getByLabel("Motivo de corrección del pH");
  if (await motivoPh.isVisible()) {
    await motivoPh.fill("Lectura del enjuague registrada en la evaluación.");
  }

  await trasGuardar(pagina, "decidir-calidad", async () => {
    await pagina.getByRole("button", { name: "Guardar decisión" }).click();
  });

  // -- Silo y descarga ----------------------------------------------------
  await irA(pagina, "/leche/descarga");
  const filaSilo = pagina.getByRole("row", { name: new RegExp(leche.guia) });
  await expect(
    filaSilo,
    `La recepción ${leche.guia} no llegó a «Aprobadas por Calidad»: el ` +
      "veredicto la retuvo. Revisa los controles de esta prueba.",
  ).toBeVisible({ timeout: 15_000 });

  await filaSilo.getByRole("button", { name: "Asignar silo" }).click();
  await elegirOpcion(pagina.getByLabel("Silo compatible"), new RegExp(`^${estanque} `));
  await trasGuardar(pagina, "asignar-silo", async () => {
    await pagina.getByRole("button", { name: "Confirmar destino" }).click();
  });

  const filaDescarga = pagina.getByRole("row", { name: new RegExp(leche.guia) });
  await trasGuardar(pagina, "descargar", async () => {
    await filaDescarga.getByRole("button", { name: "Descargar" }).click();
  });
}




/*
  Reserva tres estanques con sitio: uno de entera, uno de descremada y el
  destino del vale.

  Se consulta la ocupación por API en vez de leerla de la pantalla porque es un
  paso de preparación, no un paso del circuito: lo que la prueba comprueba es
  que el operador **pueda** operar, no cómo se entera de cuánto le cabe a un
  silo. Se piden libres del todo para que ninguna corrida herede la leche —y la
  composición— de la anterior.
*/
async function reservarEstanques(pagina: Page) {
  /* `page.request` no pasa por el interceptor de axios, así que hay que poner
     la cabecera a mano: el token vive en `localStorage`, que es de donde lo
     saca `services/api.ts`. Sin ella la respuesta es 401 y el mensaje de fallo
     hablaría de la ocupación cuando el problema es la sesión. */
  const token = await pagina.evaluate(
    () => JSON.parse(localStorage.getItem("ccaa.sesion") ?? "{}").token,
  );
  const respuesta = await pagina.request.get(`${API}/api/recepcion/ocupacion/`, {
    headers: { Authorization: `Token ${token}` },
  });
  expect(
    respuesta.ok(),
    `No se pudo consultar la ocupación de los silos (HTTP ${respuesta.status()}).`,
  ).toBeTruthy();

  const { silos } = await respuesta.json();

  interface Fila { codigo: string; tipo: string; litros: number; capacidad: number; estado: string }

  /* Con **sitio suficiente**, no vacíos: el backend rechaza la descarga por
     capacidad, no por tener leche, y en planta un silo con resto es lo normal.
     Se ordena por lo que tienen dentro para repartir las corridas en vez de
     llenar siempre el mismo. */
  const conSitio = (tipo: string, minimo: number) =>
    (silos as Fila[])
      .filter((s) => s.tipo === tipo && s.estado === "disponible"
        && Number(s.capacidad) - Number(s.litros) >= minimo)
      .sort((a, b) => Number(a.litros) - Number(b.litros))
      .map((s) => s.codigo);

  const paraEntera = conSitio("silo", Number(ENTERA.litros));
  const paraDestino = conSitio("silo", Number(VALE.volumen));
  const paraDescremada = conSitio("tk_ld", Number(DESCREMADA.litros));

  expect(
    paraEntera.length,
    `Ningún silo admite ${ENTERA.litros} L de leche entera. Vacía alguno ` +
      "despachando su leche, o corre «manage.py limpiar_transaccional --aplicar» " +
      "si la base es de pruebas.",
  ).toBeGreaterThan(0);
  expect(
    paraDescremada.length,
    `Ningún TK admite ${DESCREMADA.litros} L de leche descremada.`,
  ).toBeGreaterThan(0);

  ESTANQUES.entera = paraEntera[0];
  ESTANQUES.descremada = paraDescremada[0];

  /* El destino tiene que ser otro silo: transferir sobre el de origen mezcla
     la leche estandarizada con la cruda que aún queda. */
  const destino = paraDestino.find((codigo) => codigo !== ESTANQUES.entera);
  expect(
    destino,
    `No hay un segundo silo que admita los ${VALE.volumen} L del vale.`,
  ).toBeTruthy();
  ESTANQUES.destino = destino as string;
}




/**
 * Abre la ficha del lote del circuito desde la tabla de Producción.
 *
 * Se busca por código en vez de recorrer la tabla: son cincuenta lotes por
 * página y el del circuito no tiene por qué caer en la primera. El buscador
 * consulta a la base, así que encuentra el lote esté donde esté.
 */
async function abrirLote(pagina: Page) {
  await pagina.getByPlaceholder("Buscar por código…").fill(LOTE.codigo);

  const fila = pagina.getByRole("row", { name: new RegExp(LOTE.codigo) });
  await expect(
    fila,
    `El lote ${LOTE.codigo} no aparece en la tabla de Producción.`,
  ).toBeVisible({ timeout: 20_000 });
  await fila.click();
}


test.describe.configure({ mode: "serial" });

test.afterAll(cerrarSegundaFirma);

test("de la leche cruda al pallet, por pantalla", async ({ page }) => {
  test.setTimeout(240_000);
  const erroresJs = vigilar(page);

  await test.step("0 · se reservan estanques vacíos", async () => {
    /* Hay que cargar la aplicación antes: `localStorage` es por origen, y en
       una página en blanco está vacío. */
    await irA(page, "/dashboard");
    await reservarEstanques(page);
  });

  await test.step(`1 · llega un camión de leche entera y se descarga en ${ESTANQUES.entera}`, async () => {
    await recibirCamion(page, ENTERA, "Entera", ESTANQUES.entera);
  });

  await test.step(`2 · llega un camión de leche descremada y se descarga en ${ESTANQUES.descremada}`, async () => {
    await recibirCamion(page, DESCREMADA, "Descremada", ESTANQUES.descremada);
  });

  /* Las **dos** fuentes se analizan: `motivos_silo_no_disponible` se evalúa
     sobre cada estanque que el vale consume, no solo sobre el de entera. Es
     correcto —la mezcla la determinan las dos leches— y es fácil de olvidar,
     porque el mensaje solo nombra el estanque que falta. */
  await test.step(`3 · Recepción analiza ${ESTANQUES.entera} y ${ESTANQUES.descremada}`, async () => {
    await analizarSilo(page, ESTANQUES.entera, ENTERA);
    await analizarSilo(page, ESTANQUES.descremada, DESCREMADA);
  });

  await test.step("4 · se compone el vale de estandarización", async () => {
    await irA(page, "/estandarizacion");
    await page.getByRole("button", { name: "Nuevo vale" }).click();

    await campo(page, "Código de vale").fill(VALE.codigo);
    await campo(page, "Fecha").fill(HOY);
    await elegirOpcion(campo(page, "Producto"), /Leche entera en polvo/);
    await campo(page, "RC objetivo").fill(VALE.rcObjetivo);
    /*
      Se espera la sugerencia FIFO, que el formulario pide al escribir el
      volumen. Solo cuando llega decide si muestra «Motivo para no usar el silo
      FIFO» —un campo **obligatorio en el backend**—.

      Sin esta espera, mirar si el campo estaba era una carrera que se perdía la
      mitad de las veces: aparecía después, se quedaba vacío, y cada
      autoguardado moría con `{"motivo_desvio_fifo": ["Indica por qué no usarás
      el silo sugerido por FIFO."]}`. Como nadie espera esos autoguardados, el
      fallo emergía dos pasos más tarde como un tiempo agotado sin causa
      visible.

      La espera se arma **antes** de escribir: registrarla después llegaría
      tarde a una respuesta ya recibida.
    */
    const sugerencia = page
      .waitForResponse(
        (r) => r.url().includes("silos/sugerencia") && r.status() === 200,
        { timeout: 15_000 },
      )
      .catch(() => undefined);

    await campo(page, "Volumen a preparar (L)").fill(VALE.volumen);
    await sugerencia;

    await elegirOpcion(campo(page, "Silo de destino"), new RegExp(`^${ESTANQUES.destino} `));

    /* «Silo» a secas es la etiqueta del bloque de leche entera y solo aparece
       una vez: los otros dos estanques se llaman «Estanque». No hace falta
       acotar el bloque, y acotarlo por su título fallaba porque el `div` que
       contiene el texto «Leche entera» no es el que contiene el desplegable. */
    await elegirOpcion(campo(page, "Silo"), new RegExp(`^${ESTANQUES.entera} `));

    /* Los porcentajes se teclean aunque el silo tenga análisis: hoy el vale no
       los hereda de `AnalisisSilo`, solo guarda su procedencia. Es el punto
       donde el circuito todavía pide escribir dos veces el mismo número.

       El `.first()` toma los del bloque de entera: los tres bloques —entera,
       descremada y crema— repiten estas dos etiquetas. */
    await page.getByLabel("Materia grasa %").first().fill(ENTERA.grasa);
    await page.getByLabel("Sólidos no grasos %").first().fill(ENTERA.sng);

    /* El bloque de descremada: «Estanque» aparece dos veces —descremada y
       crema—, y el primero es el de descremada. La crema se deja en «No usar»,
       que es lo que corresponde a un polvo entero. */
    await elegirOpcion(campo(page, "Estanque"), new RegExp(`^${ESTANQUES.descremada} `));
    await page.getByLabel("Materia grasa %").nth(1).fill(DESCREMADA.grasa);
    await page.getByLabel("Sólidos no grasos %").nth(1).fill(DESCREMADA.sng);

    /* FIFO sugiere el silo con la leche más antigua; esta prueba elige el que
       tiene sitio. Cuando no coinciden, el formulario pide un motivo y **es
       obligatorio**: sin él, el navegador bloquea el envío sin mensaje visible
       y el fallo aparece como un tiempo agotado esperando `calcular`. */
    const motivoFifo = campo(page, "Motivo para no usar el silo FIFO");
    if (await motivoFifo.count()) {
      await motivoFifo.fill(
        "Circuito de prueba: se toma el silo con capacidad disponible.",
      );
    }

    await trasGuardar(page, "vales/calcular", async () => {
      await page.getByRole("button", { name: "Calcular mezcla" }).click();
    });

    await expect(
      page.getByRole("button", { name: "Crear vale" }),
      "La mezcla no salió posible con estos valores: revisa el RC objetivo " +
        "contra la composición de las dos leches.",
    ).toBeVisible({ timeout: 15_000 });

    await trasGuardar(page, "confirmar-borrador", async () => {
      await page.getByRole("button", { name: "Crear vale" }).click();
    });
  });

  await test.step("5 · transferir, agitar, muestrear y decidir", async () => {
    await irA(page, "/estandarizacion");
    await page.getByRole("button", { name: new RegExp(VALE.codigo) }).first().click();

    await trasGuardar(page, "transferir", async () => {
      await page.getByRole("button", { name: "Transferido" }).click();
    });

    await trasGuardar(page, "agitar", async () => {
      await page.getByRole("button", { name: "Iniciar agitación" }).click();
    });

    /* Se muestrea sin esperar los treinta minutos: desde 2026-08-17 la regla
       avisa y no bloquea, y el vale queda con el aviso registrado. Esperar
       media hora aquí no comprobaría nada más. */
    await page.getByLabel("Materia grasa %").fill(MUESTRA.grasa);
    await page.getByLabel("Sólidos no grasos %").fill(MUESTRA.sng);
    await trasGuardar(page, "muestrear", async () => {
      await page.getByRole("button", { name: "Registrar muestra" }).click();
    });

    await trasGuardar(page, "decidir", async () => {
      await page.getByRole("button", { name: "Decidir" }).click();
    });
  });

  await test.step("6 · se abre el lote desde el vale liberado", async () => {
    await irA(page, "/produccion");
    await page.getByRole("button", { name: "Iniciar lote desde vale" }).click();

    await elegirOpcion(campo(page, "Vale estandarizado liberado *"), new RegExp(VALE.codigo));
    await campo(page, "Fecha *").fill(HOY);
    await campo(page, "Línea *").selectOption("E1");
    await elegirOpcion(campo(page, "Máquina / equipo *"), /Egron 1/);
    await campo(page, "Código de lote *").fill(LOTE.codigo);

    await trasGuardar(page, "confirmar-borrador", async () => {
      await page.getByRole("button", { name: "Abrir proceso" }).last().click();
    });
  });

  await test.step("7 · se declaran los kilos producidos", async () => {
    await irA(page, "/produccion");
    /* El lote es una fila con `onClick`, no un botón: se abre pulsando la fila.
       Ese `<tr>` clicable tampoco llega por teclado, que es harina de otro
       costal y del informe de accesibilidad. */
    await abrirLote(page);

    await page.getByRole("button", { name: /Marcar como producido/i }).click();
    await page.getByPlaceholder("Kilos").fill(LOTE.kg);

    await trasGuardar(page, "/api/produccion/lotes", async () => {
      await page.getByRole("button", { name: "Cerrar producción" }).click();
    });
  });

  await test.step("8 · se arma el pallet y entra a cuarentena de Bodega", async () => {
    const envase = page.locator("form").filter({ hasText: "Envasar en pallet" });
    await expect(
      envase,
      "El formulario de envase no apareció: el lote no quedó en «producido».",
    ).toBeVisible({ timeout: 15_000 });

    await elegirOpcion(envase.getByRole("combobox"), /Rovema 3/);
    await envase.getByPlaceholder("Código pallet").fill(PALLET.codigo);
    await envase.getByRole("spinbutton").fill(PALLET.sacos);

    await trasGuardar(page, "/api/produccion/envases", async () => {
      await envase.getByRole("button", { name: "Crear pallet" }).click();
    });

    await expect(page.getByText(new RegExp(`Pallet ${PALLET.codigo}`))).toBeVisible();
  });

  await test.step("9 · el lote cuenta su pallet y su consumo de material", async () => {
    await irA(page, "/produccion");
    await abrirLote(page);

    /* El paso 5 del semáforo del lote es Inventario: cuenta los pallets. Que
       diga «Falta envasar» después de envasar sería el pallet sin registrar. */
    await expect(page.getByText(/pallet\(s\)/)).toBeVisible({ timeout: 15_000 });
  });

  expect(erroresJs, `Errores de JavaScript durante el circuito:\n${erroresJs.join("\n")}`)
    .toHaveLength(0);

  /* Se comprueba al final y no sobre la marcha: hay rechazos legítimos —el 409
     del autoguardado que llega tarde es la protección funcionando—, así que
     solo se listan los que no lo son. */
  const inesperados = rechazos.filter((linea) => !linea.includes("-> 409"));
  expect(
    inesperados,
    `El servidor rechazó peticiones que nadie esperaba: ${inesperados.join(" ·· ")}`,
  ).toHaveLength(0);
});
