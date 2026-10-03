"""Vitrine: início, catálogo por categoria, busca, produto e favoritos (RF01–RF03)."""

from __future__ import annotations

from typing import Any

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy import Select, and_, case, desc, exists, func, or_, select, true
from sqlalchemy.orm import selectinload
from werkzeug.wrappers import Response as RespostaWerkzeug

import config_loja
from extensoes import db
from formularios.sacola import FormAdicionar, FormVazio
from modelos import Banner, Categoria, Favorito, ItemPedido, Pedido, Produto, StatusPedido, Variacao

loja_bp = Blueprint("loja", __name__)

ORDENACOES = {
    "recentes": "Mais recentes",
    "menor-preco": "Menor preço",
    "maior-preco": "Maior preço",
    "mais-vendidos": "Mais vendidos",
}
STATUS_VENDIDOS = (
    StatusPedido.PAGO,
    StatusPedido.EM_SEPARACAO,
    StatusPedido.ENVIADO,
    StatusPedido.PRONTO_RETIRADA,
    StatusPedido.ENTREGUE,
)

preco_efetivo = case(
    (
        and_(Produto.preco_promocional.is_not(None), Produto.preco_promocional < Produto.preco),
        Produto.preco_promocional,
    ),
    else_=Produto.preco,
)


def _ids_favoritos() -> set[int]:
    if not current_user.is_authenticated:
        return set()
    return set(db.session.scalars(select(Favorito.produto_id).where(Favorito.usuario_id == current_user.id)))


def _com_imagens(consulta: Select[Produto]) -> Select[Produto]:
    return consulta.options(selectinload(Produto.imagens))


@loja_bp.get("/")
def inicio() -> str:
    banner = db.session.scalar(
        select(Banner).where(Banner.ativo.is_(True)).order_by(Banner.id.desc()).limit(1)
    )
    novidades = db.session.scalars(
        _com_imagens(select(Produto))
        .where(Produto.ativo.is_(True))
        .order_by(Produto.criado_em.desc(), Produto.id.desc())
        .limit(8)
    ).all()
    return render_template("loja/inicio.html", banner=banner, novidades=novidades, favoritos=_ids_favoritos())


# ---------------------------------------------------------------- catálogo


def _inteiro(valor: str | None) -> int | None:
    return int(valor) if valor and valor.isdigit() else None


def _catalogo(titulo: str, filtro: Any, *, categoria: Categoria | None = None, termo: str = "") -> str:
    tamanhos = [t for t in request.args.getlist("tamanho") if t in config_loja.TAMANHOS]
    cores = [c[:40] for c in request.args.getlist("cor") if c]
    preco_min = _inteiro(request.args.get("preco_min"))
    preco_max = _inteiro(request.args.get("preco_max"))
    ordem = request.args.get("ordem", "recentes")
    if ordem not in ORDENACOES:
        ordem = "recentes"
    pagina = _inteiro(request.args.get("pagina")) or 1

    base = select(Produto).where(Produto.ativo.is_(True), filtro)
    cores_disponiveis = db.session.execute(
        select(Variacao.cor, func.min(Variacao.cor_hex))
        .join(Produto)
        .where(Produto.ativo.is_(True), filtro)
        .group_by(Variacao.cor)
        .order_by(Variacao.cor)
    ).all()

    consulta = base
    if tamanhos or cores:
        condicoes = [Variacao.produto_id == Produto.id, Variacao.estoque > 0]
        if tamanhos:
            condicoes.append(Variacao.tamanho.in_(tamanhos))
        if cores:
            condicoes.append(Variacao.cor.in_(cores))
        consulta = consulta.where(exists(select(Variacao.id).where(*condicoes)))
    if preco_min is not None:
        consulta = consulta.where(preco_efetivo >= preco_min * 100)
    if preco_max is not None:
        consulta = consulta.where(preco_efetivo <= preco_max * 100)

    if ordem == "menor-preco":
        consulta = consulta.order_by(preco_efetivo.asc(), Produto.id)
    elif ordem == "maior-preco":
        consulta = consulta.order_by(preco_efetivo.desc(), Produto.id)
    elif ordem == "mais-vendidos":
        vendidos = (
            select(Variacao.produto_id, func.sum(ItemPedido.quantidade).label("qtd"))
            .join(ItemPedido, ItemPedido.variacao_id == Variacao.id)
            .join(Pedido, Pedido.id == ItemPedido.pedido_id)
            .where(Pedido.status.in_(STATUS_VENDIDOS))
            .group_by(Variacao.produto_id)
            .subquery()
        )
        consulta = consulta.outerjoin(vendidos, vendidos.c.produto_id == Produto.id).order_by(
            desc(func.coalesce(vendidos.c.qtd, 0)), Produto.criado_em.desc()
        )
    else:
        consulta = consulta.order_by(Produto.criado_em.desc(), Produto.id.desc())

    paginacao = db.paginate(
        _com_imagens(consulta),
        page=pagina,
        per_page=config_loja.PRODUTOS_POR_PAGINA,
        error_out=False,
    )
    filtros_ativos = len(tamanhos) + len(cores) + (preco_min is not None) + (preco_max is not None)
    return render_template(
        "loja/catalogo.html",
        titulo=titulo,
        categoria=categoria,
        termo=termo,
        paginacao=paginacao,
        produtos=paginacao.items,
        favoritos=_ids_favoritos(),
        ordenacoes=ORDENACOES,
        ordem=ordem,
        tamanhos=tamanhos,
        cores=cores,
        cores_disponiveis=cores_disponiveis,
        preco_min=preco_min,
        preco_max=preco_max,
        filtros_ativos=filtros_ativos,
    )


@loja_bp.get("/categoria/<slug>")
def categoria(slug: str) -> str:
    categoria = db.session.scalar(select(Categoria).where(Categoria.slug == slug))
    if categoria is None:
        abort(404)
    return _catalogo(categoria.nome, Produto.categoria_id == categoria.id, categoria=categoria)


@loja_bp.get("/busca")
def busca() -> str:
    termo = " ".join(request.args.get("q", "").split())[:80]
    if not termo:
        return _catalogo("Todos os produtos", true())
    padrao = "%" + termo.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
    filtro = or_(
        Produto.nome.ilike(padrao, escape="\\"),
        Produto.descricao.ilike(padrao, escape="\\"),
        Produto.categoria.has(Categoria.nome.ilike(padrao, escape="\\")),
    )
    return _catalogo(f"“{termo}”", filtro, termo=termo)


# ---------------------------------------------------------------- produto


@loja_bp.get("/produto/<slug>")
def produto(slug: str) -> str:
    produto = db.session.scalar(
        select(Produto)
        .where(Produto.slug == slug)
        .options(selectinload(Produto.imagens), selectinload(Produto.variacoes))
    )
    admin = current_user.is_authenticated and current_user.is_admin
    if produto is None or (not produto.ativo and not admin):
        abort(404)
    relacionados = db.session.scalars(
        _com_imagens(select(Produto))
        .where(
            Produto.ativo.is_(True),
            Produto.categoria_id == produto.categoria_id,
            Produto.id != produto.id,
        )
        .order_by(Produto.criado_em.desc())
        .limit(4)
    ).all()
    return render_template(
        "loja/produto.html",
        produto=produto,
        relacionados=relacionados,
        favoritos=_ids_favoritos(),
        form=FormAdicionar(),
        form_favorito=FormVazio(),
    )


# ---------------------------------------------------------------- favoritos


@loja_bp.post("/favoritos/<int:produto_id>")
def favoritar(produto_id: int) -> Response | RespostaWerkzeug:
    produto = db.session.get(Produto, produto_id)
    if produto is None:
        abort(404)
    quer_json = request.accept_mimetypes.best == "application/json"
    if not current_user.is_authenticated:
        destino = url_for("conta.entrar", next=url_for("loja.produto", slug=produto.slug))
        if quer_json:
            return make_response(jsonify(login=destino), 401)
        return redirect(destino)

    favorito = db.session.get(Favorito, (current_user.id, produto.id))
    if favorito is None:
        db.session.add(Favorito(usuario_id=current_user.id, produto_id=produto.id))
        ativo = True
    else:
        db.session.delete(favorito)
        ativo = False
    db.session.commit()
    if quer_json:
        return jsonify(favorito=ativo)
    return redirect(request.form.get("voltar") or url_for("loja.produto", slug=produto.slug))


@loja_bp.get("/favoritos")
def favoritos() -> str:
    produtos: list[Produto] = []
    if current_user.is_authenticated:
        produtos = list(
            db.session.scalars(
                _com_imagens(select(Produto))
                .join(Favorito, Favorito.produto_id == Produto.id)
                .where(Favorito.usuario_id == current_user.id, Produto.ativo.is_(True))
                .order_by(Favorito.criado_em.desc())
            )
        )
    return render_template("loja/favoritos.html", produtos=produtos, favoritos={p.id for p in produtos})


# ---------------------------------------------------------------- institucional e SEO


@loja_bp.get("/privacidade")
def privacidade() -> str:
    return render_template("loja/privacidade.html")


@loja_bp.get("/robots.txt")
def robots() -> Response:
    base = current_app.config["URL_BASE"]
    bloqueados = "".join(f"Disallow: {caminho}\n" for caminho in ("/admin", "/conta", "/checkout"))
    texto = f"User-agent: *\n{bloqueados}Sitemap: {base}/sitemap.xml\n"
    return Response(texto, mimetype="text/plain")


@loja_bp.get("/sitemap.xml")
def sitemap() -> Response:
    base = current_app.config["URL_BASE"]
    caminhos = [url_for("loja.inicio")]
    caminhos += [url_for("loja.categoria", slug=s) for s in db.session.scalars(select(Categoria.slug))]
    caminhos += [
        url_for("loja.produto", slug=s)
        for s in db.session.scalars(select(Produto.slug).where(Produto.ativo.is_(True)))
    ]
    xml = render_template("sitemap.xml", urls=[base + c for c in caminhos])
    return Response(xml, mimetype="application/xml")
