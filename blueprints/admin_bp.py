"""Painel administrativo: produtos, fotos, variações/estoque, categorias e pedidos (RF07–RF10)."""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from werkzeug.wrappers import Response as RespostaWerkzeug

import config_loja
from extensoes import db
from formularios.admin import (
    FormAltFoto,
    FormCategoria,
    FormFotos,
    FormNovaCor,
    FormProduto,
    FormStatusPedido,
    FormVariacao,
)
from formularios.sacola import FormVazio
from modelos import Categoria, ImagemProduto, Pedido, Produto, StatusPedido, Variacao
from modelos.pedido import ROTULOS_STATUS
from servicos import armazenamento
from servicos import pedidos as servico_pedidos
from servicos.autorizacao import admin_obrigatorio, bloquear_nao_admin
from servicos.dinheiro import centavos_de_texto, texto_de_centavos
from servicos.slugs import slug_unico, slugify

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.before_request
def proteger() -> RespostaWerkzeug | None:
    """Toda rota /admin passa por aqui; as views também levam @admin_obrigatorio."""
    return bloquear_nao_admin()


def _voltar_produto(produto: Produto, ancora: str = "") -> RespostaWerkzeug:
    return redirect(url_for("admin.editar_produto", produto_id=produto.id) + ancora)


def _produto_ou_404(produto_id: int) -> Produto:
    produto = db.session.get(Produto, produto_id)
    if produto is None:
        abort(404)
    return produto


# ---------------------------------------------------------------- painel


@admin_bp.get("")
@admin_obrigatorio
def painel() -> str:
    servico_pedidos.expirar_vencidos()
    db.session.commit()
    contagem = dict(
        db.session.execute(select(Pedido.status, func.count(Pedido.id)).group_by(Pedido.status)).all()
    )
    estoque_baixo = db.session.scalars(
        select(Variacao)
        .join(Produto)
        .where(Produto.ativo.is_(True), Variacao.estoque <= config_loja.ESTOQUE_BAIXO)
        .order_by(Variacao.estoque, Produto.nome)
        .limit(15)
    ).all()
    recentes = db.session.scalars(select(Pedido).order_by(Pedido.id.desc()).limit(6)).all()
    return render_template(
        "admin/painel.html",
        contagem=contagem,
        estoque_baixo=estoque_baixo,
        recentes=recentes,
        status=StatusPedido,
    )


# ---------------------------------------------------------------- produtos


@admin_bp.get("/produtos")
@admin_obrigatorio
def produtos() -> str:
    termo = request.args.get("q", "").strip()[:80]
    consulta = select(Produto).options(
        selectinload(Produto.imagens), selectinload(Produto.variacoes), selectinload(Produto.categoria)
    )
    if termo:
        padrao = f"%{termo}%"
        consulta = consulta.where(or_(Produto.nome.ilike(padrao), Produto.slug.ilike(padrao)))
    lista = db.session.scalars(consulta.order_by(Produto.criado_em.desc(), Produto.id.desc())).all()
    return render_template("admin/produtos.html", produtos=lista, termo=termo)


def _opcoes_categoria(form: FormProduto) -> bool:
    categorias = db.session.scalars(select(Categoria).order_by(Categoria.ordem, Categoria.nome)).all()
    form.categoria_id.choices = [(c.id, c.nome) for c in categorias]
    return bool(categorias)


def _aplicar_form_produto(form: FormProduto, produto: Produto) -> None:
    produto.nome = (form.nome.data or "").strip()
    produto.categoria_id = form.categoria_id.data
    produto.preco = centavos_de_texto(form.preco.data or "")
    produto.preco_promocional = (
        centavos_de_texto(form.preco_promocional.data) if form.preco_promocional.data else None
    )
    produto.descricao = (form.descricao.data or "").strip()
    produto.composicao = (form.composicao.data or "").strip()
    produto.ativo = bool(form.ativo.data)


def _slug_existe(slug: str, ignorar_id: int | None = None) -> bool:
    consulta = select(Produto.id).where(Produto.slug == slug)
    if ignorar_id is not None:
        consulta = consulta.where(Produto.id != ignorar_id)
    return db.session.scalar(consulta) is not None


@admin_bp.route("/produtos/novo", methods=["GET", "POST"])
@admin_obrigatorio
def novo_produto() -> str | RespostaWerkzeug:
    form = FormProduto()
    if not _opcoes_categoria(form):
        flash("Cadastre uma categoria antes de criar produtos.", "info")
        return redirect(url_for("admin.nova_categoria"))
    if form.validate_on_submit():
        produto = Produto()
        _aplicar_form_produto(form, produto)
        produto.slug = slug_unico(produto.nome, _slug_existe)
        db.session.add(produto)
        db.session.commit()
        flash("Produto criado. Agora envie as fotos e cadastre as cores e tamanhos.", "sucesso")
        return _voltar_produto(produto, "#fotos")
    return render_template("admin/produto_form.html", form=form, produto=None)


@admin_bp.route("/produtos/<int:produto_id>", methods=["GET", "POST"])
@admin_obrigatorio
def editar_produto(produto_id: int) -> str | RespostaWerkzeug:
    produto = _produto_ou_404(produto_id)
    form = FormProduto(obj=produto)
    _opcoes_categoria(form)
    if not form.is_submitted():
        form.preco.data = texto_de_centavos(produto.preco)
        form.preco_promocional.data = (
            texto_de_centavos(produto.preco_promocional) if produto.preco_promocional else ""
        )
    if form.validate_on_submit():
        nome_antigo = produto.nome
        _aplicar_form_produto(form, produto)
        if slugify(produto.nome) != slugify(nome_antigo):
            produto.slug = slug_unico(produto.nome, lambda s: _slug_existe(s, produto.id))
        db.session.commit()
        flash("Produto salvo.", "sucesso")
        return _voltar_produto(produto)
    return render_template(
        "admin/produto_form.html",
        form=form,
        produto=produto,
        form_fotos=FormFotos(),
        form_alt=FormAltFoto(),
        form_cor=FormNovaCor(formdata=None),
        form_variacao=FormVariacao(formdata=None),
        form_vazio=FormVazio(),
    )


@admin_bp.post("/produtos/<int:produto_id>/excluir")
@admin_obrigatorio
def excluir_produto(produto_id: int) -> RespostaWerkzeug:
    produto = _produto_ou_404(produto_id)
    if FormVazio().validate_on_submit():
        caminhos = [imagem.url for imagem in produto.imagens]
        db.session.delete(produto)  # itens de pedidos antigos guardam cópia dos dados
        db.session.commit()
        for caminho in caminhos:
            armazenamento.remover(caminho)
        flash(f"Produto “{produto.nome}” excluído.", "info")
    return redirect(url_for("admin.produtos"))


# ---------------------------------------------------------------- fotos


@admin_bp.post("/produtos/<int:produto_id>/fotos")
@admin_obrigatorio
def enviar_fotos(produto_id: int) -> RespostaWerkzeug:
    produto = _produto_ou_404(produto_id)
    form = FormFotos()
    if not form.validate_on_submit():
        flash("Escolha ao menos uma foto.", "erro")
        return _voltar_produto(produto, "#fotos")
    proxima_ordem = max((i.ordem for i in produto.imagens), default=-1) + 1
    enviadas = 0
    for arquivo in form.fotos.data:
        if not arquivo or not arquivo.filename:
            continue
        try:
            caminho = armazenamento.salvar_imagem(arquivo, "produtos")
        except (armazenamento.ImagemInvalida, armazenamento.ErroArmazenamento) as erro:
            flash(str(erro), "erro")
            continue
        produto.imagens.append(ImagemProduto(url=caminho, ordem=proxima_ordem))
        proxima_ordem += 1
        enviadas += 1
    db.session.commit()
    if enviadas:
        flash(f"{enviadas} foto(s) enviada(s).", "sucesso")
    return _voltar_produto(produto, "#fotos")


def _foto_ou_404(produto: Produto, foto_id: int) -> ImagemProduto:
    foto = next((i for i in produto.imagens if i.id == foto_id), None)
    if foto is None:
        abort(404)
    return foto


@admin_bp.post("/produtos/<int:produto_id>/fotos/<int:foto_id>/mover")
@admin_obrigatorio
def mover_foto(produto_id: int, foto_id: int) -> RespostaWerkzeug:
    produto = _produto_ou_404(produto_id)
    foto = _foto_ou_404(produto, foto_id)
    if FormVazio().validate_on_submit():
        fotos = list(produto.imagens)
        posicao = fotos.index(foto)
        alvo = posicao - 1 if request.form.get("direcao") == "antes" else posicao + 1
        if 0 <= alvo < len(fotos):
            fotos[posicao], fotos[alvo] = fotos[alvo], fotos[posicao]
            for ordem, imagem in enumerate(fotos):
                imagem.ordem = ordem
            db.session.commit()
    return _voltar_produto(produto, "#fotos")


@admin_bp.post("/produtos/<int:produto_id>/fotos/<int:foto_id>/alt")
@admin_obrigatorio
def alt_foto(produto_id: int, foto_id: int) -> RespostaWerkzeug:
    produto = _produto_ou_404(produto_id)
    foto = _foto_ou_404(produto, foto_id)
    form = FormAltFoto()
    if form.validate_on_submit():
        foto.alt = (form.alt.data or "").strip() or None
        db.session.commit()
        flash("Texto alternativo salvo.", "sucesso")
    return _voltar_produto(produto, "#fotos")


@admin_bp.post("/produtos/<int:produto_id>/fotos/<int:foto_id>/excluir")
@admin_obrigatorio
def excluir_foto(produto_id: int, foto_id: int) -> RespostaWerkzeug:
    produto = _produto_ou_404(produto_id)
    foto = _foto_ou_404(produto, foto_id)
    if FormVazio().validate_on_submit():
        caminho = foto.url
        produto.imagens.remove(foto)
        for ordem, imagem in enumerate(produto.imagens):
            imagem.ordem = ordem
        db.session.commit()
        armazenamento.remover(caminho)
    return _voltar_produto(produto, "#fotos")


# ---------------------------------------------------------------- variações e estoque


def _gerar_sku(produto: Produto, cor: str, tamanho: str) -> str:
    base = f"{slugify(produto.nome)[:24]}-{slugify(cor)[:12]}-{tamanho}".upper()
    sku, n = base, 2
    while db.session.scalar(select(Variacao.id).where(Variacao.sku == sku)) is not None:
        sku = f"{base}-{n}"
        n += 1
    return sku


@admin_bp.post("/produtos/<int:produto_id>/variacoes")
@admin_obrigatorio
def adicionar_cor(produto_id: int) -> RespostaWerkzeug:
    produto = _produto_ou_404(produto_id)
    form = FormNovaCor()
    if not form.validate_on_submit():
        for erros in form.errors.values():
            for erro in erros:
                flash(str(erro), "erro")
        return _voltar_produto(produto, "#variacoes")
    cor = " ".join((form.cor.data or "").split()).capitalize()
    existentes = {(v.cor.lower(), v.tamanho) for v in produto.variacoes}
    criadas = 0
    for tamanho in form.tamanhos.data or []:
        if (cor.lower(), tamanho) in existentes:
            continue
        produto.variacoes.append(
            Variacao(
                cor=cor,
                cor_hex=(form.cor_hex.data or "#000000").upper(),
                tamanho=tamanho,
                sku=_gerar_sku(produto, cor, tamanho),
                estoque=form.estoque.data or 0,
            )
        )
        db.session.flush()
        criadas += 1
    db.session.commit()
    flash(
        f"{criadas} variação(ões) criada(s) em {cor}." if criadas else "Essas variações já existem.",
        "sucesso" if criadas else "info",
    )
    return _voltar_produto(produto, "#variacoes")


def _variacao_ou_404(produto: Produto, variacao_id: int) -> Variacao:
    variacao = next((v for v in produto.variacoes if v.id == variacao_id), None)
    if variacao is None:
        abort(404)
    return variacao


@admin_bp.post("/produtos/<int:produto_id>/variacoes/<int:variacao_id>")
@admin_obrigatorio
def salvar_variacao(produto_id: int, variacao_id: int) -> RespostaWerkzeug:
    produto = _produto_ou_404(produto_id)
    variacao = _variacao_ou_404(produto, variacao_id)
    form = FormVariacao()
    if not form.validate_on_submit():
        flash("Confira o SKU e o estoque (número de 0 a 99999).", "erro")
        return _voltar_produto(produto, "#variacoes")
    sku = (form.sku.data or "").strip().upper()
    duplicado = db.session.scalar(select(Variacao.id).where(Variacao.sku == sku, Variacao.id != variacao.id))
    if duplicado is not None:
        flash(f"O SKU {sku} já está em uso.", "erro")
        return _voltar_produto(produto, "#variacoes")
    variacao.sku = sku
    variacao.estoque = form.estoque.data or 0
    if form.cor_hex.data:  # a amostra vale para todos os tamanhos da mesma cor
        for outra in produto.variacoes:
            if outra.cor == variacao.cor:
                outra.cor_hex = form.cor_hex.data.upper()
    db.session.commit()
    flash(f"{variacao.cor} {variacao.tamanho}: estoque {variacao.estoque}.", "sucesso")
    return _voltar_produto(produto, "#variacoes")


@admin_bp.post("/produtos/<int:produto_id>/variacoes/<int:variacao_id>/excluir")
@admin_obrigatorio
def excluir_variacao(produto_id: int, variacao_id: int) -> RespostaWerkzeug:
    produto = _produto_ou_404(produto_id)
    variacao = _variacao_ou_404(produto, variacao_id)
    if FormVazio().validate_on_submit():
        produto.variacoes.remove(variacao)
        db.session.commit()
        flash("Variação excluída.", "info")
    return _voltar_produto(produto, "#variacoes")


# ---------------------------------------------------------------- categorias


@admin_bp.get("/categorias")
@admin_obrigatorio
def categorias() -> str:
    lista = db.session.scalars(select(Categoria).order_by(Categoria.ordem, Categoria.nome)).all()
    quantidades = dict(
        db.session.execute(
            select(Produto.categoria_id, func.count(Produto.id)).group_by(Produto.categoria_id)
        ).all()
    )
    return render_template(
        "admin/categorias.html", categorias=lista, quantidades=quantidades, form_vazio=FormVazio()
    )


def _salvar_categoria(form: FormCategoria, categoria: Categoria) -> bool:
    categoria.nome = (form.nome.data or "").strip()
    categoria.ordem = form.ordem.data or 0
    arquivo = form.imagem.data
    if arquivo and getattr(arquivo, "filename", ""):
        try:
            novo = armazenamento.salvar_imagem(arquivo, "categorias")
        except (armazenamento.ImagemInvalida, armazenamento.ErroArmazenamento) as erro:
            form.imagem.errors = [str(erro)]
            return False
        armazenamento.remover(categoria.imagem)
        categoria.imagem = novo
    return True


def _slug_categoria_existe(slug: str, ignorar_id: int | None = None) -> bool:
    consulta = select(Categoria.id).where(Categoria.slug == slug)
    if ignorar_id is not None:
        consulta = consulta.where(Categoria.id != ignorar_id)
    return db.session.scalar(consulta) is not None


@admin_bp.route("/categorias/nova", methods=["GET", "POST"])
@admin_obrigatorio
def nova_categoria() -> str | RespostaWerkzeug:
    form = FormCategoria()
    if form.validate_on_submit():
        categoria = Categoria()
        if _salvar_categoria(form, categoria):
            categoria.slug = slug_unico(categoria.nome, _slug_categoria_existe)
            db.session.add(categoria)
            db.session.commit()
            flash("Categoria criada.", "sucesso")
            return redirect(url_for("admin.categorias"))
    return render_template("admin/categoria_form.html", form=form, categoria=None)


@admin_bp.route("/categorias/<int:categoria_id>", methods=["GET", "POST"])
@admin_obrigatorio
def editar_categoria(categoria_id: int) -> str | RespostaWerkzeug:
    categoria = db.session.get(Categoria, categoria_id)
    if categoria is None:
        abort(404)
    form = FormCategoria(obj=categoria)
    if form.validate_on_submit():
        nome_antigo = categoria.nome
        if _salvar_categoria(form, categoria):
            if slugify(categoria.nome) != slugify(nome_antigo):
                categoria.slug = slug_unico(categoria.nome, lambda s: _slug_categoria_existe(s, categoria.id))
            db.session.commit()
            flash("Categoria salva.", "sucesso")
            return redirect(url_for("admin.categorias"))
    return render_template("admin/categoria_form.html", form=form, categoria=categoria)


@admin_bp.post("/categorias/<int:categoria_id>/excluir")
@admin_obrigatorio
def excluir_categoria(categoria_id: int) -> RespostaWerkzeug:
    categoria = db.session.get(Categoria, categoria_id)
    if categoria is None:
        abort(404)
    if FormVazio().validate_on_submit():
        em_uso = db.session.scalar(select(func.count(Produto.id)).where(Produto.categoria_id == categoria.id))
        if em_uso:
            flash("Mova ou exclua os produtos desta categoria antes de excluí-la.", "erro")
        else:
            armazenamento.remover(categoria.imagem)
            db.session.delete(categoria)
            db.session.commit()
            flash("Categoria excluída.", "info")
    return redirect(url_for("admin.categorias"))


# ---------------------------------------------------------------- pedidos


@admin_bp.get("/pedidos")
@admin_obrigatorio
def pedidos() -> str:
    servico_pedidos.expirar_vencidos()
    db.session.commit()
    filtro = request.args.get("status", "")
    consulta = select(Pedido).options(selectinload(Pedido.usuario), selectinload(Pedido.itens))
    if filtro in StatusPedido.__members__:
        consulta = consulta.where(Pedido.status == filtro)
    pagina = db.paginate(consulta.order_by(Pedido.id.desc()), per_page=30, error_out=False)
    return render_template("admin/pedidos.html", paginacao=pagina, filtro=filtro, rotulos=ROTULOS_STATUS)


def _pedido_ou_404(numero: str) -> Pedido:
    pedido = db.session.scalar(select(Pedido).where(Pedido.numero == numero))
    if pedido is None:
        abort(404)
    return pedido


@admin_bp.route("/pedidos/<numero>", methods=["GET", "POST"])
@admin_obrigatorio
def pedido(numero: str) -> str | RespostaWerkzeug:
    pedido = _pedido_ou_404(numero)
    form = FormStatusPedido()
    form.status.choices = [("", "Escolha…")] + [
        (s.value, ROTULOS_STATUS[s]) for s in pedido.proximos_status()
    ]
    if not form.is_submitted():
        form.rastreio.data = pedido.rastreio
    if form.validate_on_submit():
        try:
            servico_pedidos.mudar_status_admin(pedido, StatusPedido(form.status.data), form.rastreio.data)
            db.session.commit()
            flash(f"Pedido {pedido.numero}: {pedido.rotulo_status}.", "sucesso")
            return redirect(url_for("admin.pedido", numero=pedido.numero))
        except (servico_pedidos.ErroPedido, ValueError) as erro:
            db.session.rollback()
            flash(str(erro), "erro")
    return render_template("admin/pedido.html", pedido=pedido, form=form)
