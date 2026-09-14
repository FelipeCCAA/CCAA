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
Un superusuario eludiría los permisos por rol y área. Con un perfil de
Administración se audita la interfaz con las mismas reglas funcionales que una
cuenta real. Los campos históricos de organización se completan únicamente
porque el esquema todavía los exige; no conceden alcance ni filtran datos.

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
from usuarios.models import PerfilUsuario, Rol
from usuarios.tenancy import unica_empresa_activa

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

        empresa = unica_empresa_activa()
        if empresa is None or not empresa.activa:
            raise CommandError(
                "Falta el registro técnico histórico requerido por el perfil."
            )
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

        # El registro técnico histórico solo satisface restricciones del esquema.
        # La autorización funcional depende exclusivamente de rol y área.
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
                    f"Cuenta {'creada' if creado else 'repuesta'}: {USUARIO}."
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
