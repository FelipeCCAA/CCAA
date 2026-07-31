from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MonitoreoPPROViewSet, PproLecturaViewSet

router = DefaultRouter()
router.register("monitoreos", MonitoreoPPROViewSet)
router.register("lecturas", PproLecturaViewSet)

urlpatterns = [path("", include(router.urls))]
