"""Fresh OP09 load rerun, restricted to its own fictitious local cluster."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import psycopg2

REPO = Path(__file__).resolve().parents[2]
RUNTIME = REPO.parent / "op09r-runtime"
TARGET = dict(host="127.0.0.1", port=55469, user="op09r_test", dbname="postgres")


def verify_cluster():
    with psycopg2.connect(**TARGET) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_setting('data_directory'),current_user,host(inet_server_addr()),inet_server_port()")
        directory, role, host, port = cur.fetchone()
        if (Path(directory).resolve() != (RUNTIME / "pgdata").resolve()
                or (role, host, port) != ("op09r_test", "127.0.0.1", 55469)):
            raise RuntimeError("OP09R cluster identity mismatch")
        cur.execute("SELECT datname FROM pg_database WHERE NOT datistemplate AND datname<>'postgres'")
        if not {r[0] for r in cur.fetchall()} <= {"op09r_carga"}:
            raise RuntimeError("Unexpected database in OP09R cluster")
    return {"directory": directory, "role": role, "host": host, "port": port}


def environment():
    spec = importlib.util.spec_from_file_location("old_environment", REPO / "qa/op09/manage_isolated.py")
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    env = old.environment()
    env.update({
        "PYTHONUNBUFFERED": "1",
        "DATABASE_URL": "postgresql://op09r_test@127.0.0.1:55469/op09r_carga",
        "CCAA_MEDIA_ROOT": str(RUNTIME / "media"),
        "DJANGO_SECRET_KEY": "op09r-isolated-synthetic-only-key-012345678901234567890",
    })
    return env


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in {"check", "shell", "createcachetable", "runserver"}:
        raise SystemExit("Command outside isolated QA scope")
    if args[0] == "runserver" and args != ["runserver", "127.0.0.1:8229", "--noreload"]:
        raise SystemExit("Only dedicated OP09R loopback port allowed")
    print("OP09R_ISOLATION " + json.dumps(verify_cluster()), flush=True)
    result = subprocess.run([sys.executable, "manage.py", *args], cwd=REPO / "backend", env=environment())
    raise SystemExit(result.returncode)
