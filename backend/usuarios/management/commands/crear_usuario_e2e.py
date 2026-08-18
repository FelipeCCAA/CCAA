"""
Cuenta dedicada para la auditoría automática de accesibilidad.

Por qué existe
-------------
La auditoría (`frontend/e2e/`) recorre las treinta pantallas internas, y todas
exigen sesión. Sin una cuenta conocida hay dos salidas malas: compartir por
escrito la contraseña de alguien, o tocar a mano la base cada vez que el token
caduca —doce horas— y que nadie sepa después de dónde salió esa cuenta.

Esta la deja escrita en el repositorio: reproducible, con nombre que dice para
qué es, y sin privilegios de más.

Por qué NO es superusuario
--------------------------
Un superusuario tendría `rol = admin` sin necesidad de perfil y sería una línea
más corto. Pero `scope_de` le devuelve alcance global, o sea que ve datos que
ningún administrador real ve, y la auditoría estaría midiendo pantallas que en
planta nadie tiene delante. Con un perfil de Administración general se audita lo
que de verdad se usa.

El perfil sigue la regla vigente del modelo: Administración general es de
**alcance empresa** y por tanto **sin sucursal** (ver `PerfilUsuario.clean()` y
el CHECK `alcance`/`sucursal`). Ojo con un efecto que no es de este comando:
`PerfilUsuario.save()` marca `is_staff` a todo administrador de área, así que la
cuenta acaba con acceso al admin de Django. Es la regla del modelo, no una
concesión de aquí.

Uso
---
    python manage.py crear_usuario_e2e
    python manage.py crear_usuario_e2e --clave "otra-clave"

Es idempotente: repetirlo reescribe la contraseña y deja el perfil como debe
estar, que es justo lo que hace falta cuando alguien lo dejó a medias.
"""

import os

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from config.seguridad import ENTORNOS_ENDURECIDOS
from usuarios.models import Empresa, PerfilUsuario, Rol

USUARIO = "e2e_auditoria"
CLAVE_POR_OMISION = "auditoria-e2e-ccaa"


class Command(BaseCommand):
    help = "Crea (o repone) la cuenta que usa la auditoría de accesibilidad."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clave",
            default=os.environ.get("E2E_CLAVE", CLAVE_POR_OMISION),
            help=(
                "Contraseña de la cuenta. Por omisión toma E2E_CLAVE del entorno "
                f"y, si tampoco está, «{CLAVE_POR_OMISION}»."
            ),
        )
        parser.add_argument(
            "--empresa",
            type=int,
            default=None,
            help="Id de la empresa. Solo hace falta si hay más de una activa.",
        )

    @transaction.atomic
    def handle(self, *args, **opciones):
        """
        Nunca en un entorno endurecido.

        Esto crea una cuenta administrativa con una contraseña que está escrita
        en el repositorio. En desarrollo es exactamente lo que se quiere; en
        staging o producción es una puerta abierta con la llave puesta al lado.
        """
        if settings.DJANGO_ENV in ENTORNOS_ENDURECIDOS:
            raise CommandError(
                f"DJANGO_ENV={settings.DJANGO_ENV}: este comando crea una cuenta de "
                "administración con contraseña conocida y solo debe correr en "
                "desarrollo o pruebas."
            )

        empresa = self._empresa(opciones["empresa"])
        clave = opciones["clave"]

        usuario, creado = User.objects.get_or_create(
            username=USUARIO,
            defaults={
                "first_name": "Auditoría",
                "last_name": "Accesibilidad",
                "email": "",
            },
        )

        # Se repone siempre, no solo al crear: si la cuenta quedó de una corrida
        # anterior con otra contraseña, el comando tiene que dejarla utilizable.
        usuario.set_password(clave)
        usuario.is_active = True
        usuario.save()

        # Se busca sin crear y se instancia en memoria si no había: `PerfilUsuario.save()`
        # valida en `clean()`, así que un `get_or_create` intentaría guardar un perfil
        # vacío —sin empresa— y reventaría antes de llegar a rellenarlo.
        perfil = (
            PerfilUsuario.objects.filter(usuario=usuario).first()
            or PerfilUsuario(usuario=usuario)
        )
        perfil.cargo = "Auditoría automática"
        perfil.area = PerfilUsuario.Area.ADMINISTRACION
        perfil.nivel = PerfilUsuario.Nivel.ADMIN
        perfil.rol = Rol.ADMIN
        perfil.alcance = PerfilUsuario.Alcance.EMPRESA
        perfil.empresa = empresa
        perfil.sucursal = None

        # `full_clean` y no solo `save`: las reglas de alcance viven en
        # `clean()`, y guardarlas sin validar dejaría un perfil que la propia
        # aplicación rechaza al editarlo desde el admin.
        perfil.full_clean()
        perfil.save()

        # Se respeta `verbosity`: sin esto, las pruebas que invocan el comando
        # imprimen estas instrucciones en medio de su propia salida.
        if opciones["verbosity"] >= 1:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Cuenta {'creada' if creado else 'repuesta'}: {USUARIO} "
                    f"(empresa «{empresa.nombre}», alcance empresa)."
                )
            )
            self.stdout.write("")
            self.stdout.write("Para correr la auditoría de accesibilidad:")
            self.stdout.write("")
            self.stdout.write("    cd frontend")
            self.stdout.write(f'    $env:E2E_USUARIO = "{USUARIO}"')
            self.stdout.write(f'    $env:E2E_CLAVE = "{clave}"')
            self.stdout.write("    npm run auditoria")
            self.stdout.write("")

    def _empresa(self, id_empresa):
        """
        Con una sola empresa activa no se pregunta; con varias, sí.

        Mismo criterio que `usuarios.tenancy.unica_sucursal_activa`: resolver lo
        que solo tiene una respuesta es servicial, elegir por el operador entre
        dos es dejarle la cuenta colgando de la empresa equivocada.
        """
        if id_empresa is not None:
            try:
                return Empresa.objects.get(pk=id_empresa)
            except Empresa.DoesNotExist:
                raise CommandError(f"No existe la empresa con id {id_empresa}.")

        activas = list(Empresa.objects.filter(activa=True))

        if not activas:
            raise CommandError(
                "No hay ninguna empresa activa. Crea una antes: el perfil la exige."
            )

        if len(activas) > 1:
            detalle = ", ".join(f"{e.pk}={e.nombre}" for e in activas)
            raise CommandError(
                f"Hay {len(activas)} empresas activas ({detalle}). "
                "Indica cuál con --empresa <id>."
            )

        return activas[0]
