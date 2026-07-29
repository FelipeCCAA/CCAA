from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import UsuarioSerializer


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    """
    Valida las credenciales y entrega un token.

    Es el único endpoint abierto de la API: todo lo demás exige presentar
    ese token en la cabecera `Authorization: Token <valor>`.
    """
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response(
            {"error": "Usuario y contraseña son obligatorios"},
            status=status.HTTP_400_BAD_REQUEST
        )

    usuario = authenticate(
        username=username,
        password=password
    )

    if usuario is None:
        return Response(
            {"error": "Usuario o contraseña incorrectos"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not usuario.is_active:
        return Response(
            {"error": "La cuenta está desactivada"},
            status=status.HTTP_403_FORBIDDEN
        )

    token, _ = Token.objects.get_or_create(user=usuario)

    return Response({
        "mensaje": "Login correcto",
        "token": token.key,
        "usuario": UsuarioSerializer(usuario).data,
    })


@api_view(["POST"])
def logout(request):
    """
    Cierra la sesión invalidando el token.

    Sin esto, un token robado serviría para siempre: borrarlo en el navegador
    no lo desactiva en el servidor.
    """
    Token.objects.filter(user=request.user).delete()

    return Response({"mensaje": "Sesión cerrada"})


@api_view(["GET"])
def yo(request):
    """
    Quién es el usuario del token.

    La interfaz la usa al arrancar para comprobar que la sesión guardada
    sigue siendo válida; si el token fue revocado, responde 401.
    """
    return Response(UsuarioSerializer(request.user).data)
