"""Frete da Fase 1: tabela fixa por região (config_loja.FRETE_POR_REGIAO)."""

from __future__ import annotations

from dataclasses import dataclass

import config_loja
from modelos.pedido import FRETE_ENTREGA, FRETE_RETIRADA
from servicos.cep import regiao_do_cep


@dataclass(frozen=True)
class OpcaoFrete:
    tipo: str
    nome: str
    valor: int
    prazo: str


def cotar_entrega(cep: str) -> OpcaoFrete | None:
    regiao = regiao_do_cep(cep)
    if regiao is None:
        return None
    tabela = config_loja.FRETE_POR_REGIAO[regiao]
    return OpcaoFrete(
        tipo=FRETE_ENTREGA,
        nome=config_loja.NOME_ENTREGA_PADRAO,
        valor=tabela["valor"],
        prazo=tabela["prazo"],
    )


def opcao_retirada() -> OpcaoFrete:
    """RN05: retirar na loja não cobra frete."""
    return OpcaoFrete(
        tipo=FRETE_RETIRADA,
        nome=config_loja.RETIRADA["nome"],
        valor=0,
        prazo=config_loja.RETIRADA["prazo"],
    )


def opcao_por_tipo(tipo: str, cep: str | None) -> OpcaoFrete | None:
    if tipo == FRETE_RETIRADA:
        return opcao_retirada()
    if tipo == FRETE_ENTREGA and cep:
        return cotar_entrega(cep)
    return None
