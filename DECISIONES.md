# Decisiones técnicas

Registro de las decisiones que cambian la forma del sistema y no se pueden
deducir leyendo el código. Cada una explica **qué se decidió, por qué, y qué se
pierde** — esto último es lo que suele faltar cuando alguien reabre la
discusión seis meses después.

Las decisiones de **modelado** (por qué la ocupación de un silo es un saldo,
por qué el resultado de calidad no se guarda) viven en
[prototipo/MODELO_DATOS.md](prototipo/MODELO_DATOS.md). Aquí van las de
plataforma e infraestructura.

Más recientes primero.

---

## 001 · PostgreSQL en vez de SQLite

**Fecha:** 2026-07-29 · **Estado:** aplicada

### Qué se decidió

El proyecto corre sobre **PostgreSQL**. La configuración de la base pasa a
variables de entorno (`backend/.env`, con `backend/.env.example` de plantilla).

Queda una salida explícita, `DB_ENGINE=sqlite`, para trabajar sin un PostgreSQL
levantado. **No es equivalente** y el sistema lo dice en voz alta cada vez que
arranca.

### Por qué

**1. Es la única forma de proteger la firma de una liberación.**

Es la razón que decidió el cambio. Firmar una liberación lee el checklist,
decide, y escribe la autorización:

```python
with transaction.atomic():
    contexto = _contexto_del_lote(lote, bloquear=True)   # lee
    decision = dominio.puede_liberar(**contexto)         # decide
    liberacion.save()                                    # escribe
```

`transaction.atomic()` **no basta**, y conviene tenerlo claro porque es fácil
suponer lo contrario: garantiza que la escritura sea todo-o-nada, no que lo
leído siga siendo cierto al escribir. Entre la lectura y la escritura, otro
usuario puede desmarcar un documento del checklist, y la liberación queda
firmada contra un expediente que ya no está completo. Eso es exactamente lo que
el sistema existe para impedir.

Lo que cierra esa ventana es `select_for_update()`, que bloquea las filas
leídas hasta confirmar la transacción. Y ahí está el problema:

```
motor    : sqlite      has_select_for_update = False
motor    : postgresql  has_select_for_update = True
```

En SQLite, `select_for_update()` **no falla: no hace nada**. Django comprueba
la capacidad del backend y, si no está, no emite el `FOR UPDATE`. El código
queda idéntico, la llamada se compila a nada y la garantía desaparece sin que
nadie se entere. Es la peor forma de perder una protección — mucho peor que un
error, porque un error se ve.

**2. Un solo escritor a la vez.**

SQLite serializa las escrituras a nivel de archivo. Recepción trabaja en turnos
A/B/C —24/7— mientras Producción registra lotes y Calidad firma liberaciones.
Cuando dos escrituras coinciden, la segunda espera; pasado el timeout (5
segundos por defecto) revienta con `database is locked`. Es el escenario que el
[§7 del modelo](prototipo/MODELO_DATOS.md) advierte desde el principio:
«Recepción, Producción y Calidad son personas distintas en momentos distintos».

**3. Ya estaba anticipado.** `psycopg2-binary` estaba en `requirements.txt`
desde el primer commit. La decisión ya estaba tomada; solo faltaba ejecutarla.

**4. Ahora es gratis.** No hay datos productivos. Migrar es cambiar la
configuración y correr `migrate`. Con el histórico de `Produccion.xlsx` cargado
(~954 lotes) y gente usando el sistema, deja de serlo.

### Por qué no seguir en SQLite

SQLite no es un juguete y aguanta más de lo que se le atribuye. Si esto fuera
una aplicación de un solo turno con escrituras esporádicas, el cambio no se
justificaría por rendimiento.

Lo que inclina la balanza es el punto 1: hay una regla de auditoría que en
SQLite **no se puede proteger**, y no por falta de cuidado al programar sino
porque la plataforma no ofrece la primitiva. Ninguna cantidad de código lo
arregla.

### Qué cambió en el código

| Archivo | Cambio |
|---|---|
| [backend/config/settings.py](backend/config/settings.py) | `DATABASES` por entorno, PostgreSQL por defecto |
| [backend/calidad/views.py](backend/calidad/views.py) | `_contexto_del_lote(bloquear=True)` en el camino de la firma |
| [backend/calidad/checks.py](backend/calidad/checks.py) | Check de arranque que delata al motor sin bloqueo |
| [backend/.env.example](backend/.env.example) | Plantilla de configuración |

Dos detalles del bloqueo que conviene no deshacer sin pensarlo:

- Se bloquean **los formularios y los análisis**, que son lo que la decisión
  lee y lo que otra persona puede estar tocando en el mismo turno. Las
  especificaciones también influyen en el veredicto, pero las cambia
  Administración muy de tarde en tarde; bloquearlas en cada firma sería caro
  para el riesgo que cubre.
- La consulta que bloquea **no lleva `select_related`**. Con el JOIN, el
  `FOR UPDATE` bloquearía además las filas del catálogo de documentos, que es
  un maestro compartido por todos los lotes: dos firmas de lotes distintos se
  estorbarían entre sí sin motivo.

### Qué se pierde, y cómo se avisa

Trabajar con `DB_ENGINE=sqlite` deja el sistema sin ese bloqueo. Para que eso
no pase inadvertido, el check `calidad.W001` / `calidad.E001` lo informa en
cada arranque, y la severidad distingue una decisión de un descuido:

| Situación | Resultado |
|---|---|
| PostgreSQL | nada |
| `DB_ENGINE=sqlite` puesto a mano | **aviso** — alguien lo pidió, pero ve qué pierde |
| Motor sin bloqueo que nadie pidió, con `DEBUG=False` | **error, no arranca** |

La severidad no depende solo de `DEBUG` a propósito: el runner de pruebas lo
apaga siempre, así que hacerlo depender de él convertiría el aviso en un error
que impide correr las pruebas en cualquier equipo sin PostgreSQL.

### Cómo comprobar que sigue en pie

```powershell
cd backend
python manage.py test calidad.tests_concurrencia
```

Son tres pruebas y hacen falta las tres, porque cada una cubre un agujero de
las otras:

| Prueba | Qué comprueba |
|---|---|
| `test_mientras_la_firma_decide_nadie_toca_los_formularios` | el bloqueo **existe**: otra conexión no puede borrar lo que la firma leyó |
| `test_sin_bloquear_las_filas_quedan_libres` | el control: por el camino de solo lectura las filas **no** se bloquean |
| `test_el_camino_de_la_firma_pide_el_bloqueo` | la vista **lo usa**, y no solo que el mecanismo funcione |

Las dos primeras se saltan en los motores sin bloqueo. **Que se salten no
significa que la garantía esté**: significa que ahí no la hay.

### Una trampa que costó descubrir

La primera versión de la prueba lanzaba los dos hilos —firmar y desmarcar— y
miraba el resultado. **Pasaba igual sin el bloqueo, tres veces de tres.** Dos
motivos, y los dos son fáciles de repetir:

1. Sin bloqueo la carrera se gana o se pierde por milisegundos, así que casi
   siempre sale bien y la prueba no delata nada.
2. En la rama de éxito solo comprobaba que la liberación quedara firmada, cosa
   que ocurre tanto si el checklist estaba completo como si ya no lo estaba.
   Era una afirmación que no podía fallar.

Por eso las pruebas de aquí **no miden la carrera, miden el bloqueo**: se
mantiene abierto y se intenta escribir desde otra conexión con `lock_timeout`
corto. Eso es determinista. Si alguien vuelve a escribirlas lanzando hilos a
ver qué pasa, conviene quitar el `select_for_update()` y confirmar que fallan
antes de creerles.

### Verificado contra PostgreSQL real

Comprobado sobre **PostgreSQL 17.6** (binarios temporales, puerto 55432):

- Las 12 migraciones aplican limpias desde cero.
- `manage.py check` no reporta nada (en SQLite reporta `calidad.W001`).
- **206 pruebas OK**, con 5 saltadas: las del check que solo aplican a un motor
  sin bloqueo.
- Las tres pruebas de bloqueo corren de verdad y pasan.
- Quitando `bloquear=True` de la vista, la suite **falla**
  (`Lists differ: [False] != [True]`). Antes de reescribirlas no fallaba.

En SQLite (`DB_ENGINE=sqlite`): las mismas 206 pruebas OK, 3 saltadas, y el
aviso `calidad.W001` en cada arranque.
