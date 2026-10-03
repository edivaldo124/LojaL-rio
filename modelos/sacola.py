from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensoes import Modelo
from modelos.produto import Variacao


class Sacola(Modelo):
    """Sacola da cliente (usuario_id) ou do visitante (token guardado em cookie)."""

    __tablename__ = "sacolas"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), unique=True)
    token: Mapped[str | None] = mapped_column(String(64), unique=True)
    cupom_codigo: Mapped[str | None] = mapped_column(String(40))
    cep_frete: Mapped[str | None] = mapped_column(String(8))
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    itens: Mapped[list[ItemSacola]] = relationship(
        back_populates="sacola", cascade="all, delete-orphan", order_by="ItemSacola.id"
    )


class ItemSacola(Modelo):
    __tablename__ = "itens_sacola"
    __table_args__ = (
        UniqueConstraint("sacola_id", "variacao_id", name="uq_itens_sacola_sacola_variacao"),
        CheckConstraint("quantidade > 0", name="quantidade_positiva"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sacola_id: Mapped[int] = mapped_column(ForeignKey("sacolas.id", ondelete="CASCADE"), index=True)
    variacao_id: Mapped[int] = mapped_column(ForeignKey("variacoes.id", ondelete="CASCADE"))
    quantidade: Mapped[int] = mapped_column(Integer, default=1)

    sacola: Mapped[Sacola] = relationship(back_populates="itens")
    variacao: Mapped[Variacao] = relationship()
