"""Validação de cupom de desconto (RF04, RN06)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from extensoes import db
from modelos.cupom import TIPO_PERCENTUAL, Cupom
from servicos.dinheiro import formatar_brl, percentual
from servicos.totais import CupomAplicado


class CupomInvalido(Exception):
    """Mensagem pronta para mostrar à cliente."""


def normalizar_codigo(codigo: str) -> str:
    return codigo.strip().upper()


def validar(cupom: Cupom | None, subtotal: int, agora: datetime | None = None) -> Cupom:
    agora = agora or datetime.now(UTC)
    if cupom is None or not cupom.ativo:
        raise CupomInvalido("Cupom não encontrado.")
    if cupom.validade is not None and cupom.validade < agora:
        raise CupomInvalido("Este cupom expirou.")
    if cupom.limite_uso is not None and cupom.usos >= cupom.limite_uso:
        raise CupomInvalido("Este cupom atingiu o limite de uso.")
    if subtotal < cupom.minimo:
        raise CupomInvalido(f"Este cupom vale para compras a partir de {formatar_brl(cupom.minimo)}.")
    return cupom


def buscar_valido(codigo: str, subtotal: int, agora: datetime | None = None) -> Cupom:
    codigo = normalizar_codigo(codigo)
    cupom = db.session.scalar(select(Cupom).where(func.upper(Cupom.codigo) == codigo))
    return validar(cupom, subtotal, agora)


def calcular_desconto(cupom: Cupom, subtotal: int) -> int:
    desconto = percentual(subtotal, cupom.valor) if cupom.tipo == TIPO_PERCENTUAL else cupom.valor
    return min(desconto, subtotal)


def aplicado(cupom: Cupom, subtotal: int) -> CupomAplicado:
    return CupomAplicado(
        codigo=cupom.codigo,
        desconto=calcular_desconto(cupom, subtotal),
        acumula_pix=cupom.acumula_pix,
    )


def descricao(cupom: Cupom) -> str:
    if cupom.tipo == TIPO_PERCENTUAL:
        return f"{cupom.valor}% de desconto"
    return f"{formatar_brl(cupom.valor)} de desconto"
