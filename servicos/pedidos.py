"""Criação, cancelamento, expiração e mudança de status dos pedidos."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from flask import current_app
from sqlalchemy import select

from extensoes import db
from modelos.cupom import Cupom
from modelos.endereco import Endereco
from modelos.pedido import (
    FRETE_ENTREGA,
    PAGAMENTO_PIX,
    ItemPedido,
    Pedido,
    StatusPedido,
)
from modelos.sacola import Sacola
from modelos.usuario import Usuario
from servicos import cupons, estoque
from servicos.frete import opcao_por_tipo
from servicos.totais import calcular_totais

ALFABETO_NUMERO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O e 1/I


class ErroPedido(Exception):
    """Mensagem pronta para mostrar à cliente ou ao admin."""


def agora() -> datetime:
    return datetime.now(UTC)


def _gerar_numero() -> str:
    while True:
        numero = "".join(secrets.choice(ALFABETO_NUMERO) for _ in range(8))
        if db.session.scalar(select(Pedido.id).where(Pedido.numero == numero)) is None:
            return numero


def criar_pedido(
    usuario: Usuario,
    sacola: Sacola | None,
    endereco: Endereco | None,
    tipo_frete: str,
    forma_pagamento: str,
) -> Pedido:
    """Reserva o estoque e grava o pedido na sessão (quem chama faz o commit)."""
    if forma_pagamento != PAGAMENTO_PIX:
        raise ErroPedido("Por enquanto aceitamos apenas Pix. Cartão e boleto chegam em breve.")
    if sacola is None or not sacola.itens:
        raise ErroPedido("Sua sacola está vazia.")
    if tipo_frete == FRETE_ENTREGA and endereco is None:
        raise ErroPedido("Escolha o endereço de entrega.")
    opcao = opcao_por_tipo(tipo_frete, endereco.cep if endereco else None)
    if opcao is None:
        raise ErroPedido("Não conseguimos calcular o frete para este endereço.")

    quantidades: dict[int, int] = {}
    for item in sacola.itens:
        quantidades[item.variacao_id] = quantidades.get(item.variacao_id, 0) + item.quantidade
    try:
        variacoes = estoque.reservar(quantidades)  # RN01 + RN02
    except estoque.EstoqueInsuficiente as erro:
        raise ErroPedido(str(erro)) from erro

    subtotal = sum(variacoes[vid].produto.preco_atual * qtd for vid, qtd in quantidades.items())

    cupom: Cupom | None = None
    if sacola.cupom_codigo:
        cupom = db.session.scalar(
            select(Cupom)
            .where(Cupom.codigo == cupons.normalizar_codigo(sacola.cupom_codigo))
            .with_for_update()
        )
        try:
            cupons.validar(cupom, subtotal)
        except cupons.CupomInvalido as erro:
            raise ErroPedido(f"Cupom {sacola.cupom_codigo}: {erro}") from erro

    totais = calcular_totais(
        subtotal,
        opcao.valor,
        forma_pagamento,
        cupons.aplicado(cupom, subtotal) if cupom else None,
    )
    cupom_usado = cupom is not None and totais.desconto_cupom > 0
    if cupom_usado and cupom is not None:
        cupom.usos += 1  # RN06: um cupom por pedido

    expiracao = timedelta(minutes=current_app.config["PIX_EXPIRACAO_MINUTOS"])
    pedido = Pedido(
        numero=_gerar_numero(),
        usuario_id=usuario.id,
        status=StatusPedido.AGUARDANDO_PAGAMENTO,
        endereco=endereco.como_snapshot() if tipo_frete == FRETE_ENTREGA and endereco else None,
        tipo_frete=tipo_frete,
        prazo_frete=opcao.prazo,
        valor_frete=opcao.valor,
        subtotal=totais.subtotal,
        desconto_cupom=totais.desconto_cupom,
        desconto_pix=totais.desconto_pix,
        desconto=totais.desconto,
        total=totais.total,
        cupom_codigo=cupom.codigo if cupom_usado and cupom else None,
        forma_pagamento=forma_pagamento,
        expira_em=agora() + expiracao,
    )
    for variacao_id, quantidade in quantidades.items():
        variacao = variacoes[variacao_id]
        produto = variacao.produto
        imagem = produto.imagem_principal
        pedido.itens.append(
            ItemPedido(
                variacao_id=variacao.id,
                produto_nome=produto.nome,
                produto_slug=produto.slug,
                cor=variacao.cor,
                tamanho=variacao.tamanho,
                sku=variacao.sku,
                imagem_url=imagem.url if imagem else None,
                preco_unitario=produto.preco_atual,
                quantidade=quantidade,
            )
        )
    db.session.add(pedido)
    db.session.flush()
    return pedido


def cancelar(pedido: Pedido, motivo: str) -> None:
    if pedido.status in (StatusPedido.CANCELADO, StatusPedido.ENTREGUE):
        raise ErroPedido("Este pedido não pode ser cancelado.")
    estava_aguardando = pedido.status == StatusPedido.AGUARDANDO_PAGAMENTO
    pedido.status = StatusPedido.CANCELADO
    pedido.motivo_cancelamento = motivo
    estoque.devolver(pedido)  # RN02
    if estava_aguardando and pedido.cupom_codigo:
        cupom = db.session.scalar(select(Cupom).where(Cupom.codigo == pedido.cupom_codigo).with_for_update())
        if cupom is not None and cupom.usos > 0:
            cupom.usos -= 1


def expirar_vencidos(momento: datetime | None = None) -> int:
    """Cancela pedidos com Pix vencido e devolve o estoque. Devolve quantos expiraram."""
    momento = momento or agora()
    vencidos = db.session.scalars(
        select(Pedido)
        .where(
            Pedido.status == StatusPedido.AGUARDANDO_PAGAMENTO,
            Pedido.expira_em.is_not(None),
            Pedido.expira_em < momento,
        )
        .with_for_update(skip_locked=True)
    ).all()
    for pedido in vencidos:
        cancelar(pedido, "Pagamento expirado")
    return len(vencidos)


def mudar_status_admin(pedido: Pedido, novo: StatusPedido, rastreio: str | None = None) -> None:
    if novo == StatusPedido.PAGO:
        raise ErroPedido("O status Pago só muda pela confirmação do Mercado Pago.")
    if novo not in pedido.proximos_status():
        raise ErroPedido("Esta mudança de status não é permitida.")
    if novo == StatusPedido.CANCELADO:
        cancelar(pedido, "Cancelado pela loja")
    else:
        pedido.status = novo
    if rastreio is not None:
        pedido.rastreio = rastreio.strip() or None


def confirmar_pagamento(pedido: Pedido, id_gateway: str) -> bool:
    """Chamado só pelo processamento do webhook (RN08). Devolve True se marcou como pago."""
    if pedido.status not in (StatusPedido.AGUARDANDO_PAGAMENTO, StatusPedido.CANCELADO):
        return False  # já pago ou adiante: notificação repetida
    if pedido.status == StatusPedido.CANCELADO:
        if not estoque.reservar_de_novo(pedido):
            pedido.observacao = (
                "Pagamento aprovado depois do cancelamento e sem estoque para reservar: "
                "estornar o valor para a cliente."
            )
            return False
        pedido.observacao = "Pagamento aprovado depois do cancelamento; estoque reservado de novo."
        pedido.motivo_cancelamento = None
    pedido.status = StatusPedido.PAGO
    pedido.pago_em = agora()
    pedido.id_pagamento_gateway = id_gateway
    return True
