from django.urls import path
from .views import (
    confirmar_recuperacion,
    actualizar_trabajador,
    login,
    logout,
    solicitar_recuperacion,
    trabajadores,
    yo,
)

urlpatterns = [
    path("login/", login, name="login"),
    path("logout/", logout, name="logout"),
    path("yo/", yo, name="yo"),
    path("trabajadores/", trabajadores, name="trabajadores"),
    path("trabajadores/<int:usuario_id>/", actualizar_trabajador, name="actualizar-trabajador"),
    path(
        "recuperar-contrasena/",
        solicitar_recuperacion,
        name="solicitar_recuperacion",
    ),
    path(
        "restablecer-contrasena/",
        confirmar_recuperacion,
        name="confirmar_recuperacion",
    ),
]
