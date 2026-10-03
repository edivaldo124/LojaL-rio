"""Cálculo do total do pedido: subtotal, frete, cupom e desconto do Pix (RN03, RN05, RN06)."""

from __future__ import annotations

from dataclasses import dataclass

import config_loja
from modelos.pedido import PAGAMENTO_PIX
from servicos.dinheiro import percentual

AVISO_CUPOM_VENCEU = "O cupom não acumula com o Pix; aplicamos o desconto do cupom, que é maior."
AVISO_PIX_VENCEU = (
    f"O cupom não acumula com o Pix; aplicamos os {config_loja.PIX_DESCONTO_PERCENTUAL}% do Pix, que é maior."
)


@dataclass(frozen=True)
class CupomAplicado:
    codigo: str
    desconto: int  # já calculado sobre o subtotal, em centavos
    acumula_pix: bool


@dataclass(frozen=True)
class Totais:
    subtotal: int
    frete: int
    desconto_cupom: int
    desconto_pix: int
    total: int
    aviso: str | None = None

    @property
    def desconto(self) -> int:
        return self.desconto_cupom + self.desconto_pix


def calcular_totais(
    subtotal: int,
    frete: int,
    forma_pagamento: str | None = None,
    cupom: CupomAplicado | None = None,
) -> Totais:
    desconto_cupom = min(cupom.desconto, subtotal) if cupom else 0
    desconto_pix = 0
    aviso = None

    if forma_pagamento == PAGAMENTO_PIX:
        if cupom is None or cupom.acumula_pix:
            # RN03: os 5% incidem só sobre os produtos (já com o cupom, se acumulável).
            desconto_pix = percentual(subtotal - desconto_cupom, config_loja.PIX_DESCONTO_PERCENTUAL)
        else:
            # RN06: sem acumular, vale o maior desconto (decisão registrada em DECISOES.md).
            pix_isolado = percentual(subtotal, config_loja.PIX_DESCONTO_PERCENTUAL)
            if pix_isolado > desconto_cupom:
                desconto_cupom, desconto_pix, aviso = 0, pix_isolado, AVISO_PIX_VENCEU
            else:
                aviso = AVISO_CUPOM_VENCEU

    total = subtotal - desconto_cupom - desconto_pix + frete
    return Totais(
        subtotal=subtotal,
        frete=frete,
        desconto_cupom=desconto_cupom,
        desconto_pix=desconto_pix,
        total=total,
        aviso=aviso,
    )
