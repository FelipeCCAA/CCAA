"""
Barrido: ninguna escritura le pide la planta al que administra.

Los cuatro fallos de la semana —el perfil de usuario, el mandante, el ingreso
del camión, la ejecución de proceso— eran **el mismo defecto en cuatro copias**,
y salieron uno a uno, tropezando en la aplicación. Esta prueba los habría
encontrado los cuatro de golpe.

Recorre **todos** los ViewSets publicados en las URLs, no una lista escrita a
mano: una lista se queda corta justo cuando alguien añade el quinto, que es
cuando haría falta.

## Cómo prueba sin inventarse un formulario por endpoint

Armar un cuerpo válido para veinte endpoints distintos es un trabajo que
envejece mal y que acabaría probando los formularios en vez de la regla. En su
lugar se llama a `perform_create` con un serializer de mentira —`validated_data`
vacío, `save()` que anota lo que recibe— y se mira **solo** si la llamada se
queja del tenant.

Que falle por otra cosa está bien y se ignora: significa que llegó a pedir datos
del negocio, o sea que el tenant ya lo había resuelto. Lo único que se persigue
es el «indica la sucursal» dirigido a quien no tiene por qué indicarla.

## Por qué `DJANGO_ENV=development`

Bajo `test`, el `default` de los campos de tenant entrega la empresa y la
sucursal sembradas, así que `validated_data` nunca llega vacía y **el defecto no
se reproduce**: esta prueba pasaría entera con las cuatro copias rotas. El
entorno donde el default no inventa nada es el que corre en planta.
"""

from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import get_resolver
from rest_framework import viewsets
from rest_framework.exceptions import APIException
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Empresa, Sucursal


# Lo que delata a un `perform_create` que resuelve el tenant por su cuenta y se
# queda corto. Se busca en el texto del error porque es exactamente lo que ve
# quien está delante de la pantalla.
SEÑALES = ("sucursal", "planta", "empresa")


def _viewsets_publicados():
    """Todos los ViewSets que atienden un POST, sacados del árbol de URLs."""
    vistos, encontrados = set(), []

    def recorrer(patrones):
        for patron in patrones:
            hijos = getattr(patron, "url_patterns", None)
            if hijos is not None:
                recorrer(hijos)
                continue

            clase = getattr(getattr(patron, "callback", None), "cls", None)

            if clase is None or clase in vistos:
                continue
            if not (isinstance(clase, type) and issubclass(clase, viewsets.GenericViewSet)):
                continue
            if "post" not in getattr(patron.callback, "actions", {}):
                continue

            vistos.add(clase)
            encontrados.append(clase)

    recorrer(get_resolver().url_patterns)

    return encontrados


def _acciones_post_de_lista():
    """
    Las acciones `@action(detail=False, methods=["post"])`, con su ViewSet.

    Este barrido nació mirando solo `perform_create`, y eso dejó fuera las
    acciones a medida — que son la mayoría de las escrituras del sistema.
    `registrar-llegada/` nació con la copia a mano del tenant y pasó por delante
    sin que nadie la mirara.

    Se recorren las de `detail=False` porque son las que se pueden invocar sin
    inventar un objeto existente. Las de `detail=True` siguen fuera de alcance,
    y conviene saberlo en vez de suponer que están cubiertas.
    """
    encontradas = []

    def recorrer(patrones):
        for patron in patrones:
            hijos = getattr(patron, "url_patterns", None)
            if hijos is not None:
                recorrer(hijos)
                continue

            callback = getattr(patron, "callback", None)
            clase = getattr(callback, "cls", None)

            if clase is None or not isinstance(clase, type):
                continue
            if not issubclass(clase, viewsets.GenericViewSet):
                continue

            nombre = getattr(callback, "actions", {}).get("post")

            if nombre in (None, "create"):
                continue
            # `detail=True` lleva un argumento en la ruta; sin un objeto real no
            # se puede llamar, y fabricarlo por reflexión seria adivinar.
            if getattr(getattr(clase, nombre, None), "detail", False):
                continue

            encontradas.append((clase, nombre))

    recorrer(get_resolver().url_patterns)

    return sorted(set(encontradas), key=lambda par: (par[0].__name__, par[1]))


# Lo que dice un manejador que resuelve el tenant por su cuenta y se queda
# corto: le exige al actor una planta o una empresa que no tiene por qué indicar.
FRASES_QUE_LO_PIDEN = ("indicar una sucursal", "indicar la empresa")

# Las tres formas legítimas de resolverlo, todas en `usuarios.tenancy`.
RESOLUTORES = {
    "sucursal_para_escritura",
    "unica_sucursal_activa",
    "unica_empresa_activa",
}


def _pide_el_tenant_sin_resolverlo(funcion) -> bool:
    """
    Si este manejador exige el tenant sin pasar por la función que lo resuelve.

    Se mira el **AST y no el texto**: buscar la frase en el código fuente la
    encuentra también dentro de los comentarios, y este mismo módulo tiene
    comentarios que citan el mensaje para explicar de dónde viene. La primera
    versión señalaba cinco inocentes por eso.

    El docstring se descarta por la misma razón. Lo que cuenta es un literal de
    cadena **en el código**: el mensaje que el manejador devuelve.
    """
    import ast
    import inspect
    import textwrap

    if funcion is None:
        return False

    try:
        arbol = ast.parse(textwrap.dedent(inspect.getsource(funcion)))
    except (OSError, TypeError, SyntaxError, IndentationError):
        return False

    cuerpo = arbol.body[0]
    docstring = ast.get_docstring(cuerpo)

    literales = [
        nodo.value
        for nodo in ast.walk(cuerpo)
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
    ]

    if docstring in literales:
        literales.remove(docstring)

    pide = any(
        frase in literal.lower() for literal in literales for frase in FRASES_QUE_LO_PIDEN
    )

    if not pide:
        return False

    llamadas = {
        nodo.func.id
        for nodo in ast.walk(cuerpo)
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name)
    }

    return not (llamadas & RESOLUTORES)


class _SerializerDeMentira:
    """
    Lo mínimo que `perform_create` toca de un serializer.

    `save()` devuelve un `MagicMock` porque algunos siguen trabajando con lo que
    devuelve —`recoleccion = serializer.save(...)` y luego lo usa—, y un `None`
    los rompería por una razón que no es la que se está midiendo.
    """

    def __init__(self):
        self.validated_data = {}
        self.instance = None
        self.guardado_con = None

    def save(self, **kwargs):
        self.guardado_con = kwargs
        return MagicMock()


@override_settings(DJANGO_ENV="development")
class NingunaEscrituraPideLaPlantaTests(TestCase):

    def setUp(self):
        Empresa.objects.update(activa=False)
        Sucursal.objects.update(activa=False)

        self.empresa = Empresa.objects.create(rut="76.888.888-8", nombre="CCAA")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="UNICA", nombre="Planta"
        )
        self.jefe = User.objects.create_superuser(username="barrido", password="x")
        self.fabrica = APIRequestFactory()

    def _vista(self, clase, accion):
        peticion = self.fabrica.post("/", {}, format="json")
        force_authenticate(peticion, user=self.jefe)

        vista = clase()
        vista.action_map = {"post": accion}
        vista.request = vista.initialize_request(peticion)
        vista.format_kwarg = None
        vista.action = accion
        vista.kwargs = {}

        return vista

    def _mirar(self, etiqueta, llamada):
        """
        Ejecuta y devuelve el reproche sobre el tenant, si lo hubo.

        Que falle por otra cosa está bien y se ignora: significa que llegó a
        pedir datos del negocio, o sea que el tenant ya estaba resuelto.
        """
        try:
            llamada()
        except APIException as error:
            texto = str(getattr(error, "detail", error)).lower()
            if any(señal in texto for señal in SEÑALES):
                return f"{etiqueta}: {texto[:120]}"
        except Exception:
            pass

        return None

    def _reproche_de_tenant(self, clase):
        """El mensaje sobre el tenant que suelta el `perform_create`, o `None`."""
        vista = self._vista(clase, "create")

        return self._mirar(
            f"{clase.__module__}.{clase.__name__}",
            lambda: vista.perform_create(_SerializerDeMentira()),
        )

    def _reproche_de_accion(self, clase, nombre):
        """
        Igual, pero llamando a la acción a medida con el cuerpo vacío.

        La acción devuelve `Response` en vez de levantar, así que se inspecciona
        también lo devuelto.

        **Alcanza menos de lo que parece**, y conviene decirlo: con el cuerpo
        vacío, una acción que valida sus datos antes de resolver el tenant
        devuelve su propio 400 y nunca llega a la parte que se quiere medir. Es
        justo lo que hace `registrar-llegada`. Para eso está la comprobación
        estática de más abajo, que mira el código y no la respuesta.
        """
        vista = self._vista(clase, nombre)
        etiqueta = f"{clase.__module__}.{clase.__name__}.{nombre}"
        devuelto = {}

        def llamar():
            respuesta = getattr(vista, nombre)(vista.request)
            devuelto["cuerpo"] = getattr(respuesta, "data", None)

        reproche = self._mirar(etiqueta, llamar)

        if reproche is not None:
            return reproche

        texto = str(devuelto.get("cuerpo", "")).lower()

        if any(señal in texto for señal in SEÑALES):
            return f"{etiqueta}: {texto[:120]}"

        return None

    def test_ninguna_le_pide_el_tenant_al_superusuario(self):
        publicados = _viewsets_publicados()

        # Si el descubrimiento se rompe, la prueba pasaría vacía diciendo que
        # todo está bien. Ese es el modo de fallo que hay que impedir.
        self.assertGreater(len(publicados), 15, "No se descubrieron los ViewSets")

        reproches = [
            reproche
            for clase in publicados
            if (reproche := self._reproche_de_tenant(clase)) is not None
        ]

        self.assertEqual(
            reproches,
            [],
            "Con una sola planta activa nadie debería tener que indicarla:\n"
            + "\n".join(reproches),
        )

    def test_ningun_manejador_post_resuelve_el_tenant_por_su_cuenta(self):
        """
        La red que sí llega a todas partes: se mira el **código**, no la
        respuesta.

        La sonda de arriba no alcanza a una acción que valida su cuerpo antes de
        resolver el tenant —devuelve su propio 400 y nunca llega—, que es
        exactamente el caso de `registrar-llegada`. Comprobado: con la copia a
        mano repuesta, la sonda pasaba en verde.

        Lo que delata a una copia es que **pida el tenant por su cuenta**: un
        texto que exige indicar la sucursal o la empresa, en un manejador que no
        llama a `sucursal_para_escritura`. Los usos de lectura de `scope` —
        acotar un catálogo a la planta de quien pregunta— no piden nada y no
        aparecen aquí.
        """
        manejadores = [
            (clase, "perform_create") for clase in _viewsets_publicados()
        ] + _acciones_post_de_lista()

        culpables = [
            f"{clase.__module__}.{clase.__name__}.{nombre}"
            for clase, nombre in manejadores
            if _pide_el_tenant_sin_resolverlo(getattr(clase, nombre, None))
        ]

        self.assertEqual(
            culpables,
            [],
            "Resuelven el tenant a mano en vez de usar `sucursal_para_escritura`:\n"
            + "\n".join(culpables),
        )

    def test_tampoco_las_acciones_a_medida(self):
        """
        El hueco que destapó `registrar-llegada/`: el barrido miraba solo los
        `perform_create` y las acciones a medida pasaban por delante sin que
        nadie las mirara.
        """
        acciones = _acciones_post_de_lista()

        self.assertGreater(len(acciones), 3, "No se descubrieron las acciones POST")

        reproches = [
            reproche
            for clase, nombre in acciones
            if (reproche := self._reproche_de_accion(clase, nombre)) is not None
        ]

        self.assertEqual(
            reproches,
            [],
            "Acciones que le piden la planta a quien no tiene que indicarla:\n"
            + "\n".join(reproches),
        )

    def test_con_dos_plantas_activas_alguna_si_la_pide(self):
        """
        La contraprueba, y no es una formalidad: si `_reproche_de_tenant` dejara
        de detectar nada —porque el mensaje cambió, porque la excepción ya no es
        `APIException`— la prueba de arriba pasaría igual y no protegería nada.
        Con dos plantas la ambigüedad es real y **tiene** que salir a la luz.
        """
        Sucursal.objects.create(
            empresa=self.empresa, codigo="SEGUNDA", nombre="Segunda planta"
        )

        reproches = [
            reproche
            for clase in _viewsets_publicados()
            if (reproche := self._reproche_de_tenant(clase)) is not None
        ]

        self.assertNotEqual(
            reproches, [], "Con dos plantas activas la elección tiene que pedirse"
        )
