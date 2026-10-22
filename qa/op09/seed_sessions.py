"""Prepare already-authenticated synthetic users, not a login benchmark."""
import json
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from usuarios.models import SesionUsuario
from usuarios.sesiones import nueva_credencial, revocar_sesiones

assert settings.DJANGO_ENV == "test" and settings.DATABASES["default"]["NAME"] == "op09_circuito"
tokens = {}
with transaction.atomic():
    for user in User.objects.filter(username__startswith="op09_carga_").order_by("username"):
        assert not user.is_superuser and user.perfil.cargo == "OP09 carga ficticia"
        revocar_sesiones(user, "admin")
        token, digest = nueva_credencial()
        SesionUsuario.objects.create(usuario=user, token_hash=digest, ip="127.0.0.1", user_agent="OP09 synthetic pre-authenticated workload fixture")
        tokens[user.username] = token
assert len(tokens) == 70
(Path(settings.MEDIA_ROOT).parent / "synthetic-sessions.json").write_text(json.dumps(tokens), encoding="utf-8")
print("OP09 synthetic authenticated sessions prepared; no rate-limit settings changed")
