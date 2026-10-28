from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data")).resolve()
DB_PATH = Path(os.environ.get("DATABASE_PATH", DATA_DIR / "auction.db")).resolve()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgresql+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)
USE_POSTGRES = DATABASE_URL.startswith(("postgresql://", "postgres://", "postgresql+psycopg://"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('seller', 'bidder')),
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS wallets (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    total_cents BIGINT NOT NULL DEFAULT 0 CHECK(total_cents >= 0)
);

CREATE TABLE IF NOT EXISTS wallet_movements (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL CHECK(kind IN ('deposit', 'auction_payment', 'seller_credit')),
    amount_cents BIGINT NOT NULL CHECK(amount_cents > 0),
    lot_id TEXT,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS wallet_movements_user_idx ON wallet_movements(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS catalog_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    cover_url TEXT,
    source_url TEXT NOT NULL,
    source_label TEXT NOT NULL,
    item_json TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS catalog_title_idx ON catalog_items(title);

CREATE TABLE IF NOT EXISTS catalog_search_cache (
    query_key TEXT PRIMARY KEY,
    result_json TEXT NOT NULL,
    source_mode TEXT NOT NULL,
    fetched_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS lots (
    id TEXT PRIMARY KEY,
    seller_id TEXT NOT NULL REFERENCES users(id),
    catalog_item_id TEXT NOT NULL,
    title TEXT NOT NULL,
    authors TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    cover_url TEXT,
    source_url TEXT NOT NULL,
    source_label TEXT NOT NULL,
    item_snapshot TEXT NOT NULL,
    initial_cents BIGINT NOT NULL CHECK(initial_cents > 0),
    increment_cents BIGINT NOT NULL CHECK(increment_cents > 0),
    current_cents BIGINT NOT NULL DEFAULT 0 CHECK(current_cents >= 0),
    current_bidder_id TEXT REFERENCES users(id),
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('scheduled', 'active', 'closed', 'cancelled')),
    created_at TEXT NOT NULL,
    winner_user_id TEXT REFERENCES users(id),
    winning_cents BIGINT NOT NULL DEFAULT 0 CHECK(winning_cents >= 0),
    event_seq BIGINT NOT NULL DEFAULT 0,
    event_head TEXT NOT NULL,
    event_sig TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS lots_status_end_idx ON lots(status, end_at);
CREATE INDEX IF NOT EXISTS lots_seller_idx ON lots(seller_id, created_at DESC);

CREATE TABLE IF NOT EXISTS bids (
    id TEXT PRIMARY KEY,
    lot_id TEXT NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
    bidder_id TEXT NOT NULL REFERENCES users(id),
    amount_cents BIGINT NOT NULL CHECK(amount_cents > 0),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS bids_lot_time_idx ON bids(lot_id, created_at DESC);

CREATE TABLE IF NOT EXISTS lot_participants (
    lot_id TEXT NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id),
    public_alias TEXT NOT NULL,
    PRIMARY KEY(lot_id, user_id),
    UNIQUE(lot_id, public_alias)
);

CREATE TABLE IF NOT EXISTS wallet_holds (
    lot_id TEXT NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id),
    amount_cents BIGINT NOT NULL CHECK(amount_cents > 0),
    PRIMARY KEY(lot_id, user_id)
);
CREATE INDEX IF NOT EXISTS wallet_holds_user_idx ON wallet_holds(user_id);

CREATE TABLE IF NOT EXISTS auction_events (
    id TEXT PRIMARY KEY,
    lot_id TEXT NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
    sequence BIGINT NOT NULL,
    event_type TEXT NOT NULL,
    actor_public_id TEXT NOT NULL,
    amount_cents BIGINT,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    UNIQUE(lot_id, sequence)
);
CREATE INDEX IF NOT EXISTS auction_events_lot_idx ON auction_events(lot_id, sequence);
"""


class DBConnection:
    def __init__(self, raw, dialect: str):
        self.raw = raw
        self.dialect = dialect

    def execute(self, sql: str, params=()):
        if self.dialect == "postgres":
            sql = sql.replace("?", "%s")
        return self.raw.execute(sql, params)

    def executescript(self, script: str) -> None:
        if self.dialect != "sqlite":
            for statement in script.split(";"):
                if statement.strip():
                    self.execute(statement)
        else:
            self.raw.executescript(script)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()

    def close(self) -> None:
        self.raw.close()


def connect(transactional: bool = False) -> DBConnection:
    if USE_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row

        raw = psycopg.connect(
            DATABASE_URL,
            autocommit=not transactional,
            row_factory=dict_row,
            connect_timeout=8,
        )
        return DBConnection(raw, "postgres")

    raw = sqlite3.connect(DB_PATH, timeout=8, isolation_level=None)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    raw.execute("PRAGMA busy_timeout = 8000")
    return DBConnection(raw, "sqlite")


@contextmanager
def transaction() -> Iterator[DBConnection]:
    conn = connect(transactional=True)
    try:
        if conn.dialect == "sqlite":
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def lock_lot(conn: DBConnection, lot_id: str) -> None:
    if conn.dialect == "postgres":
        conn.execute("SELECT id FROM lots WHERE id = ? FOR UPDATE", (lot_id,))


def lock_wallets(conn: DBConnection, user_ids: list[str | None]) -> None:
    if conn.dialect == "postgres":
        for user_id in sorted({value for value in user_ids if value}):
            conn.execute("SELECT user_id FROM wallets WHERE user_id = ? FOR UPDATE", (user_id,))


def init_schema() -> None:
    conn = connect(transactional=True)
    try:
        if conn.dialect == "sqlite":
            conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
