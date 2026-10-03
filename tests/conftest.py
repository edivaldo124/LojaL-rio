"""Testes rodam no PostgreSQL de teste (DATABASE_URL_TESTE), recriado a cada execução."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import text

from config import ConfigTeste
from extensoes import db
from servidor import create_app


@pytest.fixture(scope="session")
def app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Flask]:
    aplicacao = create_app(ConfigTeste)
    aplicacao.config["PASTA_UPLOADS"] = tmp_path_factory.mktemp("uploads")
    with aplicacao.app_context():
        db.drop_all()
        db.create_all()
    yield aplicacao


@pytest.fixture(autouse=True)
def limpar_banco(app: Flask) -> Iterator[None]:
    yield
    with app.app_context():
        db.session.remove()
        tabelas = ", ".join(t.name for t in db.metadata.sorted_tables)
        db.session.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))
        db.session.commit()


@pytest.fixture
def banco(app: Flask) -> Iterator[None]:
    """Contexto da aplicação para testar serviços direto (sem requisições HTTP)."""
    with app.app_context():
        yield
        db.session.rollback()


@pytest.fixture
def cliente(app: Flask) -> FlaskClient:
    return app.test_client()
