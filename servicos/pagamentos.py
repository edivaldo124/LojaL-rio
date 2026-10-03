"""Cobrança Pix e confirmação pelo webhook (RF05, RN08).

Dois gateways com a mesma interface:
- GatewayMercadoPago: API REST do Mercado Pago (sandbox ou produção, conforme o token).
- GatewaySimulado: para desenvolvimento e testes, sem conta no Mercado Pago. É recusado em produção.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol

import requests
import segno
from flask import current_app
from sqlalchemy import select

import config_loja
from extensoes import db
from modelos.pagamento_simulado import PagamentoSimulado
from modelos.pedido import Pedido
from servicos import pedidos as servico_pedidos

log = logging.getLogger(__name__)

STATUS_APROVADO = "approved"
FUSO_BRASILIA = timezone(timedelta(hours=-3))


class ErroGateway(Exception):
    pass


class PagamentoIndisponivel(ErroGateway):
    """Produção sem MP_ACCESS_TOKEN: a loja funciona, mas não gera cobranças."""


@dataclass(frozen=True)
class CobrancaPix:
    id_gateway: str
    copia_cola: str
    qr_imagem: str  # data URI pronto para <img src>


@dataclass(frozen=True)
class ConsultaPagamento:
    id_gateway: str
    status: str
    valor: int  # centavos
    referencia: str  # número do pedido


class Gateway(Protocol):
    simulado: bool

    def criar_pix(self, pedido: Pedido) -> CobrancaPix: ...

    def consultar(self, id_pagamento: str) -> ConsultaPagamento: ...

    def assinatura_valida(self, cabecalhos: Mapping[str, str], data_id: str) -> bool: ...


# ---------------------------------------------------------------- assinatura


def _manifesto(data_id: str, request_id: str, ts: str) -> str:
    # Formato do Mercado Pago: ids alfanuméricos vão em minúsculas.
    return f"id:{data_id.lower()};request-id:{request_id};ts:{ts};"


def _conferir_assinatura(segredo: str, cabecalhos: Mapping[str, str], data_id: str) -> bool:
    partes = dict(
        parte.strip().split("=", 1) for parte in cabecalhos.get("x-signature", "").split(",") if "=" in parte
    )
    ts, recebida = partes.get("ts"), partes.get("v1")
    if not ts or not recebida:
        return False
    manifesto = _manifesto(data_id, cabecalhos.get("x-request-id", ""), ts)
    esperada = hmac.new(segredo.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, recebida)


def assinar(segredo: str, data_id: str, request_id: str | None = None) -> dict[str, str]:
    """Cabeçalhos que o gateway manda no webhook (usado pelo simulado e pelos testes)."""
    request_id = request_id or secrets.token_hex(8)
    ts = str(int(time.time() * 1000))
    v1 = hmac.new(segredo.encode(), _manifesto(data_id, request_id, ts).encode(), hashlib.sha256).hexdigest()
    return {"x-signature": f"ts={ts},v1={v1}", "x-request-id": request_id}


def _centavos(valor: float | int | str) -> int:
    return int((Decimal(str(valor)) * 100).quantize(Decimal("1")))


# ---------------------------------------------------------------- Mercado Pago


class GatewayMercadoPago:
    API = "https://api.mercadopago.com"
    simulado = False

    def __init__(self, token: str, segredo_webhook: str, url_base: str, em_producao: bool) -> None:
        self.token = token
        self.segredo_webhook = segredo_webhook
        self.url_base = url_base
        self.em_producao = em_producao

    def _cabecalhos(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def criar_pix(self, pedido: Pedido) -> CobrancaPix:
        expira = (pedido.expira_em or servico_pedidos.agora()).astimezone(FUSO_BRASILIA)
        corpo: dict[str, object] = {
            "transaction_amount": float(Decimal(pedido.total) / 100),
            "payment_method_id": "pix",
            "description": f"Pedido {pedido.numero} – {config_loja.NOME}",
            "external_reference": pedido.numero,
            "date_of_expiration": expira.isoformat(timespec="milliseconds"),
            "payer": {"email": pedido.usuario.email, "first_name": pedido.usuario.primeiro_nome},
        }
        if self.url_base.startswith("https://"):  # o Mercado Pago recusa URLs locais
            corpo["notification_url"] = f"{self.url_base}/pagamentos/webhook"
        try:
            resposta = requests.post(
                f"{self.API}/v1/payments",
                json=corpo,
                headers={**self._cabecalhos(), "X-Idempotency-Key": f"pedido-{pedido.numero}"},
                timeout=20,
            )
            resposta.raise_for_status()
            dados = resposta.json()
            transacao = dados["point_of_interaction"]["transaction_data"]
            return CobrancaPix(
                id_gateway=str(dados["id"]),
                copia_cola=transacao["qr_code"],
                qr_imagem=f"data:image/png;base64,{transacao['qr_code_base64']}",
            )
        except (requests.RequestException, KeyError, ValueError) as erro:
            log.exception("Falha ao criar Pix no Mercado Pago para o pedido %s", pedido.numero)
            raise ErroGateway("Não foi possível gerar o Pix agora.") from erro

    def consultar(self, id_pagamento: str) -> ConsultaPagamento:
        try:
            resposta = requests.get(
                f"{self.API}/v1/payments/{id_pagamento}", headers=self._cabecalhos(), timeout=20
            )
            resposta.raise_for_status()
            dados = resposta.json()
            return ConsultaPagamento(
                id_gateway=str(dados["id"]),
                status=str(dados["status"]),
                valor=_centavos(dados["transaction_amount"]),
                referencia=str(dados.get("external_reference") or ""),
            )
        except (requests.RequestException, KeyError, ValueError) as erro:
            raise ErroGateway(f"Falha ao consultar o pagamento {id_pagamento}.") from erro

    def assinatura_valida(self, cabecalhos: Mapping[str, str], data_id: str) -> bool:
        if not self.segredo_webhook:
            # Sem segredo só em desenvolvimento; o pagamento é sempre reconsultado na API.
            return not self.em_producao
        return _conferir_assinatura(self.segredo_webhook, cabecalhos, data_id)


# ---------------------------------------------------------------- Simulado


class GatewaySimulado:
    simulado = True

    def __init__(self, segredo: str) -> None:
        self.segredo = segredo

    def criar_pix(self, pedido: Pedido) -> CobrancaPix:
        id_gateway = secrets.token_hex(8)
        db.session.add(PagamentoSimulado(id=id_gateway, referencia=pedido.numero, valor=pedido.total))
        # Texto propositalmente inválido para bancos: ninguém consegue pagar um Pix de teste.
        copia_cola = f"PIX-SIMULADO-NAO-PAGAR|pedido={pedido.numero}|valor={pedido.total}"
        qr = segno.make(copia_cola, error="m").svg_data_uri(scale=6, border=2, dark="#2B2B2B")
        return CobrancaPix(id_gateway=id_gateway, copia_cola=copia_cola, qr_imagem=qr)

    def consultar(self, id_pagamento: str) -> ConsultaPagamento:
        registro = db.session.get(PagamentoSimulado, id_pagamento)
        if registro is None:
            raise ErroGateway(f"Pagamento simulado {id_pagamento} não existe.")
        return ConsultaPagamento(
            id_gateway=registro.id,
            status=registro.status,
            valor=registro.valor,
            referencia=registro.referencia,
        )

    def aprovar(self, id_pagamento: str) -> None:
        registro = db.session.get(PagamentoSimulado, id_pagamento)
        if registro is None:
            raise ErroGateway(f"Pagamento simulado {id_pagamento} não existe.")
        registro.status = STATUS_APROVADO

    def assinatura_valida(self, cabecalhos: Mapping[str, str], data_id: str) -> bool:
        return _conferir_assinatura(self.segredo, cabecalhos, data_id)


def segredo_simulado(secret_key: str) -> str:
    return hmac.new(secret_key.encode(), b"webhook-simulado", hashlib.sha256).hexdigest()


def obter_gateway() -> Gateway:
    config = current_app.config
    if config["MP_ACCESS_TOKEN"]:
        return GatewayMercadoPago(
            config["MP_ACCESS_TOKEN"],
            config["MP_WEBHOOK_SECRET"],
            config["URL_BASE"],
            config["EM_PRODUCAO"],
        )
    if config["EM_PRODUCAO"]:
        raise PagamentoIndisponivel("Configure MP_ACCESS_TOKEN para receber pagamentos em produção.")
    return GatewaySimulado(segredo_simulado(config["SECRET_KEY"]))


def pagamento_disponivel() -> bool:
    try:
        obter_gateway()
    except PagamentoIndisponivel:
        return False
    return True


def pix_simulado_ativo() -> bool:
    try:
        return obter_gateway().simulado
    except PagamentoIndisponivel:
        return False


# ---------------------------------------------------------------- webhook


def processar_notificacao(gateway: Gateway, id_pagamento: str) -> Pedido | None:
    """Reconsulta o pagamento no gateway e, se aprovado com o valor certo, marca o pedido."""
    consulta = gateway.consultar(id_pagamento)
    pedido = db.session.scalar(select(Pedido).where(Pedido.numero == consulta.referencia).with_for_update())
    if pedido is None:
        log.warning("Webhook: pagamento %s sem pedido (%s)", id_pagamento, consulta.referencia)
        return None
    if consulta.status != STATUS_APROVADO:
        return pedido
    if consulta.valor != pedido.total:
        pedido.observacao = (
            f"Pagamento {consulta.id_gateway} aprovado com valor diferente do pedido "
            f"({consulta.valor} centavos, esperado {pedido.total}). Conferir antes de enviar."
        )
        log.error("Webhook: valor divergente no pedido %s", pedido.numero)
        return pedido
    servico_pedidos.confirmar_pagamento(pedido, consulta.id_gateway)
    return pedido


def datahora_expiracao(pedido: Pedido) -> datetime | None:
    return pedido.expira_em.astimezone(FUSO_BRASILIA) if pedido.expira_em else None
