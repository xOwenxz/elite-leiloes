from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from crypto import receipt_token, verify_password
from db import BASE_DIR, connect, init_schema, lock_lot, lock_wallets, transaction
from domain import (
    DEMO_CATALOG,
    ZERO_HASH,
    append_event,
    audit_lot,
    iso,
    json_dump,
    json_load,
    new_id,
    parse_iso,
    participant_alias,
    seed_demo,
    utc_now,
)


SESSION_COOKIE = "elite_leiloes_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))
EVENT_LOOP: asyncio.AbstractEventLoop | None = None
SUBSCRIBERS: set[asyncio.Queue[str]] = set()

logger = logging.getLogger("uvicorn.error")

def public_user(user: dict[str, Any] | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}


def optional_user(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = connect()
    try:
        row = conn.execute(
            """SELECT u.id, u.name, u.email, u.role
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ?""",
            (token_hash, int(time.time())),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def require_user(request: Request, role: str | None = None) -> dict[str, Any]:
    user = optional_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Entre na sua conta para continuar.")
    if role and user["role"] != role:
        detail = "Esta ação está disponível para licitantes." if role == "bidder" else "Esta ação está disponível para o leiloeiro."
        raise HTTPException(status_code=403, detail=detail)
    return user


def wallet_summary(conn, user_id: str) -> dict[str, int]:
    wallet = conn.execute("SELECT total_cents FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
    total = int(wallet["total_cents"]) if wallet else 0
    committed = int(
        conn.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) AS amount FROM wallet_holds WHERE user_id = ?",
            (user_id,),
        ).fetchone()["amount"]
    )
    return {"total_cents": total, "committed_cents": committed, "available_cents": max(0, total - committed)}


def alias_for(conn, lot_id: str, user_id: str | None) -> str | None:
    if not user_id:
        return None
    row = conn.execute(
        "SELECT public_alias FROM lot_participants WHERE lot_id = ? AND user_id = ?",
        (lot_id, user_id),
    ).fetchone()
    return str(row["public_alias"]) if row else None


def serialize_lot(conn, lot, user: dict[str, Any] | None = None) -> dict[str, Any]:
    bid_count = int(conn.execute("SELECT COUNT(*) AS n FROM bids WHERE lot_id = ?", (lot["id"],)).fetchone()["n"])
    seller = conn.execute("SELECT name FROM users WHERE id = ?", (lot["seller_id"],)).fetchone()
    own_bid = None
    if user and user["role"] == "bidder":
        own_bid = conn.execute(
            "SELECT MAX(amount_cents) AS amount FROM bids WHERE lot_id = ? AND bidder_id = ?",
            (lot["id"], user["id"]),
        ).fetchone()
    return {
        "id": lot["id"],
        "seller_name": seller["name"] if seller else "Leiloeiro",
        "title": lot["title"],
        "authors": lot["authors"],
        "description": lot["description"],
        "cover_url": lot["cover_url"],
        "source_url": lot["source_url"],
        "source_label": lot["source_label"],
        "initial_cents": int(lot["initial_cents"]),
        "increment_cents": int(lot["increment_cents"]),
        "current_cents": int(lot["current_cents"]),
        "current_bidder": alias_for(conn, lot["id"], lot["current_bidder_id"]),
        "start_at": lot["start_at"],
        "end_at": lot["end_at"],
        "status": lot["status"],
        "bid_count": bid_count,
        "is_leader": bool(user and lot["current_bidder_id"] == user["id"]),
        "my_last_bid_cents": int(own_bid["amount"] or 0) if own_bid else None,
        "can_cancel": bool(
            user and user["role"] == "seller" and user["id"] == lot["seller_id"]
            and bid_count == 0 and lot["status"] in ("scheduled", "active")
        ),
        "winner_alias": alias_for(conn, lot["id"], lot["winner_user_id"]),
        "winning_cents": int(lot["winning_cents"]),
    }


def bidder_activity(conn, user_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT DISTINCT l.* FROM lots l JOIN bids b ON b.lot_id = l.id
        WHERE b.bidder_id = ? ORDER BY l.created_at DESC""",
        (user_id,),
    ).fetchall()
    result = []
    for lot in rows:
        own = conn.execute(
            "SELECT MAX(amount_cents) AS amount FROM bids WHERE lot_id = ? AND bidder_id = ?",
            (lot["id"], user_id),
        ).fetchone()
        is_winner = lot["winner_user_id"] == user_id and lot["status"] == "closed"
        result.append({
            **serialize_lot(conn, lot),
            "my_max_bid_cents": int(own["amount"] or 0),
            "is_winner": is_winner,
            "receipt_url": "/comprovante/" + receipt_token(lot["id"]) if is_winner else None,
        })
    return result


def seller_summary(conn, seller_id: str) -> dict[str, int]:
    active = int(conn.execute(
        "SELECT COUNT(*) AS n FROM lots WHERE seller_id = ? AND status IN ('active', 'scheduled')",
        (seller_id,),
    ).fetchone()["n"])
    closed = int(conn.execute(
        "SELECT COUNT(*) AS n FROM lots WHERE seller_id = ? AND status = 'closed'",
        (seller_id,),
    ).fetchone()["n"])
    received = int(conn.execute(
        """SELECT COALESCE(SUM(winning_cents), 0) AS total FROM lots
        WHERE seller_id = ? AND status = 'closed' AND winner_user_id IS NOT NULL""",
        (seller_id,),
    ).fetchone()["total"])
    return {"active_lots": active, "closed_lots": closed, "received_cents": received}


async def broadcast(event: dict[str, Any]) -> None:
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    for queue in tuple(SUBSCRIBERS):
        try:
            queue.put_nowait(data)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
                queue.put_nowait(data)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                pass


def notify(event_type: str, lot_id: str | None = None) -> None:
    if EVENT_LOOP and EVENT_LOOP.is_running():
        payload = {"type": event_type, "lot_id": lot_id, "at": iso()}
        asyncio.run_coroutine_threadsafe(broadcast(payload), EVENT_LOOP)


def get_lot_or_404(conn, lot_id: str):
    lot = conn.execute("SELECT * FROM lots WHERE id = ?", (lot_id,)).fetchone()
    if lot is None:
        raise HTTPException(status_code=404, detail="Lote não encontrado.")
    return lot


def settle_lot(conn, lot_id: str, now: datetime) -> bool:
    lot = conn.execute("SELECT * FROM lots WHERE id = ?", (lot_id,)).fetchone()
    if lot is None or lot["status"] != "active" or parse_iso(lot["end_at"]) > now:
        return False

    current_bidder = lot["current_bidder_id"]
    amount = int(lot["current_cents"])
    timestamp = iso(now)
    if current_bidder and amount > 0:
        lock_wallets(conn, [current_bidder, lot["seller_id"]])
        hold = conn.execute(
            "SELECT amount_cents FROM wallet_holds WHERE lot_id = ? AND user_id = ?",
            (lot_id, current_bidder),
        ).fetchone()
        if hold is None or int(hold["amount_cents"]) != amount:
            raise RuntimeError("A reserva do lance vencedor não confere; liquidação bloqueada.")
        buyer_wallet = conn.execute("SELECT total_cents FROM wallets WHERE user_id = ?", (current_bidder,)).fetchone()
        if buyer_wallet is None or int(buyer_wallet["total_cents"]) < amount:
            raise RuntimeError("O saldo do vencedor não cobre o lance reservado.")

        conn.execute("UPDATE wallets SET total_cents = total_cents - ? WHERE user_id = ?", (amount, current_bidder))
        conn.execute("DELETE FROM wallet_holds WHERE lot_id = ? AND user_id = ?", (lot_id, current_bidder))
        conn.execute("UPDATE wallets SET total_cents = total_cents + ? WHERE user_id = ?", (amount, lot["seller_id"]))
        conn.execute(
            """INSERT INTO wallet_movements (id, user_id, kind, amount_cents, lot_id, note, created_at)
            VALUES (?, ?, 'auction_payment', ?, ?, ?, ?)""",
            (new_id(), current_bidder, amount, lot_id, "Pagamento do arremate", timestamp),
        )
        conn.execute(
            """INSERT INTO wallet_movements (id, user_id, kind, amount_cents, lot_id, note, created_at)
            VALUES (?, ?, 'seller_credit', ?, ?, ?, ?)""",
            (new_id(), lot["seller_id"], amount, lot_id, "Crédito do lote arrematado", timestamp),
        )
        conn.execute(
            "UPDATE lots SET status = 'closed', winner_user_id = ?, winning_cents = ? WHERE id = ?",
            (current_bidder, amount, lot_id),
        )
        winner_alias = alias_for(conn, lot_id, current_bidder) or "Licitante"
        append_event(conn, lot_id, "lot_closed", amount_cents=amount, payload={
            "winner_alias": winner_alias,
            "winning_cents": amount,
            "settled_at": timestamp,
            "bid_count": int(conn.execute("SELECT COUNT(*) AS n FROM bids WHERE lot_id = ?", (lot_id,)).fetchone()["n"]),
        }, created_at=timestamp)
    else:
        conn.execute(
            "UPDATE lots SET status = 'closed', winner_user_id = NULL, winning_cents = 0 WHERE id = ?",
            (lot_id,),
        )
        append_event(conn, lot_id, "lot_closed_without_bids", payload={"closed_at": timestamp}, created_at=timestamp)
    return True


def close_expired_lots() -> list[str]:
    now = utc_now()
    now_iso = iso(now)
    changed: list[str] = []
    with transaction() as conn:
        scheduled = conn.execute(
            "SELECT id FROM lots WHERE status = 'scheduled' AND start_at <= ? AND end_at > ?",
            (now_iso, now_iso),
        ).fetchall()
        for row in scheduled:
            lot_id = row["id"]
            lock_lot(conn, lot_id)
            lot = conn.execute("SELECT * FROM lots WHERE id = ?", (lot_id,)).fetchone()
            if not lot or lot["status"] != "scheduled" or parse_iso(lot["start_at"]) > now or parse_iso(lot["end_at"]) <= now:
                continue
            conn.execute("UPDATE lots SET status = 'active' WHERE id = ?", (lot_id,))
            append_event(conn, lot_id, "lot_started", payload={"started_at": now_iso}, created_at=now_iso)
            changed.append(lot_id)

        expired = conn.execute(
            "SELECT id FROM lots WHERE status = 'active' AND end_at <= ?",
            (now_iso,),
        ).fetchall()
        for row in expired:
            lot_id = row["id"]
            lock_lot(conn, lot_id)
            if settle_lot(conn, lot_id, now):
                changed.append(lot_id)
    return changed


async def close_scheduler() -> None:
    last_error: str | None = None
    while True:
        try:
            changed = await asyncio.to_thread(close_expired_lots)
            for lot_id in changed:
                notify("lot_changed", lot_id)
            if last_error is not None:
                logger.info("Agendador de lotes recuperado após falha anterior.")
                last_error = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # The next cycle retries; inconsistent reservations block settlement safely.
            # Log the full traceback only when the error changes, to avoid flooding the terminal every cycle.
            signature = type(exc).__name__ + ": " + str(exc)
            if signature != last_error:
                logger.exception("Falha no agendador de lotes; nova tentativa a cada 1,5 s.")
                last_error = signature
        await asyncio.sleep(1.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global EVENT_LOOP
    init_schema()
    seed_demo()
    EVENT_LOOP = asyncio.get_running_loop()
    scheduler = asyncio.create_task(close_scheduler())
    try:
        yield
    finally:
        scheduler.cancel()
        try:
            await scheduler
        except asyncio.CancelledError:
            pass
        EVENT_LOOP = None


app = FastAPI(
    title="Elite Leilões",
    description="Leilões demonstrativos com carteira transacional e auditoria encadeada.",
    version="1.0.0",
    lifespan=lifespan,
)


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class DepositBody(BaseModel):
    amount_cents: int = Field(gt=0, le=10_000_000)


class CatalogSearchBody(BaseModel):
    query: str = Field(min_length=2, max_length=120)


class CreateLotBody(BaseModel):
    catalog_item_id: str = Field(min_length=1, max_length=100)
    initial_cents: int = Field(gt=0, le=100_000_000)
    increment_cents: int = Field(gt=0, le=100_000_000)
    start_at: str
    end_at: str


class BidBody(BaseModel):
    amount_cents: int = Field(gt=0, le=100_000_000)


@app.get("/api/health")
def health():
    return {"ok": True, "database": "sqlite", "service": "elite-leiloes"}


@app.post("/api/auth/login")
def login(body: LoginBody, request: Request, response: Response):
    conn = connect()
    try:
        user = conn.execute("SELECT * FROM users WHERE lower(email) = lower(?)", (body.email.strip(),)).fetchone()
        if user is None or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (token_hash, user["id"], int(time.time()) + SESSION_TTL_SECONDS),
        )
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            secure=request.url.scheme == "https" or forwarded_proto == "https",
            samesite="lax",
            path="/",
        )
        return {"user": public_user(dict(user))}
    finally:
        conn.close()


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        conn = connect()
        try:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode("utf-8")).hexdigest(),))
        finally:
            conn.close()
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")
    return {"ok": True}


@app.get("/api/bootstrap")
def bootstrap(request: Request):
    user = optional_user(request)
    conn = connect()
    try:
        lots = conn.execute(
            """SELECT * FROM lots
            ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'scheduled' THEN 1 ELSE 2 END, end_at ASC"""
        ).fetchall()
        result: dict[str, Any] = {
            "me": public_user(user),
            "lots": [serialize_lot(conn, lot, user) for lot in lots],
            "wallet": None,
            "movements": [],
            "activity": [],
            "seller_summary": None,
        }
        if user:
            result["wallet"] = wallet_summary(conn, user["id"])
            movements = conn.execute(
                "SELECT * FROM wallet_movements WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
                (user["id"],),
            ).fetchall()
            result["movements"] = [
                {
                    "id": row["id"],
                    "kind": row["kind"],
                    "amount_cents": int(row["amount_cents"]),
                    "lot_id": row["lot_id"],
                    "note": row["note"],
                    "created_at": row["created_at"],
                }
                for row in movements
            ]
            if user["role"] == "bidder":
                result["activity"] = bidder_activity(conn, user["id"])
            else:
                result["seller_summary"] = seller_summary(conn, user["id"])
        return result
    finally:
        conn.close()


@app.get("/api/events")
async def event_stream(request: Request):
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=20)
    SUBSCRIBERS.add(queue)

    async def stream():
        try:
            yield "retry: 2500\n: conectado\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=18)
                    yield "data: " + message + "\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            SUBSCRIBERS.discard(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/wallet/deposit")
def deposit(body: DepositBody, request: Request):
    user = require_user(request, "bidder")
    timestamp = iso()
    with transaction() as conn:
        conn.execute("UPDATE wallets SET total_cents = total_cents + ? WHERE user_id = ?", (body.amount_cents, user["id"]))
        conn.execute(
            """INSERT INTO wallet_movements (id, user_id, kind, amount_cents, lot_id, note, created_at)
            VALUES (?, ?, 'deposit', ?, NULL, ?, ?)""",
            (new_id(), user["id"], body.amount_cents, "Depósito simulado", timestamp),
        )
        balance = wallet_summary(conn, user["id"])
    notify("wallet_changed")
    return {"wallet": balance, "message": "Depósito simulado realizado."}


def catalog_item_public(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "title": item["title"],
        "authors": item.get("authors", ""),
        "description": item.get("description", ""),
        "cover_url": item.get("cover_url"),
        "source_url": item["source_url"],
        "source_label": item["source_label"],
    }


def fallback_catalog(conn, query: str) -> list[dict[str, Any]]:
    needle = "%" + query.strip().casefold() + "%"
    rows = conn.execute(
        """SELECT * FROM catalog_items
        WHERE lower(title) LIKE ? OR lower(authors) LIKE ?
        ORDER BY last_seen_at DESC LIMIT 12""",
        (needle, needle),
    ).fetchall()
    if not rows:
        rows = conn.execute("SELECT * FROM catalog_items ORDER BY title LIMIT 12").fetchall()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "authors": row["authors"],
            "description": row["description"],
            "cover_url": row["cover_url"],
            "source_url": row["source_url"],
            "source_label": row["source_label"],
        }
        for row in rows
    ]


@app.post("/api/catalog/search")
def catalog_search(body: CatalogSearchBody, request: Request):
    require_user(request, "seller")
    query = body.query.strip()
    query_key = query.casefold()
    now_epoch = int(time.time())
    conn = connect()
    try:
        cached = conn.execute(
            "SELECT result_json, fetched_at FROM catalog_search_cache WHERE query_key = ?",
            (query_key,),
        ).fetchone()
        if cached and now_epoch - int(cached["fetched_at"]) < 900:
            cached_results = json_load(cached["result_json"])
            if cached_results:
                return {"mode": "cache", "results": cached_results, "message": "Resultado reutilizado do cache local."}

        params = urllib.parse.urlencode({
            "q": query,
            "fields": "key,title,author_name,cover_i,first_publish_year,edition_count",
            "limit": 12,
        })
        req = urllib.request.Request(
            "https://openlibrary.org/search.json?" + params,
            headers={"Accept": "application/json", "User-Agent": "EliteLeiloesDemo/1.0 (human book search)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=4) as response:
                payload = json.loads(response.read().decode("utf-8"))
            results = []
            for document in payload.get("docs", []):
                key = document.get("key")
                title = str(document.get("title") or "").strip()
                if not key or not title:
                    continue
                source_id = "ol-" + hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:20]
                authors = ", ".join((document.get("author_name") or [])[:3])
                cover_id = document.get("cover_i")
                cover_url = "https://covers.openlibrary.org/b/id/" + str(cover_id) + "-L.jpg" if cover_id else None
                source_url = "https://openlibrary.org" + str(key)
                item = {
                    "id": source_id,
                    "title": title[:240],
                    "authors": authors[:240],
                    "description": "",
                    "cover_url": cover_url,
                    "source_url": source_url,
                    "source_label": "Open Library",
                    "item_json": {
                        "source": "Open Library",
                        "key": key,
                        "first_publish_year": document.get("first_publish_year"),
                        "edition_count": document.get("edition_count"),
                    },
                }
                results.append(catalog_item_public(item))
                conn.execute(
                    """INSERT INTO catalog_items
                    (id, title, authors, description, cover_url, source_url, source_label, item_json, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET title=excluded.title, authors=excluded.authors,
                    cover_url=excluded.cover_url, source_url=excluded.source_url,
                    source_label=excluded.source_label, item_json=excluded.item_json, last_seen_at=excluded.last_seen_at""",
                    (
                        item["id"], item["title"], item["authors"], item["description"], item["cover_url"],
                        item["source_url"], item["source_label"], json_dump(item["item_json"]), iso(),
                    ),
                )
            conn.execute(
                """INSERT INTO catalog_search_cache (query_key, result_json, source_mode, fetched_at)
                VALUES (?, ?, 'live', ?)
                ON CONFLICT(query_key) DO UPDATE SET result_json=excluded.result_json,
                source_mode='live', fetched_at=excluded.fetched_at""",
                (query_key, json_dump(results), now_epoch),
            )
            if results:
                return {"mode": "live", "results": results, "message": "Busca atualizada na API Open Library."}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            pass

        return {
            "mode": "fallback",
            "results": fallback_catalog(conn, query),
            "message": "API indisponível. Usando itens em cache e a amostra local para manter a demonstração.",
        }
    finally:
        conn.close()


@app.post("/api/lots")
def create_lot(body: CreateLotBody, request: Request):
    user = require_user(request, "seller")
    try:
        start = parse_iso(body.start_at)
        end = parse_iso(body.end_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Informe datas válidas para início e encerramento.")
    now = utc_now()
    if end <= now:
        raise HTTPException(status_code=400, detail="O encerramento precisa estar no futuro.")
    if end <= start:
        raise HTTPException(status_code=400, detail="O encerramento precisa ser posterior ao início.")
    if start < now - timedelta(minutes=2):
        start = now

    lot_id = new_id()
    with transaction() as conn:
        item = conn.execute("SELECT * FROM catalog_items WHERE id = ?", (body.catalog_item_id,)).fetchone()
        if item is None:
            raise HTTPException(status_code=404, detail="Esse item não está no catálogo local. Faça uma nova busca.")
        status = "active" if start <= now else "scheduled"
        conn.execute(
            """INSERT INTO lots
            (id, seller_id, catalog_item_id, title, authors, description, cover_url, source_url,
             source_label, item_snapshot, initial_cents, increment_cents, current_cents,
             current_bidder_id, start_at, end_at, status, created_at, event_head, event_sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, ?, ?, ?, '')""",
            (
                lot_id, user["id"], item["id"], item["title"], item["authors"], item["description"],
                item["cover_url"], item["source_url"], item["source_label"], item["item_json"],
                body.initial_cents, body.increment_cents, iso(start), iso(end), status, iso(now), ZERO_HASH,
            ),
        )
        append_event(conn, lot_id, "lot_created", payload={
            "initial_cents": body.initial_cents,
            "increment_cents": body.increment_cents,
            "start_at": iso(start),
            "end_at": iso(end),
            "source": item["source_label"],
        }, created_at=iso(now))
    notify("lot_changed", lot_id)
    return {"lot_id": lot_id, "message": "Lote criado e pronto para a vitrine."}


@app.post("/api/lots/{lot_id}/cancel")
def cancel_lot(lot_id: str, request: Request):
    user = require_user(request, "seller")
    with transaction() as conn:
        lock_lot(conn, lot_id)
        lot = get_lot_or_404(conn, lot_id)
        if lot["seller_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Você só pode cancelar os seus próprios lotes.")
        count = int(conn.execute("SELECT COUNT(*) AS n FROM bids WHERE lot_id = ?", (lot_id,)).fetchone()["n"])
        if count:
            raise HTTPException(status_code=409, detail="Lotes com lances não podem ser cancelados.")
        if lot["status"] not in ("active", "scheduled"):
            raise HTTPException(status_code=409, detail="Este lote não pode mais ser cancelado.")
        conn.execute("UPDATE lots SET status = 'cancelled' WHERE id = ?", (lot_id,))
        append_event(conn, lot_id, "lot_cancelled", payload={"cancelled_at": iso()})
    notify("lot_changed", lot_id)
    return {"message": "Lote cancelado."}


@app.post("/api/lots/{lot_id}/bids")
def place_bid(lot_id: str, body: BidBody, request: Request):
    user = require_user(request, "bidder")
    timestamp = utc_now()
    now_iso = iso(timestamp)
    extended_to: str | None = None
    expired = False

    with transaction() as conn:
        lock_lot(conn, lot_id)
        lot = get_lot_or_404(conn, lot_id)
        if lot["status"] == "scheduled" and parse_iso(lot["start_at"]) <= timestamp:
            conn.execute("UPDATE lots SET status = 'active' WHERE id = ?", (lot_id,))
            append_event(conn, lot_id, "lot_started", payload={"started_at": now_iso}, created_at=now_iso)
            lot = get_lot_or_404(conn, lot_id)

        if lot["status"] != "active":
            raise HTTPException(status_code=409, detail="Este lote não está aceitando lances.")
        if timestamp < parse_iso(lot["start_at"]):
            raise HTTPException(status_code=409, detail="O lote ainda não começou.")
        if timestamp >= parse_iso(lot["end_at"]):
            settle_lot(conn, lot_id, timestamp)
            expired = True
        else:
            if lot["seller_id"] == user["id"]:
                raise HTTPException(status_code=403, detail="O leiloeiro não pode dar lances no próprio lote.")
            if lot["current_bidder_id"] == user["id"]:
                raise HTTPException(status_code=409, detail="Você já está liderando este lote e não pode cobrir o próprio lance.")

            lock_wallets(conn, [user["id"], lot["current_bidder_id"]])
            minimum = int(lot["initial_cents"]) if lot["current_bidder_id"] is None else int(lot["current_cents"]) + int(lot["increment_cents"])
            if body.amount_cents < minimum:
                minimum_text = format(minimum / 100, ".2f").replace(".", ",")
                raise HTTPException(status_code=400, detail="O lance mínimo agora é R$ " + minimum_text + ".")

            balance = wallet_summary(conn, user["id"])
            if balance["available_cents"] < body.amount_cents:
                raise HTTPException(status_code=409, detail="Saldo disponível insuficiente. Deposite ou escolha um valor menor.")

            previous_leader = lot["current_bidder_id"]
            if previous_leader:
                conn.execute("DELETE FROM wallet_holds WHERE lot_id = ? AND user_id = ?", (lot_id, previous_leader))
            conn.execute(
                "INSERT INTO wallet_holds (lot_id, user_id, amount_cents) VALUES (?, ?, ?)",
                (lot_id, user["id"], body.amount_cents),
            )
            participant = participant_alias(conn, lot_id, user["id"])
            bid_id = new_id()
            conn.execute(
                "INSERT INTO bids (id, lot_id, bidder_id, amount_cents, created_at) VALUES (?, ?, ?, ?, ?)",
                (bid_id, lot_id, user["id"], body.amount_cents, now_iso),
            )

            end_at = parse_iso(lot["end_at"])
            if (end_at - timestamp).total_seconds() <= 120:
                extended_to = iso(timestamp + timedelta(minutes=2))
                conn.execute(
                    "UPDATE lots SET current_cents = ?, current_bidder_id = ?, end_at = ? WHERE id = ?",
                    (body.amount_cents, user["id"], extended_to, lot_id),
                )
            else:
                conn.execute(
                    "UPDATE lots SET current_cents = ?, current_bidder_id = ? WHERE id = ?",
                    (body.amount_cents, user["id"], lot_id),
                )

            append_event(
                conn,
                lot_id,
                "bid_placed",
                actor_public_id=participant,
                amount_cents=body.amount_cents,
                payload={"bid_id": bid_id, "end_extended_to": extended_to},
                created_at=now_iso,
            )

    if expired:
        notify("lot_changed", lot_id)
        raise HTTPException(status_code=409, detail="O tempo do lote terminou; o resultado foi fechado.")
    notify("lot_changed", lot_id)
    return {
        "message": "Lance aceito.",
        "extended_to": extended_to,
        "minimum_next_cents": body.amount_cents + int(lot["increment_cents"]),
    }


@app.get("/api/lots/{lot_id}")
def lot_detail(lot_id: str, request: Request):
    user = optional_user(request)
    conn = connect()
    try:
        lot = get_lot_or_404(conn, lot_id)
        audit = audit_lot(conn, lot)
        history = [
            {
                "sequence": event["sequence"],
                "type": event["event_type"],
                "actor": event["actor"],
                "amount_cents": event["amount_cents"],
                "created_at": event["created_at"],
            }
            for event in audit["events"]
            if event["event_type"] == "bid_placed"
        ][::-1]
        return {"lot": serialize_lot(conn, lot, user), "history": history, "audit_valid": audit["valid"]}
    finally:
        conn.close()


@app.get("/api/audit/{lot_id}")
def public_audit(lot_id: str):
    conn = connect()
    try:
        lot = get_lot_or_404(conn, lot_id)
        audit = audit_lot(conn, lot)
        public_events = []
        for event in audit["events"]:
            payload: dict[str, Any] = {}
            if event["event_type"] == "lot_created":
                raw = event["payload"]
                payload = {
                    "initial_cents": raw.get("initial_cents"),
                    "increment_cents": raw.get("increment_cents"),
                    "source": raw.get("source"),
                }
            elif event["event_type"] == "bid_placed" and event["payload"].get("end_extended_to"):
                payload = {"end_extended_to": event["payload"]["end_extended_to"]}
            elif event["event_type"] == "lot_closed":
                raw = event["payload"]
                payload = {"winner_alias": raw.get("winner_alias"), "bid_count": raw.get("bid_count")}
            public_events.append({
                "sequence": event["sequence"],
                "type": event["event_type"],
                "actor": event["actor"],
                "amount_cents": event["amount_cents"],
                "created_at": event["created_at"],
                "hash": event["event_hash"],
                "payload": payload,
            })
        return {
            "lot": serialize_lot(conn, lot),
            "integrity": {
                "valid": audit["valid"],
                "checked_events": audit["checked_events"],
                "head_hash": audit["head_hash"],
                "problems": audit["problems"],
            },
            "events": public_events,
        }
    finally:
        conn.close()


@app.get("/api/receipt/{token}")
def public_receipt(token: str):
    conn = connect()
    try:
        lot_id = None
        rows = conn.execute("SELECT * FROM lots WHERE status = 'closed' AND winner_user_id IS NOT NULL").fetchall()
        for row in rows:
            if hmac.compare_digest(receipt_token(row["id"]), token):
                lot_id = row["id"]
                break
        if lot_id is None:
            raise HTTPException(status_code=404, detail="Comprovante não encontrado.")
        lot = get_lot_or_404(conn, lot_id)
        audit = audit_lot(conn, lot)
        closed_event = conn.execute(
            """SELECT created_at FROM auction_events
            WHERE lot_id = ? AND event_type IN ('lot_closed', 'lot_closed_without_bids')
            ORDER BY sequence DESC LIMIT 1""",
            (lot_id,),
        ).fetchone()
        return {
            "lot_id": lot["id"],
            "title": lot["title"],
            "authors": lot["authors"],
            "source_url": lot["source_url"],
            "seller": "Leiloeiro Verzel",
            "winner_alias": alias_for(conn, lot_id, lot["winner_user_id"]) or "Licitante",
            "winning_cents": int(lot["winning_cents"]),
            "closed_at": closed_event["created_at"] if closed_event else lot["end_at"],
            "event_count": audit["checked_events"],
            "head_hash": audit["head_hash"],
            "integrity_valid": audit["valid"],
            "audit_url": "/auditoria/" + lot_id,
        }
    finally:
        conn.close()


@app.get("/{path:path}")
def frontend(path: str):
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Rota não encontrada.")
    if not FRONTEND_DIST.exists():
        raise HTTPException(status_code=503, detail="Front-end ainda não compilado. Consulte o README para iniciar o Vite.")
    dist = FRONTEND_DIST.resolve()
    candidate = (dist / path).resolve()
    try:
        candidate.relative_to(dist)
    except ValueError:
        candidate = dist / "index.html"
    if candidate.is_file():
        return FileResponse(candidate)
    index = dist / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(status_code=503, detail="Front-end ainda não compilado.")
