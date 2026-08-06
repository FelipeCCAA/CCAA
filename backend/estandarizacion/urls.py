from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ValeEstandarizacionViewSet

router = DefaultRouter()
router.register("vales", ValeEstandarizacionViewSet)

urlpatterns = [path("", include(router.urls))]
