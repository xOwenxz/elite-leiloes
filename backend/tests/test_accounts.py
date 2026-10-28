"""Testes de regressão de autenticação, bootstrap e carteira."""

from __future__ import annotations

from conftest import ANA, BRUNO, SELLER

LOT_KEYS = {
    "id", "seller_name", "title", "authors", "description", "cover_url", "source_url", "source_label",
    "initial_cents", "increment_cents", "current_cents", "current_bidder", "start_at", "end_at", "status",
    "bid_count", "is_leader", "my_last_bid_cents", "can_cancel", "winner_alias", "winning_cents",
}


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "database": "sqlite", "service": "elite-leiloes"}


def test_anonymous_bootstrap_shows_seeded_lot(client):
    body = client.get("/api/bootstrap").json()
    assert set(body) == {"me", "lots", "wallet", "movements", "activity", "seller_summary"}
    assert body["me"] is None
    assert body["wallet"] is None
    assert body["movements"] == []
    assert body["activity"] == []
    assert body["seller_summary"] is None
    assert len(body["lots"]) == 1

    lot = body["lots"][0]
    assert set(lot) == LOT_KEYS
    assert lot["title"] == "Dom Casmurro"
    assert lot["seller_name"] == "Leiloeiro Verzel"
    assert lot["status"] == "active"
    assert lot["initial_cents"] == 3_000
    assert lot["increment_cents"] == 500
    assert lot["current_cents"] == 8_000
    assert lot["current_bidder"] == "Licitante-A4C1"
    assert lot["bid_count"] == 4
    assert lot["is_leader"] is False
    assert lot["my_last_bid_cents"] is None
    assert lot["can_cancel"] is False
    assert lot["winner_alias"] is None
    assert lot["winning_cents"] == 0
    assert lot["end_at"].endswith("Z")


def test_login_with_wrong_password_is_rejected(client):
    response = client.post("/api/auth/login", json={"email": "ana@demo.local", "password": "errada"})
    assert response.status_code == 401
    assert response.json() == {"detail": "E-mail ou senha inválidos."}


def test_login_validates_payload(client):
    assert client.post("/api/auth/login", json={"email": "ana@demo.local"}).status_code == 422


def test_login_sets_session_cookie_and_is_case_insensitive(client):
    response = client.post("/api/auth/login", json={"email": "  ANA@demo.local ", "password": "ana123"})
    assert response.status_code == 200
    assert response.json() == {
        "user": {"id": "demo-ana", "name": "Ana Colecionadora", "email": "ana@demo.local", "role": "bidder"}
    }
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("elite_leiloes_session=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie


def test_bidder_bootstrap(login):
    body = login(ANA).get("/api/bootstrap").json()
    assert body["me"] == {"id": "demo-ana", "name": "Ana Colecionadora", "email": "ana@demo.local", "role": "bidder"}
    assert body["wallet"] == {"total_cents": 90_000, "committed_cents": 8_000, "available_cents": 82_000}
    assert body["seller_summary"] is None
    assert [m["kind"] for m in body["movements"]] == ["deposit"]
    assert set(body["movements"][0]) == {"id", "kind", "amount_cents", "lot_id", "note", "created_at"}
    assert body["movements"][0]["note"] == "Saldo inicial da conta de demonstração"

    lot = body["lots"][0]
    assert lot["is_leader"] is True
    assert lot["my_last_bid_cents"] == 8_000

    assert len(body["activity"]) == 1
    activity = body["activity"][0]
    assert set(activity) == LOT_KEYS | {"my_max_bid_cents", "is_winner", "receipt_url"}
    assert activity["my_max_bid_cents"] == 8_000
    assert activity["is_winner"] is False
    assert activity["receipt_url"] is None
    # A atividade serializa o lote sem usuário: não marca liderança.
    assert activity["is_leader"] is False


def test_seller_bootstrap(login):
    body = login(SELLER).get("/api/bootstrap").json()
    assert body["me"]["role"] == "seller"
    assert body["seller_summary"] == {"active_lots": 1, "closed_lots": 0, "received_cents": 0}
    assert body["activity"] == []
    assert body["wallet"] == {"total_cents": 0, "committed_cents": 0, "available_cents": 0}
    assert body["lots"][0]["can_cancel"] is False


def test_logout_clears_session(login):
    session = login(ANA)
    response = session.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert session.get("/api/bootstrap").json()["me"] is None


def test_role_guards(client, login):
    anonymous = client.post("/api/wallet/deposit", json={"amount_cents": 100})
    assert anonymous.status_code == 401
    assert anonymous.json() == {"detail": "Entre na sua conta para continuar."}

    seller_deposit = login(SELLER).post("/api/wallet/deposit", json={"amount_cents": 100})
    assert seller_deposit.status_code == 403
    assert seller_deposit.json() == {"detail": "Esta ação está disponível para licitantes."}

    bidder_search = login(ANA).post("/api/catalog/search", json={"query": "machado"})
    assert bidder_search.status_code == 403
    assert bidder_search.json() == {"detail": "Esta ação está disponível para o leiloeiro."}


def test_deposit(login):
    session = login(BRUNO)
    response = session.post("/api/wallet/deposit", json={"amount_cents": 10_000})
    assert response.status_code == 200
    assert response.json() == {
        "wallet": {"total_cents": 85_000, "committed_cents": 0, "available_cents": 85_000},
        "message": "Depósito simulado realizado.",
    }
    movements = session.get("/api/bootstrap").json()["movements"]
    assert movements[0]["kind"] in {"deposit"}
    assert {m["note"] for m in movements} == {"Depósito simulado", "Saldo inicial da conta de demonstração"}


def test_deposit_validation(login):
    session = login(BRUNO)
    assert session.post("/api/wallet/deposit", json={"amount_cents": 0}).status_code == 422
    assert session.post("/api/wallet/deposit", json={"amount_cents": 10_000_001}).status_code == 422

