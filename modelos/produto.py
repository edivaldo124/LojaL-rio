from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

import config_loja
from extensoes import Modelo
from modelos.categoria import Categoria


class Produto(Modelo):
    __tablename__ = "produtos"
    __table_args__ = (
        CheckConstraint("preco > 0", name="preco_positivo"),
        CheckConstraint("preco_promocional IS NULL OR preco_promocional > 0", name="promocional_positivo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    descricao: Mapped[str] = mapped_column(Text, default="")
    composicao: Mapped[str] = mapped_column(String(200), default="")
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"), index=True)
    preco: Mapped[int] = mapped_column(Integer)  # centavos
    preco_promocional: Mapped[int | None] = mapped_column(Integer)  # centavos
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    categoria: Mapped[Categoria] = relationship()
    imagens: Mapped[list[ImagemProduto]] = relationship(
        back_populates="produto",
        cascade="all, delete-orphan",
        order_by="ImagemProduto.ordem",
    )
    variacoes: Mapped[list[Variacao]] = relationship(
        back_populates="produto", cascade="all, delete-orphan", order_by="Variacao.id"
    )

    @property
    def em_promocao(self) -> bool:
        return self.preco_promocional is not None and self.preco_promocional < self.preco

    @property
    def preco_atual(self) -> int:
        if self.em_promocao and self.preco_promocional is not None:
            return self.preco_promocional
        return self.preco

    @property
    def imagem_principal(self) -> ImagemProduto | None:
        return self.imagens[0] if self.imagens else None

    @property
    def estoque_total(self) -> int:
        return sum(v.estoque for v in self.variacoes)

    def cores(self) -> list[dict[str, str]]:
        """Cores na ordem em que foram cadastradas, sem repetir."""
        vistas: dict[str, dict[str, str]] = {}
        for variacao in self.variacoes:
            vistas.setdefault(variacao.cor, {"nome": variacao.cor, "hex": variacao.cor_hex})
        return list(vistas.values())

    def mapa_variacoes(self) -> list[dict[str, Any]]:
        """Dados que o JavaScript da página do produto usa para habilitar os tamanhos."""
        ordem = {t: i for i, t in enumerate(config_loja.TAMANHOS)}
        variacoes = sorted(self.variacoes, key=lambda v: ordem.get(v.tamanho, 99))
        return [{"id": v.id, "cor": v.cor, "tamanho": v.tamanho, "estoque": v.estoque} for v in variacoes]


class ImagemProduto(Modelo):
    __tablename__ = "imagens_produto"

    id: Mapped[int] = mapped_column(primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(255))
    alt: Mapped[str | None] = mapped_column(String(200))
    ordem: Mapped[int] = mapped_column(Integer, default=0)

    produto: Mapped[Produto] = relationship(back_populates="imagens")

    @property
    def texto_alternativo(self) -> str:
        return self.alt or self.produto.nome


class Variacao(Modelo):
    __tablename__ = "variacoes"
    __table_args__ = (
        UniqueConstraint("produto_id", "cor", "tamanho", name="uq_variacoes_produto_cor_tamanho"),
        CheckConstraint("estoque >= 0", name="estoque_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id", ondelete="CASCADE"), index=True)
    cor: Mapped[str] = mapped_column(String(40))
    cor_hex: Mapped[str] = mapped_column(String(7))
    tamanho: Mapped[str] = mapped_column(String(4))
    sku: Mapped[str] = mapped_column(String(60), unique=True)
    estoque: Mapped[int] = mapped_column(Integer, default=0)

    produto: Mapped[Produto] = relationship(back_populates="variacoes")

    @property
    def estoque_baixo(self) -> bool:
        return self.estoque <= config_loja.ESTOQUE_BAIXO
