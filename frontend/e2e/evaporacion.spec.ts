/*
  El flujo de evaporación, por pantalla.

  Cuatro pasos: se abre el lote sobre un evaporador, se prepara la corrida, se
  inicia y se cierra declarando el precondensado obtenido.

  Dónde empieza y por qué ahí
  ---------------------------
  Empieza en un **vale ya liberado**, no en la recepción del camión. Componer y
  liberar el vale es el flujo de estandarización, y lo recorre entero
  `circuito-polvo.spec.ts`; repetirlo aquí sumaría minutos de corrida para
  volver a comprobar lo mismo. Lo que esta prueba cubre es lo que empieza
  cuando el silo estandarizado ya tiene leche: qué puede hacer Producción con
  ella.

  Abrir el lote **es** iniciar la evaporación
  -------------------------------------------
  No son dos cosas. Para la familia «polvo» el formulario de lote solo ofrece
  evaporadores —«la torre Egron aparecerá después, únicamente cuando Calidad
  libere el concentrado»— y `_encadenar_con_la_estandarizacion` deduce la etapa
  del **tipo de máquina**: evaporador → evaporación. De ahí que el lote y la
  corrida de evaporación compartan ejecución, y que `iniciar_condensacion`
  tenga una rama entera para adoptar la que el lote ya dejó activa en vez de
  abrir una segunda.

  Prerrequisitos
  --------------
  `python manage.py preparar_circuito_polvo --aplicar` deja la **orden de
  producción** programada, que el formulario exige y que ninguna pantalla crea.
  Hace falta además un vale liberado con saldo; si no hay, la prueba lo dice y
  remite al circuito completo, que produce uno.
*/

import { test, expect } from "@playwright/test";

import {
  analizarSilo, campo, camposInvalidos, cerrarSegundaFirma, elegirOpcion, irA,
  rechazosInesperados, trasGuardar, vigilar,
} from "./ayudantes";

const SELLO = Date.now().toString().slice(-6);

const HOY = new Date().toISOString().slice(0, 10);

const LOTE = { codigo: `CCAA-EVA-${SELLO}` };

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

/* El silo del que sale la leche. Lo dice el formulario al elegir el lote, así
   que se descubre en el paso 2 y se usa en el 3. */
let origen = "";


test.describe.configure({ mode: "serial" });

test.afterAll(cerrarSegundaFirma);

test("de la leche estandarizada al precondensado, por pantalla", async ({ page }) => {
  test.setTimeout(180_000);

  const erroresJs = vigilar(page);

  await test.step("1 · se abre el lote sobre un evaporador", async () => {
    await irA(page, "/produccion");
    await page.getByRole("button", { name: "Iniciar lote desde vale" }).click();

    await expect(page.getByText("Vale estandarizado liberado")).toBeVisible();

    /*
      Se elige el vale **que tenga orden de producción compatible**.

      No sirve cualquiera: el formulario filtra las órdenes por el producto del
      vale, así que un vale sin OP programada deja ese desplegable vacío y el
      formulario no se puede enviar. Fijar un producto concreto ataba la prueba
      a que justo ese tuviera leche disponible, y la leche disponible depende
      de lo que la planta haya consumido.

      Recorrerlos es lo que hace el operador: prueba uno, ve que no tiene orden,
      prueba el siguiente.
    */
    const selectVale = campo(page, "Vale estandarizado liberado *");
    const selectOrden = campo(page, "Orden de producción *");

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

    const ofrecidos = await opcionesVale();

    /*
      Un vale sirve si cumple **las dos** condiciones, y hay que comprobarlas
      por separado porque fallan por motivos distintos:

      - tiene OP programada de su producto — si no, el desplegable de órdenes
        queda vacío;
      - su familia va a un evaporador — un vale de crema tiene orden y máquinas,
        pero las máquinas son líneas y envasadoras, y entonces el que se queda
        vacío es el desplegable de evaporadores.

      Comprobar solo la primera elegía el vale de crema y el fallo aparecía dos
      campos después, hablando de máquinas cuando el problema era el producto.
    */
    const selectMaquina = campo(page, "Máquina / equipo *");
    const util = async (select: typeof selectOrden, excluir: RegExp) =>
      (await select.locator("option").allTextContents())
        .map((t) => t.trim())
        .filter((t) => t && !excluir.test(t)).length > 0;

    let elegido = "";
    const descartados: string[] = [];

    for (const texto of ofrecidos) {
      await elegirOpcion(selectVale, new RegExp(texto.split(" · ")[0]));

      if (!(await util(selectOrden, /^(Selecciona|—)/))) {
        descartados.push(`${texto} → sin OP programada`);
        continue;
      }

      const maquinas = (await selectMaquina.locator("option").allTextContents())
        .map((t) => t.trim());

      if (!maquinas.some((m) => /Evaporador/.test(m))) {
        descartados.push(`${texto} → su familia no va a un evaporador`);
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

    await campo(page, "Fecha *").fill(HOY);

    /*
      La máquina decide la etapa. Elegir un evaporador es lo que hace que la
      ejecución del lote nazca en «Evaporación» y, por tanto, lo que hace que
      el lote aparezca luego en «Nueva evaporación». Con una torre nacería en
      «Secado» y la pantalla de procesos no lo ofrecería —sin decir por qué—.

      Para la familia polvo el formulario ya solo ofrece evaporadores, así que
      esto documenta la regla más que sortearla.
    */
    await elegirOpcion(selectMaquina, /Evaporador/);

    await elegirOpcion(selectOrden, /OP-/);

    await campo(page, "Código de lote *").fill(LOTE.codigo);

    /* «Línea» es obligatoria y no se deduce del equipo. Es un dato del turno,
       no del proceso. */
    const linea = campo(page, "Línea *");
    if (await linea.count()) await elegirOpcion(linea, /E1|E2/);

    /*
      Los litros **no se escriben**: al elegir el vale, el formulario los rellena
      con su saldo. Solo se lee lo que puso.

      Escribirlos costó dos vueltas. Primero con un valor fijo, que el navegador
      rechazaba en silencio cuando el vale tenía menos. Después leyendo el `max`
      del campo justo tras `selectOption`, que devuelve el del vale **anterior**:
      React todavía no había repintado, y el lote se pedía con veinte mil litros
      de un vale ya agotado. Esperar a que el campo tenga valor es esperar a que
      el formulario haya terminado de reaccionar.
    */
    const litros = campo(page, "Litros para esta corrida *");
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
    */
    const saldo = Number(await litros.inputValue());
    corrida.entrada = Math.min(saldo, LITROS_POR_CORRIDA);
    corrida.salida = Math.round(corrida.entrada * PROPORCION_SALIDA);
    await litros.fill(String(corrida.entrada));

    /* Antes de pulsar: si algún campo obligatorio quedó vacío, el navegador
       bloquea el envío sin decir nada y el fallo llega veinte segundos después
       como «no llegó ninguna respuesta». Preguntárselo al formulario nombra el
       campo. */
    const formulario = page.locator("form").filter({ hasText: "Vale estandarizado" });
    expect(
      await camposInvalidos(formulario),
      "El formulario de lote no se puede enviar: hay campos obligatorios sin completar.",
    ).toEqual([]);

    await trasGuardar(page, "confirmar-borrador", async () => {
      await page.getByRole("button", { name: "Abrir proceso" }).last().click();
    });
  });

  await test.step("2 · se prepara la corrida de evaporación", async () => {
    await irA(page, "/procesos");
    await page.getByRole("button", { name: "Nueva evaporación" }).click();

    /* Por rol y no por texto: «Nueva evaporación» es a la vez el botón que
       abre el formulario y el título del formulario abierto. */
    await expect(
      page.getByRole("heading", { name: "Nueva evaporación" }),
    ).toBeVisible();

    /*
      El desplegable solo trae lotes **en proceso, con orden y en una etapa de
      evaporación**, y que no tengan ya una corrida. Si el lote del paso 1 no
      está, el fallo es del paso 1 aunque se manifieste aquí: por eso el
      mensaje nombra las cuatro condiciones.
    */
    await elegirOpcion(
      campo(page, "Lote / entrada preparada"),
      new RegExp(LOTE.codigo),
    ).catch(() => {
      throw new Error(
        `El lote ${LOTE.codigo} no aparece como entrada preparada. Tiene que ` +
          "estar en proceso, con orden programada, en etapa de evaporación y " +
          "sin corrida previa.",
      );
    });

    /*
      El silo de origen se lee del resumen que el formulario dibuja al elegir el
      lote. Hace falta para el paso siguiente, y sacarlo de aquí evita
      preguntárselo a la API: es el mismo dato que ve el operador.
    */
    const resumen = page.locator("p").filter({ hasText: /^Origen/ }).first();
    await expect(
      resumen,
      "El formulario no mostró el resumen del lote: sin él no se sabe de qué " +
        "silo sale la leche.",
    ).toBeVisible({ timeout: 10_000 });

    origen = (await resumen.locator("b").innerText()).trim();
    expect(origen, "El resumen no trae el silo de origen.").not.toBe("");

    /*
      El destino tiene que estar **disponible**, y hay que filtrarlo aquí.

      El desplegable ofrece todos los silos activos con sitio, incluidos los que
      Calidad tiene bloqueados: escribe su estado en la opción —«SILO 1 · libre
      94.000 L · Bloqueado por Calidad»— pero no la deshabilita. Elegirlo deja
      preparar la corrida y hasta iniciarla; el rechazo llega al **cerrar**, con
      «SILO 1 no admite el precondensado», cuando el evaporador ya trabajó.

      Se toma el que dice «Disponible».
    */
    await elegirOpcion(campo(page, "Silo de concentrado"), /· Disponible$/);

    await trasGuardar(page, "crear-guiada", async () => {
      await page.getByRole("button", { name: "Crear corrida preparada" }).click();
    });
  });

  await test.step("3 · Calidad analiza el silo estandarizado", async () => {
    /*
      Sin esto la evaporación no arranca.

      `iniciar_condensacion` pasa el silo de origen por
      `motivos_silo_no_disponible(..., para="proceso")`, que exige análisis
      **confirmado, vigente y con las dos firmas**. Es la misma puerta que
      protege la transferencia del vale, y aquí vuelve a aplicar porque volver a
      sacar leche del silo es volver a comprometer su contenido.

      Ojo con el orden: el análisis va **después** de abrir el lote. Abrirlo
      genera una salida del silo, y una salida no invalida la muestra —sacar
      leche no cambia la composición de la que queda—, pero un ingreso sí. Al
      revés, con el análisis antes, cualquier vale que descargara en ese silo
      entremedio lo dejaría vencido.
    */
    await analizarSilo(page, origen, LECHE_ESTANDARIZADA);
  });

  await test.step("4 · se inicia la evaporación", async () => {
    /* Se vuelve a Procesos: el paso anterior dejó el navegador en la pantalla
       de silos, y la tabla de corridas está aquí. */
    await irA(page, "/procesos");

    /*
      La tabla se carga bajo demanda: la pantalla no descarga el histórico al
      entrar, así que sin pulsar «Cargar corridas» la fila no existe.

      Se insiste hasta que el botón desaparece —es lo que hace al cargar—
      porque un clic inmediato después de recargar la página cae a veces antes
      de que React haya enganchado el manejador: el botón sigue ahí, la tabla
      no llega, y el fallo aparece como una fila que nunca existió.

      `.first()` es deliberado: hay dos botones con este nombre, el de
      evaporación y el de mantequilla, y el primero es el de evaporación.
    */
    const cargar = page.getByRole("button", { name: "Cargar corridas" }).first();

    await expect
      .poll(
        async () => {
          if (await cargar.isVisible()) await cargar.click();
          return cargar.isVisible();
        },
        { timeout: 20_000, message: "La tabla de corridas no llegó a cargarse." },
      )
      .toBe(false);

    const fila = page.getByRole("row", { name: new RegExp(LOTE.codigo) });
    await expect(
      fila,
      `La corrida del lote ${LOTE.codigo} no aparece en la tabla de evaporación.`,
    ).toBeVisible({ timeout: 20_000 });

    await trasGuardar(page, "/iniciar/", async () => {
      await fila.getByRole("button", { name: "Iniciar evaporación" }).click();
    });
  });

  await test.step("5 · se declara el precondensado y pasa a Calidad", async () => {
    const fila = page.getByRole("row", { name: new RegExp(LOTE.codigo) });
    await fila.getByRole("button", { name: "Registrar salida" }).click();

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

  await test.step("6 · la corrida queda con su balance y a la espera de Calidad", async () => {
    const fila = page.getByRole("row", { name: new RegExp(LOTE.codigo) });
    await expect(fila).toBeVisible({ timeout: 20_000 });

    /*
      Se comprueba el **balance**: que la fila muestre los litros declarados y
      los sólidos es lo que distingue una corrida cerrada de una que solo cambió
      de etiqueta.
    */
    await expect(fila).toContainText(corrida.salida.toLocaleString("es-CL"));
    await expect(fila).toContainText(CONTROLES_SALIDA.solidos);

    /*
      Y que quede **pendiente de Calidad**, que es donde el botón dice que la
      manda. Producción cierra la corrida; el concentrado no sigue a la torre
      hasta que Calidad lo libere. Un cierre que dejara la corrida «cerrada» sin
      pasar por ahí se saltaría esa puerta.

      Ojo: la columna «Resultado» también dice «Pendiente» cuando aún no hay
      litros, así que afirmar «no dice Pendiente» era comprobar lo contrario de
      lo que se quiere — y fallaba justo cuando el flujo había ido bien.
    */
    await expect(fila).toContainText(/Pendiente de [Cc]alidad/);
  });

  expect(erroresJs, `Errores de JavaScript:\n${erroresJs.join("\n")}`).toHaveLength(0);

  const inesperados = rechazosInesperados();
  expect(
    inesperados,
    `El servidor rechazó peticiones que nadie esperaba: ${inesperados.join(" ·· ")}`,
  ).toHaveLength(0);
});
