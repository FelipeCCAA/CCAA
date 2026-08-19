/*
  Vacía el registro de hallazgos antes de empezar.

  Va en `globalSetup` y no en el proyecto de sesión porque el proyecto de
  sesión se puede saltar (`--no-deps`, o auditar solo las pantallas públicas),
  y entonces el registro conservaría los hallazgos de la corrida anterior. El
  informe mezclaría dos corridas y mostraría como pendientes defectos ya
  arreglados, que es la forma más rápida de que nadie vuelva a creerle.
*/

import { limpiar } from "./hallazgos";

export default function preparar(): void {
  limpiar();
}
