from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    confirmar_recuperacion,
    login,
    logout,
    solicitar_recuperacion,
    TrabajadorViewSet,
    yo,
)

router = SimpleRouter()
router.register("trabajadores", TrabajadorViewSet, basename="trabajador")

urlpatterns = [
    path("login/", login, name="login"),
    path("logout/", logout, name="logout"),
    path("yo/", yo, name="yo"),
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
