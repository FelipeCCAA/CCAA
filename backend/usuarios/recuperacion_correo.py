"""Formulario nativo con confirmación explícita del transporte, sin reenvíos."""
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import EmailMultiAlternatives
from django.template import loader

from .email_backends import MicrosoftGraphEmailError


class RecuperacionConConfirmacion(PasswordResetForm):
    def __init__(self, *args, usuario_objetivo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario_objetivo = usuario_objetivo
        self.aceptados = 0

    def get_users(self, email):
        usuarios = super().get_users(email)
        return (u for u in usuarios if self.usuario_objetivo is None or u.pk == self.usuario_objetivo.pk)

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        asunto = "".join(loader.render_to_string(subject_template_name, context).splitlines())
        mensaje = EmailMultiAlternatives(
            asunto, loader.render_to_string(email_template_name, context), from_email, [to_email],
        )
        if html_email_template_name is not None:
            mensaje.attach_alternative(loader.render_to_string(html_email_template_name, context), "text/html")
        try:
            cantidad = mensaje.send()
        except MicrosoftGraphEmailError:
            raise
        except Exception as error:
            # El transporte puede haber aceptado el mensaje antes de cortar.
            raise MicrosoftGraphEmailError("No se confirmó el envío.", estado="incierto") from error
        if cantidad != 1:
            raise MicrosoftGraphEmailError("El transporte no aceptó el correo.")
        self.aceptados += 1
