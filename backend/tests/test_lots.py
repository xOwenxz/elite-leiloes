"""Testes de regressão de lotes: criação, cancelamento, lances, encerramento e auditoria."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from conftest import ANA, BRUNO, SELLER


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seeded_lot_id(client) -> str:
    return client.get("/api/bootstrap").json()["lots"][0]["id"]


def _lot(session, lot_id: str) -> dict:
    return next(lot for lot in session.get("/api/bootstrap").json()["lots"] if lot["id"] == lot_id)


def _create_lot(seller, start: datetime, end: datetime, item_id: str = "demo-quincas-borba"):
    return seller.post("/api/lots", json={
        "catalog_item_id": item_id,
        "initial_cents": 2_000,
        "increment_cents": 300,
        "start_at": _iso(start),
        "end_at": _iso(end),
    })


def _wait_until(predicate, timeout: float = 8.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.25)
    return False


# --- Lances -----------------------------------------------------------------


def test_bid_on_unknown_lot(login):
    response = login(BRUNO).post("/api/lots/nao-existe/bids", json={"amount_cents": 10_000})
    assert response.status_code == 404
    assert response.json() == {"detail": "Lote não encontrado."}


def test_leader_cannot_outbid_self(client, login):
    response = login(ANA).post(f"/api/lots/{_seeded_lot_id(client)}/bids", json={"amount_cents": 9_000})
    assert response.status_code == 409
    assert response.json() == {"detail": "Você já está liderando este lote e não pode cobrir o próprio lance."}


def test_seller_cannot_bid(client, login):
    response = login(SELLER).post(f"/api/lots/{_seeded_lot_id(client)}/bids", json={"amount_cents": 9_000})
    assert response.status_code == 403
    assert response.json() == {"detail": "Esta ação está disponível para licitantes."}


def test_bid_below_minimum(client, login):
    response = login(BRUNO).post(f"/api/lots/{_seeded_lot_id(client)}/bids", json={"amount_cents": 8_400})
    assert response.status_code == 400
    assert response.json() == {"detail": "O lance mínimo agora é R$ 85,00."}


def test_bid_without_enough_balance(client, login):
    response = login(BRUNO).post(f"/api/lots/{_seeded_lot_id(client)}/bids", json={"amount_cents": 80_000})
    assert response.status_code == 409
    assert response.json() == {"detail": "Saldo disponível insuficiente. Deposite ou escolha um valor menor."}


def test_valid_bid_moves_hold_to_new_leader(client, login):
    lot_id = _seeded_lot_id(client)
    bruno = login(BRUNO)
    response = bruno.post(f"/api/lots/{lot_id}/bids", json={"amount_cents": 8_500})
    assert response.status_code == 200
    assert response.json() == {"message": "Lance aceito.", "extended_to": None, "minimum_next_cents": 9_000}

    bruno_view = bruno.get("/api/bootstrap").json()
    assert bruno_view["wallet"] == {"total_cents": 75_000, "committed_cents": 8_500, "available_cents": 66_500}
    lot = bruno_view["lots"][0]
    assert lot["current_cents"] == 8_500
    assert lot["current_bidder"] == "Licitante-81B2"
    assert lot["is_leader"] is True
    assert lot["bid_count"] == 5

    ana_wallet = login(ANA).get("/api/bootstrap").json()["wallet"]
    assert ana_wallet == {"total_cents": 90_000, "committed_cents": 0, "available_cents": 90_000}

    detail = client.get(f"/api/lots/{lot_id}").json()
    assert detail["audit_valid"] is True
    assert detail["history"][0]["actor"] == "Licitante-81B2"
    assert detail["history"][0]["amount_cents"] == 8_500


def test_bid_in_last_two_minutes_extends_end(client, login, sql):
    lot_id = _seeded_lot_id(client)
    sql("UPDATE lots SET end_at = ? WHERE id = ?", (_iso(_now() + timedelta(seconds=60)), lot_id))
    before = _now().replace(microsecond=0)
    response = login(BRUNO).post(f"/api/lots/{lot_id}/bids", json={"amount_cents": 8_500})
    after = _now()
    assert response.status_code == 200
    extended_to = response.json()["extended_to"]
    assert extended_to is not None
    extended = datetime.fromisoformat(extended_to.replace("Z", "+00:00"))
    assert before + timedelta(minutes=2) <= extended <= after + timedelta(minutes=2)
    assert _lot(client, lot_id)["end_at"] == extended_to
    # O novo evento reassina o checkpoint, então a auditoria volta a ser válida.
    assert client.get(f"/api/lots/{lot_id}").json()["audit_valid"] is True


def test_bid_on_scheduled_lot_is_rejected(login):
    seller = login(SELLER)
    created = _create_lot(seller, _now() + timedelta(hours=1), _now() + timedelta(hours=2))
    response = login(BRUNO).post(f"/api/lots/{created.json()['lot_id']}/bids", json={"amount_cents": 2_000})
    assert response.status_code == 409
    assert response.json() == {"detail": "Este lote não está aceitando lances."}


# --- Encerramento e comprovante ---------------------------------------------


def test_expired_lot_is_settled_and_receipt_is_issued(client, login, sql):
    lot_id = _seeded_lot_id(client)
    sql("UPDATE lots SET end_at = ? WHERE id = ?", (_iso(_now() - timedelta(seconds=5)), lot_id))

    late_bid = login(BRUNO).post(f"/api/lots/{lot_id}/bids", json={"amount_cents": 9_000})
    assert late_bid.status_code == 409
    assert late_bid.json()["detail"] in {
        "O tempo do lote terminou; o resultado foi fechado.",
        "Este lote não está aceitando lances.",  # o agendador pode ter fechado antes do lance
    }

    lot = _lot(client, lot_id)
    assert lot["status"] == "closed"
    assert lot["winner_alias"] == "Licitante-A4C1"
    assert lot["winning_cents"] == 8_000

    ana = login(ANA).get("/api/bootstrap").json()
    assert ana["wallet"] == {"total_cents": 82_000, "committed_cents": 0, "available_cents": 82_000}
    assert "auction_payment" in {m["kind"] for m in ana["movements"]}
    activity = ana["activity"][0]
    assert activity["is_winner"] is True
    assert activity["receipt_url"].startswith("/comprovante/")

    seller = login(SELLER).get("/api/bootstrap").json()
    assert seller["wallet"]["total_cents"] == 8_000
    assert seller["seller_summary"] == {"active_lots": 0, "closed_lots": 1, "received_cents": 8_000}
    assert [m["kind"] for m in seller["movements"]] == ["seller_credit"]

    token = activity["receipt_url"].removeprefix("/comprovante/")
    receipt = client.get(f"/api/receipt/{token}")
    assert receipt.status_code == 200
    body = receipt.json()
    assert set(body) == {
        "lot_id", "title", "authors", "source_url", "seller", "winner_alias", "winning_cents",
        "closed_at", "event_count", "head_hash", "integrity_valid", "audit_url",
    }
    assert body["lot_id"] == lot_id
    assert body["seller"] == "Leiloeiro Verzel"
    assert body["winner_alias"] == "Licitante-A4C1"
    assert body["winning_cents"] == 8_000
    assert body["event_count"] == 6
    assert body["integrity_valid"] is True
    assert body["audit_url"] == f"/auditoria/{lot_id}"


def test_scheduler_closes_lot_without_bids(login, client, sql):
    seller = login(SELLER)
    lot_id = _create_lot(seller, _now(), _now() + timedelta(minutes=30)).json()["lot_id"]
    sql("UPDATE lots SET end_at = ? WHERE id = ?", (_iso(_now() - timedelta(seconds=1)), lot_id))
    assert _wait_until(lambda: _lot(client, lot_id)["status"] == "closed")
    lot = _lot(client, lot_id)
    assert lot["winner_alias"] is None
    assert lot["winning_cents"] == 0
    events = client.get(f"/api/audit/{lot_id}").json()["events"]
    assert events[-1]["type"] == "lot_closed_without_bids"


def test_scheduler_starts_scheduled_lot(login, client, sql):
    seller = login(SELLER)
    lot_id = _create_lot(seller, _now() + timedelta(hours=1), _now() + timedelta(hours=2)).json()["lot_id"]
    assert _lot(client, lot_id)["status"] == "scheduled"
    sql("UPDATE lots SET start_at = ? WHERE id = ?", (_iso(_now() - timedelta(seconds=1)), lot_id))
    assert _wait_until(lambda: _lot(client, lot_id)["status"] == "active")
    events = client.get(f"/api/audit/{lot_id}").json()["events"]
    assert [event["type"] for event in events] == ["lot_created", "lot_started"]


def test_unknown_receipt(client):
    response = client.get("/api/receipt/" + "0" * 64)
    assert response.status_code == 404
    assert response.json() == {"detail": "Comprovante não encontrado."}


# --- Criação e cancelamento -------------------------------------------------


def test_create_lot_starting_now(login):
    seller = login(SELLER)
    response = _create_lot(seller, _now() - timedelta(minutes=10), _now() + timedelta(minutes=30))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"lot_id", "message"}
    assert body["message"] == "Lote criado e pronto para a vitrine."

    lot = _lot(seller, body["lot_id"])
    assert lot["status"] == "active"
    assert lot["title"] == "Quincas Borba"
    assert lot["current_cents"] == 0
    assert lot["current_bidder"] is None
    assert lot["can_cancel"] is True
    # Início muito antigo é ajustado para o momento da criação.
    start = datetime.fromisoformat(lot["start_at"].replace("Z", "+00:00"))
    assert start >= _now() - timedelta(minutes=1)


def test_create_lot_in_future_is_scheduled(login):
    seller = login(SELLER)
    lot_id = _create_lot(seller, _now() + timedelta(hours=1), _now() + timedelta(hours=2)).json()["lot_id"]
    assert _lot(seller, lot_id)["status"] == "scheduled"


def test_create_lot_validation(login):
    seller = login(SELLER)

    def detail(response):
        return response.status_code, response.json()["detail"]

    assert detail(_create_lot(seller, _now(), _now() + timedelta(hours=1), item_id="desconhecido")) == (
        404, "Esse item não está no catálogo local. Faça uma nova busca.")
    assert detail(_create_lot(seller, _now() - timedelta(hours=2), _now() - timedelta(hours=1))) == (
        400, "O encerramento precisa estar no futuro.")
    assert detail(_create_lot(seller, _now() + timedelta(hours=3), _now() + timedelta(hours=2))) == (
        400, "O encerramento precisa ser posterior ao início.")
    invalid_dates = seller.post("/api/lots", json={
        "catalog_item_id": "demo-quincas-borba", "initial_cents": 1, "increment_cents": 1,
        "start_at": "ontem", "end_at": "amanhã",
    })
    assert detail(invalid_dates) == (400, "Informe datas válidas para início e encerramento.")
    assert seller.post("/api/lots", json={"catalog_item_id": "x"}).status_code == 422


def test_cancel_lot(login, client):
    seller = login(SELLER)
    lot_id = _create_lot(seller, _now(), _now() + timedelta(hours=1)).json()["lot_id"]

    forbidden = login(ANA).post(f"/api/lots/{lot_id}/cancel")
    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": "Esta ação está disponível para o leiloeiro."}

    response = seller.post(f"/api/lots/{lot_id}/cancel")
    assert response.status_code == 200
    assert response.json() == {"message": "Lote cancelado."}
    assert _lot(seller, lot_id)["status"] == "cancelled"

    again = seller.post(f"/api/lots/{lot_id}/cancel")
    assert again.status_code == 409
    assert again.json() == {"detail": "Este lote não pode mais ser cancelado."}

    with_bids = seller.post(f"/api/lots/{_seeded_lot_id(client)}/cancel")
    assert with_bids.status_code == 409
    assert with_bids.json() == {"detail": "Lotes com lances não podem ser cancelados."}

    missing = seller.post("/api/lots/nao-existe/cancel")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Lote não encontrado."}


def test_cannot_cancel_lot_of_another_seller(login, sql, client):
    sql("INSERT INTO users (id, name, email, role, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("outro", "Outro", "outro@demo.local", "seller", "x", "2026-01-01T00:00:00Z"))
    lot_id = _create_lot(login(SELLER), _now(), _now() + timedelta(hours=1)).json()["lot_id"]
    sql("UPDATE lots SET seller_id = 'outro' WHERE id = ?", (lot_id,))
    response = login(SELLER).post(f"/api/lots/{lot_id}/cancel")
    assert response.status_code == 403
    assert response.json() == {"detail": "Você só pode cancelar os seus próprios lotes."}


# --- Detalhe e auditoria ----------------------------------------------------


def test_lot_detail(client):
    lot_id = _seeded_lot_id(client)
    body = client.get(f"/api/lots/{lot_id}").json()
    assert set(body) == {"lot", "history", "audit_valid"}
    assert body["audit_valid"] is True
    assert [item["sequence"] for item in body["history"]] == [5, 4, 3, 2]
    assert set(body["history"][0]) == {"sequence", "type", "actor", "amount_cents", "created_at"}
    assert body["history"][0]["actor"] == "Licitante-A4C1"
    assert body["history"][0]["amount_cents"] == 8_000
    assert client.get("/api/lots/nao-existe").status_code == 404


def test_public_audit(client):
    lot_id = _seeded_lot_id(client)
    body = client.get(f"/api/audit/{lot_id}").json()
    assert set(body) == {"lot", "integrity", "events"}
    assert body["integrity"]["valid"] is True
    assert body["integrity"]["checked_events"] == 5
    assert body["integrity"]["problems"] == []
    assert len(body["integrity"]["head_hash"]) == 64

    first, *bids = body["events"]
    assert set(first) == {"sequence", "type", "actor", "amount_cents", "created_at", "hash", "payload"}
    assert first["type"] == "lot_created"
    assert first["actor"] == "Sistema"
    assert first["payload"] == {"initial_cents": 3_000, "increment_cents": 500,
                                "source": "Open Library · catálogo local de demonstração"}
    assert [event["type"] for event in bids] == ["bid_placed"] * 4
    assert all(event["payload"] == {} for event in bids)
    assert body["events"][-1]["hash"] == body["integrity"]["head_hash"]


def test_audit_detects_tampering(client, sql):
    lot_id = _seeded_lot_id(client)
    sql("UPDATE bids SET amount_cents = 1 WHERE lot_id = ? AND amount_cents = 4000", (lot_id,))
    integrity = client.get(f"/api/audit/{lot_id}").json()["integrity"]
    assert integrity["valid"] is False
    assert any("diverge do evento auditável" in problem for problem in integrity["problems"])

