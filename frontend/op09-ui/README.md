# OP-09: recorridos visuales aislados

Ejecutar desde `frontend` contra los servicios de QA ya iniciados y verificados
en `127.0.0.1:5209` (web) y `127.0.0.1:8209` (API). Vite debe haber arrancado
con `VITE_API_PROXY_TARGET=http://127.0.0.1:8209`. La configuración no levanta
servidores ni limpia el registro compartido `e2e/.registro/hallazgos.jsonl`.

Definir `E2E_USUARIO` y `E2E_CLAVE` para la cuenta administrativa E2E de la
base aislada. Preparar los maestros y cuentas con los comandos de
[`e2e/README.md`](../e2e/README.md) antes de operar. `preparar_estado_qa` sólo
se usa al comenzar con una base vacía: exige cero registros operacionales y
no crea las preparaciones de cada familia ni la cuenta `e2e_auditoria`.

```powershell
$qa = 'op09-ui/playwright.config.ts'
npx.cmd playwright test --config=$qa --project=circuito
npx.cmd playwright test --config=$qa --project=evaporacion
npx.cmd playwright test --config=$qa --project=flujo-polvo --no-deps
```

Los tres pasos de polvo se ejecutan en orden y en la misma base; Evaporación
deja `e2e/.registro/flujo-polvo.json` para su continuación. Para precondensado,
fijar `E2E_PRODUCTO='Precondensado Entero NE Granel'` y
`E2E_REGISTRO='e2e/.registro/flujo-precondensado.json'`, repetir circuito y
evaporación, y ejecutar `--project=flujo-precondensado`. Descremado y suero son
`--project=flujo-descremado` y `--project=flujo-suero` tras sus preparaciones
propias. Mantequilla exige crema liberada real en `E2E_LOTE_CREMA`; sus pruebas
de envasado e inventario se saltan si no se suministran también
`E2E_MANTEQUILLA_ID` y `E2E_MANTEQUILLA_LOTE` del lote creado.

Todos los proyectos reutilizan la sesión y los registros E2E existentes;
ejecutarlos en serie. El proxy de Playwright impide que el navegador acceda a
destinos externos mediante HTTP, pero el aislamiento de Django y de los
procesos anfitriones corresponde al entorno de QA. Esta suite de un solo
worker verifica el recorrido funcional; no representa la carga de 70 usuarios
virtuales.
