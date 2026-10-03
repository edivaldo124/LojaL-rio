"""Dados iniciais: 2 categorias, 8 produtos com variações, banner, cupom e o usuário admin.

Uso: `flask seed`. Pode rodar mais de uma vez: o que já existe (pelo slug/código/e-mail) é mantido.
As fotos são ilustrações geradas (silhueta da peça na cor da variação) até a loja ter fotos reais.
"""

from __future__ import annotations

import io
import random
import secrets
from datetime import UTC, datetime, timedelta

import click
from flask import current_app
from PIL import Image, ImageDraw, ImageFilter
from sqlalchemy import select

from extensoes import db
from modelos import (
    PAPEL_ADMIN,
    TIPO_PERCENTUAL,
    Banner,
    Categoria,
    Cupom,
    ImagemProduto,
    Produto,
    Usuario,
    Variacao,
)
from servicos import armazenamento, senhas
from servicos.slugs import slugify

CORES = {
    "Rosa": "#E8B4BC",
    "Preto": "#2B2B2B",
    "Off-white": "#F3EDE4",
    "Verde sálvia": "#7D8F6E",
    "Terracota": "#B86A4B",
    "Azul-marinho": "#2F3A56",
    "Bege": "#D8C3A5",
    "Champanhe": "#E9D8C4",
    "Branco": "#FAF8F5",
}

CATEGORIAS = [("Vestidos", 1, "vestido", "Rosa"), ("Blusas", 2, "blusa", "Off-white")]

# nome, categoria, preço, promocional, cores, estampa, descrição, composição
PRODUTOS = [
    (
        "Vestido midi floral",
        "Vestidos",
        23990,
        18990,
        ["Rosa", "Preto", "Off-white", "Verde sálvia"],
        True,
        "Vestido midi com estampa floral delicada, decote em V e faixa para amarrar na cintura. "
        "A saia evasê tem movimento e cai bem do dia à noite.",
        "100% viscose",
    ),
    (
        "Vestido tubinho preto",
        "Vestidos",
        15990,
        None,
        ["Preto"],
        False,
        "O clássico que resolve qualquer ocasião: tubinho de alfaiataria com zíper invisível nas costas "
        "e forro leve.",
        "95% poliéster, 5% elastano",
    ),
    (
        "Vestido longo estampado",
        "Vestidos",
        22990,
        None,
        ["Terracota", "Azul-marinho"],
        True,
        "Longo fluido com alças finas reguláveis, fenda lateral e estampa exclusiva em tons quentes.",
        "100% viscose",
    ),
    (
        "Vestido chemise",
        "Vestidos",
        17990,
        None,
        ["Bege", "Verde sálvia"],
        False,
        "Chemise de botões com bolsos frontais, mangas dobráveis e cinto do mesmo tecido.",
        "55% linho, 45% viscose",
    ),
    (
        "Blusa de linho",
        "Blusas",
        11990,
        None,
        ["Off-white", "Rosa"],
        False,
        "Blusa solta de linho com decote canoa e barra arredondada. Fresca para os dias quentes.",
        "100% linho",
    ),
    (
        "Blusa de seda",
        "Blusas",
        13990,
        11990,
        ["Champanhe", "Preto"],
        False,
        "Blusa de toque acetinado com gola padre e punhos com botões encapados.",
        "100% poliéster com toque de seda",
    ),
    (
        "Blusa canelada",
        "Blusas",
        7990,
        None,
        ["Branco", "Rosa", "Preto"],
        False,
        "Básica canelada de malha macia, justa ao corpo, que combina com tudo.",
        "96% algodão, 4% elastano",
    ),
    (
        "Camisa de cetim",
        "Blusas",
        12990,
        None,
        ["Verde sálvia", "Off-white"],
        False,
        "Camisa de cetim de modelagem ampla, para usar aberta sobre a canelada "
        "ou fechada com calça de alfaiataria.",
        "100% poliéster",
    ),
]

ESTOQUES = (6, 3, 0, 8, 2, 5, 1, 4, 7)


# ---------------------------------------------------------------- ilustrações


def _rgb(hex_cor: str) -> tuple[int, int, int]:
    hex_cor = hex_cor.lstrip("#")
    return int(hex_cor[0:2], 16), int(hex_cor[2:4], 16), int(hex_cor[4:6], 16)


def _misturar(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    r, g, bl = (round(x + (y - x) * t) for x, y in zip(a, b, strict=True))
    return r, g, bl


def _silhueta(tipo: str, largura: int, altura: int, dx: float = 0.0) -> list[tuple[float, float]]:
    if tipo == "vestido":
        pontos = [
            (0.39, 0.20),
            (0.43, 0.20),
            (0.46, 0.27),
            (0.54, 0.27),
            (0.57, 0.20),
            (0.61, 0.20),
            (0.64, 0.31),
            (0.615, 0.43),
            (0.70, 0.62),
            (0.78, 0.86),
            (0.64, 0.885),
            (0.50, 0.89),
            (0.36, 0.885),
            (0.22, 0.86),
            (0.30, 0.62),
            (0.385, 0.43),
            (0.36, 0.31),
        ]
    else:
        pontos = [
            (0.36, 0.25),
            (0.45, 0.215),
            (0.50, 0.255),
            (0.55, 0.215),
            (0.64, 0.25),
            (0.80, 0.39),
            (0.73, 0.46),
            (0.665, 0.39),
            (0.67, 0.70),
            (0.50, 0.715),
            (0.33, 0.70),
            (0.335, 0.39),
            (0.27, 0.46),
            (0.20, 0.39),
        ]
    return [((x + dx) * largura, y * altura) for x, y in pontos]


def ilustracao(
    tipo: str,
    cor_hex: str,
    estampa: bool,
    angulo: int,
    tamanho: tuple[int, int],
    fundo: bool = True,
) -> Image.Image:
    """Peça no cabide. Com fundo=False devolve RGBA transparente (para compor o banner)."""
    escala = 2  # desenha em dobro e reduz: bordas suaves
    largura, altura = tamanho[0] * escala, tamanho[1] * escala
    fundo_topo, fundo_base = _rgb("#F4EEEA"), _rgb("#E8DFDA")
    imagem = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    pinta = ImageDraw.Draw(imagem)
    if fundo:
        for y in range(altura):
            pinta.line([(0, y), (largura, y)], fill=_misturar(fundo_topo, fundo_base, y / altura))

    cor = _rgb(cor_hex)
    deslocamento = (-0.03, 0.0, 0.03)[angulo % 3]
    silhueta = _silhueta(tipo, largura, altura, deslocamento)

    sombra = Image.new("L", (largura, altura), 0)
    ImageDraw.Draw(sombra).ellipse(
        [largura * (0.28 + deslocamento), altura * 0.885, largura * (0.72 + deslocamento), altura * 0.93],
        fill=70,
    )
    sombra = sombra.filter(ImageFilter.GaussianBlur(28 * escala))
    imagem.paste(_misturar(fundo_base, (60, 50, 45), 0.35), mask=sombra)

    # cabide
    cx = largura * (0.5 + deslocamento)
    tinta = _rgb("#8A8380")
    pinta.arc(
        [cx - 22 * escala, altura * 0.115, cx + 22 * escala, altura * 0.165],
        180,
        400,
        fill=tinta,
        width=5 * escala,
    )
    pinta.line(
        [(cx, altura * 0.165), (largura * (0.36 + deslocamento), altura * 0.215)],
        fill=tinta,
        width=5 * escala,
    )
    pinta.line(
        [(cx, altura * 0.165), (largura * (0.64 + deslocamento), altura * 0.215)],
        fill=tinta,
        width=5 * escala,
    )

    mascara = Image.new("L", (largura, altura), 0)
    ImageDraw.Draw(mascara).polygon(silhueta, fill=255)
    tecido = Image.new("RGB", (largura, altura), cor)
    desenho = ImageDraw.Draw(tecido)
    claro, escuro = _misturar(cor, (255, 255, 255), 0.18), _misturar(cor, (0, 0, 0), 0.12)
    for i in range(7):  # dobras do tecido
        x = largura * (0.30 + i * 0.07 + deslocamento)
        desenho.line(
            [(x, altura * 0.45), (x - largura * 0.03, altura * 0.88)],
            fill=claro if i % 2 else escuro,
            width=6 * escala,
        )
    if estampa:
        sorteio = random.Random(cor_hex + tipo)
        flor = (
            _misturar(cor, (255, 255, 255), 0.55) if sum(cor) < 450 else _misturar(cor, (120, 40, 50), 0.35)
        )
        miolo = _misturar(flor, (200, 150, 60), 0.5)
        for _ in range(140):
            fx, fy = sorteio.uniform(0.18, 0.82) * largura, sorteio.uniform(0.18, 0.9) * altura
            r = sorteio.uniform(6, 11) * escala
            for ang in range(5):
                ox = r * 0.9 * (1 if ang in (0, 1) else -1) * (0.5 if ang % 2 else 1)
                oy = r * 0.9 * (1 if ang in (1, 2) else -1) * (0.5 if ang % 2 == 0 else 1)
                desenho.ellipse(
                    [fx + ox - r * 0.6, fy + oy - r * 0.6, fx + ox + r * 0.6, fy + oy + r * 0.6], fill=flor
                )
            desenho.ellipse([fx - r * 0.35, fy - r * 0.35, fx + r * 0.35, fy + r * 0.35], fill=miolo)
    imagem.paste(tecido, mask=mascara.filter(ImageFilter.GaussianBlur(1.2 * escala)))
    contorno = ImageDraw.Draw(imagem)
    contorno.line(
        [*silhueta, silhueta[0]], fill=_misturar(cor, (0, 0, 0), 0.22), width=2 * escala, joint="curve"
    )
    reduzida = imagem.resize(tamanho, Image.Resampling.LANCZOS)
    return reduzida if not fundo else reduzida.convert("RGB")


def _salvar(imagem: Image.Image, nome: str) -> str:
    """Grava no Supabase Storage (produção) ou em static/uploads (desenvolvimento)."""
    saida = io.BytesIO()
    imagem.save(saida, "WEBP", quality=82, method=6)
    return armazenamento.salvar_bytes(saida.getvalue(), f"seed/{nome}.webp")


def _banner() -> str:
    largura, altura = 1600, 700
    imagem = Image.new("RGBA", (largura, altura))
    pinta = ImageDraw.Draw(imagem)
    for x in range(largura):
        pinta.line([(x, 0), (x, altura)], fill=_misturar(_rgb("#F6F1EE"), _rgb("#E6DAD4"), x / largura))
    pecas = [("Off-white", "blusa", 0), ("Rosa", "vestido", 1), ("Verde sálvia", "vestido", 2)]
    for i, (cor, tipo, angulo) in enumerate(pecas):
        peca = ilustracao(tipo, CORES[cor], cor == "Rosa", angulo, (480, 640), fundo=False)
        imagem.alpha_composite(peca, (720 + i * 270, 40 + (i % 2) * 25))
    return _salvar(imagem.convert("RGB"), "banner-nova-colecao")


# ---------------------------------------------------------------- execução


def _admin() -> None:
    email = current_app.config["ADMIN_EMAIL"].lower()
    if db.session.scalar(select(Usuario).where(Usuario.email == email)) is not None:
        click.echo(f"Admin {email} já existe (senha mantida).")
        return
    senha = current_app.config["ADMIN_SENHA"] or secrets.token_urlsafe(12)
    db.session.add(
        Usuario(nome="Administradora", email=email, senha_hash=senhas.gerar_hash(senha), papel=PAPEL_ADMIN)
    )
    origem = "definida em ADMIN_SENHA" if current_app.config["ADMIN_SENHA"] else f"gerada: {senha}"
    click.echo(f"Admin criado: {email} — senha {origem}")


def executar() -> None:
    _admin()

    categorias: dict[str, Categoria] = {}
    for nome, ordem, tipo, cor in CATEGORIAS:
        slug = slugify(nome)
        categoria = db.session.scalar(select(Categoria).where(Categoria.slug == slug))
        if categoria is None:
            imagem = ilustracao(tipo, CORES[cor], tipo == "vestido", 1, (400, 400))
            categoria = Categoria(
                nome=nome, slug=slug, ordem=ordem, imagem=_salvar(imagem, f"categoria-{slug}")
            )
            db.session.add(categoria)
        categorias[nome] = categoria
    db.session.flush()

    agora = datetime.now(UTC)
    criados = 0
    for posicao, (nome, nome_categoria, preco, promo, cores, estampa, descricao, composicao) in enumerate(
        PRODUTOS
    ):
        slug = slugify(nome)
        if db.session.scalar(select(Produto.id).where(Produto.slug == slug)) is not None:
            continue
        produto = Produto(
            nome=nome,
            slug=slug,
            descricao=descricao,
            composicao=composicao,
            categoria=categorias[nome_categoria],
            preco=preco,
            preco_promocional=promo,
            criado_em=agora - timedelta(days=posicao),
        )
        tipo = "vestido" if nome_categoria == "Vestidos" else "blusa"
        for angulo, cor in enumerate((cores * 3)[:3]):
            imagem = ilustracao(tipo, CORES[cor], estampa, angulo, (1200, 1600))
            produto.imagens.append(
                ImagemProduto(
                    url=_salvar(imagem, f"{slug}-{angulo + 1}"),
                    alt=f"{nome} na cor {cor.lower()}",
                    ordem=angulo,
                )
            )
        for i, cor in enumerate(cores):
            for j, tamanho in enumerate(("PP", "P", "M", "G", "GG")):
                produto.variacoes.append(
                    Variacao(
                        cor=cor,
                        cor_hex=CORES[cor],
                        tamanho=tamanho,
                        sku=f"{slug[:24]}-{slugify(cor)[:12]}-{tamanho}".upper(),
                        estoque=ESTOQUES[(posicao + i * 2 + j) % len(ESTOQUES)],
                    )
                )
        db.session.add(produto)
        criados += 1

    if db.session.scalar(select(Banner.id).limit(1)) is None:
        db.session.add(
            Banner(
                imagem=_banner(),
                titulo="Nova Coleção",
                texto_botao="Ver coleção",
                link="/categoria/vestidos",
            )
        )

    if db.session.scalar(select(Cupom.id).where(Cupom.codigo == "BEMVINDA10")) is None:
        db.session.add(
            Cupom(codigo="BEMVINDA10", tipo=TIPO_PERCENTUAL, valor=10, minimo=10000, limite_uso=500)
        )

    db.session.commit()
    click.echo(f"Seed concluído: {len(categorias)} categorias, {criados} produtos novos.")
