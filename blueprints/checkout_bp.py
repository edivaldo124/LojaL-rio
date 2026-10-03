"""Checkout em três etapas: Entrega → Pagamento → Revisão (RF05)."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required
from werkzeug.wrappers import Response as RespostaWerkzeug

from extensoes import db
from formularios.checkout import FormEndereco, FormEntrega, FormPagamento
from formularios.sacola import FormVazio
from modelos import FRETE_ENTREGA, FRETE_RETIRADA, PAGAMENTO_PIX, Endereco
from servicos import pedidos as servico_pedidos
from servicos import sacola as servico_sacola
from servicos.frete import OpcaoFrete, cotar_entrega, opcao_por_tipo, opcao_retirada
from servicos.pagamentos import ErroGateway, PagamentoIndisponivel, obter_gateway, pagamento_disponivel

checkout_bp = Blueprint("checkout", __name__, url_prefix="/checkout")

MSG_PAGAMENTO_INDISPONIVEL = (
    "Os pagamentos estão temporariamente indisponíveis. Sua sacola foi mantida; tente mais tarde."
)


@checkout_bp.before_request
@login_required
def exigir_login() -> None:
    """Todas as etapas exigem login (a sacola do visitante é unificada ao entrar)."""


def _estado() -> dict[str, Any]:
    return dict(session.get("checkout", {}))


def _salvar_estado(**valores: Any) -> None:
    estado = _estado()
    estado.update(valores)
    session["checkout"] = estado


def _endereco_escolhido() -> Endereco | None:
    endereco_id = _estado().get("endereco_id")
    if not endereco_id:
        return None
    endereco = db.session.get(Endereco, endereco_id)
    return endereco if endereco is not None and endereco.usuario_id == current_user.id else None


def _sacola_ou_none() -> servico_sacola.ResumoSacola | None:
    resumo = servico_sacola.resumir(servico_sacola.obter())
    return None if resumo.vazia else resumo


def _ir_para_sacola(mensagem: str = "Sua sacola está vazia.") -> RespostaWerkzeug:
    flash(mensagem, "info")
    return redirect(url_for("sacola.ver"))


@checkout_bp.get("")
def inicio() -> RespostaWerkzeug:
    return redirect(url_for("checkout.entrega"))


# ---------------------------------------------------------------- 1. Entrega


@checkout_bp.route("/entrega", methods=["GET", "POST"])
def entrega() -> str | RespostaWerkzeug:
    resumo = _sacola_ou_none()
    if resumo is None:
        return _ir_para_sacola()

    enderecos = list(current_user.enderecos)
    estado = _estado()
    form = FormEntrega()
    form.endereco_id.choices = [(e.id, e.apelido) for e in enderecos]
    if not form.is_submitted():
        escolhido = _endereco_escolhido()
        form.endereco_id.data = escolhido.id if escolhido else (enderecos[-1].id if enderecos else None)
        form.tipo_frete.data = estado.get("tipo_frete", FRETE_ENTREGA)

    if form.validate_on_submit():
        tipo = form.tipo_frete.data
        endereco = next((e for e in enderecos if e.id == form.endereco_id.data), None)
        if tipo == FRETE_ENTREGA and endereco is None:
            flash("Escolha ou cadastre um endereço para a entrega.", "erro")
        else:
            _salvar_estado(endereco_id=endereco.id if endereco else None, tipo_frete=tipo)
            return redirect(url_for("checkout.pagamento"))

    return render_template(
        "checkout/entrega.html",
        passo=1,
        form=form,
        form_endereco=FormEndereco(formdata=None),
        enderecos=enderecos,
        fretes={e.id: cotar_entrega(e.cep) for e in enderecos},
        retirada=opcao_retirada(),
        resumo=resumo,
    )


@checkout_bp.post("/endereco")
def novo_endereco() -> str | RespostaWerkzeug:
    form = FormEndereco()
    if form.validate_on_submit():
        endereco = Endereco(usuario_id=current_user.id)
        form.populate_obj(endereco)
        db.session.add(endereco)
        db.session.commit()
        _salvar_estado(endereco_id=endereco.id, tipo_frete=FRETE_ENTREGA)
        flash("Endereço salvo.", "sucesso")
        return redirect(url_for("checkout.entrega"))

    resumo = _sacola_ou_none()
    if resumo is None:
        return _ir_para_sacola()
    enderecos = list(current_user.enderecos)
    form_entrega = FormEntrega(formdata=None)
    form_entrega.endereco_id.choices = [(e.id, e.apelido) for e in enderecos]
    form_entrega.tipo_frete.data = FRETE_ENTREGA
    return render_template(
        "checkout/entrega.html",
        passo=1,
        form=form_entrega,
        form_endereco=form,
        abrir_novo_endereco=True,
        enderecos=enderecos,
        fretes={e.id: cotar_entrega(e.cep) for e in enderecos},
        retirada=opcao_retirada(),
        resumo=resumo,
    )


# ---------------------------------------------------------------- 2. Pagamento


def _opcoes_frete(endereco: Endereco | None) -> dict[str, OpcaoFrete]:
    opcoes = {FRETE_RETIRADA: opcao_retirada()}
    if endereco is not None and (entrega := cotar_entrega(endereco.cep)) is not None:
        opcoes = {FRETE_ENTREGA: entrega, **opcoes}
    return opcoes


@checkout_bp.route("/pagamento", methods=["GET", "POST"])
def pagamento() -> str | RespostaWerkzeug:
    sacola = servico_sacola.obter()
    if _sacola_ou_none() is None:
        return _ir_para_sacola()
    estado = _estado()
    endereco = _endereco_escolhido()
    if not estado.get("tipo_frete") or (estado["tipo_frete"] == FRETE_ENTREGA and endereco is None):
        return redirect(url_for("checkout.entrega"))

    opcoes = _opcoes_frete(endereco)
    form = FormPagamento()
    form.tipo_frete.choices = [(tipo, opcao.nome) for tipo, opcao in opcoes.items()]
    if not form.is_submitted():
        form.tipo_frete.data = estado["tipo_frete"]
        form.forma_pagamento.data = estado.get("forma_pagamento", PAGAMENTO_PIX)

    if form.validate_on_submit():
        _salvar_estado(tipo_frete=form.tipo_frete.data, forma_pagamento=form.forma_pagamento.data)
        return redirect(url_for("checkout.revisao"))

    # Total de cada combinação, para a barra inferior mudar na hora (sem recarregar).
    totais = {
        tipo: servico_sacola.resumir(sacola, opcao, PAGAMENTO_PIX).totais for tipo, opcao in opcoes.items()
    }
    selecionado = form.tipo_frete.data if form.tipo_frete.data in opcoes else next(iter(opcoes))
    return render_template(
        "checkout/pagamento.html",
        passo=2,
        form=form,
        endereco=endereco,
        opcoes=opcoes,
        totais=totais,
        total_atual=totais[selecionado],
    )


# ---------------------------------------------------------------- 3. Revisão


def _montar_revisao() -> tuple[servico_sacola.ResumoSacola, Endereco | None, OpcaoFrete] | None:
    estado = _estado()
    endereco = _endereco_escolhido()
    opcao = opcao_por_tipo(estado.get("tipo_frete", ""), endereco.cep if endereco else None)
    if opcao is None or not estado.get("forma_pagamento"):
        return None
    resumo = servico_sacola.resumir(servico_sacola.obter(), opcao, estado["forma_pagamento"])
    return resumo, endereco, opcao


@checkout_bp.get("/revisao")
def revisao() -> str | RespostaWerkzeug:
    if _sacola_ou_none() is None:
        return _ir_para_sacola()
    montado = _montar_revisao()
    if montado is None:
        return redirect(url_for("checkout.pagamento"))
    resumo, endereco, opcao = montado
    return render_template(
        "checkout/revisao.html",
        passo=3,
        resumo=resumo,
        endereco=endereco,
        frete=opcao,
        forma_pagamento=_estado()["forma_pagamento"],
        pagamento_indisponivel=not pagamento_disponivel(),
        form=FormVazio(),
    )


@checkout_bp.post("/confirmar")
def confirmar() -> RespostaWerkzeug:
    if not FormVazio().validate_on_submit():
        return redirect(url_for("checkout.revisao"))
    try:
        gateway = obter_gateway()  # antes de reservar estoque
    except PagamentoIndisponivel:
        current_app.logger.error("Checkout bloqueado: produção sem MP_ACCESS_TOKEN")
        flash(MSG_PAGAMENTO_INDISPONIVEL, "erro")
        return redirect(url_for("checkout.revisao"))
    estado = _estado()
    sacola = servico_sacola.obter()
    try:
        pedido = servico_pedidos.criar_pedido(
            current_user,
            sacola,
            _endereco_escolhido(),
            estado.get("tipo_frete", ""),
            estado.get("forma_pagamento", ""),
        )
        db.session.commit()  # estoque reservado antes de falar com o gateway
    except servico_pedidos.ErroPedido as erro:
        db.session.rollback()
        flash(str(erro), "erro")
        return redirect(url_for("sacola.ver"))

    try:
        cobranca = gateway.criar_pix(pedido)
    except ErroGateway:
        db.session.rollback()
        servico_pedidos.cancelar(pedido, "Não foi possível gerar o Pix")
        db.session.commit()
        flash("Não conseguimos gerar o Pix agora. Sua sacola foi mantida; tente de novo.", "erro")
        return redirect(url_for("checkout.revisao"))

    pedido.id_pagamento_gateway = cobranca.id_gateway
    pedido.pix_copia_cola = cobranca.copia_cola
    pedido.pix_qr_imagem = cobranca.qr_imagem
    if sacola is not None:
        servico_sacola.esvaziar(sacola)
    db.session.commit()
    session.pop("checkout", None)
    return redirect(url_for("conta.pedido", numero=pedido.numero, novo=1))
