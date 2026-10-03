"""Estoque por variação, cupom e ciclo de vida do pedido (RN01, RN02, RN06, RN08)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from extensoes import db
from modelos import FRETE_ENTREGA, FRETE_RETIRADA, PAGAMENTO_PIX, TIPO_VALOR, StatusPedido
from servicos import cupons, estoque
from servicos import pedidos as servico_pedidos
from tests import fabricas

pytestmark = pytest.mark.usefixtures("banco")


def _pedido_simples(quantidade: int = 2, cupom: str | None = None, tipo_frete: str = FRETE_ENTREGA):
    produto = fabricas.produto(preco=10000, estoques={("Rosa", "M"): 5})
    variacao = produto.variacoes[0]
    cliente = fabricas.usuario()
    endereco = fabricas.endereco(cliente)
    sacola = fabricas.sacola(cliente, [(variacao, quantidade)], cupom=cupom)
    pedido = servico_pedidos.criar_pedido(cliente, sacola, endereco, tipo_frete, PAGAMENTO_PIX)
    return pedido, variacao


class TestEstoque:
    def test_criar_pedido_reserva_o_estoque(self) -> None:  # RN02
        pedido, variacao = _pedido_simples(quantidade=2)
        assert variacao.estoque == 3
        assert pedido.status == StatusPedido.AGUARDANDO_PAGAMENTO
        assert pedido.total == 20000 - 1000 + 1990  # Pix 5% + frete Sudeste

    def test_sem_estoque_nada_e_reservado(self) -> None:  # RN01
        produto = fabricas.produto(estoques={("Rosa", "M"): 5, ("Rosa", "G"): 1})
        m, g = produto.variacoes
        cliente = fabricas.usuario()
        sacola = fabricas.sacola(cliente, [(m, 2), (g, 3)])
        endereco = fabricas.endereco(cliente)
        db.session.commit()
        with pytest.raises(servico_pedidos.ErroPedido, match="restam só 1"):
            servico_pedidos.criar_pedido(cliente, sacola, endereco, FRETE_ENTREGA, PAGAMENTO_PIX)
        db.session.rollback()
        db.session.refresh(m)
        db.session.refresh(g)
        assert (m.estoque, g.estoque) == (5, 1)

    def test_produto_inativo_nao_pode_ser_comprado(self) -> None:
        produto = fabricas.produto(ativo=False)
        cliente = fabricas.usuario()
        sacola = fabricas.sacola(cliente, [(produto.variacoes[0], 1)])
        with pytest.raises(servico_pedidos.ErroPedido, match="não está mais disponível"):
            servico_pedidos.criar_pedido(cliente, sacola, None, FRETE_RETIRADA, PAGAMENTO_PIX)

    def test_cancelar_devolve_o_estoque_uma_vez_so(self) -> None:  # RN02
        pedido, variacao = _pedido_simples(quantidade=2)
        servico_pedidos.cancelar(pedido, "teste")
        assert variacao.estoque == 5
        estoque.devolver(pedido)  # chamada repetida não devolve de novo
        assert variacao.estoque == 5
        with pytest.raises(servico_pedidos.ErroPedido):
            servico_pedidos.cancelar(pedido, "de novo")

    def test_pix_vencido_expira_e_devolve(self) -> None:
        pedido, variacao = _pedido_simples(quantidade=1)
        db.session.commit()
        assert servico_pedidos.expirar_vencidos(datetime.now(UTC)) == 0
        depois = datetime.now(UTC) + timedelta(minutes=31)
        assert servico_pedidos.expirar_vencidos(depois) == 1
        assert pedido.status == StatusPedido.CANCELADO
        assert pedido.motivo_cancelamento == "Pagamento expirado"
        assert variacao.estoque == 5

    def test_retirada_tem_frete_zero_e_sem_endereco(self) -> None:  # RN05
        pedido, _ = _pedido_simples(quantidade=1, tipo_frete=FRETE_RETIRADA)
        assert pedido.valor_frete == 0
        assert pedido.endereco is None
        assert pedido.total == 9500

    def test_so_aceita_pix_na_fase_1(self) -> None:
        produto = fabricas.produto()
        cliente = fabricas.usuario()
        sacola = fabricas.sacola(cliente, [(produto.variacoes[0], 1)])
        with pytest.raises(servico_pedidos.ErroPedido, match="apenas Pix"):
            servico_pedidos.criar_pedido(cliente, sacola, None, FRETE_RETIRADA, "CARTAO")


class TestCupom:
    def test_validacoes(self) -> None:
        agora = datetime.now(UTC)
        vencido = fabricas.cupom("VENCIDO", validade=agora - timedelta(days=1))
        esgotado = fabricas.cupom("ESGOTADO", limite_uso=2, usos=2)
        minimo = fabricas.cupom("MINIMO", minimo=20000)
        inativo = fabricas.cupom("INATIVO", ativo=False)
        for cupom, mensagem in [
            (vencido, "expirou"),
            (esgotado, "limite de uso"),
            (minimo, "a partir de"),
            (inativo, "não encontrado"),
        ]:
            with pytest.raises(cupons.CupomInvalido, match=mensagem):
                cupons.validar(cupom, 10000, agora)
        with pytest.raises(cupons.CupomInvalido):
            cupons.buscar_valido("NAOEXISTE", 10000)

    def test_codigo_ignora_maiusculas_e_espacos(self) -> None:
        fabricas.cupom("BEMVINDA10")
        assert cupons.buscar_valido("  bemvinda10 ", 10000).codigo == "BEMVINDA10"

    def test_desconto_percentual_e_em_valor(self) -> None:
        assert cupons.calcular_desconto(fabricas.cupom("PCT", valor=10), 18990) == 1899
        assert cupons.calcular_desconto(fabricas.cupom("FIXO", tipo=TIPO_VALOR, valor=5000), 3000) == 3000

    def test_uso_conta_no_pedido_e_volta_no_cancelamento(self) -> None:
        cupom = fabricas.cupom("TRINTA", tipo=TIPO_VALOR, valor=3000, limite_uso=1)
        pedido, _ = _pedido_simples(quantidade=2, cupom="TRINTA")
        # R$ 30 de cupom > 5% de Pix (R$ 10): vale o cupom, sem acumular (RN06)
        assert (pedido.desconto_cupom, pedido.desconto_pix) == (3000, 0)
        assert cupom.usos == 1
        servico_pedidos.cancelar(pedido, "teste")
        assert cupom.usos == 0

    def test_cupom_menor_que_pix_nao_gasta_uso(self) -> None:
        cupom = fabricas.cupom("UM", tipo=TIPO_VALOR, valor=100)
        pedido, _ = _pedido_simples(quantidade=2, cupom="UM")
        assert (pedido.desconto_cupom, pedido.desconto_pix) == (0, 1000)
        assert pedido.cupom_codigo is None
        assert cupom.usos == 0


class TestStatus:
    def test_admin_nao_marca_pago(self) -> None:  # RN08
        pedido, _ = _pedido_simples()
        with pytest.raises(servico_pedidos.ErroPedido, match="Mercado Pago"):
            servico_pedidos.mudar_status_admin(pedido, StatusPedido.PAGO)

    def test_fluxo_de_status_da_entrega(self) -> None:
        pedido, _ = _pedido_simples()
        assert servico_pedidos.confirmar_pagamento(pedido, "pg-1")
        assert not servico_pedidos.confirmar_pagamento(pedido, "pg-1")  # repetida
        assert StatusPedido.PRONTO_RETIRADA not in [*pedido.proximos_status()]
        servico_pedidos.mudar_status_admin(pedido, StatusPedido.EM_SEPARACAO)
        servico_pedidos.mudar_status_admin(pedido, StatusPedido.ENVIADO, " BR123 ")
        assert pedido.rastreio == "BR123"
        servico_pedidos.mudar_status_admin(pedido, StatusPedido.ENTREGUE)
        assert pedido.proximos_status() == []
        with pytest.raises(servico_pedidos.ErroPedido):
            servico_pedidos.mudar_status_admin(pedido, StatusPedido.CANCELADO)

    def test_pagamento_depois_da_expiracao_reserva_de_novo(self) -> None:
        pedido, variacao = _pedido_simples(quantidade=2)
        servico_pedidos.cancelar(pedido, "Pagamento expirado")
        assert variacao.estoque == 5
        assert servico_pedidos.confirmar_pagamento(pedido, "pg-2")
        assert pedido.status == StatusPedido.PAGO
        assert variacao.estoque == 3
