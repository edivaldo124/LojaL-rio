"""Valores em centavos (RN07). Formatação em BRL só na interface."""

from __future__ import annotations

import re


def formatar_brl(centavos: int) -> str:
    """18990 -> 'R$ 189,90'; 123456 -> 'R$ 1.234,56' (com espaço não separável)."""
    sinal = "-" if centavos < 0 else ""
    reais, resto = divmod(abs(centavos), 100)
    milhares = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$\u00a0{milhares},{resto:02d}"  # espaço que não quebra linha


def centavos_de_texto(texto: str) -> int:
    """Converte o que a pessoa digitou ('189,90', 'R$ 1.234,56', '189') em centavos.

    Levanta ValueError se o texto não for um valor válido.
    """
    limpo = texto.strip().replace("R$", "").replace(" ", "").replace("\u00a0", "")
    if not limpo:
        raise ValueError("valor vazio")
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", limpo):
        raise ValueError(f"valor inválido: {texto!r}")
    reais, _, decimais = limpo.partition(".")
    return int(reais) * 100 + int(decimais.ljust(2, "0") or 0)


def texto_de_centavos(centavos: int) -> str:
    """18990 -> '189,90' (para preencher campos de formulário)."""
    reais, resto = divmod(centavos, 100)
    return f"{reais},{resto:02d}"


def percentual(centavos: int, pct: int) -> int:
    """Percentual inteiro de um valor, arredondando meio centavo para cima."""
    return (centavos * pct + 50) // 100


def valor_parcela(total: int, parcelas: int) -> int:
    """Valor de cada parcela sem juros, arredondado para cima (nunca cobra a menos)."""
    return -(-total // parcelas)
