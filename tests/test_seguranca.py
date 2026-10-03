"""Redirecionamento após login e ligação de conta com o Google."""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from blueprints.conta_bp import destino_seguro, usuario_do_google
from extensoes import db
from servicos import senhas
from tests import fabricas

PADRAO = "/conta"


class TestRedirecionamento:
    @pytest.mark.parametrize(
        "destino",
        [
            "//evil.com",
            "/\\evil.com",
            "/\\/evil.com",
            "\\\\evil.com",
            "https://evil.com",
            "javascript:alert(1)",
            "/\tevil.com",
            "evil.com",
            "",
        ],
    )
    def test_recusa_destino_externo(self, destino: str) -> None:
        assert destino_seguro(destino, PADRAO) == PADRAO

    @pytest.mark.parametrize("destino", ["/conta/pedidos", "/produto/vestido?cor=Rosa", "/admin?status=PAGO"])
    def test_aceita_caminho_interno(self, destino: str) -> None:
        assert destino_seguro(destino, PADRAO) == destino

    def test_login_nao_redireciona_para_fora(self, app: Flask, cliente: FlaskClient) -> None:
        with app.app_context():
            fabricas.usuario()
            db.session.commit()
        resposta = cliente.post(
            "/conta/entrar",
            data={"email": "cliente@exemplo.com", "senha": fabricas.SENHA, "next": "/\\evil.com"},
        )
        assert resposta.status_code == 302
        assert resposta.headers["Location"] == "/conta"


@pytest.mark.usefixtures("banco")
class TestLigacaoGoogle:
    def _dados(self, email: str = "cliente@exemplo.com", sub: str = "google-123") -> dict[str, object]:
        return {"sub": sub, "email": email, "email_verified": True, "name": "Ana Google"}

    def test_conta_cadastrada_antes_perde_a_senha_ao_ligar(self) -> None:
        """Pré-sequestro: alguém cadastra o e-mail da vítima com senha própria antes dela."""
        existente = fabricas.usuario("cliente@exemplo.com")
        versao = existente.versao_sessao
        usuario, invalidada = usuario_do_google(self._dados())
        assert usuario.id == existente.id
        assert invalidada
        assert usuario.senha_hash is None
        assert not senhas.conferir(usuario.senha_hash, fabricas.SENHA)
        assert usuario.versao_sessao == versao + 1  # sessões antigas caem
        assert usuario.google_sub == "google-123"

    def test_proximo_login_google_nao_mexe_mais_na_conta(self) -> None:
        usuario_do_google(self._dados())
        usuario, invalidada = usuario_do_google(self._dados())
        assert not invalidada
        assert usuario.email == "cliente@exemplo.com"

    def test_conta_nova_e_criada_sem_senha(self) -> None:
        usuario, invalidada = usuario_do_google(self._dados("nova@exemplo.com", "google-999"))
        assert not invalidada
        assert usuario.senha_hash is None
        assert usuario.nome == "Ana Google"


class _GoogleFalso:
    def __init__(self, userinfo: dict[str, object]) -> None:
        self.userinfo = userinfo

    def authorize_access_token(self) -> dict[str, object]:
        return {"userinfo": self.userinfo}


class TestRetornoGoogle:
    def _retorno(self, cliente: FlaskClient, monkeypatch: pytest.MonkeyPatch, userinfo: dict[str, object]):
        import blueprints.conta_bp as conta

        monkeypatch.setattr(conta.oauth, "create_client", lambda nome: _GoogleFalso(userinfo))
        with cliente.session_transaction() as sessao:
            sessao["google_next"] = "/\\evil.com"
        return cliente.get("/conta/google/retorno")

    @pytest.mark.parametrize("verificado", [False, "true", None])
    def test_email_nao_verificado_e_recusado(
        self, app: Flask, cliente: FlaskClient, monkeypatch: pytest.MonkeyPatch, verificado: object
    ) -> None:
        userinfo = {"sub": "g-1", "email": "x@exemplo.com", "email_verified": verificado}
        resposta = self._retorno(cliente, monkeypatch, userinfo)
        assert resposta.headers["Location"] == "/conta/entrar"
        with app.app_context():
            assert fabricas.Usuario.query.count() == 0

    def test_login_google_entra_e_ignora_destino_externo(
        self, app: Flask, cliente: FlaskClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        userinfo = {"sub": "g-2", "email": "ana@exemplo.com", "email_verified": True, "name": "Ana"}
        resposta = self._retorno(cliente, monkeypatch, userinfo)
        assert resposta.headers["Location"] == "/conta"
        assert cliente.get("/conta").status_code == 200
