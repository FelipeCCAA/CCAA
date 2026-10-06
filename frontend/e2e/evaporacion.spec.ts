/*
  El flujo de evaporación, por pantalla.

  Todo ocurre en el **puesto de Evaporación** (`/produccion/evaporacion`): una
  tarjeta por evaporador, con un estado y una acción. Se abre el lote desde el
  vale sobre un evaporador libre —lo que también prepara la corrida, con su
  silo de destino—, Calidad analiza el silo de origen, se inicia y se cierra
  declarando el precondensado obtenido. Antes eran cinco pasos repartidos en
  tres pantallas (`/produccion`, `/procesos` y silos).

  Dónde empieza y por qué ahí
  ---------------------------
  Empieza en un **vale ya liberado**, no en la recepción del camión. Componer y
  liberar el vale es el flujo de estandarización, y lo recorre entero
  `circuito-polvo.spec.ts`; repetirlo aquí sumaría minutos de corrida para
  volver a comprobar lo mismo. Lo que esta prueba cubre es lo que empieza
  cuando el silo estandarizado ya tiene leche: qué puede hacer Producción con
  ella.

  Abrir el lote **es** preparar la evaporación
  --------------------------------------------
  No son dos cosas. En el puesto el formulario de lote solo ofrece
  evaporadores, y `_encadenar_con_la_estandarizacion` deduce la etapa del
  **tipo de máquina**: evaporador → evaporación. Por eso el mismo «Abrir lote»
  deja la corrida preparada —con el silo de destino del concentrado ya
  elegido— y la tarjeta pasa de «Disponible» a «Preparada». Es todo o nada:
  si la corrida no se puede preparar, tampoco queda lote.

  Prerrequisitos
  --------------
  `python manage.py preparar_circuito_polvo --aplicar` deja la **orden de
  producción** programada, que el formulario exige y que ninguna pantalla crea.
  Hace falta además un vale liberado con saldo; si no hay, la prueba lo dice y
  remite al circuito completo, que produce uno. Y un evaporador libre: si los
  tres están ocupados, la prueba lo dice en vez de esperar un botón que no va
  a aparecer.
*/

import { test, expect, type Locator, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

import {
  analizarSilo, campo, camposInvalidos, cerrarSegundaFirma, elegirOpcion, irA,
  rechazosInesperados, trasGuardar, vigilar,
} from "./ayudantes";
import { RUTA_FLUJO_POLVO } from "./constantes";

const SELLO = Date.now().toString().slice(-6);
const PRODUCTO_OBJETIVO = process.env.E2E_PRODUCTO ?? "";
/* El prefijo lo consume `flujo-polvo-continuacion.spec.ts`, que deriva el
   código del pallet quitándole «CCAA-EVA-»: cambiarlo aquí cambia el pallet
   allá. */
const PREFIJO_LOTE = process.env.E2E_LOTE_PREFIJO ?? "CCAA-EVA";
const RUTA_REGISTRO = process.env.E2E_REGISTRO
  ? path.resolve(process.env.E2E_REGISTRO)
  : RUTA_FLUJO_POLVO;

const HOY = new Date().toISOString().slice(0, 10);

const LOTE = { codigo: `${PREFIJO_LOTE}-${SELLO}` };

/*
  Cuánta leche entra a la corrida, y cuánto precondensado sale.

  Los litros de entrada **no se fijan aquí**: el formulario limita el campo al
  saldo que le queda al vale, y ese saldo depende de cuánto se haya consumido
  ya. Fijar 6.000 hacía que el navegador bloqueara el envío en silencio en
  cuanto el vale elegido tenía menos —«Value must be less than or equal to
  2000»— y el fallo llegaba veinte segundos después sin nombrar el campo.

  La salida es el 25 % de la entrada: un evaporador saca agua, y un 1:1 dejaría
  la prueba pasando sobre un balance que en planta sería un equipo que no
  evaporó.
*/
const PROPORCION_SALIDA = 0.25;

/* Lo que una corrida de evaporación toma del vale. Un evaporador no procesa
   veinte mil litros de una vez, y dejar que la prueba se lleve el vale entero
   obliga a fabricar leche estandarizada nueva en cada vuelta. */
const LITROS_POR_CORRIDA = 6000;

const corrida = { entrada: 0, salida: 0 };

/*
  Rendimiento de una evaporación real: de 6.000 L de leche estandarizada salen
  del orden de 1.500 L de precondensado, porque el equipo saca agua. El número
  concreto da igual para la regla —el backend solo exige que la salida no
  supere la entrada— pero un 1:1 dejaría la prueba pasando sobre un balance
  que en planta sería un evaporador que no evaporó.
*/
const CONTROLES_SALIDA = { solidos: "45.20", temperatura: "62.5" };

/* La composición del silo estandarizado. El vale la fijó en su mezcla; aquí
   solo hace falta que el análisis exista y esté firmado, porque lo que se
   comprueba es la puerta, no el número. */
const LECHE_ESTANDARIZADA = { grasa: "2.61", sng: "8.70" };

/* El silo del que sale la leche y el que recibe el concentrado. Los dice la
   tarjeta una vez preparada la corrida, así que se descubren en el paso 1 y se
   usan en los siguientes. */
let origen = "";
let destino = "";

/* El evaporador sobre el que se abrió el lote. La tarjeta se vuelve a buscar
   por su nombre en cada paso: «la primera disponible» deja de ser esta en
   cuanto la ocupamos. */
let maquina = "";

/* Un código de silo como patrón. La API conserva códigos históricos con
   espacios dobles («Silo  3») y el texto visible los colapsa: se compara por
   `\s+` para que la diferencia de representación no cuente. */
const patronSilo = (codigo: string) =>
  codigo.trim().split(/\s+/).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+");

/* Las tarjetas viven en la sección «Evaporadores». Se acota a ella y no se
   filtra por un nombre que contenga «Evaporador»: el puesto ya solo lista
   evaporadores, y el nombre lo edita Maestros. */
const tarjetas = (page: Page) =>
  page.getByRole("region", { name: "Evaporadores" }).getByRole("article");

const tarjetaDe = (page: Page): Locator =>
  tarjetas(page).filter({ has: page.getByRole("heading", { name: maquina, exact: true }) });

test.describe.configure({ mode: "serial" });

test.afterAll(cerrarSegundaFirma);

test("de la leche estandarizada al precondensado, en el puesto de Evaporación", async ({ page }) => {
  test.setTimeout(180_000);

  const erroresJs = vigilar(page);

  await test.step("1 · se abre el lote y se prepara la corrida en un evaporador libre", async () => {
    await irA(page, "/produccion/evaporacion");

    /* Las tarjetas llegan en una petición aparte: sin esta espera, «no hay
       ninguna disponible» sería cierto solo porque aún no cargó ninguna. */
    await expect(
      tarjetas(page).first(),
      "El puesto de Evaporación no mostró ningún evaporador.",
    ).toBeVisible({ timeout: 15_000 });

    const libre = tarjetas(page)
      .filter({ has: page.getByText("Disponible", { exact: true }) })
      .filter({ has: page.getByRole("button", { name: "Abrir lote desde vale" }) })
      .first();

    /*
      Si no hay ninguno libre, el motivo suele ser una corrida abandonada:
      anular un lote no cierra su ejecución y el evaporador queda ocupado
      indefinidamente (CLAUDE.md, «La pantalla ofrece lo que el backend va a
      rechazar», caso 3). La prueba no libera máquinas ajenas: lo dice.
    */
    await expect(
      libre,
      "Ningún evaporador está «Disponible». Revisa las corridas preparadas o en " +
        "curso que quedaron abiertas; la prueba no toca corridas ajenas.",
    ).toBeVisible({ timeout: 10_000 });

    maquina = (await libre.getAttribute("aria-label")) ?? "";
    expect(maquina, "La tarjeta del evaporador no tiene nombre.").not.toBe("");
    test.info().annotations.push({ type: "evaporador", description: maquina });

    /* El formulario consulta al abrirse si esta persona dejó un lote a medias.
       Se espera esa respuesta **antes** de tocar nada: el formulario se dibuja
       enseguida y el aviso del borrador llega después, reemplazándolo, así que
       sin esperar los campos se llenarían sobre un formulario que está por
       desaparecer. */
    const consultaBorrador = page.waitForResponse(
      (r) => r.url().includes("lotes/mi-borrador/") && r.request().method() === "GET",
      { timeout: 15_000 },
    );
    await libre.getByRole("button", { name: "Abrir lote desde vale" }).click();

    await expect(
      page.getByRole("heading", { name: "Abrir lote y preparar evaporación" }),
    ).toBeVisible();

    if ((await consultaBorrador).status() === 200) {
      /* Un borrador de una corrida anterior que falló a medias. Es de la
         misma cuenta de pruebas, así que descartarlo es lo que haría el
         operador para empezar de nuevo; continuarlo arrastraría un vale y
         unos litros que esta prueba no eligió. */
      await page.getByRole("button", { name: "Descartar borrador" }).click();
      await expect(page.getByRole("heading", { name: "Tienes un lote sin abrir" })).toHaveCount(0);
    }

    const formulario = page.locator("form").filter({ hasText: "Vale estandarizado" });
    await expect(formulario).toBeVisible();

    /*
      Se elige el vale **que tenga orden de producción compatible**.

      No sirve cualquiera: el formulario filtra las órdenes por el producto del
      vale, así que un vale sin OP programada deja ese desplegable vacío y el
      formulario no se puede enviar. Fijar un producto concreto ataba la prueba
      a que justo ese tuviera leche disponible, y la leche disponible depende
      de lo que la planta haya consumido.

      Recorrerlos es lo que hace el operador: prueba uno, ve que no tiene orden,
      prueba el siguiente.

      Que la familia vaya a evaporador ya no hay que comprobarlo: en el puesto
      el formulario solo ofrece los vales de familias que van a un evaporador,
      y la máquina viene elegida desde la tarjeta.
    */
    const selectVale = campo(formulario, "Vale estandarizado liberado *");
    const selectOrden = campo(formulario, "Orden de producción *");
    const selectMaquina = campo(formulario, "Máquina / equipo *");

    /* Los vales llegan en una petición aparte: leer las opciones nada más
       abrir el formulario devuelve solo el «Selecciona…» y haría creer que no
       hay leche disponible. */
    const opcionesVale = () =>
      selectVale
        .locator("option")
        .allTextContents()
        .then((ts) =>
          ts.map((t) => t.trim()).filter((t) => t && !t.startsWith("Selecciona")),
        );

    await expect
      .poll(async () => (await opcionesVale()).length, { timeout: 10_000 })
      .toBeGreaterThan(0)
      .catch(() => {
        throw new Error(
          "No hay vales liberados con saldo. Corre el circuito completo " +
            "(«npm run circuito»), que produce uno.",
        );
      });

    const ofrecidos = (await opcionesVale()).filter(
      (texto) => !PRODUCTO_OBJETIVO || texto.includes(PRODUCTO_OBJETIVO),
    );
    expect(
      ofrecidos.length,
      PRODUCTO_OBJETIVO
        ? `No hay un vale liberado con saldo para ${PRODUCTO_OBJETIVO}.`
        : "No hay vales liberados con saldo.",
    ).toBeGreaterThan(0);

    const tieneOrden = async () =>
      (await selectOrden.locator("option").allTextContents())
        .map((t) => t.trim())
        .some((t) => t && !/^(Selecciona|—)/.test(t));

    let elegido = "";
    const descartados: string[] = [];

    for (const texto of ofrecidos) {
      await elegirOpcion(selectVale, new RegExp(texto.split(" · ")[0]));

      if (!(await tieneOrden())) {
        descartados.push(`${texto} → sin OP programada`);
        continue;
      }

      elegido = texto;
      break;
    }

    expect(
      elegido,
      `Ningún vale con saldo sirve para una evaporación: ${descartados.join(" ·· ")}. ` +
        "Corre «manage.py preparar_circuito_polvo --aplicar», que programa una " +
        "OP para un producto que sí va a evaporador.",
    ).not.toBe("");

    test.info().annotations.push({ type: "vale", description: elegido });

    await campo(formulario, "Fecha *").fill(HOY);

    /*
      La máquina decide la etapa, y aquí viene elegida desde la tarjeta: es lo
      que hace que la ejecución del lote nazca en «Evaporación». Se comprueba
      que el formulario la conservó al cambiar de vale —si la soltara, el
      silo de destino desaparecería con ella, porque solo se pide sobre un
      evaporador—.
    */
    await expect(
      selectMaquina.locator("option:checked"),
      `El formulario no conservó el evaporador de la tarjeta (${maquina}).`,
    ).toHaveText(new RegExp(`^${maquina.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")} · `));

    await elegirOpcion(selectOrden, /OP-/);

    await campo(formulario, "Código de lote *").fill(LOTE.codigo);

    /* Sin «Línea»: es un dato de la torre, y sobre un evaporador el formulario
       ni la muestra. */

    /*
      Los litros **no se escriben** de entrada: al elegir el vale, el
      formulario los rellena con su saldo. Primero se lee lo que puso.

      Escribirlos costó dos vueltas. Primero con un valor fijo, que el navegador
      rechazaba en silencio cuando el vale tenía menos. Después leyendo el `max`
      del campo justo tras `selectOption`, que devuelve el del vale **anterior**:
      React todavía no había repintado, y el lote se pedía con veinte mil litros
      de un vale ya agotado. Esperar a que el campo tenga valor es esperar a que
      el formulario haya terminado de reaccionar.
    */
    const litros = campo(formulario, "Litros para esta corrida *");
    await expect
      .poll(async () => Number(await litros.inputValue()), {
        timeout: 10_000,
        message: "El formulario no propuso los litros del vale.",
      })
      .toBeGreaterThan(0);

    /*
      Se toma una **parte** del vale, no todo.

      El formulario propone el saldo entero, y aceptarlo agota el vale en una
      corrida: la prueba siguiente se queda sin leche estandarizada y hay que
      volver a fabricarla. Además es lo que dice el propio dominio —«veinte mil
      litros no se secan de una vez»—, así que un vale alimenta varias corridas.

      Va **antes** del destino: el desplegable de destinos apaga los silos que
      no tienen sitio para estos litros, y cambiar los litros después suelta
      el destino si deja de caber.
    */
    const saldo = Number(await litros.inputValue());
    corrida.entrada = Math.min(saldo, LITROS_POR_CORRIDA);
    corrida.salida = Math.round(corrida.entrada * PROPORCION_SALIDA);
    await litros.fill(String(corrida.entrada));

    /*
      El silo de origen es el silo destino del vale: lo dibuja el recuadro de
      «Leche estandarizada» —silos del vale → **silo estandarizado** →
      Producción—. Hace falta ya aquí para no elegirlo también como destino:
      el modelo rechaza una corrida que sale y entra en el mismo silo.
    */
    const origenDelVale = (
      await formulario.getByText("Producción", { exact: true }).first().locator("..").locator("strong").first().innerText()
    ).trim();
    expect(origenDelVale, "El formulario no mostró el silo estandarizado del vale.").not.toBe("");

    /*
      El destino tiene que estar **disponible** y tener sitio.

      El puesto solo ofrece silos activos en estado disponible —antes el
      desplegable de `/procesos` ofrecía también los bloqueados por Calidad y
      el rechazo llegaba al cerrar, con el evaporador ya trabajado—; los que no
      tienen sitio para estos litros salen apagados con «· sin capacidad».
      `elegirOpcion` ya se salta los apagados; el patrón lo dice igual, para
      que el fallo nombre la regla.
    */
    const destinoElegido = await elegirOpcion(
      campo(formulario, "Silo de destino del concentrado *"),
      new RegExp(`^(?!${patronSilo(origenDelVale)} · )(?!.*sin capacidad).+ · libre `),
    );
    destino = destinoElegido.split(" · ")[0].trim();

    /* Antes de pulsar: si algún campo obligatorio quedó vacío, el navegador
       bloquea el envío sin decir nada y el fallo llega veinte segundos después
       como «no llegó ninguna respuesta». Preguntárselo al formulario nombra el
       campo. */
    expect(
      await camposInvalidos(formulario),
      "El formulario de lote no se puede enviar: hay campos obligatorios sin completar.",
    ).toEqual([]);

    /* «Revisar» se apaga si la máquina está ocupada o no habilitada (aseo,
       mantenimiento). La opción elegida dice el motivo. */
    const revisar = formulario.getByRole("button", { name: "Revisar", exact: true });
    await expect(
      revisar,
      `«Revisar» está deshabilitado: ${await selectMaquina.locator("option:checked").innerText()}`,
    ).toBeEnabled();
    await revisar.click();

    /* El resumen de `ConfirmarAccion`: lo irreversible se confirma viendo lo
       que se va a abrir, incluido origen → destino. */
    await expect(page.getByText("Revisa antes de abrir el lote")).toBeVisible();

    await trasGuardar(page, "confirmar-borrador", async () => {
      // Exacto: "Abrir lote" es substring de "Abrir lote desde vale", que
      // sigue en el DOM detrás del formulario, en el encabezado y en las
      // tarjetas libres.
      await page.getByRole("button", { name: "Abrir lote", exact: true }).click();
    });

    /*
      La tarjeta pasa a «Preparada» y dice de dónde sale y adónde va la leche:
      «{origen} → {destino} · {litros}». El origen se lee de ahí —es el dato
      que ve el operador, el mismo que nombra el motivo de bloqueo— y no de la
      API.
    */
    const tarjeta = tarjetaDe(page);
    await expect(tarjeta.getByText("Preparada", { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(tarjeta).toContainText(LOTE.codigo);

    const trayecto = (await tarjeta.getByText(" → ").first().innerText()).trim();
    origen = trayecto.split(" → ")[0].trim();
    expect(origen, "La tarjeta no trae el silo de origen.").not.toBe("");
    expect(
      origen,
      "La tarjeta muestra un origen distinto del silo estandarizado del vale.",
    ).toMatch(new RegExp(`^${patronSilo(origenDelVale)}$`));
    expect(trayecto, "La tarjeta muestra otro destino que el elegido.").toMatch(
      new RegExp(` → ${patronSilo(destino)} · `),
    );
  });

  await test.step("2 · Calidad analiza el silo estandarizado", async () => {
    /*
      Sin esto la evaporación no arranca.

      `iniciar_condensacion` pasa el silo de origen por
      `motivos_silo_no_disponible(..., para="proceso")`, que exige análisis
      **confirmado, vigente y con las dos firmas**. Es la misma puerta que
      protege la transferencia del vale, y aquí vuelve a aplicar porque volver a
      sacar leche del silo es volver a comprometer su contenido.

      El puesto lo dice antes de intentar: el botón sale apagado y debajo va el
      primer motivo, que empieza por el código del silo. Ese motivo lo calcula
      `motivos_para_iniciar_condensacion`, la misma función que decide al
      iniciar: si la pantalla y el servidor discreparan, aquí se vería.

      Ojo con el orden: el análisis va **después** de abrir el lote. Abrirlo
      genera una salida del silo, y una salida no invalida la muestra —sacar
      leche no cambia la composición de la que queda—, pero un ingreso sí. Al
      revés, con el análisis antes, cualquier vale que descargara en ese silo
      entremedio lo dejaría vencido.

      Por esa misma regla el silo puede llegar **ya analizado**: una corrida
      anterior de esta prueba sobre el mismo vale lo analizó, y desde entonces
      solo ha salido leche. Entonces el botón está habilitado desde el
      principio, y exigir que esté apagado haría fallar la segunda vuelta por
      un comportamiento correcto. Se anota y se sigue.
    */
    const tarjeta = tarjetaDe(page);
    const iniciar = tarjeta.getByRole("button", { name: "Iniciar evaporación" });
    await expect(iniciar).toBeVisible();

    if (await iniciar.isEnabled()) {
      test.info().annotations.push({
        type: "silo de origen",
        description: `${origen} ya tenía un análisis vigente; no se volvió a analizar.`,
      });
      return;
    }

    const motivo = tarjeta.getByText(new RegExp(`^${patronSilo(origen)}: `));
    await expect(
      motivo,
      `«Iniciar evaporación» está deshabilitado, pero el motivo no es el silo ${origen}: ` +
        "analizarlo no lo destrabaría.",
    ).toBeVisible();

    await analizarSilo(page, origen, LECHE_ESTANDARIZADA);
  });

  await test.step("3 · se inicia la evaporación", async () => {
    /* Se vuelve al puesto: el paso anterior dejó el navegador en la pantalla
       de silos. `irA` recarga, y el puesto vuelve a pedir el estado al
       servidor: el botón se habilita porque el servidor lo dice, no porque la
       pantalla lo deduzca. */
    await irA(page, "/produccion/evaporacion");

    const tarjeta = tarjetaDe(page);
    const iniciar = tarjeta.getByRole("button", { name: "Iniciar evaporación" });
    await expect(
      iniciar,
      `La corrida del lote ${LOTE.codigo} sigue sin poder iniciarse tras analizar ${origen}.`,
    ).toBeEnabled({ timeout: 15_000 });

    await trasGuardar(page, "/iniciar/", async () => {
      await iniciar.click();
    });

    await expect(tarjeta.getByText("En curso", { exact: true })).toBeVisible({ timeout: 15_000 });
  });

  await test.step("4 · se declara el precondensado y pasa a Calidad", async () => {
    const tarjeta = tarjetaDe(page);
    await tarjeta.getByRole("button", { name: "Registrar salida y cerrar" }).click();

    const cierre = page.locator("form").filter({ hasText: "Cerrar evaporación" });
    await expect(cierre).toBeVisible();

    await campo(cierre, "Precondensado obtenido (L)").fill(String(corrida.salida));
    await campo(cierre, "Sólidos de salida (%)").fill(CONTROLES_SALIDA.solidos);
    await campo(cierre, "Temperatura de salida (°C)").fill(CONTROLES_SALIDA.temperatura);

    /* El formulario calcula el rendimiento volumétrico mientras se escribe.
       Comprobarlo es barato y cubre la única cuenta que hace la pantalla. */
    await expect(cierre.getByText(/Rendimiento volumétrico/)).toContainText("25");

    await trasGuardar(page, "/cerrar/", async () => {
      await cierre
        .getByRole("button", { name: "Registrar salida y enviar a Calidad" })
        .click();
    });
  });

  await test.step("5 · la corrida queda a la espera de Calidad", async () => {
    /*
      Y que quede **pendiente de Calidad**, que es donde el botón dice que la
      manda. Producción cierra la corrida; el concentrado no sigue a la torre
      hasta que Calidad lo libere. Un cierre que dejara la corrida «cerrada» sin
      pasar por ahí se saltaría esa puerta.

      Se mira en dos sitios porque dicen cosas distintas: «Corridas de hoy» da
      el estado de la corrida, y la tarjeta muestra que la máquina la sigue
      teniendo a cargo —«Esperando Calidad»—, o, si ya se ofrece para abrir
      otra, la línea «En Calidad» con este lote.
    */
    const hoy = page.getByRole("region", { name: "Corridas de hoy" });
    const fila = hoy.getByRole("listitem").filter({ hasText: `lote ${LOTE.codigo}` });
    await expect(
      fila,
      `La corrida del lote ${LOTE.codigo} no aparece en «Corridas de hoy».`,
    ).toBeVisible({ timeout: 20_000 });
    await expect(fila).toContainText(/Pendiente de [Cc]alidad/);

    const tarjeta = tarjetaDe(page);
    await expect(tarjeta).toContainText(LOTE.codigo);
    await expect(
      tarjeta.getByText("Esperando Calidad", { exact: true })
        .or(tarjeta.getByText(/^En Calidad:/)),
    ).toBeVisible();
  });

  expect(erroresJs, `Errores de JavaScript:\n${erroresJs.join("\n")}`).toHaveLength(0);

  const inesperados = rechazosInesperados();
  expect(
    inesperados,
    `El servidor rechazó peticiones que nadie esperaba: ${inesperados.join(" ·· ")}`,
  ).toHaveLength(0);

  /* El contrato con `flujo-polvo-continuacion.spec.ts`: el lote, el silo donde
     quedó el precondensado y sus litros. Esa prueba no vuelve a descubrirlos. */
  fs.mkdirSync(path.dirname(RUTA_REGISTRO), { recursive: true });
  fs.writeFileSync(RUTA_REGISTRO, JSON.stringify({
    lote: LOTE.codigo,
    silo_precondensado: destino,
    litros_precondensado: corrida.salida,
  }, null, 2));
});
