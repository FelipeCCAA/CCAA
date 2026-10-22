"""H09-only runner: dedicated loopback PostgreSQL and fictitious restored data."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import psycopg2

REPO = Path(__file__).resolve().parents[2]
RUNTIME = REPO.parent / "h09-runtime"
TARGET = dict(host="127.0.0.1", port=55459, user="h09_test", dbname="postgres")


def verify_cluster():
    with psycopg2.connect(**TARGET) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('data_directory'),current_user,host(inet_server_addr()),inet_server_port()")
            directory, role, address, port = cur.fetchone()
            assert Path(directory).resolve() == (RUNTIME / "pgdata").resolve()
            assert (role, address, port) == ("h09_test", "127.0.0.1", 55459)
            cur.execute("SELECT datname FROM pg_database WHERE NOT datistemplate AND datname<>'postgres'")
            assert {r[0] for r in cur.fetchall()} <= {"h09_firmas", "test_h09_firmas"}
    return {"directory": directory, "role": role, "address": address, "port": port}


def environment():
    spec = importlib.util.spec_from_file_location("op09_environment", REPO / "qa/op09/manage_isolated.py")
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    env = previous.environment()
    env.update({
        "PYTHONUNBUFFERED": "1",
        "DATABASE_URL": "postgresql://h09_test@127.0.0.1:55459/h09_firmas",
        "CCAA_MEDIA_ROOT": str(RUNTIME / "media"),
        "DJANGO_SECRET_KEY": "h09-synthetic-only-isolated-key-012345678901234567890123",
    })
    return env


if __name__ == "__main__":
    args = sys.argv[1:]
    assert args and args[0] in {"migrate", "check", "makemigrations", "shell", "test", "runserver", "preparar_circuito_polvo"}
    if args[0] == "makemigrations":
        assert args == ["makemigrations", "--check", "--dry-run"]
    if args[0] == "runserver":
        assert args == ["runserver", "127.0.0.1:8209", "--noreload"]
    print("H09_ISOLATION " + json.dumps(verify_cluster()), flush=True)
    child = subprocess.Popen([sys.executable, "manage.py", *args], cwd=REPO / "backend", env=environment())
    if args[0] == "runserver":
        (RUNTIME / "server-8209.json").write_text(json.dumps({"pid": child.pid, "port": 8209, "database": "h09_firmas"}), encoding="utf-8")
    raise SystemExit(child.wait())
