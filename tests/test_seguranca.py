"""Redirecionamento após login, ligação de conta com o Google e a conta admin."""

from __future__ import annotations

import pytest
from flask import Flask, request
from flask.testing import FlaskClient
from sqlalchemy import select

from blueprints.conta_bp import destino_seguro, usuario_do_google
from config import ConfigTeste
from extensoes import db
from modelos import Usuario
from servicos import senhas
from servicos.admin import ErroAdmin, garantir_admin
from servidor import create_app
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


class TestContaAdmin:
    """`flask admin`: a conta do painel segue ADMIN_EMAIL e ADMIN_SENHA a cada deploy."""

    SENHA = "senha-do-painel-123"

    def _admin(self) -> Usuario:
        conta = db.session.scalar(select(Usuario).where(Usuario.email == "dona@exemplo.com"))
        assert conta is not None
        return conta

    def test_cria_o_admin_com_a_senha_do_ambiente(self, banco: None) -> None:
        assert "criado" in garantir_admin("Dona@Exemplo.com", self.SENHA, em_producao=True)
        conta = self._admin()
        assert conta.is_admin and senhas.conferir(conta.senha_hash, self.SENHA)

    def test_troca_a_senha_e_derruba_as_sessoes(self, banco: None) -> None:
        garantir_admin("dona@exemplo.com", self.SENHA, em_producao=True)
        versao = self._admin().versao_sessao
        assert "atualizada" in garantir_admin("dona@exemplo.com", "outra-senha-longa-456", em_producao=True)
        conta = self._admin()
        assert senhas.conferir(conta.senha_hash, "outra-senha-longa-456")
        assert conta.versao_sessao == versao + 1

    def test_mesma_senha_nao_mexe_na_conta(self, banco: None) -> None:
        garantir_admin("dona@exemplo.com", self.SENHA, em_producao=True)
        versao = self._admin().versao_sessao
        assert "em dia" in garantir_admin("dona@exemplo.com", self.SENHA, em_producao=True)
        assert "em dia" in garantir_admin("dona@exemplo.com", "", em_producao=True)
        assert self._admin().versao_sessao == versao

    def test_recusa_senha_curta(self, banco: None) -> None:
        with pytest.raises(ErroAdmin):
            garantir_admin("dona@exemplo.com", "curta", em_producao=False)

    def test_producao_sem_senha_nao_gera_senha_no_log(self, banco: None) -> None:
        with pytest.raises(ErroAdmin):
            garantir_admin("dona@exemplo.com", "", em_producao=True)
        assert "gerada" in garantir_admin("dona@exemplo.com", "", em_producao=False)

    def test_cliente_com_o_email_do_admin(self, banco: None) -> None:
        """Alguém cadastrou o e-mail da dona antes do deploy: sem ADMIN_SENHA não vira admin; com ela,
        a senha e o Google dessa pessoa são descartados."""
        intrusa = fabricas.usuario("dona@exemplo.com")
        intrusa.google_sub = "google-da-intrusa"
        db.session.commit()
        with pytest.raises(ErroAdmin):
            garantir_admin("dona@exemplo.com", "", em_producao=True)
        assert not self._admin().is_admin

        garantir_admin("dona@exemplo.com", self.SENHA, em_producao=True)
        conta = self._admin()
        assert conta.is_admin and conta.google_sub is None
        assert not senhas.conferir(conta.senha_hash, fabricas.SENHA)

    def test_comando_flask_admin(self, app: Flask) -> None:
        app.config.update(ADMIN_EMAIL="dona@exemplo.com", ADMIN_SENHA=self.SENHA)
        try:
            saida = app.test_cli_runner().invoke(args=["admin"])
        finally:
            app.config.update(ADMIN_EMAIL="admin@exemplo.com", ADMIN_SENHA="")
        assert saida.exit_code == 0 and "criado" in saida.output


class TestProxy:
    def test_ip_real_atras_do_proxy(self) -> None:
        """O limite de login conta por visitante, não pelo IP do proxy do Render."""

        class ConfigProxy(ConfigTeste):
            PROXY_SALTOS = 1

        app = create_app(ConfigProxy)

        @app.get("/_ip")
        def ip() -> str:
            return request.remote_addr or ""

        resposta = app.test_client().get("/_ip", headers={"X-Forwarded-For": "203.0.113.7"})
        assert resposta.text == "203.0.113.7"
