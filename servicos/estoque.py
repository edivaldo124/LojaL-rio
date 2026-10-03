"""Reserva e devolução de estoque por variação (RN01, RN02)."""

from __future__ import annotations

from sqlalchemy import select

from extensoes import db
from modelos.pedido import Pedido
from modelos.produto import Variacao


class EstoqueInsuficiente(Exception):
    def __init__(self, variacao: Variacao | None, pedida: int) -> None:
        self.variacao = variacao
        self.pedida = pedida
        if variacao is None or not variacao.produto.ativo:
            mensagem = "Um dos itens da sacola não está mais disponível."
        elif variacao.estoque == 0:
            mensagem = (
                f"{variacao.produto.nome} ({variacao.cor}, {variacao.tamanho}) esgotou. "
                "Remova o item da sacola para continuar."
            )
        else:
            mensagem = (
                f"{variacao.produto.nome} ({variacao.cor}, {variacao.tamanho}): "
                f"restam só {variacao.estoque} unidade(s)."
            )
        super().__init__(mensagem)


def _travar(ids: list[int]) -> dict[int, Variacao]:
    """Trava as linhas em ordem de id (evita deadlock entre dois pedidos simultâneos)."""
    consulta = select(Variacao).where(Variacao.id.in_(ids)).order_by(Variacao.id).with_for_update()
    return {v.id: v for v in db.session.scalars(consulta)}


def reservar(quantidades: dict[int, int]) -> dict[int, Variacao]:
    """Baixa o estoque de todas as variações ou de nenhuma. Levanta EstoqueInsuficiente."""
    ids = sorted(quantidades)
    variacoes = _travar(ids)
    for variacao_id in ids:
        variacao = variacoes.get(variacao_id)
        pedida = quantidades[variacao_id]
        if variacao is None or not variacao.produto.ativo or variacao.estoque < pedida:
            raise EstoqueInsuficiente(variacao, pedida)
    for variacao_id in ids:
        variacoes[variacao_id].estoque -= quantidades[variacao_id]
    return variacoes


def _quantidades_do_pedido(pedido: Pedido) -> dict[int, int]:
    quantidades: dict[int, int] = {}
    for item in pedido.itens:
        if item.variacao_id is not None:
            quantidades[item.variacao_id] = quantidades.get(item.variacao_id, 0) + item.quantidade
    return quantidades


def devolver(pedido: Pedido) -> None:
    """Devolve o estoque do pedido uma única vez (cancelamento ou expiração)."""
    if pedido.estoque_devolvido:
        return
    quantidades = _quantidades_do_pedido(pedido)
    variacoes = _travar(sorted(quantidades))
    for variacao_id, quantidade in quantidades.items():
        variacao = variacoes.get(variacao_id)
        if variacao is not None:  # variação apagada no admin: não há onde devolver
            variacao.estoque += quantidade
    pedido.estoque_devolvido = True


def reservar_de_novo(pedido: Pedido) -> bool:
    """Para pagamento que chega depois do cancelamento: tenta reservar outra vez."""
    if not pedido.estoque_devolvido:
        return True
    try:
        reservar(_quantidades_do_pedido(pedido))
    except EstoqueInsuficiente:
        return False
    pedido.estoque_devolvido = False
    return True
