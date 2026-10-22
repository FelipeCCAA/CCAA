"""Restore only a fresh OP09 database and private-file tree, never overwrite."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import time

import psycopg2
from psycopg2 import sql
from manage_isolated import RUNTIME, TARGET, environment, verify_cluster

PG_BIN = Path("C:/Program Files/PostgreSQL/17/bin")


def snapshot(database, media):
    tables = {}
    with psycopg2.connect(**dict(TARGET, dbname=database)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            names = [r[0] for r in cur.fetchall()]
            for name in names:
                digest, count = hashlib.sha256(), 0
                cur.execute(sql.SQL('SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text COLLATE "C"').format(sql.Identifier(name)))
                for (row,) in cur:
                    digest.update(row.encode("utf-8") + b"\n")
                    count += 1
                tables[name] = {"rows": count, "sha256": digest.hexdigest()}
            expected = json.loads((RUNTIME / "evidence-upload.json").read_text(encoding="utf-8"))
            cur.execute("SELECT hash_sha256 FROM inventario_adjunto WHERE id=%s", (expected["id"],))
            if cur.fetchone() != (expected["sha256"],):
                raise RuntimeError("The exact API-uploaded evidence is absent or changed")
            cur.execute("SELECT archivo,hash_sha256 FROM inventario_adjunto ORDER BY id")
            attachments = cur.fetchall()
    files = {}
    if media.exists():
        for file in sorted(media.rglob("*")):
            if file.is_symlink() or not file.resolve().is_relative_to(media.resolve()):
                raise RuntimeError("File escapes isolated private-media root")
            if file.is_file():
                files[file.relative_to(media).as_posix()] = {"bytes": file.stat().st_size, "sha256": hashlib.file_digest(file.open("rb"), "sha256").hexdigest()}
    for name, expected in attachments:
        if name not in files or files[name]["sha256"] != expected:
            raise RuntimeError("Attachment missing or checksum differs: " + name)
    return {"tables": tables, "files": files, "attachments": len(attachments)}


def main():
    identity = verify_cluster()
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", 8209)) == 0:
            raise SystemExit("Freeze every OP09 writer before backup; API still running")
    with psycopg2.connect(**dict(TARGET, dbname="op09_circuito")) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname='op09_circuito' AND pid<>pg_backend_pid() AND backend_type='client backend'")
            if cur.fetchone()[0]:
                raise SystemExit("Other source database clients remain; refuse inconsistent cut")
    target_media = RUNTIME / "media-restaurada"
    if target_media.exists():
        raise SystemExit("Refusing to overwrite restored private files")
    conn = psycopg2.connect(**TARGET)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname='op09_restaurada'")
        if cur.fetchone():
            raise SystemExit("Refusing existing restore destination")
    conn.close()
    started = time.perf_counter()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = RUNTIME / ("backup-" + stamp)
    backup.mkdir()
    source_media = RUNTIME / "media"
    before = snapshot("op09_circuito", source_media)
    if not before["attachments"]:
        raise RuntimeError("Backup test must include at least one real API attachment")
    dump = backup / "database.dump"
    command = [str(PG_BIN / "pg_dump.exe"), "--host=127.0.0.1", "--port=55449", "--username=op09_test", "--no-password", "--format=custom", "--no-owner", "--file=" + str(dump), "op09_circuito"]
    subprocess.run(command, check=True, env=environment())
    shutil.copytree(source_media, backup / "private-files")
    if snapshot("op09_circuito", source_media) != before:
        raise RuntimeError("Source changed during backup; refuse inconsistent cut")
    backup_seconds = time.perf_counter() - started
    restore_start = time.perf_counter()
    conn = psycopg2.connect(**TARGET)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute('CREATE DATABASE "op09_restaurada"')
    conn.close()
    subprocess.run([str(PG_BIN / "pg_restore.exe"), "--host=127.0.0.1", "--port=55449", "--username=op09_test", "--no-password", "--no-owner", "--exit-on-error", "--dbname=op09_restaurada", str(dump)], check=True, env=environment("op09_restaurada"))
    shutil.copytree(backup / "private-files", target_media)
    restore_seconds = time.perf_counter() - restore_start
    after = snapshot("op09_restaurada", target_media)
    if before != after:
        raise RuntimeError("Restored database/private files differ from frozen source")
    report = {"identity": identity, "timestamp_utc": stamp, "backup_seconds": backup_seconds, "restore_seconds": restore_seconds, "verification_seconds": time.perf_counter() - restore_start, "dump_bytes": dump.stat().st_size, "dump_sha256": hashlib.file_digest(dump.open("rb"), "sha256").hexdigest(), "source_equals_restore": True, "tables_compared": len(before["tables"]), "attachments_verified": before["attachments"], "manifest": before, "rpo_scope": "zero divergence at frozen synthetic cut; no production schedule/RPO certified", "rto_scope": "measured dump/restore/verification on local dataset; application smoke measured separately"}
    (backup / "manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (RUNTIME / "backup-summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("OP09_RESTORE_OK " + json.dumps({k: v for k, v in report.items() if k != "manifest"}), flush=True)


if __name__ == "__main__":
    main()
