import assert from "node:assert/strict";
import test from "node:test";

import { debeCerrarSesion, mensajeDeCierre } from "../src/services/auth-errors.ts";

test("una sesión revocada limpia y redirige una sola vez", () => {
  assert.equal(debeCerrarSesion(401, "/dashboard", false), true);
  assert.equal(debeCerrarSesion(401, "/dashboard", true), false);
  assert.equal(debeCerrarSesion(401, "/login", false), false);
  assert.match(mensajeDeCierre("SESSION_REVOKED"), /sesión fue cerrada/i);
});

test("presenta mensajes estables para cada causa de cierre", () => {
  assert.match(mensajeDeCierre("SESSION_EXPIRED"), /expiró por inactividad/i);
  assert.match(mensajeDeCierre("USER_DISABLED"), /desactivada/i);
  assert.match(mensajeDeCierre("PASSWORD_CHANGED"), /contraseña cambió/i);
});
