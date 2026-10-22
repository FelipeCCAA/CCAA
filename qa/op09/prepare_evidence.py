"""Upload and download synthetic evidence through the real protected API."""
import hashlib
import http.client
import json
import uuid
from urllib.parse import urlsplit
from manage_isolated import RUNTIME, verify_cluster

verify_cluster()
account = json.loads((RUNTIME / "load-accounts.json").read_text())[1]
token = json.loads((RUNTIME / "synthetic-sessions.json").read_text())[account["username"]]
content = b"documento,origen,estado\nOP09,datos ficticios,prueba de restauracion\n"
boundary = "op09" + uuid.uuid4().hex
parts = []
for name, value in {"documento_tipo": "inventario.LoteInventario", "documento_id": str(account["lot"]), "tipo": "OP09_evidencia_ficticia"}.items():
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="archivo"; filename="op09-evidencia.csv"\r\nContent-Type: text/csv\r\n\r\n'.encode() + content + f'\r\n--{boundary}--\r\n'.encode())
connection = http.client.HTTPConnection("127.0.0.1", 8209, timeout=15)
connection.request("POST", "/api/inventario/adjuntos/", body=b"".join(parts), headers={"Authorization": "Token " + token, "Content-Type": "multipart/form-data; boundary=" + boundary})
response = connection.getresponse()
body = response.read()
if response.status != 201:
    raise RuntimeError(f"Evidence upload HTTP {response.status}: {body[:300]!r}")
attachment = json.loads(body)
connection.close()
url = urlsplit(attachment["archivo"])
assert url.hostname in {None, "127.0.0.1"} and url.path.startswith("/api/")
connection = http.client.HTTPConnection("127.0.0.1", 8209, timeout=15)
connection.request("GET", url.path, headers={"Authorization": "Token " + token})
response = connection.getresponse()
downloaded = response.read()
assert response.status == 200 and downloaded == content
assert response.getheader("Cache-Control") == "private, no-store"
result = {"id": attachment["id"], "path": url.path, "sha256": hashlib.sha256(content).hexdigest(), "download_bytes": len(downloaded), "private": True}
connection.close()
(RUNTIME / "evidence-upload.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print("OP09_PRIVATE_EVIDENCE_OK " + json.dumps(result))
