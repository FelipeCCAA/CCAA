import { expect, test, type Page } from "@playwright/test";

import {
  analizarSilo,
  campo,
  cerrarSegundaFirma,
  cerrarSesionesArea,
  elegirOpcion,
  firmarVisualizacion,
  irA,
  trasGuardar,
  usarSesionArea,
  vigilar,
} from "./ayudantes";
import { API } from "./constantes";

test.describe.configure({ mode: "serial" });
test.afterAll(async () => {
  await cerrarSegundaFirma();
  await cerrarSesionesArea();
});

/*
  El código de una corrida como texto exacto: `EJ-DES-2` no debe acertarle a
  `EJ-DES-23` de una corrida anterior en la misma base. El código lo asigna
  el servidor (`EJ-DES-{id}`): no trae caracteres especiales de RegExp.
*/
function exacto(codigo: string): RegExp {
  return new RegExp(`${codigo}(?!\\d)`);
}

interface Preparado {
  codigo: string;
  litrosDescremada: string;
  litrosCrema: string;
}

interface Estanques {
  siloOrigen: string;
  tkDescremada: string;
  tkCrema: string;
}

/* Los TK que ya tomó una prueba de este archivo: la siguiente no los repite,
   porque guardan la rama de la anterior. La tercera prueba mira los de la
   primera. */
const tanquesUsados = new Set<string>();
let ramasPrimeraPrueba: Estanques | null = null;

/*
  Elige silo de origen y TK entre lo que **sirve el puesto**
  (`descremaciones/puesto/`), como `circuito-polvo` elige silos con sitio: un
  nombre de estanque escrito en la prueba deja de existir en cuanto la base
  usa otros códigos. Origen: sin motivo y con saldo para los litros pedidos.
  Destinos: los que el puesto ofrece —ya sin reserva ni bloqueo de Calidad—
  con sitio para todo lo que entra, el más vacío primero para no mezclar con
  lo que ya guardan. Las variables de entorno, si vienen, mandan.
*/
async function elegirEstanques(page: Page, litros: number, entorno: {
  silo?: string; tkDescremada?: string; tkCrema?: string;
}): Promise<Estanques> {
  await usarSesionArea(page, "e2e_produccion");
  /* `page.request` no pasa por axios: la cabecera va a mano, con el token de
     la sesión que acaba de quedar en `localStorage`. */
  const token = await page.evaluate(
    () => JSON.parse(localStorage.getItem("ccaa.sesion") ?? "{}").token,
  );
  const respuesta = await page.request.get(`${API}/api/procesos/descremaciones/puesto/`, {
    headers: { Authorization: `Token ${token}` },
  });
  expect(respuesta.ok(), `No se pudo leer el puesto de Descremado (HTTP ${respuesta.status()}).`).toBeTruthy();
  const puesto = await respuesta.json() as {
    origenes: { codigo: string; libre_l: string; motivo: string | null }[];
    destinos_descremada: { codigo: string; libre_l: string }[];
    destinos_crema: { codigo: string; libre_l: string }[];
  };

  const origen = entorno.silo ?? puesto.origenes
    .filter((o) => !o.motivo && Number(o.libre_l) >= litros)
    .sort((a, b) => Number(b.libre_l) - Number(a.libre_l))[0]?.codigo;
  const conSitio = (destinos: { codigo: string; libre_l: string }[]) => destinos
    .filter((d) => !tanquesUsados.has(d.codigo) && Number(d.libre_l) >= litros)
    .sort((a, b) => Number(b.libre_l) - Number(a.libre_l))[0]?.codigo;
  const tkDescremada = entorno.tkDescremada ?? conSitio(puesto.destinos_descremada);
  const tkCrema = entorno.tkCrema ?? conSitio(puesto.destinos_crema);

  expect(
    origen,
    `El puesto no ofrece ningún silo con ${litros} L para descremar. Ofrece: ` +
      `${puesto.origenes.map((o) => `${o.codigo} ${o.libre_l} L libres${o.motivo ? ` (${o.motivo})` : ""}`).join(" · ") || "ninguno"}.`,
  ).toBeTruthy();
  expect(
    tkDescremada && tkCrema,
    `El puesto no ofrece un TK de descremada y uno de crema con ${litros} L libres. ` +
      "Libéralos en Calidad o cancela la preparación que los retiene desde el puesto.",
  ).toBeTruthy();
  for (const tk of [tkDescremada!, tkCrema!]) tanquesUsados.add(tk);
  return { siloOrigen: origen!, tkDescremada: tkDescremada!, tkCrema: tkCrema! };
}

/*
  Calidad analiza el origen **sin** la segunda firma y entrega el enlace
  «Descremar» del silo: preparar no exige firmas, iniciar sí. Devuelve la ruta
  del enlace y el id del análisis, para firmarlo después.
*/
async function analizarOrigenSinFirma(page: Page, siloOrigen: string) {
  await usarSesionArea(page, "e2e_calidad");
  const analisisId = await analizarSilo(page, siloOrigen, { grasa: "2.61", sng: "8.70" }, { segundaFirma: false });
  const href = await page.getByRole("link", { name: "Descremar" }).getAttribute("href");
  const rutaDescremar = new URL(href!, page.url()).hash.replace(/^#/, "");
  expect(rutaDescremar).toMatch(/^\/produccion\/descremado\?silo=\d+$/);
  return { analisisId, rutaDescremar };
}

/*
  Producción llega al puesto por «Descremar» con el silo elegido y prepara.
  La tarjeta se busca por el código que asignó el servidor, no por uno
  tecleado.
*/
async function preparar(page: Page, rutaDescremar: string, opciones: {
  litros: string; tkDescremada: string; tkCrema: string; cremaADespacho?: boolean;
}): Promise<Preparado> {
  await usarSesionArea(page, "e2e_produccion");
  await irA(page, rutaDescremar);
  const dialogo = page.getByRole("dialog", { name: "Preparar descremado" });
  await expect(dialogo).toBeVisible({ timeout: 20_000 });
  await elegirOpcion(campo(dialogo, "Descremadora"), /DES-01/i);
  await campo(dialogo, "Litros de entrada").fill(opciones.litros);
  await elegirOpcion(campo(dialogo, "TK de leche descremada"), new RegExp(opciones.tkDescremada, "i"));
  await elegirOpcion(campo(dialogo, "TK de crema"), new RegExp(opciones.tkCrema, "i"));
  if (opciones.cremaADespacho) {
    await campo(dialogo, "Destino de la crema").selectOption("despacho_directo");
    await elegirOpcion(campo(dialogo, "Ruta de la crema"), /despacho directo/i);
  }
  await trasGuardar(page, "/sugerir-balance/", async () => {
    await dialogo.getByRole("button", { name: "Calcular sugerencia" }).click();
  });
  const litrosDescremada = await campo(dialogo, "Descremada planificada (L)").inputValue();
  const litrosCrema = await campo(dialogo, "Crema planificada (L)").inputValue();
  expect(Number(litrosDescremada)).toBeGreaterThan(Number(opciones.litros) * 0.9);
  expect(Number(litrosCrema)).toBeGreaterThan(0);
  await dialogo.getByRole("checkbox", { name: /Confirmo que revisé/ }).check();
  await dialogo.getByRole("button", { name: "Revisar y confirmar" }).click();
  const respuesta = await trasGuardar(page, "/crear-guiada/", async () => {
    await dialogo.getByRole("button", { name: "Preparar descremado" }).click();
  });
  const { ejecucion_codigo: codigo } = await respuesta.json();
  return { codigo: String(codigo), litrosDescremada, litrosCrema };
}

/*
  «Iniciar descremado» está deshabilitado con el motivo de la segunda firma
  hasta que Calidad completa el análisis del origen; entonces el servidor lo
  habilita. La segunda firma es de otra persona (`e2e_calidad_firma`). El
  enlace a /silos no se comprueba: Condensación no entra a Recepción
  (Desviación 7 del plan); lo fija la prueba unitaria.
*/
async function iniciarTrasLaFirma(page: Page, codigo: string, analisisId: number) {
  const tarjeta = page.getByRole("article").filter({ hasText: exacto(codigo) });
  await expect(tarjeta).toContainText("Preparada", { timeout: 20_000 });
  const iniciar = tarjeta.getByRole("button", { name: "Iniciar descremado" });
  await expect(iniciar).toBeDisabled();
  await expect(tarjeta).toContainText("firma de realización y visualización");

  await firmarVisualizacion(analisisId);
  await page.getByRole("button", { name: "Actualizar" }).click();
  await expect(iniciar).toBeEnabled({ timeout: 20_000 });
  await trasGuardar(page, "/iniciar/", async () => iniciar.click());
  await expect(tarjeta).toContainText("En curso", { timeout: 20_000 });
}

/*
  Registra las dos salidas viendo el aviso de grasa que calcula el servidor
  mientras se teclea (`revisar-cierre/`): primero un valor fuera del límite,
  luego el corregido.
*/
async function registrarSalidas(page: Page, codigo: string, datos: Preparado & {
  tkDescremada: string; tkCrema: string;
  aviso: { campo: string; fuera: string; dentro: string; texto: RegExp };
}) {
  const tarjeta = page.getByRole("article").filter({ hasText: exacto(codigo) });
  await tarjeta.getByRole("button", { name: "Registrar salidas y cerrar" }).click();
  const dialogo = page.getByRole("dialog", { name: "Registrar salidas" });
  await campo(dialogo, `Litros a ${datos.tkDescremada}`).fill(datos.litrosDescremada);
  await campo(dialogo, "Grasa leche descremada (%)").fill("0.06");
  await campo(dialogo, `Litros a ${datos.tkCrema}`).fill(datos.litrosCrema);
  await campo(dialogo, "Grasa crema (%)").fill("42.00");

  const avisos = dialogo.getByRole("region", { name: "Avisos del cierre" });
  await campo(dialogo, datos.aviso.campo).fill(datos.aviso.fuera);
  await expect(avisos).toContainText(datos.aviso.texto, { timeout: 10_000 });
  await campo(dialogo, datos.aviso.campo).fill(datos.aviso.dentro);
  await expect(avisos).not.toContainText(datos.aviso.texto, { timeout: 10_000 });

  await dialogo.getByRole("button", { name: "Revisar cierre" }).click();
  await trasGuardar(page, "/cerrar/", async () => {
    await dialogo.getByRole("button", { name: "Confirmar salidas y cerrar" }).click();
  });
  const hoy = page.getByRole("region", { name: "Corridas de hoy" });
  await expect(hoy.getByRole("listitem").filter({ hasText: exacto(codigo) })).toContainText(/Esperando Calidad|Terminada/);
}

async function liberarRamas(page: Page, codigo: string, tkDescremada: string, tkCrema: string) {
  await usarSesionArea(page, "e2e_calidad");
  await analizarSilo(page, tkDescremada, { grasa: "0.06", sng: "8.80" });
  await analizarSilo(page, tkCrema, { grasa: "42.00", sng: "8.80" });
  await irA(page, "/calidad");
  for (const tk of [tkDescremada, tkCrema]) {
    const tarjeta = page.locator("article").filter({ hasText: exacto(codigo) }).filter({ hasText: tk });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await elegirOpcion(tarjeta.getByRole("combobox"), /conforme/i);
    await trasGuardar(page, "/liberar/", async () => {
      await tarjeta.getByRole("button", { name: "Liberar etapa" }).click();
    });
  }
}

test("descremado separa, Calidad libera y conserva ambas rutas", async ({ page }) => {
  test.setTimeout(180_000);
  const erroresJs = vigilar(page);
  const { siloOrigen, tkDescremada, tkCrema } = await elegirEstanques(page, 1000, {
    silo: process.env.E2E_SILO_ENTERA,
    tkDescremada: process.env.E2E_TK_DESCREMADA,
    tkCrema: process.env.E2E_TK_CREMA,
  });
  ramasPrimeraPrueba = { siloOrigen, tkDescremada, tkCrema };
  let origen = { analisisId: 0, rutaDescremar: "" };
  let preparado: Preparado = { codigo: "", litrosDescremada: "", litrosCrema: "" };

  await test.step("1 · Calidad analiza el origen sin la segunda firma", async () => {
    origen = await analizarOrigenSinFirma(page, siloOrigen);
  });

  await test.step("2 · Producción prepara desde «Descremar» del silo", async () => {
    preparado = await preparar(page, origen.rutaDescremar, { litros: "1000", tkDescremada, tkCrema });
  });

  await test.step("3 · Iniciar espera la segunda firma; con ella, inicia", async () => {
    await iniciarTrasLaFirma(page, preparado.codigo, origen.analisisId);
  });

  await test.step("4 · Producción registra las salidas viendo el aviso de la descremada", async () => {
    await registrarSalidas(page, preparado.codigo, {
      ...preparado, tkDescremada, tkCrema,
      aviso: { campo: "Grasa leche descremada (%)", fuera: "0.15", dentro: "0.06", texto: /sobre el límite/ },
    });
  });

  await test.step("5 · Calidad analiza y libera cada rama por separado", async () => {
    await liberarRamas(page, preparado.codigo, tkDescremada, tkCrema);
  });

  await test.step("6 · Las ramas muestran su siguiente acción contractual", async () => {
    await irA(page, "/leche/silos");
    await page.getByRole("button", { name: new RegExp(tkDescremada, "i") }).first().click();
    await expect(page.getByRole("link", { name: /Enviar a Estandarizaci[oó]n/ }).first()).toBeVisible();
    await page.getByRole("button", { name: new RegExp(tkCrema, "i") }).first().click();
    await expect(page.getByRole("link", { name: "Preparar en Mantequilla" }).first()).toBeVisible();
  });

  expect(erroresJs).toHaveLength(0);
});

test("crema liberada sigue su ruta comercial hasta despacho directo", async ({ page }) => {
  test.setTimeout(180_000);
  const erroresJs = vigilar(page);
  const { siloOrigen, tkDescremada, tkCrema } = await elegirEstanques(page, 500, {
    silo: process.env.E2E_SILO_ENTERA,
    tkDescremada: process.env.E2E_TK_DESCREMADA_DIRECTA,
    tkCrema: process.env.E2E_TK_CREMA_DIRECTA,
  });
  let origen = { analisisId: 0, rutaDescremar: "" };
  let preparado: Preparado = { codigo: "", litrosDescremada: "", litrosCrema: "" };

  await test.step("1 · Calidad analiza el origen sin la segunda firma", async () => {
    origen = await analizarOrigenSinFirma(page, siloOrigen);
  });

  await test.step("2 · Producción prepara con la crema a despacho directo", async () => {
    preparado = await preparar(page, origen.rutaDescremar, {
      litros: "500", tkDescremada, tkCrema, cremaADespacho: true,
    });
  });

  await test.step("3 · Iniciar espera la segunda firma; con ella, inicia", async () => {
    await iniciarTrasLaFirma(page, preparado.codigo, origen.analisisId);
  });

  await test.step("4 · Producción registra las salidas viendo el aviso de la crema para despacho", async () => {
    await registrarSalidas(page, preparado.codigo, {
      ...preparado, tkDescremada, tkCrema,
      aviso: { campo: "Grasa crema (%)", fuera: "41", dentro: "42.00", texto: /fuera del rango/ },
    });
  });

  await test.step("5 · Calidad libera por separado descremada y crema", async () => {
    await liberarRamas(page, preparado.codigo, tkDescremada, tkCrema);
  });

  await test.step("6 · Producción expone la crema como despacho, no como mantequilla", async () => {
    await usarSesionArea(page, "e2e_produccion");
    await irA(page, "/produccion");
    await page.getByRole("button", { name: "Consultar disponibles" }).click();
    const tarjeta = page.locator("article").filter({ hasText: exacto(preparado.codigo) }).filter({ hasText: tkCrema });
    await expect(tarjeta.getByRole("link", { name: "Preparar despacho" })).toBeVisible({ timeout: 20_000 });
    await expect(tarjeta.getByRole("link", { name: "Preparar en Mantequilla" })).toHaveCount(0);
  });

  await test.step("7 · Despacho arma, autoriza y ejecuta la hoja de carga de la crema", async () => {
    await usarSesionArea(page, "e2e_despacho");
    await irA(page, "/despacho");
    await page.getByRole("button", { name: "Nueva hoja de carga" }).click();
    await page.getByRole("region", { name: "Nueva hoja de carga" }).getByLabel("Cliente").selectOption({ index: 1 });
    const graneles = page.getByRole("group", { name: "Graneles liberados" });
    await graneles.getByRole("listitem").filter({ hasText: exacto(preparado.codigo) }).getByRole("checkbox").check();
    await page.getByRole("button", { name: "Revisar hoja" }).click();
    await trasGuardar(page, "/api/inventario/despachos/", async () => {
      await page.getByRole("button", { name: "Guardar hoja" }).click();
    });
    const tarjeta = page.locator("article").filter({ hasText: exacto(preparado.codigo) });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await trasGuardar(page, "/autorizar/", async () => {
      await tarjeta.getByRole("button", { name: "Autorizar" }).click();
    });
    await tarjeta.getByRole("button", { name: "Ejecutar salida" }).click();
    await trasGuardar(page, "/ejecutar/", async () => {
      await tarjeta.getByRole("button", { name: "Confirmar salida" }).click();
    });
    await expect(page.getByRole("region", { name: "Despachadas hoy" })).toContainText(exacto(preparado.codigo));
  });

  expect(erroresJs).toHaveLength(0);
});

test("ramas liberadas muestran Estandarización y Mantequilla", async ({ page }) => {
  /* Los TK de la primera prueba; corrida sola, los que digan las variables. */
  const tkDescremada = ramasPrimeraPrueba?.tkDescremada ?? process.env.E2E_TK_DESCREMADA;
  const tkCrema = ramasPrimeraPrueba?.tkCrema ?? process.env.E2E_TK_CREMA;
  test.skip(!tkDescremada || !tkCrema, "Sin la primera prueba ni E2E_TK_DESCREMADA/E2E_TK_CREMA no hay ramas que mirar.");
  await usarSesionArea(page, "e2e_calidad");
  await irA(page, "/leche/silos");
  await page.getByRole("button", { name: new RegExp(tkDescremada, "i") }).first().click();
  await expect(page.getByRole("link", { name: /Enviar a Estandarizaci[oó]n/ }).first()).toBeVisible();
  await page.getByRole("button", { name: new RegExp(tkCrema, "i") }).first().click();
  await expect(page.getByRole("link", { name: "Preparar en Mantequilla" }).first()).toBeVisible();
});
