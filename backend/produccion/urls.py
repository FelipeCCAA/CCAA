from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AnalisisViewSet, LoteViewSet, resumen

router = DefaultRouter()
router.register("lotes", LoteViewSet)
router.register("analisis", AnalisisViewSet)

urlpatterns = [
    path("resumen/", resumen, name="resumen"),
    path("", include(router.urls)),
]
