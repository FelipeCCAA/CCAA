# Auditoría de accesibilidad

Recorre todas las pantallas de la aplicación con [axe-core](https://github.com/dequelabs/axe-core)
sobre Chromium y deja un informe en `informe-accesibilidad.md`.

## Qué mide — y qué no

Mide lo que una máquina puede comprobar sin opinar: contraste de color, campos
sin etiqueta, botones sin nombre accesible, tablas sin encabezados, orden de
títulos y tamaño de objetivo táctil.

**No mide usabilidad.** No dice si una pantalla se entiende, si el flujo tiene
demasiados pasos, ni si el motivo por el que un lote no se puede liberar sirve
para que el operario sepa qué hacer. Eso solo lo contesta ver a alguien de
planta usándola. Esta auditoría despeja lo objetivo para que esa sesión se
gaste en lo que de verdad hay que discutir.

De las normas se incluye `wcag22aa`, que es donde vive `target-size`: en planta,
el tamaño del objetivo y el contraste deciden si alguien con guantes, frente a
una pantalla con reflejo, acierta el campo a la primera.

## Cómo se corre

Una vez, para crear la cuenta de la auditoría:

```powershell
cd backend
.venv\Scripts\python.exe manage.py crear_usuario_e2e
```

El comando imprime las variables a definir. Después:

```powershell
cd frontend
$env:E2E_USUARIO = "e2e_auditoria"
$env:E2E_CLAVE = "auditoria-e2e-ccaa"
npm run auditoria
```

Levanta Vite y Django solo si no los tienes ya corriendo. Para verlo pantalla a
pantalla: `npm run auditoria:ui`.

## Qué deja

| Archivo | Qué es |
|---|---|
| `informe-accesibilidad.md` | El informe, agrupado por regla. Es lo que hay que leer. |
| `.registro/hallazgos.jsonl` | Registro crudo, una línea por hallazgo. |
| `.informe-html/` | Informe de Playwright, con capturas y trazas de cada fallo. |
| `.auth/estado.json` | La sesión. **Contiene un token real**, por eso está en `.gitignore`. |

El informe se agrupa **por regla y no por pantalla** a propósito: el menú
lateral está en las treinta pantallas internas, así que un contraste flojo ahí
produce treinta hallazgos idénticos. Por pantalla se lee como treinta problemas;
por regla dice lo que es, un arreglo que cubre treinta pantallas.

## Que la corrida falle es lo normal

Cada pantalla con defectos falla su prueba, y las comprobaciones son «soft» para
que la corrida siga y mida todas antes de terminar en rojo. El objetivo de la
primera pasada es el inventario completo, no un semáforo.

Cuando el informe esté en cero y se quiera mantener ahí, esto sirve tal cual
como red de regresión: un botón nuevo sin etiqueta vuelve a ponerlo en rojo.

## Detalles que conviene saber antes de tocarlo

- La aplicación usa `HashRouter`: las direcciones son `/#/dashboard`. Navegar a
  `/dashboard` a secas devuelve el mismo `index.html` y se auditaría treinta
  veces la misma pantalla.
- Los hallazgos se escriben en disco según aparecen, no se acumulan en memoria.
  Playwright reinicia el worker tras cada prueba fallida, y aquí fallar es lo
  normal: en memoria, el informe salía con los datos de la última prueba.
- El inventario de pantallas (`rutas.ts`) está escrito a mano y no deducido del
  router. Una lista generada se mantiene sola, pero también deja de auditar sola
  lo que alguien borre.
- La auditoría comprueba que terminó en la ruta que pidió. Si la sesión no
  valiera, `RutaProtegida` mandaría todo al login y las treinta pantallas
  saldrían limpias por haber medido treinta veces el formulario de acceso.

---

# Circuito de producción de leche en polvo

`circuito-polvo.spec.ts` recorre **por pantalla** lo que hace un turno completo:
llegan dos camiones —entera y descremada—, Calidad los decide, se descargan en
sus estanques, Recepción analiza los dos, se compone y libera un vale de
estandarización, se abre el lote, se declaran los kilos y se arma el pallet.

Vive en el mismo directorio que la auditoría pero es otra cosa: **escribe**.
Cada corrida deja recepciones, análisis, un vale, un lote y un pallet en la base
contra la que apunta. Por eso tiene su propio proyecto y `npm run auditoria` ya
no lo incluye.

## Por qué por pantalla

La cadena ya está cubierta por API —`manage.py sembrar_flujo_demo`— y por unidad
en cada `tests_dominio`. Lo que ninguna de las dos comprueba es que **alguien
pueda recorrerla**: un desplegable vacío, un botón deshabilitado o una pantalla
que no ofrece el paso siguiente dejan el backend impecable y la planta detenida.

Sirvió: encontró que confirmar un análisis de silo se podía deshacer solo,
porque el autoguardado del formulario llegaba después de la confirmación y
reescribía `estado`. Las dos peticiones respondían 200 y el fallo aparecía dos
pantallas más allá, al transferir el vale. Está fijado en
`recepcion/tests_borrador_carrera.py`.

## Cómo se corre

Una vez, para dejar la planta en condiciones:

```powershell
cd backend
.venv\Scripts\python.exe manage.py configurar_inventario_inicial --empresa 2 --aplicar
.venv\Scripts\python.exe manage.py preparar_circuito_polvo --aplicar
.venv\Scripts\python.exe manage.py crear_usuario_e2e
.venv\Scripts\python.exe manage.py crear_usuario_e2e --usuario e2e_segunda_firma --clave "segunda-firma-e2e-ccaa"
```

Después, cada vez:

```powershell
cd frontend
$env:E2E_USUARIO = "e2e_auditoria"
$env:E2E_CLAVE = "auditoria-e2e-ccaa"
npm run circuito
```

## Por qué hacen falta dos cuentas

El análisis de silo exige **dos firmas de personas distintas** —quien realiza y
quien visualiza— y el backend rechaza con 409 que las ponga la misma. Es el
control de cuatro ojos del formato, no un capricho: sin la segunda cuenta el
circuito no pasa de la transferencia del vale.

## Lo que el circuito consume

Es leche de verdad. Cada corrida mete 25.000 L en un silo y 8.000 en un TK, y
deja en el silo de destino lo que el lote no se lleva. Los estanques se eligen
al arrancar entre los que tienen sitio —ordenados por lo que ya guardan—, así
que las corridas se reparten solas; pero **el sitio se acaba**. Cuando ninguno
admita 25.000 L, la prueba lo dice con esas palabras. Se libera despachando la
leche desde la pantalla de silos o, si la base es de pruebas, con
`manage.py limpiar_transaccional --aplicar`.

## Si falla el acceso

- **HTTP 429** — hay **dos** límites: 15 accesos por hora y cuenta
  (`THROTTLE_LOGIN_USUARIO`) y 60 por hora y dirección
  (`THROTTLE_LOGIN_IP`). Corriendo el circuito en serie se agota antes el de
  la dirección, y ese no nombra a nadie: el mensaje habla de la cuenta y la
  cuenta está libre. `manage.py desbloquear_login --listar` dice cuál de los
  dos saltó; se levanta con `--usuario` o con `--ip 127.0.0.1`.
- **HTTP 409** — quedó una sesión abierta. `auth.setup.ts` cierra la anterior
  antes de entrar, así que esto solo debería verse si la sesión la abrió otra
  máquina.

## Detalles que conviene saber antes de tocarlo

- Los formularios **autoguardan un borrador** y confirman aparte. Toda espera
  apunta a `confirmar-borrador`, nunca a «cualquier petición del módulo»:
  engancharse al autoguardado da el paso por hecho antes de tiempo, y la
  pantalla siguiente carga su lista —una sola vez— antes de que el dato exista.
- Las etiquetas de los formularios **no usan `htmlFor`**, así que `getByLabel`
  no las asocia. El ayudante `campo()` cubre las dos convenciones del proyecto.
  Que haga falta es un hallazgo de accesibilidad, no una comodidad de la prueba.
- `window.confirm` bloquea la descarga: Playwright **descarta** los diálogos por
  omisión, o sea que el operador simulado siempre diría que no.
- Navegar al mismo hash **no recarga**. Una ficha abierta sobre la lista sigue
  ahí, en una capa fija, interceptando clics sobre filas que la traza describe
  como perfectamente visibles.
- Toda respuesta de error queda anotada, se esperara o no. Un autoguardado que
  el servidor rechaza no rompe nada de inmediato: el formulario reintenta cada
  dos segundos y el fallo emerge después como un tiempo agotado sin causa. Así
  el motivo real sale en el informe.

---

# Flujo de evaporación

`evaporacion.spec.ts` recorre lo que hace Producción con la leche que la
estandarización dejó en el silo: abre el lote sobre un evaporador, prepara la
corrida, la inicia y la cierra declarando el precondensado. Se corre con
`npm run evaporacion`.

## Abrir el lote **es** iniciar la evaporación

No son dos cosas. Para la familia «polvo» el formulario de lote solo ofrece
evaporadores —«la torre Egron aparecerá después, únicamente cuando Calidad
libere el concentrado»— y `_encadenar_con_la_estandarizacion` deduce la etapa
del **tipo de máquina**: evaporador → evaporación, torre → secado. Elegir la
máquina equivocada no da error: el lote nace en otra etapa y simplemente no
aparece nunca en «Nueva evaporación».

## Dónde empieza

En un vale **ya liberado**. Componer y liberar el vale es estandarización, y lo
recorre `circuito-polvo.spec.ts`; repetirlo aquí sumaría minutos para volver a
comprobar lo mismo. Si no hay vale con saldo, la prueba lo dice y remite al
circuito.

Cada corrida toma 6.000 L del vale, no el saldo entero: un evaporador no
procesa veinte mil litros de una vez, y así un vale de 20.000 L alimenta tres
corridas en vez de una.

## Qué vale sirve, y por qué hay que probar varios

Uno vale si cumple **las dos** condiciones, que fallan por motivos distintos:

- **tiene OP programada de su producto** — el formulario filtra las órdenes por
  el producto del vale, así que sin ella el desplegable queda vacío;
- **su familia va a un evaporador** — un vale de crema tiene orden y tiene
  máquinas, pero son líneas y envasadoras.

La prueba los recorre igual que el operador. `preparar_circuito_polvo` programa
la OP mirando qué vales tienen saldo, no un producto fijo: una orden del
producto que toca pero sin leche disponible bloquea exactamente igual que no
tener ninguna.

## El silo de origen se analiza *después* de abrir el lote

`iniciar_condensacion` exige que el silo estandarizado tenga análisis
confirmado, vigente y con las **dos firmas** —la misma puerta que protege la
transferencia del vale—.

El orden importa: abrir el lote genera una **salida** del silo, y una salida no
invalida la muestra —sacar leche no cambia la composición de la que queda—,
pero un ingreso sí. Analizar antes dejaría la muestra vencida si algún vale
descargara ahí entremedio.

## Lo que esta prueba destapó

Tres veces el mismo patrón: **la pantalla ofrece lo que el backend va a
rechazar**.

1. **Vales sin saldo real.** El desplegable contaba el consumo uniendo por
   `movimiento.lote`; la regla que bloquea lo cuenta por `origen_id` y acotando
   al silo del vale. Con un movimiento que tiene `origen_id` y no `lote` —los
   hay— el desplegable ofrecía 20.000 L libres y el formulario, ya completo,
   respondía «quedan 0,00 L». Corregido: ahora la pantalla usa
   `litros_ya_tomados`, la misma función que la regla.
2. **Silos bloqueados por Calidad como destino.** `opciones-alta` ofrece todos
   los silos activos sin mirar su estado. Escribe «Bloqueado por Calidad» en la
   opción pero no la deshabilita, y el rechazo llega al **cerrar** —cuando el
   evaporador ya trabajó—. Sin corregir; la prueba filtra por «Disponible».
3. **Máquinas ocupadas por lotes anulados.** Anular un lote **no cierra su
   `EjecucionProceso`**, así que el evaporador queda ocupado para siempre. Con
   tres evaporadores, tres corridas abandonadas dejan la planta sin ninguno, y
   el único síntoma es «Máquina ocupada por otra corrida» sobre una máquina que
   nadie usa. Sin corregir.
