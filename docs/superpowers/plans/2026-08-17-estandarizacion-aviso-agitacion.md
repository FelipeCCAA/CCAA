# Los 30 minutos de agitación avisan, no bloquean — Plan de implementación

> **Para quien ejecute esto con agentes:** SUB-SKILL REQUERIDA — usa
> `superpowers:subagent-driven-development` (recomendado) o
> `superpowers:executing-plans` para implementarlo tarea por tarea. Los pasos
> usan casillas (`- [ ]`) para seguimiento.

**Objetivo:** que `registrar_muestra` acepte una muestra tomada antes de los 30
minutos de agitación advirtiendo, en vez de rechazarla, y que el vale guarde
cuándo se muestreó para que la advertencia sea auditable.

**Arquitectura:** el aviso lo produce el servidor —que es quien tiene el reloj—
y viaja como lista de motivos, siguiendo la convención del proyecto de que las
decisiones devuelven motivos y no un booleano. Un campo nuevo, `muestreado_en`,
congela `minutos_agitando`; que la muestra fue temprana se deriva comparando, no
se guarda como bandera.

**Stack:** Django 6.0.7 + DRF sobre PostgreSQL 17; React 19 + TypeScript + Vite
en el frontend.

**Spec:** `docs/superpowers/specs/2026-08-17-estandarizacion-aviso-agitacion-design.md`

## Restricciones globales

- **Rama:** `feature-estandarizaciónfix`. No mezclar con `main`.
- **Español** en identificadores, comentarios, mensajes y UI. Fechas ISO.
- **`MINUTOS_DE_AGITACION = 30` no se toca ni se hace configurable.** Pasa de
  umbral de bloqueo a umbral de aviso, nada más.
- **La hora la pone el servidor.** Ni el inicio de la agitación ni la hora del
  muestreo se aceptan del cliente.
- **No tocar `calidad`, el checklist del lote ni `puede_liberar`.**
- **La máquina de estados no cambia.** `TRANSICIONES` queda igual: muestrear sin
  haber agitado sigue fallando por transición inválida.
- **Después de `makemigrations`, correr `migrate`.** El runner migra solo la base
  de pruebas: una migración generada y no aplicada deja la suite verde y revienta
  en el navegador.

## Cómo correr las pruebas

**Cinco variables de entorno, todas obligatorias.** Sin `DJANGO_ENV=test` los
defaults de tenant de `usuarios/tenancy.py:16` no existen y las seis clases de
`tests_vale.py` mueren en `setUpClass` con `empresa_id` nulo. Sin las cuatro
`CCAA_INITIAL_*`, la migración `usuarios.0008` aborta al crear la base de
pruebas. Verificado el 2026-08-17: con esto, `estandarizacion` + `procesos` dan
83 pruebas en OK.

```powershell
Set-Location "C:\Users\Ingjs\OneDrive - Campos Australes\Gestión TI\GitHub\CCAA\backend"
$env:DJANGO_ENV='test'
$env:CCAA_INITIAL_COMPANY_RUT='76.123.456-7'
$env:CCAA_INITIAL_COMPANY_NAME='Campos Australes'
$env:CCAA_INITIAL_BRANCH_CODE='CCAA'
$env:CCAA_INITIAL_BRANCH_NAME='Planta CCAA'
& .\.venv\Scripts\python.exe manage.py test estandarizacion procesos --noinput
```

`--noinput` no es opcional: si una corrida anterior murió a media creación, la
base `test_ccaa` queda en pie y el runner se cuelga preguntando por consola si
borrarla. Sin `--noinput` eso es un `EOFError`.

El intérprete es `backend\.venv\Scripts\python.exe`. El Python del sistema no
tiene Django instalado.

Frontend: `cd frontend && npx tsc -b`. **`npx tsc --noEmit` a secas no comprueba
nada** — `tsconfig.json` es de tipo solución (`files: []` + referencias) y sale
con 0 sin mirar un archivo.

---

### Tarea 1: `muestreado_en` congela el reloj de la agitación

Hoy `minutos_agitando` se calcula contra `timezone.now()`, así que un vale mirado
al día siguiente informa 1.400 minutos. Sin congelarlo, la advertencia de
muestreo temprano no se puede auditar después: es el cimiento de todo lo demás.

**Archivos:**
- Modificar: `backend/estandarizacion/models.py` (campo nuevo tras
  `agitacion_desde` en la línea 112; propiedad `minutos_agitando` en 160-166)
- Crear: `backend/estandarizacion/migrations/0002_muestreado_en.py` (generada)
- Probar: `backend/estandarizacion/tests_vale.py` (clase `AgitacionTests`)

**Interfaces:**
- Produce: `ValeEstandarizacion.muestreado_en` (`DateTimeField`, nulable) y
  `ValeEstandarizacion.minutos_agitando` → `float | None`, ahora congelado.

- [ ] **Paso 1: escribir la prueba que falla**

En `tests_vale.py`, dentro de `class AgitacionTests`, después de
`test_el_reloj_lo_pone_el_servidor`:

```python
    def test_muestreado_en_congela_los_minutos_de_agitacion(self):
        """
        Sin el sello, `minutos_agitando` cuenta contra el reloj actual: un vale
        mirado más tarde informa el tiempo transcurrido y no el que agitó, y la
        advertencia de muestreo temprano deja de ser auditable.
        """
        vale = self.llevar_a_agitando(self.crear_vale(), minutos=40)

        vale.muestreado_en = vale.agitacion_desde + timedelta(minutes=12)
        vale.save(update_fields=["muestreado_en"])
        vale.refresh_from_db()

        # 12, no 40: cuenta hasta la muestra, no hasta ahora.
        self.assertAlmostEqual(vale.minutos_agitando, 12, places=1)

    def test_sin_muestrear_los_minutos_siguen_corriendo(self):
        vale = self.llevar_a_agitando(self.crear_vale(), minutos=40)

        self.assertIsNone(vale.muestreado_en)
        self.assertAlmostEqual(vale.minutos_agitando, 40, places=1)
```

- [ ] **Paso 2: correr y ver que falla**

Comando: el bloque de «Cómo correr las pruebas», con
`manage.py test estandarizacion.tests_vale.AgitacionTests --noinput`
Esperado: FAIL — `AttributeError` o `TypeError` sobre `muestreado_en`, que
todavía no existe.

- [ ] **Paso 3: agregar el campo**

En `models.py`, justo después del bloque de `agitacion_desde` (línea 112):

```python
    muestreado_en = models.DateTimeField(
        "Hora del muestreo", null=True, blank=True,
        help_text=(
            "Cuándo se tomó la muestra. Congela «minutos agitando»: sin este "
            "sello el contador sigue creciendo contra el reloj actual y "
            "después no hay forma de saber si la muestra fue temprana."
        ),
    )
```

- [ ] **Paso 4: congelar `minutos_agitando`**

Reemplazar la propiedad completa (líneas 160-166):

```python
    @property
    def minutos_agitando(self):
        """
        Cuánto agitó. Mientras no se muestrea cuenta contra el reloj actual;
        una vez muestreado se congela en la hora de la muestra.

        Congelarlo es lo que hace auditable el aviso de muestreo temprano: sin
        el sello, un vale mirado al día siguiente informa mil cuatrocientos
        minutos y el aviso ya no se puede contrastar con nada.
        """
        if self.agitacion_desde is None:
            return None

        hasta = self.muestreado_en or timezone.now()

        return (hasta - self.agitacion_desde).total_seconds() / 60
```

- [ ] **Paso 5: generar y aplicar la migración**

```powershell
& .\.venv\Scripts\python.exe manage.py makemigrations estandarizacion
& .\.venv\Scripts\python.exe manage.py migrate
```

El `migrate` no es opcional: el runner migra solo la base de pruebas.

- [ ] **Paso 6: correr y ver que pasa**

Comando: `manage.py test estandarizacion --noinput`
Esperado: PASS en las dos nuevas, y el resto de `estandarizacion` sin regresión.

- [ ] **Paso 7: commit**

```bash
git add backend/estandarizacion/models.py backend/estandarizacion/migrations/ backend/estandarizacion/tests_vale.py
git commit -m "El vale sella cuándo se muestreó y congela los minutos de agitación"
```

---

### Tarea 2: `avisos_de_muestreo` reemplaza a `puede_muestrear`

El booleano se cambia por una lista de motivos, que es la convención del
proyecto para las decisiones. Vacía significa que no hay nada que advertir.

**Archivos:**
- Modificar: `backend/estandarizacion/models.py` (propiedad `puede_muestrear`,
  líneas 168-180)
- Probar: `backend/estandarizacion/tests_vale.py` (clase `AgitacionTests`)

**Interfaces:**
- Consume: `minutos_agitando` congelado (Tarea 1).
- Produce: `ValeEstandarizacion.avisos_de_muestreo` → `list[str]`. Desaparece
  `ValeEstandarizacion.puede_muestrear`.

- [ ] **Paso 1: escribir las pruebas que fallan**

En `tests_vale.py`, en `class AgitacionTests`:

```python
    def test_avisa_cuando_se_muestrea_antes_de_los_treinta(self):
        vale = self.llevar_a_agitando(self.crear_vale(), minutos=12)

        avisos = vale.avisos_de_muestreo

        self.assertEqual(len(avisos), 1)
        self.assertIn("12", avisos[0])
        self.assertIn(str(MINUTOS_DE_AGITACION), avisos[0])

    def test_cumplidos_los_treinta_no_avisa_nada(self):
        vale = self.llevar_a_agitando(self.crear_vale())

        self.assertEqual(vale.avisos_de_muestreo, [])

    def test_sin_agitar_no_hay_nada_que_avisar(self):
        """
        Un vale que no arrancó el reloj no se puede muestrear igual: lo impide
        la transición, no este aviso. Devolver un aviso aquí sería advertir de
        algo que ya está prohibido por otra vía.
        """
        vale = self.crear_vale()

        self.assertIsNone(vale.agitacion_desde)
        self.assertEqual(vale.avisos_de_muestreo, [])
```

- [ ] **Paso 2: correr y ver que falla**

Comando: `manage.py test estandarizacion.tests_vale.AgitacionTests --noinput`
Esperado: FAIL — `AttributeError: 'ValeEstandarizacion' object has no attribute 'avisos_de_muestreo'`.

- [ ] **Paso 3: reemplazar la propiedad**

En `models.py`, borrar `puede_muestrear` (líneas 168-180) y poner en su lugar:

```python
    @property
    def avisos_de_muestreo(self) -> list[str]:
        """
        Qué advertir sobre la agitación. Lista vacía: nada que advertir.

        **Avisa, no bloquea** (decisión de planta, 2026-08-17). Antes de los
        treinta minutos la mezcla no es homogénea y el RC medido puede no ser
        el del silo, pero detener la operación por eso lo decide la planta y no
        el sistema. Mismo criterio que `codigo_lote_valido` y que la leche
        asignada del lote, que avisan sin frenar.

        Sirve en los dos momentos sin ramificar, porque se apoya en
        `minutos_agitando`: **antes** de muestrear cuenta contra el reloj actual
        y dice cuánto lleva; **después** cuenta contra `muestreado_en` y dice a
        los cuántos minutos se muestreó. Es la misma frase leída en dos
        instantes, no dos cálculos.

        Devuelve motivos y no un booleano porque un `False` no le dice al
        operador qué pasó, y es la convención del resto del proyecto.
        """
        minutos = self.minutos_agitando

        # Sin reloj arrancado no hay nada que advertir: muestrear sin agitar ya
        # lo impide la transición de estado.
        if minutos is None or minutos >= MINUTOS_DE_AGITACION:
            return []

        return [
            f"Agitó {minutos:.0f} minutos de los {MINUTOS_DE_AGITACION} que "
            "pide el procedimiento: antes de eso la mezcla no es homogénea y "
            "la muestra puede no medir el silo."
        ]
```

- [ ] **Paso 4: correr y ver que pasa**

Comando: `manage.py test estandarizacion --noinput`
Esperado: las tres nuevas en PASS. **`serializers.py` todavía referencia
`puede_muestrear` y las pruebas de API van a fallar** — se arregla en la Tarea 4;
si quieres el commit en verde, haz las Tareas 2, 3 y 4 antes de commitear.

- [ ] **Paso 5: commit**

```bash
git add backend/estandarizacion/models.py backend/estandarizacion/tests_vale.py
git commit -m "Los minutos de agitación devuelven motivos, no un booleano"
```

---

### Tarea 3: el servicio avisa en vez de rechazar

**Archivos:**
- Modificar: `backend/estandarizacion/servicios.py` (import línea 15;
  `registrar_muestra` 133-163; `reagitar` 208-229)
- Modificar: `backend/estandarizacion/tests_vale.py` (invertir las pruebas de
  las líneas 145 y 273)

**Interfaces:**
- Consume: `avisos_de_muestreo` (Tarea 2), `muestreado_en` (Tarea 1).
- Produce: `registrar_muestra(*, vale_id, grasa, sng)` → `(vale, avisos)`, donde
  `avisos` es `list[str]`. Antes devolvía solo `vale`.

- [ ] **Paso 1: invertir la prueba del bloqueo**

En `tests_vale.py`, reemplazar `test_no_se_muestrea_antes_de_los_treinta_minutos`
completo (líneas 145-161) por:

```python
    def test_muestrear_antes_de_los_treinta_avisa_pero_no_frena(self):
        """
        Decisión de planta (2026-08-17): la regla de §10.3 dejó de bloquear.
        Una muestra temprana mide una mezcla que todavía no es homogénea, así
        que el vale queda con el aviso y con la hora del muestreo — que es lo
        que permite auditar después cuánto agitó de verdad.
        """
        vale = self.llevar_a_agitando(self.crear_vale(), minutos=20)

        actualizado, avisos = servicios.registrar_muestra(
            vale_id=vale.pk, grasa=1.79, sng=8.9
        )

        self.assertEqual(actualizado.estado, ValeEstandarizacion.Estado.MUESTREADO)
        self.assertEqual(len(avisos), 1)
        self.assertIn("20", avisos[0])

        vale.refresh_from_db()
        self.assertIsNotNone(vale.muestreado_en)
        self.assertAlmostEqual(vale.minutos_agitando, 20, places=0)

    def test_muestrear_a_tiempo_no_devuelve_avisos(self):
        vale = self.llevar_a_agitando(self.crear_vale())

        _, avisos = servicios.registrar_muestra(
            vale_id=vale.pk, grasa=1.79, sng=8.9
        )

        self.assertEqual(avisos, [])
```

- [ ] **Paso 2: invertir la prueba del reagitado**

En `tests_vale.py`, reemplazar las líneas 273-275 (el bloque que empieza con el
comentario `# Y no se puede muestrear de inmediato`) por:

```python
        # Se puede muestrear de inmediato, pero avisa: el reloj arrancó de nuevo.
        self.assertIsNone(vale.muestreado_en)

        _, avisos = servicios.registrar_muestra(
            vale_id=vale.pk, grasa=1.79, sng=8.9
        )

        self.assertEqual(len(avisos), 1)
```

- [ ] **Paso 3: agregar la prueba del sello que se limpia**

En `tests_vale.py`, en `class CorreccionTests`, después de
`test_reagitar_reinicia_el_reloj_y_borra_el_analisis`:

```python
    def test_reagitar_limpia_el_sello_del_muestreo_anterior(self):
        """
        Si `muestreado_en` sobrevive al reagitado queda **antes** del nuevo
        `agitacion_desde`, y `minutos_agitando` sale negativo: el vale diría
        que agitó menos que nada y el aviso quedaría deformado.
        """
        vale = self.llevar_a_agitando(self.crear_vale())
        servicios.registrar_muestra(vale_id=vale.pk, grasa=2.20, sng=8.9)
        servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        vale.refresh_from_db()
        self.assertIsNotNone(vale.muestreado_en)

        servicios.reagitar(vale_id=vale.pk)
        vale.refresh_from_db()

        self.assertIsNone(vale.muestreado_en)
        self.assertGreaterEqual(vale.minutos_agitando, 0)
```

- [ ] **Paso 4: correr y ver que fallan**

Comando: `manage.py test estandarizacion.tests_vale --noinput`
Esperado: FAIL — `ValueError: too many values to unpack` o `not enough values`,
porque `registrar_muestra` todavía devuelve solo el vale, y `muestreado_en`
sigue sin escribirse.

- [ ] **Paso 5: reescribir `registrar_muestra`**

Reemplazar la función completa (líneas 133-163):

```python
@transaction.atomic
def registrar_muestra(*, vale_id, grasa, sng):
    """
    Guarda el análisis de la muestra y deja el vale listo para decidir.

    **Los treinta minutos avisan, no bloquean** (decisión de planta,
    2026-08-17). Una muestra tomada antes mide una mezcla que todavía no es
    homogénea, así que el RC que devuelve puede no ser el del silo; el vale
    queda con el aviso y con `muestreado_en`, que es lo que después permite
    auditar cuánto agitó de verdad. Lo que sigue impidiendo muestrear sin haber
    agitado nada es la transición de estado, no esta función.

    Devuelve `(vale, avisos)`, como `decidir` devuelve `(vale, evaluacion)`: la
    vista necesita el resultado del cálculo y no solo el objeto guardado.
    """
    vale = ValeEstandarizacion.objects.select_for_update().get(pk=vale_id)
    _exigir_transicion(vale, ValeEstandarizacion.Estado.MUESTREADO)

    if sng is None or float(sng) <= 0:
        raise ValidationError(
            "Sin sólidos no grasos no hay RC que calcular: revisa el análisis."
        )

    vale.grasa_real = grasa
    vale.sng_real = sng
    vale.muestreado_en = timezone.now()
    vale.estado = ValeEstandarizacion.Estado.MUESTREADO
    vale.save(update_fields=[
        "grasa_real", "sng_real", "muestreado_en", "estado",
    ])

    # Después de sellar, no antes: así el aviso que devuelve la acción es el
    # mismo que la ficha del vale mostrará más tarde. Calculado antes contaría
    # contra el reloj actual y los dos podrían no coincidir.
    return vale, vale.avisos_de_muestreo
```

- [ ] **Paso 6: quitar el import que quedó sin uso**

En `servicios.py`, línea 15, `MINUTOS_DE_AGITACION` ya no se usa:

```python
from .models import ValeEstandarizacion
```

- [ ] **Paso 7: que `reagitar` limpie el sello**

En `reagitar`, reemplazar el bloque de las líneas 222-227:

```python
    # El análisis anterior ya no describe lo que hay en el silo.
    vale.grasa_real = None
    vale.sng_real = None
    # Y el sello del muestreo anterior tampoco: conservarlo lo dejaría *antes*
    # del nuevo `agitacion_desde`, y `minutos_agitando` saldría negativo.
    vale.muestreado_en = None
    vale.save(update_fields=[
        "estado", "agitacion_desde", "grasa_real", "sng_real", "muestreado_en",
    ])
```

- [ ] **Paso 8: correr y ver que pasa**

Comando: `manage.py test estandarizacion.tests_vale --noinput`
Esperado: PASS en todo salvo `ApiTests`, que arregla la Tarea 4.

- [ ] **Paso 9: commit**

```bash
git add backend/estandarizacion/servicios.py backend/estandarizacion/tests_vale.py
git commit -m "Muestrear antes de los 30 minutos avisa en vez de fallar"
```

---

### Tarea 4: la API responde 200 con los avisos

**Archivos:**
- Modificar: `backend/estandarizacion/serializers.py` (líneas 27-29 y la lista
  `fields` en 34-45)
- Modificar: `backend/estandarizacion/views.py` (acción `muestrear`, 123-137)
- Modificar: `backend/estandarizacion/tests_vale.py` (clase `ApiTests`, la prueba
  de la línea 384)

**Interfaces:**
- Consume: `registrar_muestra` → `(vale, avisos)` (Tarea 3),
  `avisos_de_muestreo` (Tarea 2).
- Produce: el JSON del vale incorpora `muestreado_en` (ISO 8601 o `null`) y
  `avisos` (lista de textos). Desaparece `puede_muestrear`.

- [ ] **Paso 1: invertir la prueba del 409**

En `tests_vale.py`, reemplazar `test_muestrear_antes_de_tiempo_responde_409`
completo (líneas 384-394) por:

```python
    def test_muestrear_antes_de_tiempo_responde_200_con_aviso(self):
        """
        Era un 409. Desde 2026-08-17 la regla avisa y no bloquea, así que la
        muestra entra y el aviso viaja en el cuerpo.
        """
        vale = self.llevar_a_agitando(self.crear_vale(), minutos=5)

        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{vale.pk}/muestrear/",
            {"grasa": 1.79, "sng": 8.9},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)

        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["estado"], "muestreado")
        self.assertEqual(len(cuerpo["avisos"]), 1)
        self.assertIn("5", cuerpo["avisos"][0])
        self.assertIsNotNone(cuerpo["muestreado_en"])

    def test_muestrear_a_tiempo_responde_sin_avisos(self):
        vale = self.llevar_a_agitando(self.crear_vale())

        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{vale.pk}/muestrear/",
            {"grasa": 1.79, "sng": 8.9},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["avisos"], [])
```

- [ ] **Paso 2: corregir el docstring que menciona la regla vieja**

En `tests_vale.py` línea 372, el docstring de
`test_el_analisis_tampoco_se_escribe_por_patch` dice «Muestrear exige los 30
minutos; un PATCH los esquivaría». La prueba sigue siendo válida —el análisis no
se escribe por PATCH— pero el motivo cambió:

```python
    def test_el_analisis_tampoco_se_escribe_por_patch(self):
        """
        El análisis entra por la acción, que es la que sella `muestreado_en` y
        calcula los avisos. Un PATCH lo escribiría sin nada de eso.
        """
```

- [ ] **Paso 3: correr y ver que falla**

Comando: `manage.py test estandarizacion.tests_vale.ApiTests --noinput`
Esperado: FAIL — `KeyError: 'avisos'`, y además un error al serializar porque
`puede_muestrear` ya no existe en el modelo.

- [ ] **Paso 4: actualizar el serializer**

En `serializers.py`, reemplazar las líneas 27-29:

```python
    rc_real = serializers.FloatField(read_only=True)
    minutos_agitando = serializers.FloatField(read_only=True)
    # Motivos y no un booleano: un `False` no le dice al operador qué pasó.
    avisos = serializers.ListField(
        source="avisos_de_muestreo",
        child=serializers.CharField(),
        read_only=True,
    )
    evaluacion = serializers.SerializerMethodField()
```

Y en `Meta.fields` (líneas 42-43), cambiar esas dos líneas por:

```python
            "estado", "agitacion_desde", "muestreado_en",
            "grasa_real", "sng_real",
            "rc_real", "minutos_agitando", "avisos", "evaluacion",
```

En `Meta.read_only_fields` (líneas 48-51), agregar `muestreado_en` — lo sella el
servicio, no un PATCH:

```python
        read_only_fields = [
            "estado", "agitacion_desde", "muestreado_en",
            "grasa_real", "sng_real",
            "responsable", "creado_en",
        ]
```

- [ ] **Paso 5: desempaquetar en la vista**

En `views.py`, en la acción `muestrear` (línea 129), `registrar_muestra` ahora
devuelve una tupla:

```python
        try:
            vale, _ = servicios.registrar_muestra(
                vale_id=self.get_object().pk,
                grasa=entrada.validated_data["grasa"],
                sng=entrada.validated_data["sng"],
            )
        except DjangoValidationError as error:
            return _conflicto(error)
```

Los avisos no se agregan a mano al cuerpo: el serializer ya los expone desde
`avisos_de_muestreo`, y con `muestreado_en` sellado dan el mismo texto. Una
segunda copia en la respuesta podría contradecir a la de la ficha.

Las otras llamadas a `registrar_muestra` —`procesos/tests_estandarizacion.py:108`
y `sembrar_flujo_demo.py:298`— no usan el valor de retorno y no hay que tocarlas.

- [ ] **Paso 6: correr toda la suite**

Comando: `manage.py test estandarizacion procesos --noinput`
Esperado: OK, sin errores ni fallos.

- [ ] **Paso 7: commit**

```bash
git add backend/estandarizacion/serializers.py backend/estandarizacion/views.py backend/estandarizacion/tests_vale.py
git commit -m "La API del muestreo responde 200 con los avisos de agitación"
```

---

### Tarea 5: la pantalla muestra el aviso

El formulario de muestreo **ya está siempre habilitado** — el botón solo se
deshabilita por `ocupado`, nunca por tiempo—, así que aquí no hay que
desbloquear nada. Lo que cambia es el texto del cronómetro, que hoy da permiso, y
que el aviso se vea.

`puede_muestrear` está declarado en el tipo del servicio pero **no lo usa nadie**:
quitarlo no rompe ninguna pantalla.

**Archivos:**
- Modificar: `frontend/src/services/estandarizacion.service.ts` (líneas 44-49)
- Modificar: `frontend/src/pages/Estandarizacion/Cronometro.tsx` (líneas 56-64)
- Modificar: `frontend/src/pages/Estandarizacion/Estandarizacion.tsx`
  (bloque de la evaluación, líneas 271-275)

**Interfaces:**
- Consume: el JSON de la Tarea 4 (`avisos: string[]`, `muestreado_en`).

- [ ] **Paso 1: actualizar el tipo**

En `estandarizacion.service.ts`, en el bloque de líneas 44-49, cambiar
`puede_muestrear: boolean;` por los dos campos nuevos:

```ts
  agitacion_desde: string | null;
  muestreado_en: string | null;
  minutos_agitando: number | null;
  avisos: string[];
```

- [ ] **Paso 2: el cronómetro informa en vez de dar permiso**

En `Cronometro.tsx`, reemplazar el bloque de las líneas 56-64:

```tsx
  const faltan = Math.max(0, minutosExigidos - minutos);

  if (faltan <= 0) {
    return (
      <Marco tono="emerald">
        Agitando hace {minutos.toFixed(0)} min — cumplidos los{" "}
        {minutosExigidos} del procedimiento.
      </Marco>
    );
  }
```

Y el bloque de las líneas 68-81, que hoy habla como si frenara:

```tsx
  return (
    <Marco tono="indigo">
      <span className="font-medium">
        Faltan {Math.ceil(faltan)} min de agitación
      </span>{" "}
      — antes de los {minutosExigidos} la mezcla no es homogénea y la muestra
      puede no medir el silo. Se puede muestrear igual; queda registrado.
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/60">
        <div
          className="h-full rounded-full bg-indigo-500 transition-all"
          style={{ width: `${porcentaje}%` }}
        />
      </div>
    </Marco>
  );
```

- [ ] **Paso 3: mostrar los avisos en la ficha**

En `Estandarizacion.tsx`, justo antes del bloque de `vale.evaluacion` (línea
271), agregar:

```tsx
                {vale.avisos.length > 0 && (
                  <ul className="mt-4 space-y-2">
                    {vale.avisos.map((aviso) => (
                      <li
                        key={aviso}
                        className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
                      >
                        {aviso}
                      </li>
                    ))}
                  </ul>
                )}
```

Mismo tratamiento visual que ya recibe `evaluacion.motivo`: es la misma clase de
información —algo que el operador debe saber y que no le impide seguir— y darle
un estilo propio sugeriría una gravedad distinta.

- [ ] **Paso 4: compilar**

```powershell
Set-Location "C:\Users\Ingjs\OneDrive - Campos Australes\Gestión TI\GitHub\CCAA\frontend"
npx tsc -b
```

Esperado: sin errores. Si sale limpio a la primera, comprobar que de verdad
compiló algo: `tsc --noEmit` a secas no mira nada en este proyecto.

- [ ] **Paso 5: verlo funcionando**

Con el backend en `127.0.0.1:8000` y el frontend en `localhost:5173`, abrir un
vale en estado «agitando» antes de los 30 minutos y registrar una muestra. La
muestra debe entrar, el vale pasar a «muestreado» y el aviso ámbar aparecer en la
ficha.

- [ ] **Paso 6: commit**

```bash
git add frontend/src/services/estandarizacion.service.ts frontend/src/pages/Estandarizacion/
git commit -m "La pantalla avisa del muestreo temprano en vez de anunciar un bloqueo"
```

---

### Tarea 6: corregir la documentación que quedó mintiendo

Tres documentos afirman que no se muestrea antes de los 30 minutos. Sin esto,
el próximo que los lea va a creer que el sistema garantiza algo que ya no
garantiza.

**Archivos:**
- Modificar: `docs/REGLAS_DE_PLANTA.md` (§3)
- Modificar: `CLAUDE.md` (párrafo de Estandarización)
- Modificar: `backend/estandarizacion/models.py` (comentario de
  `MINUTOS_DE_AGITACION`, líneas 27-33)

- [ ] **Paso 1: el comentario de la constante**

En `models.py`, reemplazar el comentario de las líneas 27-33:

```python
#: Minutos de agitación que pide el procedimiento antes de muestrear (§10.3).
#:
#: Es un mínimo físico: una muestra tomada antes mide una mezcla que todavía no
#: es homogénea, y el RC que devuelve no es el del silo.
#:
#: **Avisa, no bloquea** desde 2026-08-17, por decisión de planta: el sistema
#: advierte y deja constancia en `muestreado_en`, pero no detiene la operación.
#: Antes rechazaba la muestra, y entonces no quedaba registro de nada; ahora no
#: la impide pero sí queda escrito cuánto agitó cada vale.
MINUTOS_DE_AGITACION = 30
```

- [ ] **Paso 2: `docs/REGLAS_DE_PLANTA.md` §3**

**Solo cambia el bloque de las líneas 208-211**, que es el que describe lo que
hace el sistema. Reemplazar:

```markdown
- **No se muestrea antes de los 30 minutos** (`MINUTOS_DE_AGITACION`). Una
  muestra tomada antes mide una mezcla que todavía no es homogénea. La hora de
  inicio la pone el servidor: aceptarla del cliente permitiría declarar treinta
  minutos que no ocurrieron.
```

por:

```markdown
- **Muestrear antes de los 30 minutos avisa, no bloquea** (`MINUTOS_DE_AGITACION`,
  decisión de planta del 2026-08-17). Una muestra tomada antes mide una mezcla
  que todavía no es homogénea, así que el vale queda con el aviso y con la hora
  del muestreo en `muestreado_en` — que es lo que después permite auditar cuánto
  agitó de verdad. Antes la rechazaba, y entonces no quedaba constancia de nada.
  La hora la sigue poniendo el servidor: aceptarla del cliente permitiría
  declarar treinta minutos que no ocurrieron.
```

**No tocar la línea 158** («Transferir, agitar **30 minutos**, tomar muestra»):
describe el procedimiento de planta, que no cambió. **Tampoco la 348**, que
inventaria el tiempo de agitación como aporte del documento — sigue siéndolo.

Ojo con el §3 de arriba: la frase que lo introduce dice «hay **tres** reglas que
solo se sostienen así». Siguen siendo tres —esta pasa de bloquear a avisar, pero
sigue necesitando ser una acción del servicio para poder sellar la hora—, así que
el número no cambia.

- [ ] **Paso 3: `CLAUDE.md`**

En el párrafo de **Estandarización**, reemplazar exactamente:

```markdown
**no se muestrea antes de 30 minutos** de agitación (antes la mezcla no es
homogénea y la muestra no mide el silo; la hora la pone el servidor)
```

por:

```markdown
**muestrear antes de 30 minutos avisa pero no frena** (desde 2026-08-17: antes
la mezcla no es homogénea, pero detener la operación lo decide la planta; el
vale sella `muestreado_en` y el aviso queda auditable — la hora la pone el
servidor)
```

Es la misma corrección que ya llevan `codigo_lote_valido` y la leche asignada en
ese mismo archivo, y conviene que las tres se lean igual.

- [ ] **Paso 4: revisar que no quede ninguna otra afirmación vieja**

```bash
grep -rn "30 minutos\|treinta minutos\|MINUTOS_DE_AGITACION" --include=*.md --include=*.py --include=*.tsx .
```

Revisar cada resultado. El comentario de `sembrar_flujo_demo.py:289-292` dice que
retrasa el reloj «en vez de saltarse la comprobación»; el truco ya no hace falta
pero tampoco molesta —un vale de demostración agitado 35 minutos es el caso
normal que conviene sembrar—, así que basta con actualizar el comentario para que
no afirme que existe una comprobación que rechaza.

- [ ] **Paso 5: correr todo por última vez**

```powershell
& .\.venv\Scripts\python.exe manage.py test --noinput
```

Esperado: OK en la suite completa, no solo en `estandarizacion`.

- [ ] **Paso 6: commit**

```bash
git add CLAUDE.md docs/REGLAS_DE_PLANTA.md backend/estandarizacion/models.py backend/usuarios/management/commands/sembrar_flujo_demo.py
git commit -m "La documentación dice que los 30 minutos avisan, no bloquean"
```
