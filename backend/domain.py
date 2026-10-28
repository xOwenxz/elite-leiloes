from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from crypto import hash_password, sign_snapshot
from db import transaction


ZERO_HASH = "0" * 64
SELLER_ID = "demo-seller"
ANA_ID = "demo-ana"
BRUNO_ID = "demo-bruno"


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(value: datetime | None = None) -> str:
    moment = value or utc_now()
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_load(value: str) -> Any:
    return json.loads(value)


DEMO_CATALOG = [
    {
        "id": "demo-dom-casmurro",
        "title": "Dom Casmurro",
        "authors": "Machado de Assis",
        "description": "Romance clássico brasileiro. Item de demonstração do catálogo de livros.",
        "cover_url": None,
        "source_url": "https://openlibrary.org/search?q=dom+casmurro",
        "source_label": "Open Library · catálogo local de demonstração",
        "item_json": {"source": "Open Library", "query": "dom casmurro", "demo_fallback": True},
    },
    {
        "id": "demo-quincas-borba",
        "title": "Quincas Borba",
        "authors": "Machado de Assis",
        "description": "Romance clássico brasileiro. Item de demonstração do catálogo de livros.",
        "cover_url": None,
        "source_url": "https://openlibrary.org/search?q=quincas+borba",
        "source_label": "Open Library · catálogo local de demonstração",
        "item_json": {"source": "Open Library", "query": "quincas borba", "demo_fallback": True},
    },
    {
        "id": "demo-o-cortico",
        "title": "O Cortiço",
        "authors": "Aluísio Azevedo",
        "description": "Romance clássico brasileiro. Item de demonstração do catálogo de livros.",
        "cover_url": None,
        "source_url": "https://openlibrary.org/search?q=o+cortico",
        "source_label": "Open Library · catálogo local de demonstração",
        "item_json": {"source": "Open Library", "query": "o cortico", "demo_fallback": True},
    },
]


def event_digest(previous_hash: str, event: dict[str, Any]) -> str:
    canonical = json_dump(event).encode("utf-8")
    return hashlib.sha256(previous_hash.encode("ascii") + b"\n" + canonical).hexdigest()


def refresh_signature(conn: sqlite3.Connection, lot_id: str) -> None:
    row = conn.execute("SELECT * FROM lots WHERE id = ?", (lot_id,)).fetchone()
    if row is None:
        return
    conn.execute("UPDATE lots SET event_sig = ? WHERE id = ?", (sign_snapshot(dict(row)), lot_id))


def append_event(
    conn: sqlite3.Connection,
    lot_id: str,
    event_type: str,
    actor_public_id: str = "Sistema",
    amount_cents: int | None = None,
    payload: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    lot = conn.execute("SELECT * FROM lots WHERE id = ?", (lot_id,)).fetchone()
    if lot is None:
        raise ValueError("Lote não encontrado.")
    event_id = new_id()
    sequence = int(lot["event_seq"]) + 1
    previous_hash = str(lot["event_head"])
    timestamp = created_at or iso()
    body = {
        "id": event_id,
        "lot_id": lot_id,
        "sequence": sequence,
        "event_type": event_type,
        "actor_public_id": actor_public_id,
        "amount_cents": amount_cents,
        "created_at": timestamp,
        "payload": payload or {},
    }
    digest = event_digest(previous_hash, body)
    conn.execute(
        """INSERT INTO auction_events
        (id, lot_id, sequence, event_type, actor_public_id, amount_cents, created_at,
         payload_json, previous_hash, event_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            event_id,
            lot_id,
            sequence,
            event_type,
            actor_public_id,
            amount_cents,
            timestamp,
            json_dump(payload or {}),
            previous_hash,
            digest,
        ),
    )
    conn.execute(
        "UPDATE lots SET event_seq = ?, event_head = ? WHERE id = ?",
        (sequence, digest, lot_id),
    )
    refresh_signature(conn, lot_id)
    return {**body, "previous_hash": previous_hash, "event_hash": digest}


def participant_alias(conn: sqlite3.Connection, lot_id: str, user_id: str) -> str:
    row = conn.execute(
        "SELECT public_alias FROM lot_participants WHERE lot_id = ? AND user_id = ?",
        (lot_id, user_id),
    ).fetchone()
    if row:
        return str(row["public_alias"])
    for _ in range(8):
        alias = "Licitante-" + secrets.token_hex(2).upper()
        try:
            conn.execute(
                "INSERT INTO lot_participants (lot_id, user_id, public_alias) VALUES (?, ?, ?)",
                (lot_id, user_id, alias),
            )
            return alias
        except sqlite3.IntegrityError:
            continue
    raise RuntimeError("Não foi possível criar um identificador público para o licitante.")


def seed_demo() -> None:
    now = utc_now()
    with transaction() as conn:
        count = int(conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"])
        if count:
            return

        users = [
            (SELLER_ID, "Leiloeiro Verzel", "leiloeiro@demo.local", "seller", "verzel123"),
            (ANA_ID, "Ana Colecionadora", "ana@demo.local", "bidder", "ana123"),
            (BRUNO_ID, "Bruno Colecionador", "bruno@demo.local", "bidder", "bruno123"),
        ]
        for user_id, name, email, role, password in users:
            conn.execute(
                "INSERT INTO users (id, name, email, role, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, name, email, role, hash_password(password), iso(now)),
            )
            conn.execute("INSERT INTO wallets (user_id, total_cents) VALUES (?, ?)", (user_id, 0))

        conn.execute("UPDATE wallets SET total_cents = ? WHERE user_id = ?", (90_000, ANA_ID))
        conn.execute("UPDATE wallets SET total_cents = ? WHERE user_id = ?", (75_000, BRUNO_ID))
        for user_id, amount, note in (
            (ANA_ID, 90_000, "Saldo inicial da conta de demonstração"),
            (BRUNO_ID, 75_000, "Saldo inicial da conta de demonstração"),
        ):
            conn.execute(
                """INSERT INTO wallet_movements
                (id, user_id, kind, amount_cents, lot_id, note, created_at)
                VALUES (?, ?, 'deposit', ?, NULL, ?, ?)""",
                (new_id(), user_id, amount, note, iso(now)),
            )

        for item in DEMO_CATALOG:
            conn.execute(
                """INSERT INTO catalog_items
                (id, title, authors, description, cover_url, source_url, source_label, item_json, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item["id"],
                    item["title"],
                    item["authors"],
                    item["description"],
                    item["cover_url"],
                    item["source_url"],
                    item["source_label"],
                    json_dump(item["item_json"]),
                    iso(now),
                ),
            )

        lot_id = new_id()
        starts_at = iso(now - timedelta(minutes=15))
        ends_at = iso(now + timedelta(minutes=15))
        item = DEMO_CATALOG[0]
        conn.execute(
            """INSERT INTO lots
            (id, seller_id, catalog_item_id, title, authors, description, cover_url, source_url,
             source_label, item_snapshot, initial_cents, increment_cents, current_cents,
             current_bidder_id, start_at, end_at, status, created_at, event_head, event_sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, '')""",
            (
                lot_id,
                SELLER_ID,
                item["id"],
                item["title"],
                item["authors"],
                "Edição de demonstração para percorrer o fluxo de lances ao vivo.",
                item["cover_url"],
                item["source_url"],
                item["source_label"],
                json_dump(item["item_json"]),
                3_000,
                500,
                8_000,
                ANA_ID,
                starts_at,
                ends_at,
                iso(now),
                ZERO_HASH,
            ),
        )

        aliases = {ANA_ID: "Licitante-A4C1", BRUNO_ID: "Licitante-81B2"}
        for user_id, alias in aliases.items():
            conn.execute(
                "INSERT INTO lot_participants (lot_id, user_id, public_alias) VALUES (?, ?, ?)",
                (lot_id, user_id, alias),
            )

        append_event(
            conn,
            lot_id,
            "lot_created",
            payload={
                "initial_cents": 3_000,
                "increment_cents": 500,
                "start_at": starts_at,
                "end_at": ends_at,
                "source": item["source_label"],
            },
            created_at=iso(now - timedelta(minutes=16)),
        )

        seeded_bids = [
            (BRUNO_ID, 4_000, now - timedelta(minutes=12)),
            (ANA_ID, 5_000, now - timedelta(minutes=10)),
            (BRUNO_ID, 6_500, now - timedelta(minutes=8)),
            (ANA_ID, 8_000, now - timedelta(minutes=6)),
        ]
        for bidder_id, amount, bid_time in seeded_bids:
            bid_id = new_id()
            timestamp = iso(bid_time)
            conn.execute(
                "INSERT INTO bids (id, lot_id, bidder_id, amount_cents, created_at) VALUES (?, ?, ?, ?, ?)",
                (bid_id, lot_id, bidder_id, amount, timestamp),
            )
            append_event(
                conn,
                lot_id,
                "bid_placed",
                actor_public_id=aliases[bidder_id],
                amount_cents=amount,
                payload={"bid_id": bid_id},
                created_at=timestamp,
            )
        conn.execute(
            "INSERT INTO wallet_holds (lot_id, user_id, amount_cents) VALUES (?, ?, ?)",
            (lot_id, ANA_ID, 8_000),
        )


def audit_lot(conn: sqlite3.Connection, lot: sqlite3.Row) -> dict[str, Any]:
    problems: list[str] = []
    rows = conn.execute(
        "SELECT * FROM auction_events WHERE lot_id = ? ORDER BY sequence",
        (lot["id"],),
    ).fetchall()
    previous = ZERO_HASH
    verified_events: list[dict[str, Any]] = []
    bid_events: dict[str, dict[str, Any]] = {}

    for expected_sequence, row in enumerate(rows, start=1):
        try:
            payload = json_load(row["payload_json"])
        except (ValueError, TypeError):
            payload = {}
            problems.append(f"Evento {expected_sequence}: conteúdo JSON inválido.")
        body = {
            "id": row["id"],
            "lot_id": row["lot_id"],
            "sequence": int(row["sequence"]),
            "event_type": row["event_type"],
            "actor_public_id": row["actor_public_id"],
            "amount_cents": row["amount_cents"],
            "created_at": row["created_at"],
            "payload": payload,
        }
        if int(row["sequence"]) != expected_sequence:
            problems.append(f"Evento {expected_sequence}: sequência ausente ou reordenada.")
        if row["previous_hash"] != previous:
            problems.append(f"Evento {expected_sequence}: elo anterior divergente.")
        computed = event_digest(previous, body)
        if not secrets.compare_digest(computed, row["event_hash"]):
            problems.append(f"Evento {expected_sequence}: hash divergente.")
        if row["event_type"] == "bid_placed":
            bid_id = str(payload.get("bid_id", ""))
            if not bid_id or bid_id in bid_events:
                problems.append(f"Evento {expected_sequence}: referência de lance inválida.")
            else:
                bid_events[bid_id] = {
                    "amount_cents": row["amount_cents"],
                    "created_at": row["created_at"],
                    "actor_public_id": row["actor_public_id"],
                }
        verified_events.append(
            {
                "id": row["id"],
                "sequence": int(row["sequence"]),
                "event_type": row["event_type"],
                "actor": row["actor_public_id"],
                "amount_cents": row["amount_cents"],
                "created_at": row["created_at"],
                "payload": payload,
                "event_hash": row["event_hash"],
            }
        )
        previous = row["event_hash"]

    lot_dict = dict(lot)
    if len(rows) != int(lot["event_seq"]):
        problems.append("A quantidade de eventos não corresponde ao checkpoint assinado.")
    if previous != lot["event_head"]:
        problems.append("O hash final não corresponde ao checkpoint assinado.")
    try:
        expected_signature = sign_snapshot(lot_dict)
        if not secrets.compare_digest(expected_signature, str(lot["event_sig"])):
            problems.append("A assinatura do checkpoint não confere.")
    except (KeyError, TypeError):
        problems.append("O checkpoint do lote está incompleto.")

    bid_rows = conn.execute(
        """SELECT b.id, b.bidder_id, b.amount_cents, b.created_at, p.public_alias
        FROM bids b
        LEFT JOIN lot_participants p ON p.lot_id = b.lot_id AND p.user_id = b.bidder_id
        WHERE b.lot_id = ?""",
        (lot["id"],),
    ).fetchall()
    stored_bids = {str(row["id"]): row for row in bid_rows}
    if set(stored_bids) != set(bid_events):
        problems.append("Os registros de lance não correspondem aos eventos auditáveis.")
    for bid_id, event in bid_events.items():
        stored = stored_bids.get(bid_id)
        if stored is None:
            continue
        if (
            int(stored["amount_cents"]) != int(event["amount_cents"])
            or stored["created_at"] != event["created_at"]
            or stored["public_alias"] != event["actor_public_id"]
        ):
            problems.append(f"O registro do lance {bid_id} diverge do evento auditável.")

    if bid_rows:
        last_bid_event = next(
            (event for event in reversed(verified_events) if event["event_type"] == "bid_placed"),
            None,
        )
        if last_bid_event:
            bidder_row = conn.execute(
                "SELECT bidder_id FROM bids WHERE id = ?",
                (last_bid_event["payload"].get("bid_id"),),
            ).fetchone()
            if (
                int(lot["current_cents"]) != int(last_bid_event["amount_cents"])
                or bidder_row is None
                or lot["current_bidder_id"] != bidder_row["bidder_id"]
            ):
                problems.append("O maior lance atual diverge do último lance registrado.")
            if lot["status"] == "closed" and (
                lot["winner_user_id"] != bidder_row["bidder_id"]
                or int(lot["winning_cents"]) != int(last_bid_event["amount_cents"])
            ):
                problems.append("O vencedor ou valor liquidado diverge do último lance.")
    elif lot["current_cents"] != 0 or lot["current_bidder_id"] is not None:
        problems.append("O lote informa um lance atual, mas não há lances registrados.")

    return {
        "valid": not problems,
        "checked_events": len(rows),
        "head_hash": previous,
        "problems": problems,
        "events": verified_events,
    }
