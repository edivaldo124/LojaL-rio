"""Sacola: itens, quantidade, cupom e cálculo de frete por CEP (RF04)."""

from __future__ import annotations

from flask import (
    Blueprint,
    Response,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers import Response as RespostaWerkzeug

from extensoes import db
from formularios.sacola import FormAdicionar, FormCep, FormCupom, FormQuantidade, FormVazio
from modelos import Variacao
from servicos import cupons
from servicos import sacola as servico_sacola
from servicos.cep import normalizar_cep, uf_do_cep

sacola_bp = Blueprint("sacola", __name__, url_prefix="/sacola")


def _quer_json() -> bool:
    return request.accept_mimetypes.best == "application/json"


def _voltar() -> RespostaWerkzeug:
    return redirect(url_for("sacola.ver"))


@sacola_bp.get("")
def ver() -> str:
    sacola = servico_sacola.obter()
    resumo = servico_sacola.resumir(sacola)
    form_cupom = FormCupom()
    if sacola and sacola.cupom_codigo:
        form_cupom.codigo.data = sacola.cupom_codigo
    form_cep = FormCep()
    if sacola and sacola.cep_frete:
        form_cep.cep.data = sacola.cep_frete
    return render_template(
        "loja/sacola.html",
        resumo=resumo,
        form_cupom=form_cupom,
        form_cep=form_cep,
        form_quantidade=FormQuantidade(),
        form_vazio=FormVazio(),
    )


@sacola_bp.post("/adicionar")
def adicionar() -> Response | RespostaWerkzeug:
    form = FormAdicionar()
    erro = None
    if not form.validate_on_submit():
        erro = "Escolha a cor e o tamanho."
    else:
        variacao = db.session.get(Variacao, form.variacao_id.data)
        if variacao is None:
            erro = "Esta opção não existe mais."
        else:
            try:
                servico_sacola.adicionar(variacao, form.quantidade.data or 1)
                db.session.commit()
            except servico_sacola.ErroSacola as e:
                db.session.rollback()
                erro = str(e)

    if _quer_json():
        if erro:
            return make_response(jsonify(ok=False, erro=erro), 400)
        return jsonify(ok=True, quantidade=servico_sacola.contar_itens())
    if erro:
        flash(erro, "erro")
        return redirect(request.referrer or url_for("loja.inicio"))
    flash("Peça adicionada à sacola.", "sucesso")
    return _voltar()


@sacola_bp.post("/item/<int:item_id>/quantidade")
def quantidade(item_id: int) -> RespostaWerkzeug:
    form = FormQuantidade()
    item = servico_sacola.item_da_sacola(item_id)
    if item is not None and form.validate_on_submit() and form.quantidade.data is not None:
        try:
            servico_sacola.alterar_quantidade(item, form.quantidade.data)
            db.session.commit()
        except servico_sacola.ErroSacola as erro:
            db.session.rollback()
            flash(str(erro), "erro")
    return _voltar()


@sacola_bp.post("/item/<int:item_id>/remover")
def remover(item_id: int) -> RespostaWerkzeug:
    item = servico_sacola.item_da_sacola(item_id)
    if item is not None and FormVazio().validate_on_submit():
        servico_sacola.remover(item)
        db.session.commit()
        flash("Item removido da sacola.", "info")
    return _voltar()


@sacola_bp.post("/cupom")
def aplicar_cupom() -> RespostaWerkzeug:
    form = FormCupom()
    sacola = servico_sacola.obter()
    if sacola is None or not sacola.itens:
        flash("Adicione peças à sacola antes de usar um cupom.", "erro")
        return _voltar()
    if not form.validate_on_submit() or not form.codigo.data:
        flash("Digite o código do cupom.", "erro")
        return _voltar()
    resumo = servico_sacola.resumir(sacola)
    try:
        cupom = cupons.buscar_valido(form.codigo.data, resumo.subtotal)
    except cupons.CupomInvalido as erro:
        flash(str(erro), "erro")
        return _voltar()
    sacola.cupom_codigo = cupom.codigo
    db.session.commit()
    flash(f"Cupom {cupom.codigo} aplicado: {cupons.descricao(cupom)}.", "sucesso")
    return _voltar()


@sacola_bp.post("/cupom/remover")
def remover_cupom() -> RespostaWerkzeug:
    sacola = servico_sacola.obter()
    if sacola is not None and FormVazio().validate_on_submit():
        sacola.cupom_codigo = None
        db.session.commit()
    return _voltar()


@sacola_bp.post("/frete")
def calcular_frete() -> RespostaWerkzeug:
    form = FormCep()
    sacola = servico_sacola.obter()
    if sacola is None or not form.validate_on_submit():
        return _voltar()
    cep = normalizar_cep(form.cep.data)
    if cep is None or uf_do_cep(cep) is None:
        flash("CEP inválido. Confira os 8 dígitos.", "erro")
        return _voltar()
    sacola.cep_frete = cep
    db.session.commit()
    return _voltar()
