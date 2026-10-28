"""Seed: fotos reais do Unsplash, com a ilustração quando o download falha."""

from __future__ import annotations

import io
from typing import Any

import pytest
import requests
from PIL import Image
from sqlalchemy import select

import seed
from extensoes import db
from modelos import Banner, Categoria, Produto


class _Foto:
    """Resposta do Unsplash: um JPEG paisagem, para conferir o recorte vertical."""

    def __init__(self) -> None:
        conteudo = io.BytesIO()
        Image.new("RGB", (3000, 2000), "#7D8F6E").save(conteudo, "JPEG")
        self.content = conteudo.getvalue()

    def raise_for_status(self) -> None:
        return None


def _baixa(*_: Any, **__: Any) -> _Foto:
    return _Foto()


def _sem_rede(*_: Any, **__: Any) -> None:
    raise requests.ConnectionError("sem rede")


def _produto(slug: str) -> Produto:
    produto = db.session.scalar(select(Produto).where(Produto.slug == slug))
    assert produto is not None
    return produto


class TestFotosDoSeed:
    def test_recorta_a_foto_no_tamanho_pedido(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(seed.requests, "get", _baixa)
        foto = seed.foto_unsplash("abc", (1200, 1600))
        assert foto is not None and foto.size == (1200, 1600)

    def test_seed_usa_as_fotos_reais(self, banco: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(seed.requests, "get", _baixa)
        seed.executar()
        produto = _produto("vestido-midi-floral")
        assert len(produto.imagens) == len(seed.FOTOS_PRODUTOS["vestido-midi-floral"])
        assert all("seed/foto-" in imagem.url for imagem in produto.imagens)
        assert all("seed/foto-" in (c.imagem or "") for c in db.session.scalars(select(Categoria)))
        assert "seed/foto-" in (db.session.scalars(select(Banner)).one().imagem or "")

    def test_sem_rede_usa_a_ilustracao(self, banco: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(seed.requests, "get", _sem_rede)
        seed.executar()
        produto = _produto("blusa-de-linho")
        assert len(produto.imagens) == 3
        assert all(seed._e_ilustracao(imagem.url) for imagem in produto.imagens)

    def test_troca_so_as_ilustracoes(self, banco: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(seed.requests, "get", _sem_rede)
        seed.executar()
        foto_da_loja = _produto("blusa-canelada")
        foto_da_loja.imagens[0].url = "uploads/produtos/foto-enviada-no-painel.webp"
        db.session.commit()

        monkeypatch.setattr(seed.requests, "get", _baixa)
        seed.trocar_ilustracoes()
        assert all("seed/foto-" in imagem.url for imagem in _produto("camisa-de-cetim").imagens)
        assert foto_da_loja.imagens[0].url == "uploads/produtos/foto-enviada-no-painel.webp"
        assert all("seed/foto-" in (c.imagem or "") for c in db.session.scalars(select(Categoria)))
