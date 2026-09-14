"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from .views import liveness, readiness


urlpatterns = [

    # Se conserva /api/salud/ por compatibilidad como liveness. Readiness
    # comprueba además que PostgreSQL acepte consultas.
    path("api/salud/", liveness, name="salud"),
    path("api/salud/listo/", readiness, name="readiness"),

    # El panel administrativo no forma parte de la API REST.
    path("admin/", admin.site.urls),

    path("api/usuarios/", include("usuarios.urls")),

    path("api/maestros/", include("maestros.urls")),

    path("api/produccion/", include("produccion.urls")),

    path("api/recepcion/", include("recepcion.urls")),
    path("api/recoleccion/", include("recoleccion.urls")),
    path("api/estandarizacion/", include("estandarizacion.urls")),


    path("api/calidad/", include("calidad.urls")),

    path("api/planificacion/", include("planificacion.urls")),

    path("api/inocuidad/", include("inocuidad.urls")),

    path("api/inventario/", include("inventario.urls")),

    path("api/auditoria/", include("auditoria.urls")),

    path("api/procesos/", include("procesos.urls")),

    path("api/mantenimiento/", include("mantenimiento.urls")),

]
