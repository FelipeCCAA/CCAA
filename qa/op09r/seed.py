"""Synthetic workload only; execute through manage_isolated.py shell."""
import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from inventario.models import Bodega, Existencia, Insumo, LoteInventario, Ubicacion
from inventario.servicios import registrar_entrada
from usuarios.models import PerfilUsuario, Rol, SesionUsuario, Sucursal
from usuarios.sesiones import nueva_credencial

assert settings.DATABASES["default"]["NAME"] == "op09r_carga"
assert settings.DATABASES["default"]["PORT"] == 55469 or str(settings.DATABASES["default"]["PORT"]) == "55469"
runtime = Path(settings.MEDIA_ROOT).parent
assert not (runtime / "load-accounts.json").exists(), "Do not repeat fictitious fixture preparation"
assert not User.objects.filter(username__startswith="op09r_carga_").exists(), "New namespace required"
accounts = []
areas = [PerfilUsuario.Area.RECEPCION, PerfilUsuario.Area.BODEGA, PerfilUsuario.Area.CALIDAD, PerfilUsuario.Area.CONDENSACION]
roles = [Rol.RECEPCION, Rol.OPERARIO, Rol.CALIDAD, Rol.PRODUCCION]
with transaction.atomic():
    branch = Sucursal.objects.filter(activa=True).order_by("pk").first()
    assert branch is not None, "OP09R fixture needs its migrated branch"
    author = User.objects.get(username="op09_semilla")
    warehouse, _ = Bodega.objects.get_or_create(sucursal=branch, codigo="OP09R-CARGA", defaults={"nombre": "Bodega ficticia de carga"})
    a, _ = Ubicacion.objects.get_or_create(bodega=warehouse, codigo="A")
    b, _ = Ubicacion.objects.get_or_create(bodega=warehouse, codigo="B")
    supply, _ = Insumo.objects.get_or_create(empresa=branch.empresa, codigo="OP09R-FICTICIO", defaults={"nombre": "Material ficticio de prueba", "area": "bodega", "unidad": "un"})
    for i in range(70):
        name = f"op09r_carga_{i + 1:02}"
        u, created = User.objects.get_or_create(username=name)
        if created:
            u.set_password("OP09R-carga-ficticia-2026")
            u.save()
        profile, _ = PerfilUsuario.objects.get_or_create(usuario=u, defaults={"empresa": branch.empresa, "sucursal": branch})
        profile.empresa, profile.sucursal = branch.empresa, branch
        profile.alcance, profile.nivel = "sucursal", "trabajador"
        profile.rol, profile.area = roles[i % 4], areas[i % 4]
        profile.cargo = "OP09R carga ficticia"
        profile.full_clean()
        profile.save()
        item = {"username": name, "area": profile.area}
        if profile.area == "bodega":
            lot, new = LoteInventario.objects.get_or_create(sucursal=branch, insumo=supply, codigo=name, defaults={"estado_calidad": "no_requiere"})
            if new:
                registrar_entrada(lote=lot, ubicacion=a, cantidad=Decimal("10000"), usuario=author, documento_tipo="OP09R.Fixture", documento_id=i + 1)
            ea = Existencia.objects.get(lote=lot, ubicacion=a)
            eb, _ = Existencia.objects.get_or_create(lote=lot, ubicacion=b)
            item.update(lot=lot.pk, existence_a=ea.pk, existence_b=eb.pk, location_a=a.pk, location_b=b.pk)
        accounts.append(item)
(runtime / "load-accounts.json").write_text(json.dumps(accounts, indent=2), encoding="utf-8")
print("OP09R_LOAD_FIXTURE", len(accounts), "synthetic accounts; stock dedicated and traceable")

# Dedicated synthetic sessions: load excludes login, tested separately.
tokens = {}
with transaction.atomic():
    for account in accounts:
        user = User.objects.get(username=account["username"])
        assert not user.is_superuser and user.perfil.cargo == "OP09R carga ficticia"
        token, digest = nueva_credencial()
        SesionUsuario.objects.create(usuario=user, token_hash=digest, ip="127.0.0.1", user_agent="OP09R fictitious preauthenticated load")
        tokens[user.username] = token
(runtime / "synthetic-sessions.json").write_text(json.dumps(tokens), encoding="utf-8")
print("70 synthetic sessions; login limits unchanged")
