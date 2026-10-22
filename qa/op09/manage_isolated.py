"""OP-09 test-only launcher. Refuses every database except its own cluster."""
import json
import os
from pathlib import Path
import subprocess
import sys

import psycopg2

REPO = Path(__file__).resolve().parents[2]
RUNTIME = REPO.parent / "op09-runtime"
BACKEND = REPO / "backend"
TARGET = dict(host="127.0.0.1", port=55449, user="op09_test", dbname="postgres")
DATABASES = {"op09_circuito", "op09_restaurada", "test_op09_circuito"}


def verify_cluster():
    with psycopg2.connect(**TARGET) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('data_directory'),current_user,host(inet_server_addr()),inet_server_port()")
            directory, role, address, port = cur.fetchone()
            if (Path(directory).resolve() != (RUNTIME / "pgdata").resolve()
                    or role != "op09_test" or address != "127.0.0.1" or port != 55449):
                raise SystemExit("OP09 isolation check failed")
            cur.execute("SELECT datname FROM pg_database WHERE NOT datistemplate AND datname <> 'postgres'")
            if not {x[0] for x in cur.fetchall()} <= DATABASES:
                raise SystemExit("Unexpected database in OP09 cluster")
    return dict(directory=directory, role=role, host=address, port=port)


def environment(database="op09_circuito"):
    if database not in DATABASES:
        raise SystemExit("Database outside OP09")
    if (BACKEND / ".env").exists():
        raise SystemExit("Refusing application .env")
    allowed = {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE"}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    env.update({
        "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHON_DOTENV_DISABLED": "1",
        "DJANGO_ENV": "test", "DJANGO_DEBUG": "false",
        "DJANGO_SECRET_KEY": "op09-synthetic-only-isolated-test-key-012345678901234567890",
        "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1,testserver",
        "DJANGO_SECURE_SSL_REDIRECT": "false", "DB_ENGINE": "postgresql",
        "DATABASE_URL": f"postgresql://op09_test@127.0.0.1:55449/{database}",
        "DB_CONN_MAX_AGE": "0", "CACHE_URL": "", "CELERY_BROKER_URL": "",
        "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
        "CCAA_MEDIA_ROOT": str(RUNTIME / ("media-restaurada" if database == "op09_restaurada" else "media")),
        "CCAA_INITIAL_COMPANY_RUT": "OP09-FICTICIA",
        "CCAA_INITIAL_COMPANY_NAME": "OP09 PLANTA FICTICIA",
        "CCAA_INITIAL_BRANCH_CODE": "OP09", "CCAA_INITIAL_BRANCH_NAME": "OP09 AISLADA",
    })
    return env


if __name__ == "__main__":
    args = sys.argv[1:]
    database = "op09_circuito"
    if args[:1] == ["--restored"]:
        database = "op09_restaurada"
        args = args[1:]
    permitted = {"migrate", "check", "shell", "runserver", "createcachetable", "test", "configurar_maestro_inicial", "configurar_inventario_inicial", "crear_usuario_e2e", "crear_usuarios_flujo_e2e", "preparar_circuito_polvo", "preparar_circuito_precondensado", "preparar_circuito_descremado", "preparar_circuito_mantequilla", "preparar_circuito_suero"}
    if not args or args[0] not in permitted:
        raise SystemExit("Command outside authorized test preparation")
    identity = verify_cluster()
    with psycopg2.connect(**TARGET) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname='op09_circuito'")
            exists = cur.fetchone()
    if not exists:
        conn = psycopg2.connect(**TARGET)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute('CREATE DATABASE "op09_circuito"')
        conn.close()
    port = 8219 if database == "op09_restaurada" else 8209
    if args[0] == "runserver" and args != ["runserver", f"127.0.0.1:{port}", "--noreload"]:
        raise SystemExit("Only loopback OP09 server allowed")
    print("OP09_ISOLATION " + json.dumps(identity), flush=True)
    process = subprocess.Popen([sys.executable, "manage.py", *args], cwd=BACKEND, env=environment(database))
    if args[0] == "runserver":
        (RUNTIME / f"server-{port}.json").write_text(json.dumps({"pid": process.pid, "port": port, "database": database, "identity": identity}), encoding="utf-8")
    raise SystemExit(process.wait())
