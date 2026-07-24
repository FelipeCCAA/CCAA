from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['GET'])
def prueba_usuario(request):

    return Response({
        "nombre": "Administrador",
        "rol": "Jefe TI",
        "mensaje": "Django conectado correctamente"
    })