"""
La matemática de la estandarización. Sin ORM: reglas puras y comprobables.

**RC = % materia grasa / % sólidos no grasos.** Es el cálculo central de la
fábrica: decide qué producto sale. Los productos se nombran por él —«RC 0,201»,
«RC 0,422»— y el maestro de productos ya usa esos nombres.

Estandarizar es mezclar leche entera con leche descremada hasta alcanzar el RC
que el producto pide. La cuenta es la de una mezcla ponderada, pero con dos
detalles que importan más que la fórmula:

1. **Un RC objetivo puede ser inalcanzable** con las dos leches que hay. Si se
   pide más grasa de la que tiene la entera, no hay mezcla que lo consiga. El
   cálculo tiene que decirlo, no devolver un volumen negativo que alguien
   termine tecleando en una válvula.

2. **El RC real casi nunca sale igual al calculado.** La leche del silo no es
   exactamente la que se midió, así que el procedimiento incluye analizar
   después de agitar y corregir. Por eso hay dos funciones: la que planifica y
   la que evalúa lo que salió.

Fuente: `docs/REGLAS_DE_PLANTA.md` §3, extraído del flujo de fábrica §10.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Leche:
    """
    Una leche disponible para mezclar, con su composición.

    `grasa` y `sng` van en **porcentaje** (3.6 significa 3,6 %), que es como se
    leen en el análisis. `cantidad` en litros.
    """

    cantidad: float
    grasa: float
    sng: float

    @property
    def rc(self) -> float | None:
        """Su propio RC. `None` si no tiene sólidos: la división no existe."""
        return self.grasa / self.sng if self.sng else None


@dataclass(frozen=True)
class Mezcla:
    """
    Cuánta leche de cada una hay que juntar, y qué se espera obtener.

    `posible` en falso significa que **no hay mezcla** que alcance el objetivo;
    `motivo` dice por qué. Devolver cantidades igual, con una bandera aparte,
    invitaría a usarlas sin mirarla.
    """

    posible: bool
    motivo: str = ""
    entera: float = 0.0
    descremada: float = 0.0
    crema: float = 0.0
    rc_esperado: float | None = None
    grasa_esperada: float | None = None
    sng_esperado: float | None = None
    avisos: list[str] = field(default_factory=list)


def sugerir_mezcla_con_crema(
    *, entera: Leche, descremada: Leche, crema: Leche,
    rc_objetivo: float, volumen: float,
) -> Mezcla:
    """Maximiza la crema utilizable y resuelve el resto con las dos leches."""
    if volumen <= 0 or rc_objetivo <= 0:
        return calcular_mezcla(
            entera=entera, descremada=descremada,
            rc_objetivo=rc_objetivo, volumen=volumen,
        )

    tope = min(max(crema.cantidad, 0.0), volumen)
    ae = entera.grasa - rc_objetivo * entera.sng
    ad = descremada.grasa - rc_objetivo * descremada.sng
    ac = crema.grasa - rc_objetivo * crema.sng

    def resolver(litros_crema):
        restante = volumen - litros_crema
        denominador = ae - ad
        if abs(denominador) < 1e-9:
            return None
        litros_entera = (-litros_crema * ac - restante * ad) / denominador
        litros_descremada = restante - litros_entera
        if litros_entera < -1e-6 or litros_descremada < -1e-6:
            return None
        return max(0.0, litros_entera), max(0.0, litros_descremada)

    elegido = None
    # Baja el tope en pasos de 0,1 %. Es determinista, suficientemente fino
    # para una válvula medida a décimas de litro y no agrega un solucionador.
    for paso in range(1001):
        litros_crema = tope * (1000 - paso) / 1000
        par = resolver(litros_crema)
        if par is not None:
            elegido = (*par, litros_crema)
            break
    if elegido is None:
        base = calcular_mezcla(
            entera=entera, descremada=descremada,
            rc_objetivo=rc_objetivo, volumen=volumen,
        )
        base.avisos.append("La crema disponible no permite una mezcla factible.")
        return base

    x, y, z = elegido
    grasa = (x * entera.grasa + y * descremada.grasa + z * crema.grasa) / volumen
    sng = (x * entera.sng + y * descremada.sng + z * crema.sng) / volumen
    avisos = []
    if tope - z > 0.1:
        avisos.append(
            f"Con {_redondear(tope)} L de crema el RC no se alcanza; "
            f"la sugerencia usa {_redondear(z)} L."
        )
    for nombre, requerido, disponible in (
        ("leche entera", x, entera.cantidad),
        ("descremada", y, descremada.cantidad),
    ):
        if requerido > disponible:
            avisos.append(
                f"Faltan {_redondear(requerido - disponible)} L de {nombre}: "
                f"hay {_redondear(disponible)} y se necesitan {_redondear(requerido)}."
            )
    return Mezcla(
        True, entera=_redondear(x), descremada=_redondear(y), crema=_redondear(z),
        rc_esperado=grasa / sng if sng else None,
        grasa_esperada=round(grasa, 3), sng_esperado=round(sng, 3), avisos=avisos,
    )


def _redondear(valor: float) -> float:
    """Litros al decilitro. Nadie abre una válvula con más precisión."""
    return round(valor, 1)


def calcular_mezcla(
    *,
    entera: Leche,
    descremada: Leche | None,
    rc_objetivo: float,
    volumen: float,
) -> Mezcla:
    """
    Cuántos litros de cada leche para obtener `volumen` litros al `rc_objetivo`.

    De la mezcla ponderada:

        RC = (x·ge + y·gd) / (x·se + y·sd)      con  x + y = V

    despejando x (litros de entera):

        x = V·(RC·sd - gd) / [(ge - gd) - RC·(se - sd)]

    El denominador se anula cuando las dos leches tienen el mismo RC: ahí
    cualquier mezcla da ese mismo RC, y solo sirve si es el que se busca.
    """
    if volumen <= 0:
        return Mezcla(False, "El volumen a preparar debe ser mayor que cero.")

    if rc_objetivo <= 0:
        return Mezcla(False, "El RC objetivo debe ser mayor que cero.")

    if descremada is None:
        alcanzado = entera.rc
        if alcanzado is not None and abs(alcanzado - rc_objetivo) < 1e-6:
            avisos = []
            if volumen > entera.cantidad:
                avisos.append(
                    f"Faltan {_redondear(volumen - entera.cantidad)} L de leche entera: "
                    f"hay {_redondear(entera.cantidad)} y se necesitan {_redondear(volumen)}."
                )
            return Mezcla(
                True, entera=_redondear(volumen), descremada=0.0,
                rc_esperado=alcanzado, grasa_esperada=entera.grasa,
                sng_esperado=entera.sng, avisos=avisos,
            )
        return Mezcla(
            False,
            "La leche entera no está al RC objetivo. Selecciona una fuente "
            "complementaria para ajustar la mezcla.",
        )

    denominador = (entera.grasa - descremada.grasa) - rc_objetivo * (
        entera.sng - descremada.sng
    )

    if abs(denominador) < 1e-9:
        # Las dos leches tienen el mismo RC: la mezcla no lo mueve.
        alcanzado = entera.rc
        if alcanzado is not None and abs(alcanzado - rc_objetivo) < 1e-6:
            return Mezcla(
                True,
                entera=_redondear(volumen),
                descremada=0.0,
                rc_esperado=alcanzado,
                grasa_esperada=entera.grasa,
                sng_esperado=entera.sng,
                avisos=["Las dos leches ya están al RC objetivo."],
            )
        return Mezcla(
            False,
            "Las dos leches tienen el mismo RC y no es el buscado: mezclarlas "
            "no lo cambia. Hace falta una leche de composición distinta.",
        )

    x = volumen * (rc_objetivo * descremada.sng - descremada.grasa) / denominador
    y = volumen - x

    if x < -1e-6 or y < -1e-6:
        cual = "más grasa" if x > volumen else "menos grasa"
        return Mezcla(
            False,
            f"El RC {rc_objetivo:g} no se alcanza con estas dos leches: haría "
            f"falta {cual} de la que hay. La entera está en "
            f"{entera.rc:.4g} y la descremada en {descremada.rc:.4g}."
            if entera.rc and descremada.rc
            else f"El RC {rc_objetivo:g} no se alcanza con estas dos leches.",
        )

    x, y = max(x, 0.0), max(y, 0.0)

    avisos = []

    # Que la cuenta dé no significa que haya leche. Se avisa en vez de fallar:
    # el operador puede estar planificando contra un silo que todavía se está
    # llenando, y negarle el cálculo no le ayuda a decidir.
    if x > entera.cantidad:
        avisos.append(
            f"Faltan {_redondear(x - entera.cantidad)} L de leche entera: "
            f"hay {_redondear(entera.cantidad)} y se necesitan {_redondear(x)}."
        )

    if y > descremada.cantidad:
        avisos.append(
            f"Faltan {_redondear(y - descremada.cantidad)} L de descremada: "
            f"hay {_redondear(descremada.cantidad)} y se necesitan {_redondear(y)}."
        )

    grasa = (x * entera.grasa + y * descremada.grasa) / volumen
    sng = (x * entera.sng + y * descremada.sng) / volumen

    return Mezcla(
        True,
        entera=_redondear(x),
        descremada=_redondear(y),
        rc_esperado=grasa / sng if sng else None,
        grasa_esperada=round(grasa, 3),
        sng_esperado=round(sng, 3),
        avisos=avisos,
    )


@dataclass(frozen=True)
class Correccion:
    """
    Qué agregar cuando el RC medido no da, y cuánto.

    `cumple` en verdadero significa que no hay nada que corregir.
    """

    cumple: bool
    rc_real: float | None
    desvio: float | None = None
    agregar: str = ""
    litros: float = 0.0
    motivo: str = ""


def evaluar_rc(
    *,
    grasa: float,
    sng: float,
    rc_objetivo: float,
    tolerancia: float = 0.005,
) -> Correccion:
    """
    ¿El RC medido cumple? Y si no, ¿qué falta?

    Se evalúa **después de agitar y muestrear**: la leche del silo no es
    exactamente la que se midió al planificar, así que el procedimiento de
    planta incluye analizar y corregir (§10.4 del flujo de fábrica).

    `tolerancia` es cuánto se admite de desvío. El valor por omisión es
    referencial —**lo define Calidad**— y va como parámetro para que cambiarlo
    no sea buscar un número por el código.
    """
    if sng <= 0:
        return Correccion(
            False, None,
            motivo="Sin sólidos no grasos no hay RC que calcular: revisa el análisis.",
        )

    rc_real = grasa / sng
    desvio = rc_real - rc_objetivo

    if abs(desvio) <= tolerancia:
        return Correccion(True, rc_real, desvio)

    return Correccion(
        False,
        rc_real,
        desvio,
        agregar="descremada" if desvio > 0 else "entera",
        motivo=(
            f"El RC real es {rc_real:.4f} y el objetivo {rc_objetivo:.4f}: "
            f"{'sobra' if desvio > 0 else 'falta'} grasa. Agrega leche "
            f"{'descremada' if desvio > 0 else 'entera'}, reagita y vuelve a "
            "analizar."
        ),
    )


def litros_a_agregar(
    *,
    volumen_actual: float,
    grasa: float,
    sng: float,
    rc_objetivo: float,
    correctora: Leche,
) -> float | None:
    """
    Cuántos litros de la leche correctora hacen falta.

    Se agrega `z` litros de una leche de composición conocida a lo que ya hay:

        RC = (V·g + z·gc) / (V·s + z·sc)

    despejando z:

        z = V·(RC·s - g) / [gc - RC·sc]

    Devuelve `None` cuando la corrección no existe —la leche correctora no
    mueve el RC en la dirección necesaria—, que es distinto de «cero litros».
    """
    denominador = correctora.grasa - rc_objetivo * correctora.sng

    if abs(denominador) < 1e-9:
        return None

    z = volumen_actual * (rc_objetivo * sng - grasa) / denominador

    return _redondear(z) if z > 0 else None
