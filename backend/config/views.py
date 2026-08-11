import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


logger = logging.getLogger(__name__)


def comprobar_postgresql() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


@require_GET
@never_cache
def liveness(_request):
    """El proceso HTTP está vivo; no consulta dependencias."""
    return JsonResponse({"estado": "ok"})


@require_GET
@never_cache
def readiness(_request):
    """El proceso está listo únicamente si PostgreSQL responde."""
    try:
        comprobar_postgresql()
    except DatabaseError:
        logger.warning("Readiness falló: PostgreSQL no está disponible")
        return JsonResponse({"estado": "no_disponible"}, status=503)

    return JsonResponse({"estado": "ok"})
