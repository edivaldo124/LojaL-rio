from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from extensoes import Modelo

TIPO_PERCENTUAL = "PERCENTUAL"
TIPO_VALOR = "VALOR"


class Cupom(Modelo):
    __tablename__ = "cupons"
    __table_args__ = (
        CheckConstraint("valor > 0", name="valor_positivo"),
        CheckConstraint("tipo <> 'PERCENTUAL' OR valor <= 100", name="percentual_ate_100"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    tipo: Mapped[str] = mapped_column(String(12))
    # PERCENTUAL: 10 = 10%. VALOR: centavos.
    valor: Mapped[int] = mapped_column(Integer)
    minimo: Mapped[int] = mapped_column(Integer, default=0)  # subtotal mínimo, em centavos
    validade: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    limite_uso: Mapped[int | None] = mapped_column(Integer)
    usos: Mapped[int] = mapped_column(Integer, default=0)
    acumula_pix: Mapped[bool] = mapped_column(Boolean, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
