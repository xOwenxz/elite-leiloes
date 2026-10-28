"""Testes de regressão do catálogo externo e da entrega do front-end compilado."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from conftest import SELLER

CATALOG_KEYS = {"id", "title", "authors", "description", "cover_url", "source_url", "source_label"}


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


@pytest.fixture()
def offline_catalog(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise urllib.error.URLError("sem rede nos testes")

    monkeypatch.setattr(urllib.request, "urlopen", _raise)


@pytest.fixture()
def online_catalog(monkeypatch):
    calls = []
    payload = {"docs": [
        {"key": "/works/OL1W", "title": "Memórias Póstumas", "author_name": ["Machado de Assis"], "cover_i": 42},
        {"key": "/works/OL2W", "title": "  ", "author_name": ["Ignorado"]},
        {"title": "Sem chave"},
        {"key": "/works/OL3W", "title": "Esaú e Jacó"},
    ]}

    def _urlopen(request, timeout):
        calls.append((request.full_url, timeout))
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    return calls


def test_catalog_fallback_when_api_is_down(login, offline_catalog):
    response = login(SELLER).post("/api/catalog/search", json={"query": "machado"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "fallback"
    assert body["message"] == "API indisponível. Usando itens em cache e a amostra local para manter a demonstração."
    assert {item["title"] for item in body["results"]} == {"Dom Casmurro", "Quincas Borba"}
    assert all(set(item) == CATALOG_KEYS for item in body["results"])


def test_catalog_fallback_without_matches_lists_everything(login, offline_catalog):
    body = login(SELLER).post("/api/catalog/search", json={"query": "zzzz"}).json()
    assert [item["title"] for item in body["results"]] == ["Dom Casmurro", "O Cortiço", "Quincas Borba"]


def test_catalog_live_search_then_cache(login, online_catalog):
    seller = login(SELLER)
    live = seller.post("/api/catalog/search", json={"query": "Machado"}).json()
    assert live["mode"] == "live"
    assert live["message"] == "Busca atualizada na API Open Library."
    assert [item["title"] for item in live["results"]] == ["Memórias Póstumas", "Esaú e Jacó"]
    first = live["results"][0]
    assert set(first) == CATALOG_KEYS
    assert first["id"].startswith("ol-") and len(first["id"]) == 23
    assert first["authors"] == "Machado de Assis"
    assert first["cover_url"] == "https://covers.openlibrary.org/b/id/42-L.jpg"
    assert first["source_url"] == "https://openlibrary.org/works/OL1W"
    assert first["source_label"] == "Open Library"
    assert live["results"][1]["cover_url"] is None

    url, timeout = online_catalog[0]
    assert url.startswith("https://openlibrary.org/search.json?q=Machado&")
    assert timeout == 4

    cached = seller.post("/api/catalog/search", json={"query": "  machado "}).json()
    assert cached == {"mode": "cache", "results": live["results"], "message": "Resultado reutilizado do cache local."}
    assert len(online_catalog) == 1

    # O item vindo da API fica disponível para criar lotes.
    created = seller.post("/api/lots", json={
        "catalog_item_id": first["id"], "initial_cents": 1_000, "increment_cents": 100,
        "start_at": "2020-01-01T00:00:00Z", "end_at": "2099-01-01T00:00:00Z",
    })
    assert created.status_code == 200


def test_catalog_query_validation(login):
    assert login(SELLER).post("/api/catalog/search", json={"query": "a"}).status_code == 422


def test_unknown_api_route_returns_404(client):
    response = client.get("/api/nao-existe")
    assert response.status_code == 404
    assert response.json() == {"detail": "Rota não encontrada."}


def test_frontend_serves_files_and_spa_fallback(client):
    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert asset.text == "console.log('ok');"

    for path in ("/", "/auditoria/qualquer", "/comprovante/abc"):
        page = client.get(path)
        assert page.status_code == 200
        assert "<title>SPA</title>" in page.text

