from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from extensoes import Modelo


class Banner(Modelo):
    __tablename__ = "banners"

    id: Mapped[int] = mapped_column(primary_key=True)
    imagem: Mapped[str | None] = mapped_column(String(255))
    titulo: Mapped[str] = mapped_column(String(80))
    texto_botao: Mapped[str] = mapped_column(String(30), default="Ver coleção")
    link: Mapped[str] = mapped_column(String(255), default="/")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
