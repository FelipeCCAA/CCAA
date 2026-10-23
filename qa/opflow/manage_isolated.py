"""Fresh OP09 load rerun, restricted to its own fictitious local cluster."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import psycopg2

REPO = Path(__file__).resolve().parents[2]
RUNTIME = REPO.parent / "opflow-runtime"
TARGET = dict(host="127.0.0.1", port=55479, user="opflow_test", dbname="postgres")


def verify_cluster():
    with psycopg2.connect(**TARGET) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_setting('data_directory'),current_user,host(inet_server_addr()),inet_server_port()")
        directory, role, host, port = cur.fetchone()
        if (Path(directory).resolve() != (RUNTIME / "pgdata").resolve()
                or (role, host, port) != ("opflow_test", "127.0.0.1", 55479)):
            raise RuntimeError("OPFLOW cluster identity mismatch")
        cur.execute("SELECT datname FROM pg_database WHERE NOT datistemplate AND datname<>'postgres'")
        if not {r[0] for r in cur.fetchall()} <= {"opflow_circuito"}:
            raise RuntimeError("Unexpected database in OPFLOW cluster")
    return {"directory": directory, "role": role, "host": host, "port": port}


def environment():
    spec = importlib.util.spec_from_file_location("old_environment", REPO / "qa/op09/manage_isolated.py")
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    env = old.environment()
    env.update({
        "PYTHONUNBUFFERED": "1",
        "DATABASE_URL": "postgresql://opflow_test@127.0.0.1:55479/opflow_circuito",
        "CCAA_MEDIA_ROOT": str(RUNTIME / "media"),
        "DJANGO_SECRET_KEY": "op09r-isolated-synthetic-only-key-012345678901234567890",
    })
    return env


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in {"check", "shell", "createcachetable", "runserver", "migrate", "configurar_maestro_inicial", "configurar_inventario_inicial", "crear_usuario_e2e", "crear_usuarios_flujo_e2e", "preparar_circuito_polvo"}:
        raise SystemExit("Command outside isolated QA scope")
    if args[0] == "runserver" and args != ["runserver", "127.0.0.1:8209", "--noreload"]:
        raise SystemExit("Only dedicated OPFLOW loopback port allowed")
    print("OPFLOW_ISOLATION " + json.dumps(verify_cluster()), flush=True)
    result = subprocess.run([sys.executable, "manage.py", *args], cwd=REPO / "backend", env=environment())
    raise SystemExit(result.returncode)
