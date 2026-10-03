"""Fotos no disco (desenvolvimento) e no Supabase Storage (produção)."""

from __future__ import annotations

import io
from collections.abc import Iterator
from typing import Any

import pytest
import requests
from flask import Flask
from PIL import Image
from werkzeug.datastructures import FileStorage

from servicos import armazenamento

URL = "https://projeto.supabase.co"
PUBLICO = f"{URL}/storage/v1/object/public/loja/"


def _png() -> FileStorage:
    conteudo = io.BytesIO()
    Image.new("RGB", (3000, 1500), "#C97B84").save(conteudo, "PNG")
    conteudo.seek(0)
    return FileStorage(conteudo, filename="foto.png")


class _Resposta:
    def __init__(self, status: int = 200) -> None:
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture
def supabase(app: Flask) -> Iterator[None]:
    app.config.update(SUPABASE_URL=URL, SUPABASE_SECRET_KEY="sb_secret_teste", SUPABASE_BUCKET="loja")
    with app.test_request_context():
        yield
    app.config.update(SUPABASE_URL="", SUPABASE_SECRET_KEY="")


def test_disco_local_converte_para_webp_e_remove(app: Flask) -> None:
    with app.test_request_context():
        referencia = armazenamento.salvar_imagem(_png(), "produtos")
        assert referencia.startswith("uploads/produtos/") and referencia.endswith(".webp")
        arquivo = app.config["PASTA_UPLOADS"] / referencia.removeprefix("uploads/")
        with Image.open(arquivo) as gravada:
            assert gravada.format == "WEBP" and gravada.size == (1600, 800)
        assert armazenamento.url_publica(referencia) == f"/static/{referencia}"
        armazenamento.remover(referencia)
        assert not arquivo.exists()


def test_remover_ignora_caminho_fora_dos_uploads(app: Flask) -> None:
    with app.test_request_context():
        armazenamento.remover("uploads/../../config.py")  # não pode apagar fora da pasta
        armazenamento.remover("css/app.css")


@pytest.mark.usefixtures("supabase")
def test_envia_ao_storage_e_guarda_a_url_publica(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[dict[str, Any]] = []

    def post(url: str, **kwargs: Any) -> _Resposta:
        chamadas.append({"url": url, **kwargs})
        return _Resposta()

    monkeypatch.setattr(armazenamento.requests, "post", post)
    referencia = armazenamento.salvar_imagem(_png(), "produtos")

    assert referencia.startswith(PUBLICO + "produtos/") and referencia.endswith(".webp")
    assert armazenamento.url_publica(referencia) == referencia
    (chamada,) = chamadas
    caminho = referencia.removeprefix(PUBLICO)
    assert chamada["url"] == f"{URL}/storage/v1/object/loja/{caminho}"
    cabecalhos = chamada["headers"]
    assert cabecalhos["apikey"] == "sb_secret_teste"
    assert cabecalhos["Authorization"] == "Bearer sb_secret_teste"
    assert cabecalhos["Content-Type"] == "image/webp"
    assert cabecalhos["x-upsert"] == "true"
    assert chamada["data"][:4] == b"RIFF"  # WebP


@pytest.mark.usefixtures("supabase")
def test_falha_no_storage_vira_erro_amigavel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(armazenamento.requests, "post", lambda url, **kw: _Resposta(500))
    with pytest.raises(armazenamento.ErroArmazenamento):
        armazenamento.salvar_bytes(b"x", "produtos/a.webp")


@pytest.mark.usefixtures("supabase")
def test_remove_do_storage_so_o_que_e_do_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    apagados: list[Any] = []

    def delete(url: str, **kwargs: Any) -> _Resposta:
        apagados.append((url, kwargs["json"]))
        return _Resposta()

    monkeypatch.setattr(armazenamento.requests, "delete", delete)
    armazenamento.remover(PUBLICO + "produtos/abc.webp")
    armazenamento.remover("https://outro-site.com/foto.webp")
    assert apagados == [(f"{URL}/storage/v1/object/loja", {"prefixes": ["produtos/abc.webp"]})]
