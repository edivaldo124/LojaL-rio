"""Identidade e regras da loja em um só lugar.

O nome "Lírio" é provisório: para trocar a marca, edite este arquivo e substitua os SVGs em
static/img/marca/. As cores daqui sobrescrevem as do CSS em tempo de execução (base.html),
então não é preciso recompilar o Tailwind para mudar a paleta.
"""

from __future__ import annotations

from typing import TypedDict


class TabelaFrete(TypedDict):
    valor: int  # centavos
    prazo: str


NOME = "Lírio"
SLOGAN = "Moda feminina"
TITULO_SITE = f"{NOME} · {SLOGAN.lower()}"
DESCRICAO = (
    "Vestidos, blusas e peças femininas com caimento leve e tecidos confortáveis. "
    "Compre online com Pix e receba em todo o Brasil."
)

LOGOS = {
    "horizontal": "img/marca/logo-horizontal.svg",
    "horizontal_branca": "img/marca/logo-horizontal-branca.svg",
    "horizontal_fundo_escuro": "img/marca/logo-horizontal-fundo-escuro.svg",
    "vertical": "img/marca/logo-vertical.svg",
    "simbolo": "img/marca/simbolo.svg",
}

# Tokens de cor. "rose_texto" e "taupe_texto" são as versões com contraste AA para texto
# pequeno sobre o creme (ver DECISOES.md).
CORES = {
    "rose": "#C97B84",
    "rose-texto": "#A4545F",
    "ink": "#2B2B2B",
    "cream": "#FAF7F5",
    "taupe": "#8A8380",
    "taupe-texto": "#706966",
    "line": "#E4DDD9",
    "placeholder": "#E8DFDA",
}

CONTATO = {
    "email": "contato@exemplo.com",
    "whatsapp": "(00) 00000-0000",
    "instagram": "@lirio.modafeminina",
}

RETIRADA = {
    "nome": "Retirar na loja",
    "endereco": "Rua Exemplo, 123 – Centro, Cidade – UF",
    "prazo": "Disponível em 1 dia útil",
    "horario": "Segunda a sexta, das 9h às 18h; sábado, das 9h às 13h",
}

# Frete da Fase 1: tabela fixa por região (valores em centavos, de exemplo).
FRETE_POR_REGIAO: dict[str, TabelaFrete] = {
    "Sudeste": {"valor": 1990, "prazo": "5 a 8 dias úteis"},
    "Sul": {"valor": 2490, "prazo": "6 a 9 dias úteis"},
    "Centro-Oeste": {"valor": 2790, "prazo": "7 a 10 dias úteis"},
    "Nordeste": {"valor": 2990, "prazo": "8 a 12 dias úteis"},
    "Norte": {"valor": 3490, "prazo": "10 a 15 dias úteis"},
}
NOME_ENTREGA_PADRAO = "Entrega padrão"

PIX_DESCONTO_PERCENTUAL = 5
PARCELAS_SEM_JUROS = 3

TAMANHOS = ("PP", "P", "M", "G", "GG")
ESTOQUE_BAIXO = 3  # alerta no admin quando a variação tem esta quantidade ou menos
QUANTIDADE_MAXIMA_POR_ITEM = 10
PRODUTOS_POR_PAGINA = 12

# Medidas em centímetros (de exemplo; revisar com a modelagem da loja).
GUIA_MEDIDAS = {
    "colunas": ("Tamanho", "Busto", "Cintura", "Quadril"),
    "linhas": (
        ("PP", "78–82", "60–64", "86–90"),
        ("P", "82–86", "64–68", "90–94"),
        ("M", "86–92", "68–74", "94–100"),
        ("G", "92–98", "74–80", "100–106"),
        ("GG", "98–104", "80–86", "106–112"),
    ),
    "observacao": "Meça sobre a roupa íntima, com a fita justa mas sem apertar.",
}

TEXTOS = {
    "aviso_cookies": (
        "Usamos apenas cookies essenciais: um para manter você conectada e outro para guardar "
        "a sua sacola. Não usamos cookies de rastreamento."
    ),
    "rodape": "Peças escolhidas com carinho para o seu dia a dia.",
}
