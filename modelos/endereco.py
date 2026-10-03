from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensoes import Modelo
from servicos.cep import formatar_cep

if TYPE_CHECKING:
    from modelos.usuario import Usuario


class Endereco(Modelo):
    __tablename__ = "enderecos"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    apelido: Mapped[str] = mapped_column(String(40))
    cep: Mapped[str] = mapped_column(String(8))
    rua: Mapped[str] = mapped_column(String(160))
    numero: Mapped[str] = mapped_column(String(20))
    complemento: Mapped[str | None] = mapped_column(String(80))
    bairro: Mapped[str] = mapped_column(String(80))
    cidade: Mapped[str] = mapped_column(String(80))
    uf: Mapped[str] = mapped_column(String(2))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usuario: Mapped[Usuario] = relationship(back_populates="enderecos")

    @property
    def linha_rua(self) -> str:
        complemento = f", {self.complemento}" if self.complemento else ""
        return f"{self.rua}, {self.numero}{complemento} – {self.bairro}"

    @property
    def linha_cidade(self) -> str:
        return f"{self.cidade} – {self.uf} · {formatar_cep(self.cep)}"

    def como_snapshot(self) -> dict[str, Any]:
        """Cópia gravada no pedido: o endereço pode mudar ou sumir depois."""
        return {
            "apelido": self.apelido,
            "cep": self.cep,
            "rua": self.rua,
            "numero": self.numero,
            "complemento": self.complemento,
            "bairro": self.bairro,
            "cidade": self.cidade,
            "uf": self.uf,
            "linha_rua": self.linha_rua,
            "linha_cidade": self.linha_cidade,
        }
