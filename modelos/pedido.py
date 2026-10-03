from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensoes import Modelo

if TYPE_CHECKING:
    from modelos.usuario import Usuario


class StatusPedido(StrEnum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    PAGO = "PAGO"
    EM_SEPARACAO = "EM_SEPARACAO"
    ENVIADO = "ENVIADO"
    PRONTO_RETIRADA = "PRONTO_RETIRADA"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


ROTULOS_STATUS = {
    StatusPedido.AGUARDANDO_PAGAMENTO: "Aguardando pagamento",
    StatusPedido.PAGO: "Pago",
    StatusPedido.EM_SEPARACAO: "Em separação",
    StatusPedido.ENVIADO: "Enviado",
    StatusPedido.PRONTO_RETIRADA: "Pronto para retirada",
    StatusPedido.ENTREGUE: "Entregue",
    StatusPedido.CANCELADO: "Cancelado",
}

# Mudanças que o admin pode fazer. "Pago" não aparece: só o webhook marca (RN08).
TRANSICOES_ADMIN: dict[StatusPedido, tuple[StatusPedido, ...]] = {
    StatusPedido.AGUARDANDO_PAGAMENTO: (StatusPedido.CANCELADO,),
    StatusPedido.PAGO: (StatusPedido.EM_SEPARACAO, StatusPedido.CANCELADO),
    StatusPedido.EM_SEPARACAO: (
        StatusPedido.ENVIADO,
        StatusPedido.PRONTO_RETIRADA,
        StatusPedido.CANCELADO,
    ),
    StatusPedido.ENVIADO: (StatusPedido.ENTREGUE,),
    StatusPedido.PRONTO_RETIRADA: (StatusPedido.ENTREGUE,),
    StatusPedido.ENTREGUE: (),
    StatusPedido.CANCELADO: (),
}

FRETE_ENTREGA = "ENTREGA"
FRETE_RETIRADA = "RETIRADA"

PAGAMENTO_PIX = "PIX"
PAGAMENTO_CARTAO = "CARTAO"
PAGAMENTO_BOLETO = "BOLETO"
ROTULOS_PAGAMENTO = {
    PAGAMENTO_PIX: "Pix",
    PAGAMENTO_CARTAO: "Cartão de crédito",
    PAGAMENTO_BOLETO: "Boleto",
}


class Pedido(Modelo):
    __tablename__ = "pedidos"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default=StatusPedido.AGUARDANDO_PAGAMENTO, index=True)

    endereco: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # cópia; vazio na retirada
    tipo_frete: Mapped[str] = mapped_column(String(10))
    prazo_frete: Mapped[str] = mapped_column(String(60), default="")
    valor_frete: Mapped[int] = mapped_column(Integer, default=0)

    subtotal: Mapped[int] = mapped_column(Integer)
    desconto_cupom: Mapped[int] = mapped_column(Integer, default=0)
    desconto_pix: Mapped[int] = mapped_column(Integer, default=0)
    desconto: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer)
    cupom_codigo: Mapped[str | None] = mapped_column(String(40))

    forma_pagamento: Mapped[str] = mapped_column(String(10))
    id_pagamento_gateway: Mapped[str | None] = mapped_column(String(64), index=True)
    pix_copia_cola: Mapped[str | None] = mapped_column(Text)
    pix_qr_imagem: Mapped[str | None] = mapped_column(Text)  # data URI
    expira_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pago_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rastreio: Mapped[str | None] = mapped_column(String(60))
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(200))
    observacao: Mapped[str | None] = mapped_column(Text)
    estoque_devolvido: Mapped[bool] = mapped_column(Boolean, default=False)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    usuario: Mapped[Usuario] = relationship()
    itens: Mapped[list[ItemPedido]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan", order_by="ItemPedido.id"
    )

    @property
    def status_enum(self) -> StatusPedido:
        return StatusPedido(self.status)

    @property
    def rotulo_status(self) -> str:
        return ROTULOS_STATUS[self.status_enum]

    @property
    def rotulo_pagamento(self) -> str:
        return ROTULOS_PAGAMENTO.get(self.forma_pagamento, self.forma_pagamento)

    @property
    def aguardando_pagamento(self) -> bool:
        return self.status == StatusPedido.AGUARDANDO_PAGAMENTO

    @property
    def quantidade_itens(self) -> int:
        return sum(item.quantidade for item in self.itens)

    def proximos_status(self) -> list[StatusPedido]:
        opcoes = list(TRANSICOES_ADMIN[self.status_enum])
        if self.tipo_frete == FRETE_RETIRADA:
            opcoes = [s for s in opcoes if s != StatusPedido.ENVIADO]
        else:
            opcoes = [s for s in opcoes if s != StatusPedido.PRONTO_RETIRADA]
        return opcoes


class ItemPedido(Modelo):
    """Cópia do produto no momento da compra (nome, cor, tamanho e preço não mudam depois)."""

    __tablename__ = "itens_pedido"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id", ondelete="CASCADE"), index=True)
    variacao_id: Mapped[int | None] = mapped_column(
        ForeignKey("variacoes.id", ondelete="SET NULL"), index=True
    )
    produto_nome: Mapped[str] = mapped_column(String(120))
    produto_slug: Mapped[str] = mapped_column(String(140))
    cor: Mapped[str] = mapped_column(String(40))
    tamanho: Mapped[str] = mapped_column(String(4))
    sku: Mapped[str] = mapped_column(String(60))
    imagem_url: Mapped[str | None] = mapped_column(String(255))
    preco_unitario: Mapped[int] = mapped_column(Integer)
    quantidade: Mapped[int] = mapped_column(Integer)

    pedido: Mapped[Pedido] = relationship(back_populates="itens")

    @property
    def total(self) -> int:
        return self.preco_unitario * self.quantidade
