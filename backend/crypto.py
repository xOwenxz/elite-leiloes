from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from pathlib import Path

from db import DATA_DIR


PASSWORD_ROUNDS = 240_000
SECRET_PATH = Path(os.environ.get("AUDIT_SECRET_FILE", DATA_DIR / "audit.secret"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ROUNDS)
    return chr(36).join(("pbkdf2_sha256", str(PASSWORD_ROUNDS), salt.hex(), digest.hex()))


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_hex, expected_hex = stored.split(chr(36), 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(actual.hex(), expected_hex)
    except (ValueError, TypeError):
        return False


def load_audit_secret() -> bytes:
    configured = os.environ.get("AUCTION_AUDIT_SECRET")
    if configured:
        secret = configured.encode("utf-8")
        if len(secret) < 32:
            raise RuntimeError("AUCTION_AUDIT_SECRET deve ter pelo menos 32 bytes.")
        return secret

    SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with SECRET_PATH.open("xb") as stream:
            stream.write(secrets.token_bytes(32))
    except FileExistsError:
        pass
    return SECRET_PATH.read_bytes()


AUDIT_SECRET = load_audit_secret()


def sign_snapshot(snapshot: dict) -> str:
    fields = (
        "id",
        "seller_id",
        "catalog_item_id",
        "title",
        "authors",
        "description",
        "cover_url",
        "source_url",
        "source_label",
        "item_snapshot",
        "initial_cents",
        "increment_cents",
        "current_cents",
        "current_bidder_id",
        "start_at",
        "end_at",
        "status",
        "winner_user_id",
        "winning_cents",
        "event_seq",
        "event_head",
    )
    stable = {key: snapshot[key] for key in fields}
    message = repr(sorted(stable.items())).encode("utf-8")
    return hmac.new(AUDIT_SECRET, message, hashlib.sha256).hexdigest()


def receipt_token(lot_id: str) -> str:
    return hmac.new(AUDIT_SECRET, f"receipt:{lot_id}".encode("utf-8"), hashlib.sha256).hexdigest()
