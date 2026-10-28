"""Keep-alive: desligado por padrão, só pinga a própria loja e fica abaixo dos 15 min do Render."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from flask.testing import FlaskClient

from servicos import keep_alive

BASE = "https://loja.exemplo.com"


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    yield
    keep_alive.parar()


def test_desligado_por_padrao() -> None:
    assert keep_alive.iniciar(False, BASE) is False


@pytest.mark.parametrize("base", ["javascript:alert(1)", "", "loja.exemplo.com", "ftp://loja.exemplo.com"])
def test_nao_liga_sem_endereco_http(base: str) -> None:
    assert keep_alive.iniciar(True, base) is False


def test_prefere_o_endereco_do_render(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://lojal-rio.onrender.com/")
    assert keep_alive.url_do_ping("http://127.0.0.1:5000") == "https://lojal-rio.onrender.com/health"
    monkeypatch.delenv("RENDER_EXTERNAL_URL")
    assert keep_alive.url_do_ping(BASE + "/") == BASE + "/health"


def test_liga_uma_unica_thread() -> None:
    assert keep_alive.iniciar(True, BASE) is True
    assert keep_alive.iniciar(True, BASE) is False


@pytest.mark.parametrize(
    ("configurado", "esperado"),
    [
        ("", keep_alive.INTERVALO_PADRAO),
        ("5", keep_alive.INTERVALO_MINIMO),
        ("99999", keep_alive.INTERVALO_MAXIMO),
        ("nao-e-numero", keep_alive.INTERVALO_PADRAO),
        ("300", 300),
    ],
)
def test_intervalo_fica_dentro_da_faixa(configurado: str, esperado: int) -> None:
    assert keep_alive.intervalo(configurado) == esperado


def test_ping_usa_timeout_e_nao_segue_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[tuple[str, dict[str, Any]]] = []

    def get_falso(url: str, **kwargs: Any) -> SimpleNamespace:
        chamadas.append((url, kwargs))
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(keep_alive.requests, "get", get_falso)
    assert keep_alive.pingar(BASE + "/health") is True
    ((url, kwargs),) = chamadas
    assert url == BASE + "/health"
    assert kwargs["allow_redirects"] is False and kwargs["timeout"] == keep_alive.TIMEOUT


def test_ping_engole_erro_de_rede(monkeypatch: pytest.MonkeyPatch) -> None:
    def sem_rede(*_: Any, **__: Any) -> None:
        raise keep_alive.requests.ConnectionError("sem rede")

    monkeypatch.setattr(keep_alive.requests, "get", sem_rede)
    assert keep_alive.pingar(BASE + "/health") is False


@pytest.mark.parametrize("status", [200, 301, 403, 500])
def test_ping_so_aceita_200(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    monkeypatch.setattr(keep_alive.requests, "get", lambda *_, **__: SimpleNamespace(status_code=status))
    assert keep_alive.pingar(BASE + "/health") is (status == 200)


def test_falha_repete_em_60_segundos(monkeypatch: pytest.MonkeyPatch) -> None:
    esperas: list[float] = []
    resultados = iter([False, True])

    def esperar(segundos: float) -> bool:
        esperas.append(segundos)
        return len(esperas) == 3

    monkeypatch.setattr(keep_alive._parar, "wait", esperar)
    monkeypatch.setattr(keep_alive, "pingar", lambda _: next(resultados))
    keep_alive._laco(BASE + "/health", 600)
    assert esperas == [600, 60, 600]


def test_health_responde_sem_banco(cliente: FlaskClient) -> None:
    resposta = cliente.get("/health")
    assert resposta.status_code == 200 and resposta.text == "ok"
