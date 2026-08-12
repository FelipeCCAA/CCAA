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

    def _reproche_de_tenant(self, clase):
        """El mensaje sobre el tenant que suelta este ViewSet, o `None`."""
        peticion = self.fabrica.post("/", {}, format="json")
        force_authenticate(peticion, user=self.jefe)

        vista = clase()
        vista.action_map = {"post": "create"}
        vista.request = vista.initialize_request(peticion)
        vista.format_kwarg = None
        vista.action = "create"
        vista.kwargs = {}

        try:
            vista.perform_create(_SerializerDeMentira())
        except APIException as error:
            texto = str(getattr(error, "detail", error)).lower()
            if any(señal in texto for señal in SEÑALES):
                return f"{clase.__module__}.{clase.__name__}: {texto[:120]}"
        except Exception:
            # Cualquier otro fallo es del negocio —un campo que falta, una
            # relación inexistente— y significa que el tenant ya se resolvió.
            pass

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
