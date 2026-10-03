"""Webhook do gateway (único caminho para "Pago", RN08) e o botão de pagamento simulado."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, current_app, flash, redirect, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select
from werkzeug.wrappers import Response as RespostaWerkzeug

from extensoes import csrf, db
from formularios.sacola import FormVazio
from modelos import Pedido
from servicos.pagamentos import (
    ErroGateway,
    GatewaySimulado,
    assinar,
    obter_gateway,
    processar_notificacao,
)

pagamentos_bp = Blueprint("pagamentos", __name__, url_prefix="/pagamentos")


@pagamentos_bp.post("/webhook")
@csrf.exempt
def webhook() -> tuple[str, int]:
    corpo: dict[str, Any] = request.get_json(silent=True) or {}
    tipo = request.args.get("type") or request.args.get("topic") or corpo.get("type")
    data_id = request.args.get("data.id") or str((corpo.get("data") or {}).get("id") or "")
    if tipo != "payment" or not data_id:
        return "ignorado", 200  # outros eventos não interessam à loja

    gateway = obter_gateway()
    cabecalhos = {nome.lower(): valor for nome, valor in request.headers.items()}
    if not gateway.assinatura_valida(cabecalhos, data_id):
        current_app.logger.warning("Webhook com assinatura inválida (pagamento %s)", data_id)
        return "assinatura inválida", 401
    try:
        processar_notificacao(gateway, data_id)
        db.session.commit()
    except ErroGateway:
        db.session.rollback()
        current_app.logger.exception("Webhook: falha ao consultar o pagamento %s", data_id)
        return "tente de novo", 502  # o Mercado Pago reenvia a notificação
    return "ok", 200


@pagamentos_bp.post("/simulado/<numero>/aprovar")
@login_required
def aprovar_simulado(numero: str) -> RespostaWerkzeug:
    """Só fora de produção e sem Mercado Pago: aprova a cobrança no gateway simulado e
    dispara o webhook como o gateway faria, com assinatura."""
    gateway = obter_gateway()
    if not isinstance(gateway, GatewaySimulado) or current_app.config["EM_PRODUCAO"]:
        abort(404)
    pedido = db.session.scalar(select(Pedido).where(Pedido.numero == numero))
    if pedido is None or pedido.usuario_id != current_user.id or not pedido.id_pagamento_gateway:
        abort(404)
    if not FormVazio().validate_on_submit():
        abort(400)

    gateway.aprovar(pedido.id_pagamento_gateway)
    db.session.commit()
    resposta = current_app.test_client().post(
        f"/pagamentos/webhook?data.id={pedido.id_pagamento_gateway}&type=payment",
        json={"type": "payment", "data": {"id": pedido.id_pagamento_gateway}},
        headers=assinar(gateway.segredo, pedido.id_pagamento_gateway),
    )
    db.session.expire_all()
    if resposta.status_code != 200:
        flash("O webhook simulado falhou. Veja o log do servidor.", "erro")
    return redirect(url_for("conta.pedido", numero=numero))
