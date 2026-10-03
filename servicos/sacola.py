"""Sacola de compras: visitante (cookie) ou cliente logada, unificadas no login (RF04)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from flask import Response, current_app, g, request
from flask_login import current_user
from sqlalchemy import func, select

import config_loja
from extensoes import db
from modelos.cupom import Cupom
from modelos.produto import Produto, Variacao
from modelos.sacola import ItemSacola, Sacola
from modelos.usuario import Usuario
from servicos import cupons
from servicos.frete import OpcaoFrete, cotar_entrega
from servicos.totais import CupomAplicado, Totais, calcular_totais

COOKIE = "sacola"
DURACAO_COOKIE = 60 * 60 * 24 * 60  # 60 dias


class ErroSacola(Exception):
    pass


# ---------------------------------------------------------------- obter / cookie


def _por_token(token: str | None) -> Sacola | None:
    if not token:
        return None
    return db.session.scalar(select(Sacola).where(Sacola.token == token))


def obter(criar: bool = False) -> Sacola | None:
    if current_user.is_authenticated:
        sacola = db.session.scalar(select(Sacola).where(Sacola.usuario_id == current_user.id))
        if sacola is None and criar:
            sacola = Sacola(usuario_id=current_user.id)
            db.session.add(sacola)
            db.session.flush()
        return sacola

    sacola = _por_token(request.cookies.get(COOKIE))
    if sacola is None and criar:
        token = secrets.token_urlsafe(32)
        sacola = Sacola(token=token)
        db.session.add(sacola)
        db.session.flush()
        g.sacola_token_novo = token
    return sacola


def gravar_cookie(resposta: Response) -> Response:
    """after_request: grava ou apaga o cookie da sacola do visitante."""
    seguro = current_app.config["EM_PRODUCAO"]
    if token := g.pop("sacola_token_novo", None):
        resposta.set_cookie(
            COOKIE, token, max_age=DURACAO_COOKIE, httponly=True, samesite="Lax", secure=seguro
        )
    elif g.pop("sacola_apagar_cookie", False):
        resposta.delete_cookie(COOKIE, httponly=True, samesite="Lax", secure=seguro)
    return resposta


def contar_itens() -> int:
    """Quantidade de peças para o contador do cabeçalho."""
    if current_user.is_authenticated:
        filtro = Sacola.usuario_id == current_user.id
    else:
        # Sacola criada nesta mesma requisição: o cookie só chega ao navegador na resposta.
        token = g.get("sacola_token_novo") or request.cookies.get(COOKIE)
        if not token:
            return 0
        filtro = Sacola.token == token
    consulta = select(func.coalesce(func.sum(ItemSacola.quantidade), 0)).join(Sacola).where(filtro)
    return int(db.session.scalar(consulta) or 0)


# ---------------------------------------------------------------- itens


def _limite(variacao: Variacao) -> int:
    return min(variacao.estoque, config_loja.QUANTIDADE_MAXIMA_POR_ITEM)


def adicionar(variacao: Variacao, quantidade: int = 1) -> ItemSacola:
    if not variacao.produto.ativo:
        raise ErroSacola("Este produto não está mais disponível.")
    if variacao.estoque <= 0:  # RN01
        raise ErroSacola("Este tamanho está esgotado nesta cor.")

    sacola = obter(criar=True)
    assert sacola is not None
    item = next((i for i in sacola.itens if i.variacao_id == variacao.id), None)
    atual = item.quantidade if item else 0
    nova = atual + quantidade
    if nova > _limite(variacao):
        raise ErroSacola(
            f"Você já tem {atual} na sacola e restam {variacao.estoque} unidade(s) deste tamanho."
            if atual
            else f"Restam só {variacao.estoque} unidade(s) deste tamanho."
        )
    if item is None:
        item = ItemSacola(variacao=variacao, quantidade=quantidade)
        sacola.itens.append(item)
    else:
        item.quantidade = nova
    return item


def item_da_sacola(item_id: int) -> ItemSacola | None:
    sacola = obter()
    if sacola is None:
        return None
    return next((i for i in sacola.itens if i.id == item_id), None)


def alterar_quantidade(item: ItemSacola, quantidade: int) -> None:
    if quantidade <= 0:
        remover(item)
        return
    if quantidade > _limite(item.variacao):
        raise ErroSacola(f"Restam só {item.variacao.estoque} unidade(s) deste tamanho.")
    item.quantidade = quantidade


def remover(item: ItemSacola) -> None:
    item.sacola.itens.remove(item)


def esvaziar(sacola: Sacola) -> None:
    sacola.itens.clear()
    sacola.cupom_codigo = None


def unificar_no_login(usuario: Usuario) -> None:
    """Junta a sacola do visitante à da cliente que acabou de entrar."""
    visitante = _por_token(request.cookies.get(COOKIE))
    if visitante is None:
        return
    g.sacola_apagar_cookie = True
    if not visitante.itens:
        db.session.delete(visitante)
        return

    da_cliente = db.session.scalar(select(Sacola).where(Sacola.usuario_id == usuario.id))
    if da_cliente is None:
        visitante.token = None
        visitante.usuario_id = usuario.id
        return

    existentes = {i.variacao_id: i for i in da_cliente.itens}
    for item in list(visitante.itens):
        limite = _limite(item.variacao)
        if item.variacao_id in existentes:
            alvo = existentes[item.variacao_id]
            alvo.quantidade = max(1, min(alvo.quantidade + item.quantidade, limite))
        elif limite > 0:
            da_cliente.itens.append(
                ItemSacola(variacao_id=item.variacao_id, quantidade=min(item.quantidade, limite))
            )
    if visitante.cupom_codigo and not da_cliente.cupom_codigo:
        da_cliente.cupom_codigo = visitante.cupom_codigo
    db.session.delete(visitante)


# ---------------------------------------------------------------- resumo


@dataclass
class LinhaSacola:
    item: ItemSacola
    variacao: Variacao
    produto: Produto
    preco_unitario: int
    total: int
    problema: str | None = None


@dataclass
class ResumoSacola:
    sacola: Sacola | None
    linhas: list[LinhaSacola] = field(default_factory=list)
    subtotal: int = 0
    quantidade: int = 0
    cupom: Cupom | None = None
    cupom_aplicado: CupomAplicado | None = None
    cupom_erro: str | None = None
    frete: OpcaoFrete | None = None
    totais: Totais | None = None

    @property
    def vazia(self) -> bool:
        return not self.linhas

    @property
    def tem_problema(self) -> bool:
        return any(linha.problema for linha in self.linhas)


def resumir(
    sacola: Sacola | None,
    frete: OpcaoFrete | None = None,
    forma_pagamento: str | None = None,
) -> ResumoSacola:
    resumo = ResumoSacola(sacola=sacola)
    if sacola is None:
        resumo.totais = calcular_totais(0, 0)
        return resumo

    for item in sacola.itens:
        variacao = item.variacao
        produto = variacao.produto
        problema = None
        if not produto.ativo:
            problema = "Produto indisponível"
        elif variacao.estoque == 0:
            problema = "Esgotado"
        elif item.quantidade > variacao.estoque:
            problema = f"Restam só {variacao.estoque}"
        preco = produto.preco_atual
        resumo.linhas.append(LinhaSacola(item, variacao, produto, preco, preco * item.quantidade, problema))
        resumo.subtotal += preco * item.quantidade
        resumo.quantidade += item.quantidade

    if sacola.cupom_codigo and resumo.linhas:
        try:
            resumo.cupom = cupons.buscar_valido(sacola.cupom_codigo, resumo.subtotal)
            resumo.cupom_aplicado = cupons.aplicado(resumo.cupom, resumo.subtotal)
        except cupons.CupomInvalido as erro:
            resumo.cupom_erro = str(erro)

    if frete is None and sacola.cep_frete:
        frete = cotar_entrega(sacola.cep_frete)
    resumo.frete = frete

    resumo.totais = calcular_totais(
        resumo.subtotal,
        frete.valor if frete else 0,
        forma_pagamento,
        resumo.cupom_aplicado,
    )
    return resumo
