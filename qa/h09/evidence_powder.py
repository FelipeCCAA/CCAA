"""Read-only evidence of the real synthetic browser circuit, not authentication data."""
import json
from pathlib import Path

from django.conf import settings

from auditoria.models import RegistroAuditoria
from calidad.models import Liberacion, LiberacionProceso
from calidad.vigencia import exigir_liberacion_lote_vigente, exigir_liberacion_salida_vigente
from inventario.models import ExistenciaProductoTerminado
from produccion.models import Lote, PalletProducto

database = settings.DATABASES["default"]
assert database["NAME"] == "h09_firmas" and str(database["PORT"]) == "55459" and database["HOST"] == "127.0.0.1"
repo = Path(settings.BASE_DIR).parent
runtime = repo.parent / "h09-runtime"
flow = json.loads((repo / "frontend/e2e/.registro/flujo-polvo.json").read_text())
assert flow["lote"].startswith("H09-POLVO-")
lot = Lote.objects.get(codigo_lote=flow["lote"])
releases = []
for release in LiberacionProceso.objects.filter(salida__lote=lot).select_related("salida__ejecucion__etapa"):
    assert exigir_liberacion_salida_vigente(release.salida_id, bloquear=False) == str(release.firma_id)
    events = RegistroAuditoria.objects.filter(modelo="calidad.LiberacionProceso", objeto_id=str(release.pk), cambios__has_key="firma_id")
    acts = sum(bool(e.cambios["firma_id"][1]) for e in events)
    releases.append({"stage": release.salida.ejecucion.etapa.tipo, "output_id": release.salida_id, "quantity": str(release.salida.cantidad), "unit": release.salida.unidad, "state": release.estado, "format": release.evidencia_firmada["formato"], "evidence_version": release.version_evidencia, "signature_acts": acts})
assert len(releases) == 2 and all(r["format"] == 2 and r["signature_acts"] == 1 for r in releases)
commercial = Liberacion.objects.get(lote=lot)
assert exigir_liberacion_lote_vigente(lot.pk, bloquear=False) == str(commercial.firma_id)
pallet = PalletProducto.objects.get(envase__lote=lot)
stock = ExistenciaProductoTerminado.objects.select_related("ubicacion__bodega").get(pallet=pallet)
assert pallet.kg_neto == 500 and stock.activo and stock.ubicacion.codigo == "PT-DISP"
result = {"scope": "Fictitious H09 circuit continued in documented cuts; no physical recipe/yield certified", "lot_id": lot.pk, "lot": lot.codigo_lote, "stage_releases": releases, "commercial_signature_valid": True, "pallet": pallet.codigo, "kg": str(pallet.kg_neto), "pallet_state": pallet.estado, "active_stock": stock.activo, "location": stock.ubicacion.codigo}
output = runtime / "powder-browser-evidence.json"
assert not output.exists(), "Preserve prior evidence"
output.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
