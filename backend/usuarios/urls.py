from django.urls import path
from .views import (
    confirmar_recuperacion,
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
