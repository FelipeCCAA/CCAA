import { expect, test } from "@playwright/test";

const ORIGEN = "http://127.0.0.1:5199";
const usuario = {
  id: 908, username: "envase-op08", nombre: "Operador", apellido: "Envase",
  email: "", rol: "produccion", capacidades: [],
  perfil: { area: "envase", nivel: "trabajador", rol: "produccion", debe_cambiar_password: false },
};
const material = {
  salida_id: 9, lote_id: 8, lote_codigo: "L-ENV-OP08",
  producto_id: 3, producto_nombre: "Leche en polvo",
  cantidad_disponible: "500", pallets_total: 0, unidad: "kg",
  formato: "saco_25kg", formato_id: 6, formato_codigo: "saco-25",
  formato_nombre: "Saco 25 kg", formato_kg: "25",
  maximo_unidad_logistica_kg: "500", tipo_unidad_logistica: "pallet",
  tipo_unidad_logistica_etiqueta: "Pallet", equipos: [
    { id: 7, codigo: "ENV-7", nombre: "Envasadora 7" },
  ],
  unidades_por_producto: 20, unidades_disponibles: 20,
  cantidad_envasable: "500", remanente_kg: "0",
  materiales_envase: [{ insumo_id: 2, codigo: "BOLSA", nombre: "Bolsa",
    unidad: "un", cantidad_por_kg: "0.04", stock_disponible: "20" }],
  puede_envasar: true, calidad: "liberado", motivo_bloqueo: "", advertencia_materiales: "",
};

test("una respuesta incierta conserva exactamente UUID y cuerpo al reintentar tras recargar", async ({ page }) => {
  const enviados: unknown[] = [];
  const externas: string[] = [];
  await page.addInitScript((dato) => {
    sessionStorage.setItem("ccaa.sesion", JSON.stringify({ token: "op08-ficticio", usuario: dato }));
  }, usuario);
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== ORIGEN) { externas.push(url.origin); await route.abort(); return; }
    if (!url.pathname.startsWith("/api/")) { await route.continue(); return; }
    if (url.pathname === "/api/produccion/envases/" && route.request().method() === "POST") {
      const pedido = JSON.parse(route.request().postData()!);
      enviados.push(pedido);
      if (enviados.length === 1) { await route.abort("failed"); return; }
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({
        id: 31, ...pedido, pallets: [{ id: 44, ...pedido.pallets_datos[0], estado: "pendiente_calidad" }],
      }) });
      return;
    }
    const data = url.pathname === "/api/usuarios/yo/" ? usuario
      : url.pathname === "/api/produccion/envases/bandeja/"
        ? { materiales: enviados.length ? [] : [material], bloqueados_calidad: [], registros_recientes: [] }
        : { results: [], count: 0 };
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(data) });
  });

  await page.goto("/#/envasado");
  await page.getByRole("button", { name: /L-ENV-OP08/ }).click();
  const formulario = page.locator("form");
  await formulario.getByRole("combobox").first().selectOption("7");
  await formulario.getByPlaceholder("Código pallet").fill("PAL-OP08-001");
  await formulario.getByRole("button", { name: "Crear pallet" }).click();
  await expect(page.getByText("Cierre pendiente de confirmación")).toBeVisible();
  expect((enviados[0] as { operacion_id: string }).operacion_id).toMatch(/^[0-9a-f-]{36}$/);

  await page.reload();
  await expect(page.getByText("No hay material liberado para envasar.")).toBeVisible();
  await expect(page.getByText("Cierre pendiente de confirmación")).toBeVisible();
  await page.getByRole("button", { name: "Reintentar el mismo cierre" }).click();
  await expect(page.getByText(/PAL-OP08-001 confirmado/)).toBeVisible();
  expect(enviados).toHaveLength(2);
  expect(enviados[1]).toEqual(enviados[0]);
  expect(await page.evaluate(() => sessionStorage.getItem("envasado-pendiente-908-8"))).toBeNull();
  expect(externas).toEqual([]);
});

test("otro operador no ve el cierre pendiente de la cuenta anterior", async ({ page }) => {
  const otro = { ...usuario, id: 909, username: "envase-otro" };
  const pedidoAjeno = {
    operacion_id: "cd066870-0e1b-439b-95db-9d3e94bb3424",
    lote: 8, equipo: 7, formato: 6,
    inicio: "2026-10-22T09:00:00Z", termino: "2026-10-22T10:00:00Z",
    pallets_datos: [{ codigo: "PAL-AJENO", unidades: 20, kg_neto: 500 }],
  };
  await page.addInitScript(({ cuenta, pedido }) => {
    sessionStorage.setItem("ccaa.sesion", JSON.stringify({ token: "op08-ficticio", usuario: cuenta }));
    sessionStorage.setItem("envasado-pendiente-908-8", JSON.stringify(pedido));
  }, { cuenta: otro, pedido: pedidoAjeno });
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== ORIGEN || !url.pathname.startsWith("/api/")) {
      await route.continue(); return;
    }
    const data = url.pathname === "/api/usuarios/yo/" ? otro
      : url.pathname === "/api/produccion/envases/bandeja/"
        ? { materiales: [], bloqueados_calidad: [], registros_recientes: [] }
        : { results: [], count: 0 };
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(data) });
  });
  await page.goto("/#/envasado");
  await expect(page.getByText("No hay material liberado para envasar.")).toBeVisible();
  await expect(page.getByText("Cierre pendiente de confirmación")).toHaveCount(0);
  await expect(page.getByText("PAL-AJENO")).toHaveCount(0);
  expect(await page.evaluate(() => sessionStorage.getItem("envasado-pendiente-908-8"))).not.toBeNull();
});

test("rechazos tras respuesta incierta conservan el mismo pedido y bloquean otro cierre", async ({ page }) => {
  const enviados: unknown[] = [];
  await page.addInitScript((dato) => {
    sessionStorage.setItem("ccaa.sesion", JSON.stringify({ token: "op08-ficticio", usuario: dato }));
  }, usuario);
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== ORIGEN) { await route.abort(); return; }
    if (!url.pathname.startsWith("/api/")) { await route.continue(); return; }
    if (url.pathname === "/api/produccion/envases/" && route.request().method() === "POST") {
      enviados.push(JSON.parse(route.request().postData()!));
      if (enviados.length === 1) { await route.abort("failed"); return; }
      await route.fulfill({ status: enviados.length === 2 ? 403 : 400,
        contentType: "application/json", body: JSON.stringify({ detail: "Reintento rechazado" }) });
      return;
    }
    const data = url.pathname === "/api/usuarios/yo/" ? usuario
      : url.pathname === "/api/produccion/envases/bandeja/"
        ? { materiales: enviados.length ? [] : [material], bloqueados_calidad: [], registros_recientes: [] }
        : { results: [], count: 0 };
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(data) });
  });
  await page.goto("/#/envasado");
  await page.getByRole("button", { name: /L-ENV-OP08/ }).click();
  const formulario = page.locator("form");
  await formulario.getByRole("combobox").first().selectOption("7");
  await formulario.getByPlaceholder("Código pallet").fill("PAL-INCIERTO");
  await formulario.getByRole("button", { name: "Crear pallet" }).click();
  await expect(page.getByText("Cierre pendiente de confirmación")).toBeVisible();
  await page.reload();
  for (const rechazo of [403, 400]) {
    await page.getByRole("button", { name: "Reintentar el mismo cierre" }).click();
    await expect(page.getByText(new RegExp(`rechazado \\(${rechazo}\\)`))).toBeVisible();
    await expect(page.getByText("Cierre pendiente de confirmación")).toBeVisible();
    await expect(page.getByRole("button", { name: "Crear pallet" })).toHaveCount(0);
    expect(await page.evaluate(() => sessionStorage.getItem("envasado-pendiente-908-8"))).not.toBeNull();
  }
  expect(enviados).toHaveLength(3);
  expect(enviados[1]).toEqual(enviados[0]);
  expect(enviados[2]).toEqual(enviados[0]);
});

test("lote visible sin embalajes mantiene accesible la recuperación pendiente", async ({ page }) => {
  const pedido = {
    operacion_id: "e00ec104-7a6f-4c4f-b823-b5f6b5e8fd47",
    lote: 8, equipo: 7, formato: 6,
    inicio: "2026-10-22T09:00:00Z", termino: "2026-10-22T10:00:00Z",
    controles: { sellado: "conforme" }, observacion: "cierre incierto",
    pallets_datos: [{ codigo: "PAL-SIN-EMBALAJE", unidades: 20, kg_neto: 500 }],
  };
  const enviados: unknown[] = [];
  await page.addInitScript(({ cuenta, pendiente }) => {
    sessionStorage.setItem("ccaa.sesion", JSON.stringify({ token: "op08-ficticio", usuario: cuenta }));
    sessionStorage.setItem("envasado-pendiente-908-8", JSON.stringify(pendiente));
  }, { cuenta: usuario, pendiente: pedido });
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== ORIGEN) { await route.abort(); return; }
    if (!url.pathname.startsWith("/api/")) { await route.continue(); return; }
    if (url.pathname === "/api/produccion/envases/" && route.request().method() === "POST") {
      enviados.push(JSON.parse(route.request().postData()!));
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({
        id: 31, ...pedido, pallets: [{ id: 44, ...pedido.pallets_datos[0], estado: "pendiente_calidad" }],
      }) });
      return;
    }
    const sinEmbalajes = { ...material, cantidad_disponible: "100", cantidad_envasable: "0",
      unidades_disponibles: 0, puede_envasar: false, motivo_bloqueo: "Stock insuficiente de embalajes" };
    const data = url.pathname === "/api/usuarios/yo/" ? usuario
      : url.pathname === "/api/produccion/envases/bandeja/"
        ? { materiales: [sinEmbalajes], bloqueados_calidad: [], registros_recientes: [] }
        : { results: [], count: 0 };
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(data) });
  });

  await page.goto("/#/envasado");
  await page.getByRole("button", { name: /L-ENV-OP08/ }).click();
  await expect(page.getByText("Stock insuficiente de embalajes")).toBeVisible();
  await expect(page.getByText("Cierre pendiente de confirmación")).toBeVisible();
  await expect(page.getByRole("button", { name: "Crear pallet" })).toHaveCount(0);
  await page.getByRole("button", { name: "Reintentar el mismo cierre" }).click();
  await expect(page.getByText(/PAL-SIN-EMBALAJE confirmado/)).toBeVisible();
  expect(enviados).toEqual([pedido]);
  expect(await page.evaluate(() => sessionStorage.getItem("envasado-pendiente-908-8"))).toBeNull();
});
