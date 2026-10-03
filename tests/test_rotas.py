"""Rotas: proteção do admin, webhook (RN08), sacola do visitante e o fluxo completo da compra."""

from __future__ import annotations

import io

import pytest
from flask import Flask
from flask.testing import FlaskClient
from PIL import Image
from sqlalchemy import func, select

from extensoes import db
from modelos import FRETE_ENTREGA, PAGAMENTO_PIX, Pedido, Sacola, StatusPedido, Usuario, Variacao
from servicos import pedidos as servico_pedidos
from servicos.pagamentos import GatewaySimulado, assinar, segredo_simulado
from tests import fabricas

ROTAS_GET_ADMIN = ["/admin", "/admin/produtos", "/admin/produtos/novo", "/admin/categorias", "/admin/pedidos"]


def _admin_e_cliente(app: Flask) -> None:
    with app.app_context():
        fabricas.usuario("admin@exemplo.com", admin=True)
        fabricas.usuario("cliente@exemplo.com")
        fabricas.produto()
        db.session.commit()


class TestAdminProtegido:
    def test_toda_rota_admin_passa_pela_checagem(self, app: Flask) -> None:
        regras = [r for r in app.url_map.iter_rules() if r.rule.startswith("/admin")]
        assert regras and all(r.endpoint.startswith("admin.") for r in regras)

    def test_visitante_vai_para_o_login(self, app: Flask, cliente: FlaskClient) -> None:
        for rota in ROTAS_GET_ADMIN:
            resposta = cliente.get(rota)
            assert resposta.status_code == 302
            assert "/conta/entrar" in resposta.headers["Location"]
        assert cliente.post("/admin/produtos/1/excluir").status_code == 302

    def test_cliente_recebe_403(self, app: Flask, cliente: FlaskClient) -> None:
        _admin_e_cliente(app)
        fabricas.entrar(cliente, "cliente@exemplo.com")
        for rota in ROTAS_GET_ADMIN:
            assert cliente.get(rota).status_code == 403
        assert cliente.post("/admin/produtos/1/excluir").status_code == 403
        with app.app_context():
            assert db.session.get(Variacao, 1) is not None

    def test_admin_acessa(self, app: Flask, cliente: FlaskClient) -> None:
        _admin_e_cliente(app)
        fabricas.entrar(cliente, "admin@exemplo.com")
        for rota in [*ROTAS_GET_ADMIN, "/admin/produtos/1"]:
            assert cliente.get(rota).status_code == 200, rota

    def test_admin_cria_produto_e_envia_foto(self, app: Flask, cliente: FlaskClient) -> None:
        _admin_e_cliente(app)
        fabricas.entrar(cliente, "admin@exemplo.com")
        resposta = cliente.post(
            "/admin/produtos/novo",
            data={"nome": "Saia plissada", "categoria_id": 1, "preco": "149,90", "ativo": "y"},
        )
        assert resposta.status_code == 302
        png = io.BytesIO()
        Image.new("RGB", (40, 60), "#C97B84").save(png, "PNG")
        png.seek(0)
        enviar = cliente.post(
            "/admin/produtos/2/fotos",
            data={"fotos": [(png, "saia.png"), (io.BytesIO(b"nao e imagem"), "virus.png")]},
            content_type="multipart/form-data",
        )
        assert enviar.status_code == 302
        cores = cliente.post(
            "/admin/produtos/2/variacoes",
            data={"cor": "preto", "cor_hex": "#2B2B2B", "tamanhos": ["P", "M"], "estoque": 4},
        )
        assert cores.status_code == 302
        with app.app_context():
            from modelos import Produto

            produto = db.session.get(Produto, 2)
            assert produto is not None
            assert produto.preco == 14990
            assert [i.url.endswith(".webp") for i in produto.imagens] == [True]
            assert sorted((v.cor, v.tamanho, v.estoque) for v in produto.variacoes) == [
                ("Preto", "M", 4),
                ("Preto", "P", 4),
            ]


class TestWebhook:
    def _pedido_aguardando(self, app: Flask) -> tuple[str, str]:
        with app.app_context():
            produto = fabricas.produto(preco=10000)
            cliente = fabricas.usuario()
            sacola = fabricas.sacola(cliente, [(produto.variacoes[0], 1)])
            pedido = servico_pedidos.criar_pedido(
                cliente, sacola, fabricas.endereco(cliente), FRETE_ENTREGA, PAGAMENTO_PIX
            )
            gateway = GatewaySimulado(segredo_simulado(app.config["SECRET_KEY"]))
            cobranca = gateway.criar_pix(pedido)
            pedido.id_pagamento_gateway = cobranca.id_gateway
            db.session.commit()
            return pedido.numero, cobranca.id_gateway

    def _status(self, app: Flask, numero: str) -> str:
        with app.app_context():
            return db.session.scalar(select(Pedido.status).where(Pedido.numero == numero)) or ""

    def _notificar(self, app: Flask, cliente: FlaskClient, id_pg: str, segredo: str | None = None):
        segredo = segredo or segredo_simulado(app.config["SECRET_KEY"])
        return cliente.post(
            f"/pagamentos/webhook?data.id={id_pg}&type=payment",
            json={"type": "payment", "data": {"id": id_pg}},
            headers=assinar(segredo, id_pg),
        )

    def test_assinatura_invalida_e_recusada(self, app: Flask, cliente: FlaskClient) -> None:
        numero, id_pg = self._pedido_aguardando(app)
        assert self._notificar(app, cliente, id_pg, segredo="segredo-errado").status_code == 401
        sem_assinatura = cliente.post(f"/pagamentos/webhook?data.id={id_pg}&type=payment")
        assert sem_assinatura.status_code == 401
        assert self._status(app, numero) == StatusPedido.AGUARDANDO_PAGAMENTO

    def test_pagamento_pendente_nao_muda_o_pedido(self, app: Flask, cliente: FlaskClient) -> None:
        numero, id_pg = self._pedido_aguardando(app)
        assert self._notificar(app, cliente, id_pg).status_code == 200
        assert self._status(app, numero) == StatusPedido.AGUARDANDO_PAGAMENTO

    def test_aprovado_marca_pago_e_e_idempotente(self, app: Flask, cliente: FlaskClient) -> None:
        numero, id_pg = self._pedido_aguardando(app)
        with app.app_context():
            GatewaySimulado("x").aprovar(id_pg)
            db.session.commit()
        assert self._notificar(app, cliente, id_pg).status_code == 200
        assert self._notificar(app, cliente, id_pg).status_code == 200
        assert self._status(app, numero) == StatusPedido.PAGO

    def test_valor_divergente_nao_marca_pago(self, app: Flask, cliente: FlaskClient) -> None:
        numero, id_pg = self._pedido_aguardando(app)
        with app.app_context():
            from modelos import PagamentoSimulado

            registro = db.session.get(PagamentoSimulado, id_pg)
            assert registro is not None
            registro.valor -= 1
            registro.status = "approved"
            db.session.commit()
        assert self._notificar(app, cliente, id_pg).status_code == 200
        assert self._status(app, numero) == StatusPedido.AGUARDANDO_PAGAMENTO
        with app.app_context():
            pedido = db.session.scalar(select(Pedido).where(Pedido.numero == numero))
            assert pedido is not None and "valor diferente" in (pedido.observacao or "")

    def test_outros_eventos_sao_ignorados(self, cliente: FlaskClient) -> None:
        assert cliente.post("/pagamentos/webhook?type=merchant_order&data.id=1").status_code == 200


class TestSacola:
    def test_visitante_adiciona_e_sacola_e_unificada_no_login(self, app: Flask, cliente: FlaskClient) -> None:
        with app.app_context():
            produto = fabricas.produto(estoques={("Rosa", "M"): 5, ("Rosa", "G"): 0})
            m, g = produto.variacoes
            dona = fabricas.usuario()
            fabricas.sacola(dona, [(m, 2)])
            db.session.commit()
            id_m, id_g = m.id, g.id

        assert cliente.post("/sacola/adicionar", data={"variacao_id": id_g}).status_code == 302  # esgotado
        resposta = cliente.post(
            "/sacola/adicionar",
            data={"variacao_id": id_m, "quantidade": 1},
            headers={"Accept": "application/json"},
        )
        assert resposta.get_json() == {"ok": True, "quantidade": 1}
        excesso = cliente.post(
            "/sacola/adicionar",
            data={"variacao_id": id_m, "quantidade": 9},
            headers={"Accept": "application/json"},
        )
        assert excesso.status_code == 400

        fabricas.entrar(cliente, "cliente@exemplo.com")
        with app.app_context():
            sacolas = db.session.scalars(select(Sacola)).all()
            assert len(sacolas) == 1  # a do visitante foi absorvida
            assert [(i.variacao_id, i.quantidade) for i in sacolas[0].itens] == [(id_m, 3)]

    def test_cupom_na_sacola(self, app: Flask, cliente: FlaskClient) -> None:
        with app.app_context():
            produto = fabricas.produto(preco=20000)
            fabricas.cupom("BEMVINDA10", minimo=10000)
            db.session.commit()
            id_variacao = produto.variacoes[0].id
        cliente.post("/sacola/adicionar", data={"variacao_id": id_variacao})
        cliente.post("/sacola/cupom", data={"codigo": "bemvinda10"})
        pagina = cliente.get("/sacola").get_data(as_text=True)
        assert "BEMVINDA10" in pagina and "−R$ 20,00" in pagina
        cliente.post("/sacola/cupom", data={"codigo": "NAOEXISTE"}, follow_redirects=True)


def test_fluxo_completo_ate_pago_no_admin(app: Flask, cliente: FlaskClient) -> None:
    """Critério de pronto: produto → sacola → checkout → Pix → webhook → admin vê "Pago"."""
    _admin_e_cliente(app)
    with app.app_context():
        id_variacao = db.session.scalars(select(Variacao.id)).first()

    assert cliente.get("/produto/vestido-teste").status_code == 200
    cliente.post("/sacola/adicionar", data={"variacao_id": id_variacao, "quantidade": 2})
    assert cliente.get("/checkout/entrega").status_code == 302  # pede login
    fabricas.entrar(cliente, "cliente@exemplo.com")

    novo = cliente.post(
        "/checkout/endereco",
        data={
            "apelido": "Casa",
            "cep": "01310-100",
            "rua": "Av. Paulista",
            "numero": "1000",
            "bairro": "Bela Vista",
            "cidade": "São Paulo",
            "uf": "SP",
        },
    )
    assert novo.status_code == 302
    assert (
        cliente.post("/checkout/entrega", data={"endereco_id": 1, "tipo_frete": "ENTREGA"}).status_code == 302
    )
    assert cliente.get("/checkout/pagamento").status_code == 200
    pagamento = cliente.post("/checkout/pagamento", data={"tipo_frete": "ENTREGA", "forma_pagamento": "PIX"})
    assert pagamento.headers["Location"].endswith("/checkout/revisao")
    revisao = cliente.get("/checkout/revisao").get_data(as_text=True)
    assert "R$ 209,90" in revisao  # 2 × 100 − 5% + 19,90

    confirmado = cliente.post("/checkout/confirmar")
    assert confirmado.status_code == 302
    numero = confirmado.headers["Location"].split("/conta/pedidos/")[1].split("?")[0]
    pagina = cliente.get(f"/conta/pedidos/{numero}").get_data(as_text=True)
    assert "Pague com Pix" in pagina and "PIX-SIMULADO" in pagina
    with app.app_context():
        assert db.session.get(Variacao, id_variacao).estoque == 3  # type: ignore[union-attr]
        sacola = db.session.scalar(select(Sacola))
        assert sacola is not None and sacola.itens == []

    assert cliente.get(f"/conta/pedidos/{numero}/status.json").get_json()["status"] == "AGUARDANDO_PAGAMENTO"
    assert cliente.post(f"/pagamentos/simulado/{numero}/aprovar").status_code == 302
    assert cliente.get(f"/conta/pedidos/{numero}/status.json").get_json()["status"] == "PAGO"

    cliente.post("/conta/sair")
    fabricas.entrar(cliente, "admin@exemplo.com")
    admin = cliente.get(f"/admin/pedidos/{numero}").get_data(as_text=True)
    assert "status-PAGO" in admin
    assert '<option value="PAGO"' not in admin  # RN08: o admin não marca pago


def test_producao_sem_mercado_pago_nao_quebra(
    app: Flask, cliente: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem MP_ACCESS_TOKEN em produção: a loja funciona, só não aceita pedidos."""
    _admin_e_cliente(app)
    with app.app_context():
        variacao = db.session.scalars(select(Variacao)).one()
        dona = db.session.scalars(select(Usuario).where(Usuario.email == "cliente@exemplo.com")).one()
        sacola = fabricas.sacola(dona, [(variacao, 1)])
        pedido = servico_pedidos.criar_pedido(dona, sacola, None, "RETIRADA", PAGAMENTO_PIX)
        db.session.commit()
        numero, id_variacao = pedido.numero, variacao.id  # estoque: 5 - 1 reservado = 4

    fabricas.entrar(cliente, "cliente@exemplo.com")
    cliente.post("/sacola/adicionar", data={"variacao_id": id_variacao})
    cliente.post("/checkout/entrega", data={"tipo_frete": "RETIRADA"})
    cliente.post("/checkout/pagamento", data={"tipo_frete": "RETIRADA", "forma_pagamento": "PIX"})

    monkeypatch.setitem(app.config, "EM_PRODUCAO", True)
    revisao = cliente.get("/checkout/revisao")
    assert revisao.status_code == 200
    assert "temporariamente indisponíveis" in revisao.get_data(as_text=True)
    confirmar = cliente.post("/checkout/confirmar")
    assert confirmar.headers["Location"].endswith("/checkout/revisao")
    with app.app_context():
        assert db.session.scalar(select(func.count(Pedido.id))) == 1  # só o pedido antigo
        assert db.session.get(Variacao, id_variacao).estoque == 4  # type: ignore[union-attr]

    pagina = cliente.get(f"/conta/pedidos/{numero}")
    assert pagina.status_code == 200
    assert "Simular pagamento" not in pagina.get_data(as_text=True)
    assert cliente.post("/pagamentos/webhook?type=payment&data.id=1").status_code == 503
