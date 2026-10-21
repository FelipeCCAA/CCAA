import { expect, test, type Page, type Route } from "@playwright/test";

const BASE = "http://127.0.0.1:5198";
const usuario = {
  id: 907, username: "op07-sintetico", nombre: "Cuenta", apellido: "Prueba", email: "",
  rol: "admin", capacidades: [],
  perfil: { area: "administracion", nivel: "admin", rol: "admin", debe_cambiar_password: false },
};
const limite = { code: "REPORTE_DEMASIADO_GRANDE", detail: "El reporte supera 1000 recepciones; reduce el rango de fechas. No se generó un reporte parcial." };
const resumen = (fecha: string) => ({
  fecha, desde: fecha, hasta: fecha, camiones: 0, litros: "0.00", kg_guia: "0.00",
  kg_romana: "0.00", diferencia_kg: null, horas_a_pagar: 0, camiones_sin_romana: 0,
  camiones_sin_marcas_horarias: 0, por_silo: {}, por_procedencia: {}, detalle: [],
});

async function preparar(page: Page, reporte: (route: Route, url: URL) => Promise<void>) {
  const externas: string[] = [];
  await page.addInitScript((usuario) => {
    sessionStorage.setItem("ccaa.sesion", JSON.stringify({ token: "op07-ficticio", usuario }));
  }, usuario);
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== BASE) { externas.push(url.origin); await route.abort(); return; }
    if (!url.pathname.startsWith("/api/")) { await route.continue(); return; }
    if (url.pathname.includes("resumen-diario")) { await reporte(route, url); return; }
    const data = url.pathname === "/api/usuarios/yo/" ? usuario : { results: [], count: 0 };
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(data) });
  });
  return externas;
}

test("explica el exceso y permite consultar otro período sin reporte parcial", async ({ page }) => {
  let consultas = 0;
  const externas = await preparar(page, async (route, url) => {
    consultas++;
    await route.fulfill({ status: consultas === 1 ? 400 : 200, contentType: "application/json",
      body: JSON.stringify(consultas === 1 ? limite : resumen(url.searchParams.get("fecha")!)) });
  });
  await page.goto("/#/leche/reporte");
  await expect(page.getByRole("alert")).toHaveText(limite.detail);
  await expect(page.getByRole("button", { name: "CSV", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Día anterior" }).click();
  await expect(page.getByText("Detalle por camión")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(externas).toEqual([]);
});

test("el error Blob de una descarga se explica y no inicia un archivo", async ({ page }) => {
  const descargas: string[] = [];
  page.on("download", (d) => descargas.push(d.suggestedFilename()));
  const externas = await preparar(page, async (route, url) => {
    const exportando = url.searchParams.has("formato");
    await route.fulfill({ status: exportando ? 400 : 200, contentType: "application/json",
      body: JSON.stringify(exportando ? limite : resumen(url.searchParams.get("fecha")!)) });
  });
  await page.goto("/#/leche/reporte");
  await expect(page.getByText("Detalle por camión")).toBeVisible();
  for (const formato of ["CSV", "Excel"]) {
    await page.getByRole("button", { name: formato, exact: true }).click();
    await expect(page.getByRole("alert")).toHaveText(limite.detail);
  }
  expect(descargas).toEqual([]);
  expect(externas).toEqual([]);
});
