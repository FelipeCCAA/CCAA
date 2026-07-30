"""Comando operativo para verificar el envío configurado."""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Envía un correo de prueba con el backend configurado."

    def add_arguments(self, parser):
        parser.add_argument(
            "--destinatario",
            required=True,
            help="Dirección que recibirá el correo de diagnóstico.",
        )

    def handle(self, *args, **options):
        destinatario = options["destinatario"]

        try:
            enviados = send_mail(
                subject="Prueba de correo · Planta CCAA",
                message=(
                    "Microsoft Graph quedó configurado correctamente para "
                    "Gestión Productiva · Planta CCAA."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[destinatario],
                fail_silently=False,
            )
        except Exception as error:
            raise CommandError(f"No se pudo enviar el correo: {error}") from error

        if enviados != 1:
            raise CommandError("El backend no confirmó el envío del correo.")

        self.stdout.write(
            self.style.SUCCESS(f"Correo de prueba enviado a {destinatario}.")
        )
