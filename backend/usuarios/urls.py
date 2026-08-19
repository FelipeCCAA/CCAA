from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    confirmar_recuperacion,
    cambiar_password,
    login,
    logout,
    solicitar_recuperacion,
    TrabajadorViewSet,
    SesionUsuarioViewSet,
    yo,
)

router = SimpleRouter()
router.register("trabajadores", TrabajadorViewSet, basename="trabajador")
router.register("sesiones", SesionUsuarioViewSet, basename="sesion")

urlpatterns = [
    path("login/", login, name="login"),
    path("logout/", logout, name="logout"),
    path("yo/", yo, name="yo"),
    path("cambiar-password/", cambiar_password, name="cambiar_password"),
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
] + router.urls
