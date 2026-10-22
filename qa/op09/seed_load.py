"""Synthetic workload only; execute through manage_isolated.py shell."""
import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from inventario.models import Bodega, Existencia, Insumo, LoteInventario, Ubicacion
from inventario.servicios import registrar_entrada
from usuarios.models import PerfilUsuario, Rol, Sucursal

assert settings.DATABASES["default"]["NAME"] == "op09_circuito"
assert settings.DATABASES["default"]["PORT"] == 55449 or str(settings.DATABASES["default"]["PORT"]) == "55449"
runtime = Path(settings.MEDIA_ROOT).parent
accounts = []
areas = [PerfilUsuario.Area.RECEPCION, PerfilUsuario.Area.BODEGA, PerfilUsuario.Area.CALIDAD, PerfilUsuario.Area.CONDENSACION]
roles = [Rol.RECEPCION, Rol.OPERARIO, Rol.CALIDAD, Rol.PRODUCCION]
with transaction.atomic():
    branch = Sucursal.objects.filter(activa=True).order_by("pk").first()
    assert branch is not None, "OP09 fixture needs its migrated branch"
    author = User.objects.get(username="op09_semilla")
    warehouse, _ = Bodega.objects.get_or_create(sucursal=branch, codigo="OP09-CARGA", defaults={"nombre": "Bodega ficticia de carga"})
    a, _ = Ubicacion.objects.get_or_create(bodega=warehouse, codigo="A")
    b, _ = Ubicacion.objects.get_or_create(bodega=warehouse, codigo="B")
    supply, _ = Insumo.objects.get_or_create(empresa=branch.empresa, codigo="OP09-FICTICIO", defaults={"nombre": "Material ficticio de prueba", "area": "bodega", "unidad": "un"})
    for i in range(70):
        name = f"op09_carga_{i + 1:02}"
        u, created = User.objects.get_or_create(username=name)
        if created:
            u.set_password("OP09-carga-ficticia-2026")
            u.save()
        profile, _ = PerfilUsuario.objects.get_or_create(usuario=u, defaults={"empresa": branch.empresa, "sucursal": branch})
        profile.empresa, profile.sucursal = branch.empresa, branch
        profile.alcance, profile.nivel = "sucursal", "trabajador"
        profile.rol, profile.area = roles[i % 4], areas[i % 4]
        profile.cargo = "OP09 carga ficticia"
        profile.full_clean()
        profile.save()
        item = {"username": name, "area": profile.area}
        if profile.area == "bodega":
            lot, new = LoteInventario.objects.get_or_create(sucursal=branch, insumo=supply, codigo=name, defaults={"estado_calidad": "no_requiere"})
            if new:
                registrar_entrada(lote=lot, ubicacion=a, cantidad=Decimal("10000"), usuario=author, documento_tipo="OP09.Fixture", documento_id=i + 1)
            ea = Existencia.objects.get(lote=lot, ubicacion=a)
            eb, _ = Existencia.objects.get_or_create(lote=lot, ubicacion=b)
            item.update(lot=lot.pk, existence_a=ea.pk, existence_b=eb.pk, location_a=a.pk, location_b=b.pk)
        accounts.append(item)
(runtime / "load-accounts.json").write_text(json.dumps(accounts, indent=2), encoding="utf-8")
print("OP09_LOAD_FIXTURE", len(accounts), "synthetic accounts; stock dedicated and traceable")
