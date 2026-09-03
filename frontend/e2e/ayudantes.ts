/*
  Ayudantes compartidos por las pruebas que **operan** la aplicación.

  Viven aparte de cada `spec` porque los dos recorridos —el circuito completo de
  leche en polvo y el flujo de evaporación— cruzan las mismas pantallas y
  tropiezan con las mismas cosas: formularios sin `htmlFor`, desplegables que se
  llenan tarde, autoguardados que nadie espera y navegación por hash. Duplicar
  estas funciones garantizaba que la corrección de una se olvidara en la otra.

  No hay nada de dominio aquí: qué leche entra o qué RC se busca es de cada
  prueba. Esto es solo cómo se conduce el navegador contra ESTA aplicación.
*/

import { expect, request as peticion, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import fs from "node:fs";

import { API, ORIGEN, RUTA_ESTADO } from "./constantes";


/*
  Encuentra un control a partir del texto de su etiqueta.

  Hay **dos** convenciones conviviendo en el proyecto, y ninguna usa `htmlFor`:

  - Recepción, producción y el vale ponen etiqueta y control como hermanos
    dentro de un `div`. Ahí no hay asociación que `getByLabel` pueda encontrar.
  - El análisis de silo y el `<Campo>` de estandarización anidan el control
    **dentro** del `label`, que sí asocia — pero entonces el texto accesible
    incluye el del control, y el localizador por etiqueta exacta falla igual.

  Se prueban las dos formas: primero el control anidado, y si no hay, el
  primero que sigue a la etiqueta.

  Que haga falta este ayudante ES un hallazgo: un lector de pantalla tampoco
  asocia las etiquetas de la primera convención. El día que los formularios
  lleven `htmlFor`, esto se reduce a `getByLabel`.
*/
export function campo(scope: Page | Locator, etiqueta: string): Locator {
  /* Se compara contra `text()` —los nodos de texto propios del `label`— y no
     contra `.`, que incluye el de los descendientes. Con `.`, un desplegable
     anidado aporta el texto de todas sus opciones y la etiqueta «Producto»
     pasa a ser «ProductoSeleccionaLeche entera en polvo…», que no coincide
     con nada. */
  const raiz = ".//label[normalize-space(text())=" + JSON.stringify(etiqueta) + "]";
  const controles = "self::input or self::select or self::textarea";

  /* El prefijo `xpath=` va **una** vez, delante de la unión entera. Repetirlo
     en la segunda rama lo mete dentro de la expresión y el navegador responde
     «the result is not a node set», que no menciona la causa por ningún lado. */
  return scope
    .locator(
      `xpath=${raiz}//*[${controles}] | ` +
        `${raiz}/following-sibling::*[${controles}][1]`,
    )
    .first();
}

/*
  Elige la opción de un desplegable por lo que dice, no por su valor.

  `selectOption({ label })` solo acepta texto exacto, y aquí las etiquetas
  llevan datos que cambian en cada corrida —«SILO 1 · capacidad 100.000 L»,
  «VE-482913 · Leche entera en polvo · 20.000 L»—. Fijar el texto completo
  ataría la prueba a la ocupación del silo del día.

  Se resuelve leyendo el `value` de la primera opción que coincide, así que el
  desplegable recibe exactamente lo que la aplicación espera.
*/
export async function elegirOpcion(select: Locator, patron: RegExp) {
  const opciones = select.locator("option");

  /*
    Se **espera** a que la opción aparezca, no se mira una vez.

    Los desplegables se llenan con una petición aparte, así que en el instante
    en que se abre el formulario solo está el «Selecciona…». Una lectura única
    veía esa opción sola y daba por hecho que la buscada no existía — y el
    mensaje de error, construido un segundo después, la listaba entre las
    disponibles: acusaba de faltar algo que estaba ahí.
  */
  /* Se acumula lo último visto para poder decir qué **sí** ofrecía: sin eso el
     fallo solo dice que no encontró lo buscado, que es la mitad del dato. */
  let vistas: string[] = [];

  await expect
    .poll(
      async () => {
        vistas = (await opciones.allTextContents()).map((t) => t.trim());
        return vistas.some((t) => patron.test(t));
      },
      {
        timeout: 15_000,
        message:
          `Ningún elemento del desplegable coincide con ${patron} tras esperar. ` +
          "Comprueba que el paso anterior dejara el documento en el estado que " +
          "esta pantalla exige.",
      },
    )
    .toBe(true)
    .catch((error) => {
      throw new Error(
        `${error}\nEl desplegable ofrecía: ${vistas.length ? vistas.join(" | ") : "(vacío)"}`,
      );
    });

  /*
    Se salta las opciones **deshabilitadas**.

    La aplicación no esconde lo que no se puede elegir: lo muestra apagado y con
    el motivo pegado al texto —«Evaporador Scheffers 2 · Evaporador · ocupado
    por EJ-PROD-55»—, que es lo correcto para el operador, porque enterarse de
    que la máquina está ocupada es más útil que no verla. Para la prueba
    significa que la primera coincidencia puede no ser elegible: Playwright
    entonces se queda esperando con un «option being selected is not enabled»
    que no dice cuál era el impedimento, aunque estuviera escrito en la propia
    opción.
  */
  const candidatas: { texto: string; valor: string | null }[] = [];

  for (const opcion of await opciones.all()) {
    const texto = ((await opcion.textContent()) ?? "").trim();

    if (!patron.test(texto)) continue;

    candidatas.push({ texto, valor: await opcion.getAttribute("value") });

    if (await opcion.isEnabled()) {
      await select.selectOption(candidatas.at(-1)!.valor);
      return texto;
    }
  }

  if (candidatas.length) {
    throw new Error(
      `Todas las opciones que coinciden con ${patron} están deshabilitadas: ` +
        candidatas.map((c) => c.texto).join(" | "),
    );
  }

  const disponibles = (await opciones.allTextContents()).map((t) => t.trim());
  throw new Error(
    `Ningún elemento del desplegable coincide con ${patron}. Ofrece: ` +
      (disponibles.length ? disponibles.join(" | ") : "(vacío)"),
  );
}

/*
  Descarta el borrador que otra sesión dejó a medias, si lo hay.

  Recepción y análisis de silo **bloquean el formulario** mientras exista un
  borrador abierto de la misma persona: muestran «Análisis sin terminar» con
  Continuar/Descartar y dejan los campos deshabilitados. Es correcto —evita dos
  documentos del mismo hecho— pero significa que el circuito no puede empezar
  hasta resolverlo, igual que el operador.
*/
export async function descartarPendiente(pagina: Page, scope: Page | Locator = pagina) {
  const descartar = (scope as Page).getByRole
    ? (scope as Page).getByRole("button", { name: "Descartar" })
    : (scope as Locator).getByRole("button", { name: "Descartar" });

  if (await descartar.count()) {
    await descartar.first().click();
    await pagina.waitForTimeout(500);
  }
}

/*
  Peticiones que el servidor rechazó durante la corrida.

  Vive fuera de la prueba porque `trasGuardar` la consulta al quedarse sin
  respuesta: es ahí donde el motivo real resulta útil, no cinco pasos después.
*/
export const rechazos: string[] = [];

const sesionesArea: Array<{
  usuario: string;
  valor: string;
  contexto: APIRequestContext;
  cabeceras: Record<string, string>;
}> = [];

/** Cambia la sesión visible por una cuenta operacional real del área. */
export async function usarSesionArea(
  pagina: Page,
  usuario: string,
  clave = process.env.E2E_CLAVE_AREAS ?? "flujo-e2e-ccaa",
) {
  if (!pagina.url().startsWith(ORIGEN)) {
    await pagina.goto(ORIGEN);
  }
  const existente = sesionesArea.find((sesion) => sesion.usuario === usuario);
  if (existente) {
    await pagina.evaluate((contenido) => {
      window.localStorage.setItem("ccaa.sesion", contenido);
      window.sessionStorage.setItem("ccaa.sesion", contenido);
    }, existente.valor);
    await pagina.reload();
    return;
  }
  if (usuario === process.env.E2E_USUARIO && fs.existsSync(RUTA_ESTADO)) {
    const estado = JSON.parse(fs.readFileSync(RUTA_ESTADO, "utf8")) as {
      origins?: Array<{ localStorage?: Array<{ name: string; value: string }> }>;
    };
    const valor = estado.origins?.flatMap((origen) => origen.localStorage ?? [])
      .find((item) => item.name === "ccaa.sesion")?.value;
    if (valor) {
      await pagina.evaluate((contenido) => {
        window.localStorage.setItem("ccaa.sesion", contenido);
        window.sessionStorage.setItem("ccaa.sesion", contenido);
      }, valor);
      await pagina.reload();
      return JSON.parse(valor).usuario;
    }
  }
  const contexto = await peticion.newContext();
  const respuesta = await contexto.post(`${API}/api/usuarios/login/`, {
    data: { username: usuario, password: clave },
  });
  if (respuesta.status() !== 200) {
    throw new Error(
      `No se pudo iniciar la sesión operacional ${usuario}: ` +
      `${respuesta.status()} ${(await respuesta.text()).slice(0, 300)}`,
    );
  }
  const sesion = await respuesta.json();
  const valor = JSON.stringify({ token: sesion.token, usuario: sesion.usuario });
  await pagina.evaluate((contenido) => {
    window.localStorage.setItem("ccaa.sesion", contenido);
    window.sessionStorage.setItem("ccaa.sesion", contenido);
  }, valor);
  sesionesArea.push({
    usuario,
    valor,
    contexto,
    cabeceras: { Authorization: `Token ${sesion.token}` },
  });
  await pagina.reload();
  return sesion.usuario;
}

export async function cerrarSesionesArea() {
  await Promise.all(sesionesArea.splice(0).map(async ({ contexto, cabeceras }) => {
    await contexto.post(`${API}/api/usuarios/logout/`, { headers: cabeceras }).catch(() => undefined);
    await contexto.dispose();
  }));
}


/** Espera a que una petición del circuito termine antes de seguir. */
export async function trasGuardar(pagina: Page, fragmentoUrl: string, accion: () => Promise<void>) {
  const respuesta = pagina.waitForResponse(
    (r) => r.url().includes(fragmentoUrl) && r.request().method() !== "GET",
    { timeout: 20_000 },
  );
  await accion();

  /* Si la respuesta esperada no llega, lo que suele haber pasado es que el
     servidor rechazó **otra** petición —típicamente un autoguardado, que nadie
     espera— y el formulario nunca llegó a pedir esta. El tiempo agotado a
     secas no lo dice; los rechazos recogidos sí. */
  const r = await respuesta.catch((error) => {
    const pistas = rechazos.length
      ? `Antes de eso el servidor rechazó: ${rechazos.join(" ·· ")}`
      : "No hubo ninguna petición rechazada: la acción no llegó a pedir nada. " +
        "Suele ser un campo obligatorio vacío que el navegador bloquea sin avisar.";
    throw new Error(
      `No llegó ninguna respuesta de «${fragmentoUrl}». ${pistas}\n${error}`,
    );
  });
  expect(
    r.ok(),
    `${r.request().method()} ${new URL(r.url()).pathname} respondió ${r.status()}: ` +
      `${(await r.text()).slice(0, 400)}`,
  ).toBeTruthy();
  return r;
}

export async function irA(pagina: Page, ruta: string) {
  /* HashRouter: las rutas de la aplicación viven detrás de `#`. Navegar a
     `/leche` sin él carga el index y deja la aplicación en el panel. */
  const destino = `/#${ruta}`;
  const yaEstaba = pagina.url().endsWith(destino);

  await pagina.goto(destino);

  /* Ir al mismo hash **no recarga**: el navegador solo cambia el fragmento y
     React conserva su estado, así que una ficha abierta sobre la lista sigue
     ahí, en una capa fija, interceptando los clics. El síntoma es un clic que
     agota el tiempo sobre una fila que la traza describe como «visible,
     enabled y estable». */
  if (yaEstaba) await pagina.reload();

  /* `.first()`: hay pantallas con más de un `main` —una ficha abierta sobre la
     lista aporta el suyo— y sin acotar, la espera falla por ambigüedad en vez
     de por que la página no cargó. */
  await expect(pagina.getByRole("main").first()).toBeVisible();
}

/*
  La segunda firma del análisis de silo, con **otra** persona.

  `motivos_silo_no_disponible` exige `analista_id` y `visualizado_por_id`, y
  `visualizar/` responde 409 si es la misma cuenta: es el control de cuatro ojos
  del formato, no un capricho. Por eso el circuito necesita dos usuarios, y por
  eso esto va por API y no por pantalla — abrir un segundo navegador para pulsar
  un botón no comprueba nada que la pantalla no haya comprobado ya con el
  primero, y el backend permite una sola sesión activa por usuario.

  La cuenta la crea `manage.py crear_usuario_e2e --usuario e2e_segunda_firma`.
*/
export let segundaFirma: { contexto: APIRequestContext; cabeceras: Record<string, string> } | null = null;

/*
  Entra **una vez** por corrida y guarda la sesión.

  El circuito firma dos análisis —el de entera y el del TK—, y al principio
  cada firma abría su propia sesión. El servidor limita los intentos de login
  por cuenta, así que a las pocas corridas devolvía 429 y el mensaje culpaba a
  la cuenta de no existir. Con una sola sesión reutilizada son dos logins por
  corrida en total, uno por persona.
*/
export async function sesionSegundaFirma() {
  if (segundaFirma) return segundaFirma;

  const usuario = process.env.E2E_USUARIO_2 ?? "e2e_segunda_firma";
  const clave = process.env.E2E_CLAVE_2 ?? "segunda-firma-e2e-ccaa";

  const contexto = await peticion.newContext();
  const sesion = await contexto.post(`${API}/api/usuarios/login/`, {
    data: { username: usuario, password: clave },
  });

  expect(
    sesion.status(),
    sesion.status() === 429
      ? "El servidor cortó el acceso por exceso de intentos. El límite es por " +
        "cuenta (15/hora) **y por dirección** (60/hora), y correr el circuito " +
        "muchas veces seguidas agota antes el de la dirección — que no menciona " +
        "a nadie. Mira cuál es con «manage.py desbloquear_login --listar» y " +
        "levántalo con «--usuario» o «--ip»."
      : `La cuenta de segunda firma «${usuario}» no pudo entrar (HTTP ${sesion.status()}). ` +
        `Créala con «manage.py crear_usuario_e2e --usuario ${usuario}».`,
  ).toBe(200);

  const { token } = await sesion.json();
  segundaFirma = { contexto, cabeceras: { Authorization: `Token ${token}` } };
  return segundaFirma;
}

/** Cierra la sesión de la segunda firma. Se llama una vez, al terminar. */
export async function cerrarSegundaFirma() {
  if (!segundaFirma) return;

  /* El backend admite una sesión activa por usuario: dejarla abierta haría
     fallar la corrida siguiente con un 409 que parece un problema de
     credenciales y no lo es. */
  await segundaFirma.contexto
    .post(`${API}/api/usuarios/logout/`, { headers: segundaFirma.cabeceras })
    .catch(() => undefined);
  await segundaFirma.contexto.dispose();
  segundaFirma = null;
}

export async function firmarVisualizacion(analisisId: number) {
  const { contexto, cabeceras } = await sesionSegundaFirma();

  const firma = await contexto.post(
    `${API}/api/recepcion/analisis-silo/${analisisId}/visualizar/`,
    { headers: cabeceras, data: {} },
  );
  expect(
    firma.ok(),
    `La segunda firma respondió ${firma.status()}: ${(await firma.text()).slice(0, 300)}`,
  ).toBeTruthy();
}


/*
  Deja el navegador vigilado: errores de JavaScript, escrituras rechazadas y
  los `window.confirm` de la aplicación.

  Va junto porque las tres cosas son el mismo problema —fallos que no se ven
  donde ocurren— y porque olvidar cualquiera de ellas produce un síntoma que no
  menciona su causa. Devuelve la lista de errores de JavaScript para que la
  prueba la revise al final.
*/
export function vigilar(pagina: Page): string[] {

  /* Un error de JavaScript deja la pantalla a medias y el paso siguiente falla
     con «no encuentro el botón», que no dice nada. Recogerlos aquí permite
     nombrar la causa. */
  const erroresJs: string[] = [];
  pagina.on("pageerror", (e) => erroresJs.push(String(e)));

  /*
    Toda escritura que el servidor rechaza queda anotada, la esperemos o no.

    Los autoguardados no se esperan en ningún paso, así que un `crear-borrador`
    que responde 400 no rompe nada de inmediato: el formulario reintenta cada
    dos segundos, nunca consigue id, y el fallo aparece cinco líneas después
    como «tiempo agotado esperando confirmar-borrador», sin decir por qué. Con
    esto, el motivo real sale en el informe.
  */
  rechazos.length = 0;
  pagina.on("response", async (r) => {
    if (r.request().method() === "GET" || r.status() < 400) return;
    const cuerpo = await r.text().catch(() => "");
    rechazos.push(
      `${r.request().method()} ${new URL(r.url()).pathname} -> ${r.status()} ${cuerpo.slice(0, 200)}`,
    );
  });

  /*
    Los `window.confirm` de la aplicación, contestados uno por uno.

    Playwright los **descarta** por omisión, así que sin manejador el operador
    simulado siempre dice que no: la descarga nunca se pide y el fallo aparece
    como un tiempo agotado esperando una respuesta que nadie solicitó.

    Contestar «sí» a todo tampoco vale, y es un error que costó encontrar. La
    pantalla del vale pregunta al abrirse si se continúa un borrador anterior;
    aceptando, el formulario se rellenaba con los silos de una corrida vieja
    —silos que para esta ya no son válidos—, y el desplegable de destino dejaba
    de ofrecer el que se buscaba porque el formulario ya lo tenía puesto como
    origen. El síntoma no mencionaba borradores por ningún lado.
  */
  pagina.on("dialog", (dialogo) => {
    const continuarBorrador = /sin confirmar|continuarlo/i.test(dialogo.message());
    void (continuarBorrador ? dialogo.dismiss() : dialogo.accept());
  });

  return erroresJs;
}


/**
 * Los rechazos que no son la protección haciendo su trabajo.
 *
 * El 409 del autoguardado que llega tarde es esperable y correcto: significa
 * que el candado de fila impidió pisar una confirmación. Cualquier otro código
 * de error es un problema.
 */
export function rechazosInesperados(): string[] {
  return rechazos.filter((linea) => !linea.includes("-> 409"));
}


/** Registra el análisis del silo — CCAA.REC.FORM.005, el vale de trazabilidad. */
export async function analizarSilo(
  pagina: Page, estanque: string, leche: { grasa: string; sng: string },
) {
  await irA(pagina, "/leche/silos");

  /*
    Los silos **vacíos están plegados** tras un «Ver los N silos vacíos», y un
    silo recién consumido del todo cae ahí. Es razonable para el turno —que
    mira los que tienen leche— pero significa que el estanque buscado puede no
    estar en pantalla aunque exista, y el fallo se ve como un botón que nunca
    aparece.
  */
  /* Primero se espera a que la pantalla tenga silos. Preguntar antes devuelve
     cero porque todavía no cargó, no porque el estanque falte, y entonces el
     desplegado de vacíos se dispara sobre una página en blanco. */
  await expect(
    pagina.getByRole("button", { name: /SILO |TK / }).first(),
    "La pantalla de silos no cargó ningún estanque.",
  ).toBeVisible({ timeout: 15_000 });

  /* La API conserva algunos códigos maestros históricos con espacios dobles
     (por ejemplo, `Silo  3`), mientras el nombre accesible del navegador
     colapsa esos espacios. El operador ve el mismo código; el localizador no
     debe depender de esa diferencia de representación. */
  const nombreVisible = estanque.trim().split(/\s+/).join("\\s+");
  const boton = pagina
    .getByRole("button", { name: new RegExp(nombreVisible, "i") })
    .first();

  if (!(await boton.isVisible())) {
    const desplegar = pagina.getByRole("button", { name: /Ver los \d+ silos vacíos/ });
    if (await desplegar.count()) await desplegar.first().click();
  }

  await expect(
    boton,
    `El estanque ${estanque} no aparece en la pantalla de silos, ni entre los vacíos.`,
  ).toBeVisible({ timeout: 15_000 });

  await boton.click();
  await pagina.getByRole("button", { name: "Tomar muestra" }).click();

  const analisis = pagina.locator("#analisis-silo");
  await expect(analisis).toBeVisible();

  await descartarPendiente(pagina, analisis);

  await campo(analisis, "pH").fill("6.72");
  await campo(analisis, "Acidez (°Th)").fill("15.4");
  await campo(analisis, "Grasa (%)").fill(leche.grasa);
  await campo(analisis, "SNG (%)").fill(leche.sng);
  await campo(analisis, "Proteína (%)").fill("3.44");
  await campo(analisis, "Temperatura (°C)").fill("4.2");
  await campo(analisis, "Densidad (kg/m³)").fill("1032");
  await campo(analisis, "Inhibidores").selectOption("negativo");

  /* Revalidación de leche sobre 48 h. Se registra siempre porque el circuito
     reutiliza silos de planta y suele caer en uno que ya guardaba leche de
     ayer: entonces `motivos_silo_no_disponible` exige alcohol 75°, hervor y
     organoléptico conformes, y sin ellos el vale no se puede transferir. */
  for (const control of ["Alcohol 75° conforme", "Hervor conforme", "Organoléptico conforme"]) {
    await analisis.getByRole("checkbox", { name: control }).check();
  }

  const respuesta = await trasGuardar(pagina, "confirmar-borrador", async () => {
    await analisis.getByRole("button", { name: "Confirmar análisis" }).click();
  });

  const { id } = await respuesta.json();
  await firmarVisualizacion(id);
}


/*
  Los controles que la validación del navegador está bloqueando.

  Un `<form>` con un campo `required` vacío **no envía y no avisa**: el submit
  simplemente no ocurre. Desde fuera se ve como un botón que no hace nada, y la
  prueba lo reporta como «no llegó ninguna respuesta», que describe el síntoma y
  no la causa.

  Se devuelve el texto de la etiqueta asociada —o el `name`, o el `id`— para que
  el mensaje nombre el campo como lo ve el operador.
*/
export async function camposInvalidos(scope: Locator): Promise<string[]> {
  return scope.evaluate((raiz) => {
    const controles = raiz.querySelectorAll<HTMLInputElement>(
      "input, select, textarea",
    );

    return [...controles]
      .filter((c) => !c.checkValidity())
      .map((c) => {
        const etiqueta =
          c.closest("label")?.childNodes[0]?.textContent?.trim()
          || c.previousElementSibling?.textContent?.trim()
          || c.getAttribute("aria-label")
          || c.name
          || c.id
          || c.tagName.toLowerCase();
        return `${etiqueta} (${c.validationMessage || "inválido"})`;
      });
  });
}
