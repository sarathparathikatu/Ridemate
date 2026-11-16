"""Back up the database to a compressed file, and check that a backup is complete.

Run from the backend folder:

    uv run python -m scripts.backup_db                # writes backups/ridemate-<time>.sql.gz
    uv run python -m scripts.backup_db --keep 14      # ...and keeps only the newest 14 files
    uv run python -m scripts.backup_db --verify FILE  # checks a backup file is complete

It uses mysqldump, which ships with MySQL, and reads the connection details from the same
DATABASE_URL as the app. Schedule it (cron, Task Scheduler) and copy the files somewhere
else: a backup on the same disk as the database protects against mistakes, not disk loss.

A backup you have never restored is only a hope. To test one, load it into a spare database:

    mysql -u root -p -e "CREATE DATABASE restore_test"
    gunzip -c backups/ridemate-<time>.sql.gz | mysql -u root -p restore_test
"""

import argparse
import glob
import gzip
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import get_settings

WINDOWS_GUESSES = r"C:\Program Files\MySQL\MySQL Server *\bin\mysqldump.exe"
END_MARKER = b"-- Dump completed"  # mysqldump's last line; missing means the dump was cut short


def find_mysqldump(explicit: str | None) -> str:
    found = explicit or os.environ.get("MYSQLDUMP") or shutil.which("mysqldump")
    if not found and (guesses := sorted(glob.glob(WINDOWS_GUESSES))):
        found = guesses[-1]
    if not found:
        sys.exit("mysqldump not found. Install the MySQL client, or pass --mysqldump PATH.")
    return found


def backup(out_dir: Path, mysqldump: str) -> Path:
    url = make_url(get_settings().database_url)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{url.database}-{datetime.now():%Y%m%d-%H%M%S}.sql.gz"

    # The password goes in a private options file, not on the command line, where every
    # other user of the machine could read it in the process list.
    options = tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False, encoding="utf-8")
    try:
        escaped = (url.password or "").replace("\\", "\\\\").replace('"', '\\"')
        options.write(f'[client]\nuser="{url.username}"\npassword="{escaped}"\n')
        options.close()
        command = [
            mysqldump,
            f"--defaults-extra-file={options.name}",  # must be the first option
            f"--host={url.host or 'localhost'}",
            f"--port={url.port or 3306}",
            "--single-transaction",  # one consistent snapshot, without locking anyone out
            "--routines",
            "--no-tablespaces",  # otherwise mysqldump demands an extra privilege (PROCESS)
            "--default-character-set=utf8mb4",
            url.database,
        ]
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as dump:
            with gzip.open(target, "wb") as archive:
                shutil.copyfileobj(dump.stdout, archive)
            errors = dump.stderr.read().decode(errors="replace").strip()
        if dump.returncode != 0:
            target.unlink(missing_ok=True)  # never leave a half-written backup lying around
            sys.exit(f"mysqldump failed:\n{errors}")
    finally:
        os.unlink(options.name)
    return target


def verify(path: Path) -> int:
    """Read the whole file back: it must decompress and end with mysqldump's last line."""
    tables = 0
    tail = b""
    with gzip.open(path, "rb") as archive:
        for line in archive:
            if line.startswith(b"CREATE TABLE"):
                tables += 1
            if line.strip():
                tail = line
    if not tail.startswith(END_MARKER):
        sys.exit(f"{path} is incomplete: it doesn't end with '{END_MARKER.decode()}'.")
    return tables


def prune(out_dir: Path, keep: int) -> list[Path]:
    backups = sorted(out_dir.glob("*.sql.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        old.unlink()
    return backups[keep:]


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up the RideMate database")
    parser.add_argument("--out", type=Path, default=Path("backups"), help="folder for backup files")
    parser.add_argument("--keep", type=int, help="after backing up, keep only the newest N files")
    parser.add_argument("--verify", type=Path, metavar="FILE", help="only check this backup file")
    parser.add_argument("--mysqldump", help="path to mysqldump if it isn't on PATH")
    args = parser.parse_args()

    if args.verify:
        print(f"{args.verify}: complete, {verify(args.verify)} tables.")
        return
    target = backup(args.out, find_mysqldump(args.mysqldump))
    tables = verify(target)
    print(f"Backed up {tables} tables to {target} ({target.stat().st_size / 1024:.0f} KB).")
    if args.keep and (removed := prune(args.out, args.keep)):
        print(f"Removed {len(removed)} older backup(s).")


if __name__ == "__main__":
    main()
