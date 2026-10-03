"""Fotos: validadas pelo Pillow e gravadas como WebP (RNF02).

O destino depende da configuração:
- Supabase Storage (produção), com SUPABASE_URL e SUPABASE_SECRET_KEY: o banco guarda a URL pública.
- Disco local (desenvolvimento e testes), em static/uploads/: o banco guarda 'uploads/...'.
O disco do Render é apagado a cada deploy, por isso em produção as fotos vão para o Storage.
"""

from __future__ import annotations

import io
import logging
import uuid
from pathlib import Path

import requests
from flask import current_app, url_for
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.datastructures import FileStorage

log = logging.getLogger(__name__)

LARGURA_MAXIMA = 1600
CACHE_SEGUNDOS = 60 * 60 * 24 * 365  # nomes únicos: o navegador pode guardar por 1 ano


class ImagemInvalida(Exception):
    pass


class ErroArmazenamento(Exception):
    pass


def _pasta_uploads() -> Path:
    return Path(current_app.config["PASTA_UPLOADS"])


def _supabase() -> tuple[str, str, str] | None:
    """(url do projeto, chave secreta, bucket) ou None quando o Storage não está configurado."""
    config = current_app.config
    if config["SUPABASE_URL"] and config["SUPABASE_SECRET_KEY"]:
        return config["SUPABASE_URL"], config["SUPABASE_SECRET_KEY"], config["SUPABASE_BUCKET"]
    return None


def _prefixo_publico(url: str, bucket: str) -> str:
    return f"{url}/storage/v1/object/public/{bucket}/"


def _cabecalhos(chave: str) -> dict[str, str]:
    return {"apikey": chave, "Authorization": f"Bearer {chave}"}


def salvar_bytes(conteudo: bytes, caminho: str, tipo: str = "image/webp") -> str:
    """Grava em `caminho` (ex.: 'produtos/abc.webp') e devolve a referência para guardar no banco."""
    supabase = _supabase()
    if supabase is None:
        destino = _pasta_uploads() / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)
        return f"uploads/{caminho}"

    url, chave, bucket = supabase
    try:
        resposta = requests.post(
            f"{url}/storage/v1/object/{bucket}/{caminho}",
            data=conteudo,
            headers={
                **_cabecalhos(chave),
                "Content-Type": tipo,
                "Cache-Control": f"max-age={CACHE_SEGUNDOS}",
                "x-upsert": "true",
            },
            timeout=30,
        )
        resposta.raise_for_status()
    except requests.RequestException as erro:
        log.exception("Falha ao enviar %s ao Supabase Storage", caminho)
        raise ErroArmazenamento("Não foi possível enviar a imagem. Tente de novo.") from erro
    return _prefixo_publico(url, bucket) + caminho


def preparar_imagem(arquivo: FileStorage) -> bytes:
    """Valida o arquivo como imagem, corrige a rotação, limita o tamanho e converte para WebP."""
    try:
        imagem: Image.Image = Image.open(arquivo.stream)
        imagem.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as erro:
        raise ImagemInvalida(f"{arquivo.filename or 'Arquivo'} não é uma imagem válida.") from erro

    imagem = ImageOps.exif_transpose(imagem) or imagem
    tem_transparencia = imagem.mode in ("RGBA", "LA") or "transparency" in imagem.info
    imagem = imagem.convert("RGBA" if tem_transparencia else "RGB")
    imagem.thumbnail((LARGURA_MAXIMA, LARGURA_MAXIMA * 2))
    saida = io.BytesIO()
    imagem.save(saida, "WEBP", quality=82, method=6)
    return saida.getvalue()


def salvar_imagem(arquivo: FileStorage, pasta: str) -> str:
    return salvar_bytes(preparar_imagem(arquivo), f"{pasta}/{uuid.uuid4().hex}.webp")


def remover(referencia: str | None) -> None:
    """Apaga o arquivo. Falha no Storage só vai para o log: não impede excluir o registro."""
    if not referencia:
        return
    supabase = _supabase()
    if supabase is not None:
        url, chave, bucket = supabase
        prefixo = _prefixo_publico(url, bucket)
        if referencia.startswith(prefixo):
            try:
                requests.delete(
                    f"{url}/storage/v1/object/{bucket}",
                    json={"prefixes": [referencia.removeprefix(prefixo)]},
                    headers=_cabecalhos(chave),
                    timeout=30,
                ).raise_for_status()
            except requests.RequestException:
                log.warning("Não foi possível apagar %s do Storage", referencia, exc_info=True)
            return

    if referencia.startswith("uploads/"):
        arquivo = (_pasta_uploads() / referencia.removeprefix("uploads/")).resolve()
        if _pasta_uploads().resolve() in arquivo.parents:
            arquivo.unlink(missing_ok=True)


def url_publica(referencia: str | None) -> str:
    if not referencia:
        return ""
    if referencia.startswith(("http://", "https://")):
        return referencia
    return url_for("static", filename=referencia)
