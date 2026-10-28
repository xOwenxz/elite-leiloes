"""Configuração compartilhada dos testes de regressão da API.

As variáveis de ambiente precisam ser definidas antes de importar a aplicação,
porque os módulos de configuração leem o ambiente no momento da importação.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
_SESSION_DIR = Path(tempfile.mkdtemp(prefix="elite-leiloes-tests-"))
FRONTEND_DIST_DIR = _SESSION_DIR / "dist"
(FRONTEND_DIST_DIR / "assets").mkdir(parents=True)
(FRONTEND_DIST_DIR / "index.html").write_text("<!doctype html><title>SPA</title>", encoding="utf-8")
(FRONTEND_DIST_DIR / "assets" / "app.js").write_text("console.log('ok');", encoding="utf-8")

os.environ["DATA_DIR"] = str(_SESSION_DIR / "data")
os.environ["AUCTION_AUDIT_SECRET"] = "segredo-de-auditoria-somente-para-testes-0123456789"
os.environ["FRONTEND_DIST"] = str(FRONTEND_DIST_DIR)
os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_PATH", None)
sys.path.insert(0, str(BACKEND_DIR))

import db  # noqa: E402
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

SELLER = ("leiloeiro@demo.local", "verzel123")
ANA = ("ana@demo.local", "ana123")
BRUNO = ("bruno@demo.local", "bruno123")


@pytest.fixture()
def database_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Aponta a aplicação para um banco SQLite novo e isolado em cada teste."""
    path = tmp_path / "auction.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    return path


@pytest.fixture()
def client(database_path: Path) -> Iterator[TestClient]:
    """Cliente anônimo que também executa o ciclo de vida (schema, seed e agendador)."""
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture()
def login(client: TestClient) -> Callable[[tuple[str, str]], TestClient]:
    """Fábrica de clientes autenticados, cada um com seu próprio cookie de sessão."""

    def _login(credentials: tuple[str, str]) -> TestClient:
        session_client = TestClient(main.app)
        email, password = credentials
        response = session_client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        return session_client

    return _login


@pytest.fixture()
def sql(database_path: Path) -> Callable[..., list[sqlite3.Row]]:
    """Executa SQL direto no banco do teste para montar cenários difíceis de obter pela API."""

    def _sql(statement: str, params: tuple = ()) -> list[sqlite3.Row]:
        conn = sqlite3.connect(database_path, timeout=8, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(statement, params).fetchall()
        finally:
            conn.close()

    return _sql

