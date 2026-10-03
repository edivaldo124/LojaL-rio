from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from extensoes import Modelo


class PagamentoSimulado(Modelo):
    """Cobranças do gateway simulado (desenvolvimento e testes, sem Mercado Pago)."""

    __tablename__ = "pagamentos_simulados"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    referencia: Mapped[str] = mapped_column(String(12), index=True)
    valor: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
