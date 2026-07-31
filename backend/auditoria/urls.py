from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RegistroAuditoriaViewSet, filtros

router = DefaultRouter()
router.register("registros", RegistroAuditoriaViewSet)

urlpatterns = [
    path("filtros/", filtros, name="auditoria-filtros"),
    path("", include(router.urls)),
]
