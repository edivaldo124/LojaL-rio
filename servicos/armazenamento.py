"""Fotos enviadas pelo admin: validadas pelo Pillow e gravadas como WebP (RNF02).

Para trocar por S3/Cloudinary, basta reimplementar salvar_imagem/remover/url_publica.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from flask import current_app, url_for
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.datastructures import FileStorage

LARGURA_MAXIMA = 1600


class ImagemInvalida(Exception):
    pass


def _pasta_uploads() -> Path:
    return Path(current_app.config["PASTA_UPLOADS"])


def salvar_imagem(arquivo: FileStorage, pasta: str) -> str:
    """Grava a imagem e devolve o caminho relativo a static/ (ex.: 'uploads/produtos/x.webp')."""
    try:
        imagem: Image.Image = Image.open(arquivo.stream)
        imagem.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as erro:
        raise ImagemInvalida(f"{arquivo.filename or 'Arquivo'} não é uma imagem válida.") from erro

    imagem = ImageOps.exif_transpose(imagem) or imagem
    tem_transparencia = imagem.mode in ("RGBA", "LA") or "transparency" in imagem.info
    imagem = imagem.convert("RGBA" if tem_transparencia else "RGB")
    imagem.thumbnail((LARGURA_MAXIMA, LARGURA_MAXIMA * 2))

    destino = _pasta_uploads() / pasta
    destino.mkdir(parents=True, exist_ok=True)
    nome = f"{uuid.uuid4().hex}.webp"
    imagem.save(destino / nome, "WEBP", quality=82, method=6)
    return f"uploads/{pasta}/{nome}"


def remover(caminho: str | None) -> None:
    if not caminho or not caminho.startswith("uploads/"):
        return
    arquivo = (_pasta_uploads() / caminho.removeprefix("uploads/")).resolve()
    if _pasta_uploads().resolve() in arquivo.parents:
        arquivo.unlink(missing_ok=True)


def url_publica(caminho: str | None) -> str:
    if not caminho:
        return ""
    if caminho.startswith(("http://", "https://")):
        return caminho
    return url_for("static", filename=caminho)
