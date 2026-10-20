# OP-02 — antecedente histórico y autorización posterior

El usuario aprobó las ocho reglas y autorizó implementar en una rama, con pruebas y PR, sin producción ni despliegue. El estado y la evidencia vigentes están en [OP-02_VALIDACION.md](OP-02_VALIDACION.md).

El alcance aprobado es balance contable en litros comparables y registro a 0,01 L, sin conversiones kg↔L ni tolerancias físicas inventadas. Las diferencias medidas se registran y retienen liberación/despacho; no se adoptaron densidades ni porcentajes de merma.

A continuación se conserva íntegro el diagnóstico anterior a la autorización. Sus estados y preguntas corresponden a ese corte histórico; las referencias de líneas son del commit `c6aba44`, no de la implementación nueva.

---

# OP-02 — Balance y receta de estandarización

**Estado:** DIAGNÓSTICO · **prioridad:** P0 · **WP:** WP004 · **dependencia:** OP-00 satisfecha. No se autoriza aquí ninguna implementación funcional ni cambio de regla. Este documento reúne hallazgos estáticos confirmados en código; no afirma reproducción en pruebas, incidente real ni uso de datos productivos.

## Propósito y límite

Definir con Calidad, Producción y Bodega el balance/receta desde entradas a silos hasta transferencia, agitación, muestreo, evaluación de RC, liberación o corrección. OP-02 se limita a estandarización; no sustituye OP-03 (saldo/reservas/inventario) ni construye genealogía industrial. Este diagnóstico no decide unidades, densidades, redondeos ni tolerancias.

## Hallazgos estáticos

### OP02-01 — No hay conciliación explícita del balance de componentes y salida

`transferir()` en [estandarizacion/servicios.py](../../backend/estandarizacion/servicios.py#L57) es atómico, bloquea el vale y los silos, comprueba estado, disponibilidad, reservas y capacidad, y registra movimientos. Resta litros de las fuentes y acredita el destino con `vale.volumen` ([líneas de movimientos](../../backend/estandarizacion/servicios.py#L127)). El código no comprueba que la suma de componentes que se debitan concuerde con el volumen acreditado, ni calcula un balance de masa con densidades.

La validación del [serializer](../../backend/estandarizacion/serializers.py#L90) revisa presencia de campos, tipos de silo y algunas relaciones FIFO, no concilia cantidades. `ValeEstandarizacion.clean()` ([models.py](../../backend/estandarizacion/models.py#L451)) solo impide que el destino sea uno de los orígenes; `CAMPOS_QUE_MUEVEN_LIBRO` está declarado en [models.py](../../backend/estandarizacion/models.py#L101), pero no se usa dentro de `estandarizacion` para validar el balance.

**Ejemplo únicamente simulado:** 4.000 L de entera + 6.000 L de descremada con un vale que declara 12.000 L de salida deja una diferencia de 2.000 L en volumen. El ejemplo requiere reproducirse en una prueba sintética aislada si se autoriza la fase de implementación; no es un evento real ni una prueba ejecutada.

### OP02-02 — La receta editable puede divergir de los movimientos y del snapshot ya transferidos

`ValeEstandarizacionViewSet` hereda `ModelViewSet` ([views.py](../../backend/estandarizacion/views.py#L33)); el [serializer](../../backend/estandarizacion/serializers.py#L44) permite escribir producto, RC objetivo, volumen, silos, cantidades por componente y referencias analíticas. Los campos read-only se limitan a los indicados en [read_only_fields](../../backend/estandarizacion/serializers.py#L68). No se observa un override de actualización que impida editar esos datos después de transferir.

Al transferir, [registrar_estandarizacion()](../../backend/procesos/servicios.py#L1221) crea el snapshot de `EntradaProceso` y `SalidaProceso` usando los litros de componentes y `vale.volumen`. Un PATCH posterior al vale no actualiza esos registros ni los movimientos de silo. La declaración `CAMPOS_QUE_MUEVEN_LIBRO` no funciona por sí sola como protección. La atribución de recepción en [heredar_atribuciones()](../../backend/recepcion/servicios.py#L220) reparte proporcionalmente la procedencia recibida al volumen de ingreso y redondea partes intermedias a 0,01 L; es una atribución de trazabilidad, no una comprobación física de conservación de masa.

Esto es una brecha de contrato observable en el código, no una afirmación de que alguien haya alterado un vale transferido en producción. No debe resolverse bloqueando toda edición post-transferencia: el ciclo legítimo incluye agitación, muestreo, evaluación de RC y, si procede, corrección, reagitación, remuestreo y liberación. El diagnóstico delimita cambios a hechos físicos ya ejecutados y preserva las acciones permitidas de muestra, corrección documental y trazabilidad.

## Decisiones requeridas antes de implementar

Las decisiones siguientes están abiertas y no se adoptan por este diagnóstico:

1. **Magnitud:** decidir litros, kg o ambos balances separados y definir la base comparable de entradas/salida.
2. **Densidad/conversión:** aprobar fuente, vigencia, condiciones, unidades y factores. No reutilizar automáticamente el factor documental de recepción como densidad de proceso.
3. **Precisión:** acordar escala, cálculo interno, redondeo y residuo; los campos de litros con dos decimales no definen estas reglas.
4. **Tolerancias:** Calidad/Producción deben separar masa, volumen y RC y acordar si cada diferencia advierte, bloquea o exige aprobación. `evaluar_rc()` tiene default RC `0.005` ([dominio.py](../../backend/estandarizacion/dominio.py#L278)) atribuido a Calidad; no es tolerancia de masa/volumen ni se adopta aquí.
5. **Cambios/correcciones:** decidir la rectificación versionada de hechos ya ejecutados y su auditoría; preservar el ciclo válido de muestreo, corrección, reagitación, remuestreo, revisión y liberación. No sobrescribir movimientos ni bloquear indiscriminadamente ediciones post-transferencia.

Orden de decisión: Calidad (muestra/RC/tolerancias), Producción (magnitudes/receta), Bodega (movimientos/silos). Aprobar reglas precede cambios funcionales o migraciones.

## Ruta propuesta si se autoriza la implementación

1. Aprobar contrato, unidades, ejemplos y política de corrección; valorar migraciones aditivas solo si hacen falta. Sin backfill ni reinterpretación histórica.
2. Definir conciliación pura y determinista, separando receta/RC de balances y expresando fuente, unidad, conversión, redondeo y diferencia.
3. Integrar validación en transferencia atómica, con la misma versión de receta en movimientos y snapshot; aplicar el contrato de PUT/PATCH físico post-transferencia sin romper el ciclo de muestra/corrección.
4. Alinear trazabilidad de recepción, presentar al operador magnitudes y diferencias; luego ejecutar focales y regresión en PostgreSQL aislado OP-00 ya existente, cuando se autorice. No arrancar ni contratar clúster durante el diagnóstico.

## Pruebas propuestas para la fase autorizada

- Balance/densidad en límites aprobados; precisión, redondeo y residuo; entradas inválidas, faltantes, exceso, reserva y capacidad.
- Caso sintético 4.000 L + 6.000 L frente a salida declarada de 12.000 L: detectar la diferencia según reglas aprobadas. Ficticio; sin reproducir.
- Atomicidad y rollback de movimientos/snapshot; reintento idempotente y dos transferencias concurrentes sin duplicado ni saldo negativo.
- PUT/PATCH físico post-transferencia conforme a contrato, coherencia de vale/libro/snapshot/atribuciones y preservación del ciclo de muestreo, corrección, reagitación, remuestreo y liberación.
- Auditoría de correcciones; regresiones de composición, FIFO, agitación, muestreo, Calidad y recepción.

Pruebas futuras: fixtures sintéticos y PostgreSQL aislado OP-00; no usar datos reales, arrancar ahora el clúster detenido, tocar servicios externos ni crear instancias/credenciales.

**Estado final: EN ANÁLISIS.** No hay implementación autorizada; la autorización queda pendiente de acordar las reglas de negocio. No se ejecutaron pruebas de OP-02 ni se reprodujo el ejemplo simulado.
