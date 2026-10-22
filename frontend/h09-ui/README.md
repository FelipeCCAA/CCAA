# H09-01: comprobación web aislada de firmas

Usar sólo con `qa/h09/manage_isolated.py`, API127.0.0.1:8209, Vite127.0.0.1:5209
y clúster H0955459 verificado. Requiere copia ficticia y vale liberado con saldo.
El preparador genérico puede elegir otro producto; `qa/h09/prepare_powder.py`
prepara exclusivamente la orden de polvo que falta, sin fabricar resultados.

Desde frontend, con credenciales ficticias E2E en variables del proceso:

```powershell
$env:E2E_PRODUCTO='Leche entera en polvo'
$env:E2E_LOTE_PREFIJO='H09-POLVO'
npx.cmd playwright test --config=h09-ui/playwright.config.ts --project=evaporacion
npx.cmd playwright test --config=h09-ui/playwright.config.ts --project=flujo-polvo --no-deps
```

Una sola persona virtual, sin reintentos automáticos. La continuación lee el
handoff `e2e/.registro/flujo-polvo.json`; preservar el anterior antes de crear
otro. Archivos de salida en `h09-runtime`, fuera de frontend. La configuración
no levanta servidores ni permite destinos HTTP externos del navegador.
