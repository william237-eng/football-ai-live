"""Script to migrate JSON prediction registries into the SQLite DB.

Usage (PowerShell):
$env:QL_DB_DSN = 'sqlite:///./quant_engine.db'
python .\scripts\migrate_registries_to_db.py
"""
import asyncio
import os
import sys
from pathlib import Path

from storage.db import AsyncDB


async def main() -> int:
    db_dsn = os.getenv("QL_DB_DSN", "sqlite:///./quant_engine.db")
    repo_root = Path(__file__).resolve().parents[1]
    registry_folder = repo_root / "database"

    db = AsyncDB(dsn=db_dsn)
    await db.connect()
    await db.ensure_schema()
    print(f"Migrating registries from {registry_folder} into {db_dsn} ...")
    count = await db.migrate_registries_from_dir(str(registry_folder))
    print(f"Inserted {count} prediction rows.")
    await db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

