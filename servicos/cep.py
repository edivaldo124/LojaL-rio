"""CEP: normalização e UF pela faixa oficial dos Correios (sem chamada externa)."""

from __future__ import annotations

import re

# (início, fim, UF) — faixas de CEP por estado, pelos 5 primeiros dígitos.
_FAIXAS_UF: tuple[tuple[int, int, str], ...] = (
    (1000, 19999, "SP"),
    (20000, 28999, "RJ"),
    (29000, 29999, "ES"),
    (30000, 39999, "MG"),
    (40000, 48999, "BA"),
    (49000, 49999, "SE"),
    (50000, 56999, "PE"),
    (57000, 57999, "AL"),
    (58000, 58999, "PB"),
    (59000, 59999, "RN"),
    (60000, 63999, "CE"),
    (64000, 64999, "PI"),
    (65000, 65999, "MA"),
    (66000, 68899, "PA"),
    (68900, 68999, "AP"),
    (69000, 69299, "AM"),
    (69300, 69399, "RR"),
    (69400, 69899, "AM"),
    (69900, 69999, "AC"),
    (70000, 72799, "DF"),
    (72800, 72999, "GO"),
    (73000, 73699, "DF"),
    (73700, 76799, "GO"),
    (76800, 76999, "RO"),
    (77000, 77999, "TO"),
    (78000, 78899, "MT"),
    (79000, 79999, "MS"),
    (80000, 87999, "PR"),
    (88000, 89999, "SC"),
    (90000, 99999, "RS"),
)

REGIAO_POR_UF = {
    **dict.fromkeys(("SP", "RJ", "ES", "MG"), "Sudeste"),
    **dict.fromkeys(("PR", "SC", "RS"), "Sul"),
    **dict.fromkeys(("DF", "GO", "MT", "MS"), "Centro-Oeste"),
    **dict.fromkeys(("BA", "SE", "PE", "AL", "PB", "RN", "CE", "PI", "MA"), "Nordeste"),
    **dict.fromkeys(("PA", "AP", "AM", "RR", "AC", "RO", "TO"), "Norte"),
}

UFS = tuple(sorted(REGIAO_POR_UF))


def normalizar_cep(texto: str | None) -> str | None:
    """'01310-100' -> '01310100'. Devolve None se não tiver 8 dígitos."""
    digitos = re.sub(r"\D", "", texto or "")
    return digitos if len(digitos) == 8 else None


def formatar_cep(cep: str) -> str:
    return f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cep


def uf_do_cep(cep: str) -> str | None:
    normalizado = normalizar_cep(cep)
    if normalizado is None:
        return None
    prefixo = int(normalizado[:5])
    for inicio, fim, uf in _FAIXAS_UF:
        if inicio <= prefixo <= fim:
            return uf
    return None


def regiao_do_cep(cep: str) -> str | None:
    uf = uf_do_cep(cep)
    return REGIAO_POR_UF.get(uf) if uf else None
