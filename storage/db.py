"""Wrapper asynchrone pour SQLite/Postgres.

Le module essaie d'utiliser aiosqlite pour SQLite et asyncpg pour Postgres si disponibles.
Sinon, il utilise sqlite3 en ThreadPoolExecutor pour rester non-bloquant.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Iterable, List, Optional
import json
from pathlib import Path

DB_DSN_ENV = "QL_DB_DSN"


class AsyncDB:
    """Interface minimale asynchrone pour stockage.

    - dsn: acceptons sqlite:///path or postgres DSN
    - ensure_schema() applique le SQL de storage/schema.sql
    """

    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn or os.getenv(DB_DSN_ENV, "sqlite:///./quant_engine.db")
        self._conn: Optional[sqlite3.Connection] = None
        self._executor = ThreadPoolExecutor(max_workers=2)

    async def connect(self) -> None:
        # Support minimal: sqlite only via sqlite3 + executor
        if self.dsn.startswith("sqlite"):
            # extract path
            path = self.dsn.split("///", 1)[-1]
            loop = asyncio.get_running_loop()
            def open_conn():
                conn = sqlite3.connect(path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                return conn

            self._conn = await loop.run_in_executor(self._executor, open_conn)
        else:
            raise RuntimeError("Only sqlite DSN supported in this lightweight wrapper")

    async def close(self) -> None:
        if self._conn:
            await asyncio.get_running_loop().run_in_executor(self._executor, self._conn.close)

    async def ensure_schema(self) -> None:
        """Applique le fichier schema.sql depuis storage/schema.sql"""
        here = os.path.dirname(__file__)
        schema_path = os.path.join(here, "schema.sql")
        with open(schema_path, "r", encoding="utf8") as f:
            sql = f.read()
        await self.executescript(sql)

    async def executescript(self, script: str) -> None:
        if not self._conn:
            raise RuntimeError("DB not connected")
        def _exec():
            self._conn.executescript(script)
            self._conn.commit()
        await asyncio.get_running_loop().run_in_executor(self._executor, _exec)

    async def fetchall(self, query: str, params: Optional[Iterable[Any]] = None) -> List[Dict[str, Any]]:
        if not self._conn:
            raise RuntimeError("DB not connected")
        params = params or []
        def _run():
            cur = self._conn.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            return rows
        return await asyncio.get_running_loop().run_in_executor(self._executor, _run)

    async def execute(self, query: str, params: Optional[Iterable[Any]] = None) -> None:
        if not self._conn:
            raise RuntimeError("DB not connected")
        params = params or []
        def _run():
            self._conn.execute(query, params)
            self._conn.commit()
        await asyncio.get_running_loop().run_in_executor(self._executor, _run)

    async def upsert_matches(self, matches: List[Dict[str, Any]]) -> None:
        """Inserer ou mettre à jour une liste de matches (upsert simplifié)."""
        if not self._conn:
            raise RuntimeError("DB not connected")

        def _run(items: List[Dict[str, Any]]):
            cur = self._conn.cursor()
            for m in items:
                cur.execute(
                    """
                    INSERT INTO matches(match_id, home_team, away_team, start_time, status, meta)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(match_id) DO UPDATE SET
                        home_team=excluded.home_team,
                        away_team=excluded.away_team,
                        start_time=excluded.start_time,
                        status=excluded.status,
                        meta=excluded.meta
                    """,
                    (
                        str(m.get("id")),
                        m.get("home_team"),
                        m.get("away_team"),
                        m.get("start_time"),
                        m.get("status"),
                        str(m.get("meta", {})),
                    ),
                )
            self._conn.commit()

        await asyncio.get_running_loop().run_in_executor(self._executor, _run, matches)

    async def insert_prediction_from_dict(self, d: Dict[str, Any]) -> None:
        """Insert a prediction dict (from registry JSON) into the predictions table."""
        if not self._conn:
            raise RuntimeError("DB not connected")

        def _run(item: Dict[str, Any]):
            fixture_id = item.get("fixture_id") or item.get("id") or None
            market = item.get("prediction") or item.get("market") or None
            prob = item.get("probability")
            prob_pct = item.get("probability_pct")
            confidence = item.get("confidence")
            status = item.get("status")
            result = item.get("result")
            total_cards = item.get("total_cards_final")
            ts_pred = item.get("timestamp_prediction")
            ts_val = item.get("timestamp_validated")
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO predictions(fixture_id, market, probability, probability_pct, confidence, status, result, total_cards_final, timestamp_prediction, timestamp_validated, raw) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    fixture_id,
                    market,
                    prob,
                    prob_pct,
                    confidence,
                    status,
                    result,
                    total_cards,
                    ts_pred,
                    ts_val,
                    json.dumps(item, default=str),
                ),
            )
            self._conn.commit()

        await asyncio.get_running_loop().run_in_executor(self._executor, _run, d)

    async def migrate_registries_from_dir(self, folder: str) -> int:
        """Import all prediction_registry*.json files from a folder. Returns count of inserted rows."""
        p = Path(folder)
        if not p.exists():
            raise FileNotFoundError(folder)
        total = 0
        for f in p.glob("prediction_registry*.json"):
            data = json.loads(f.read_text(encoding="utf8"))
            preds = data.get("predictions") or data.get("items") or {}
            for k, v in preds.items():
                await self.insert_prediction_from_dict(v)
                total += 1
        return total

