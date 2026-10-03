from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from flask_login import UserMixin
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensoes import Modelo

if TYPE_CHECKING:
    from modelos.endereco import Endereco

PAPEL_CLIENTE = "CLIENTE"
PAPEL_ADMIN = "ADMIN"


class Usuario(UserMixin, Modelo):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    senha_hash: Mapped[str | None] = mapped_column(String(255))
    telefone: Mapped[str | None] = mapped_column(String(20))
    papel: Mapped[str] = mapped_column(String(10), default=PAPEL_CLIENTE)
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)
    # Incrementada ao trocar a senha: derruba as sessões abertas em outros aparelhos.
    versao_sessao: Mapped[int] = mapped_column(Integer, default=1)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    enderecos: Mapped[list[Endereco]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan", order_by="Endereco.id"
    )

    @property
    def is_admin(self) -> bool:
        return self.papel == PAPEL_ADMIN

    @property
    def primeiro_nome(self) -> str:
        return self.nome.split(" ")[0] if self.nome else ""

    def get_id(self) -> str:
        return f"{self.id}:{self.versao_sessao}"
