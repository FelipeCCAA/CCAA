from django.urls import path
from .views import prueba_usuario


urlpatterns = [

    path(
        "prueba/",
        prueba_usuario
    ),

]