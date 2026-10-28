"""Mantém a loja acordada no plano gratuito do Render, que hiberna após ~15 min sem visitas.

Uma thread daemon faz GET no próprio /health a cada KEEP_ALIVE_INTERVALO segundos. Reduz a
hibernação, sem garantia: não acorda um processo já suspenso nem impede reinícios da plataforma.

Desligado por padrão (KEEP_ALIVE=true liga). O destino nunca vem de uma requisição: é o endereço
que o próprio Render informa (RENDER_EXTERNAL_URL) ou o URL_BASE, e só http(s). Assim isto não vira
um jeito de fazer a loja chamar endereços de terceiros.
"""

from __future__ import annotations

import logging
import os
import threading
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)

CAMINHO_PING = "/health"
INTERVALO_PADRAO = 600
# O piso evita que um erro de digitação vire um laço de requisições; o teto fica abaixo dos
# ~15 min que o Render espera para hibernar.
INTERVALO_MINIMO = 60
INTERVALO_MAXIMO = 840
TIMEOUT = 15
INTERVALO_RETENTATIVA = 60

_parar = threading.Event()
_trava = threading.Lock()
_thread: threading.Thread | None = None


def intervalo(bruto: str) -> int:
    """KEEP_ALIVE_INTERVALO em segundos, dentro da faixa permitida."""
    if not bruto.strip():
        return INTERVALO_PADRAO
    try:
        segundos = int(bruto)
    except ValueError:
        log.warning("KEEP_ALIVE_INTERVALO inválido (%r): usando %s s.", bruto, INTERVALO_PADRAO)
        return INTERVALO_PADRAO
    return max(INTERVALO_MINIMO, min(segundos, INTERVALO_MAXIMO))


def url_do_ping(url_base: str) -> str | None:
    """RENDER_EXTERNAL_URL (definido pelo Render) ou URL_BASE, só se for http(s) com host."""
    base = (os.environ.get("RENDER_EXTERNAL_URL") or url_base).strip().rstrip("/")
    partes = urlsplit(base)
    if partes.scheme not in ("http", "https") or not partes.netloc:
        return None
    return base + CAMINHO_PING


def pingar(url: str) -> bool:
    try:
        resposta = requests.get(
            url,
            timeout=TIMEOUT,
            # Sem seguir redirecionamento: um 3xx inesperado não leva a requisição para outro host.
            allow_redirects=False,
            headers={"User-Agent": "lojalirio-keepalive/1.0"},
        )
    except requests.RequestException as erro:
        log.warning("Keep-alive falhou: %s", erro)
        return False
    if resposta.status_code != 200:
        log.warning("Keep-alive recebeu HTTP %s de %s.", resposta.status_code, url)
        return False
    return True


def _laco(url: str, segundos: int) -> None:
    # Espera antes do primeiro ping: o processo acabou de subir, então já está acordado.
    espera = segundos
    while not _parar.wait(espera):
        # Uma falha passageira não deve deixar dois intervalos inteiros sem ping.
        espera = segundos if pingar(url) else INTERVALO_RETENTATIVA


def iniciar(ligado: bool, url_base: str, intervalo_bruto: str = "") -> bool:
    """Sobe a thread se KEEP_ALIVE estiver ligado. Chamar de novo no mesmo processo não duplica.

    Cada worker do gunicorn tem a sua thread: com 2 workers, são 2 pings por intervalo.
    """
    global _thread
    if not ligado:
        return False
    url = url_do_ping(url_base)
    if url is None:
        log.warning("Keep-alive desligado: defina URL_BASE com http(s)://.")
        return False
    segundos = intervalo(intervalo_bruto)
    with _trava:
        if _thread is not None and _thread.is_alive():
            return False
        _thread = threading.Thread(target=_laco, args=(url, segundos), name="keep-alive", daemon=True)
        _thread.start()
    log.info("Keep-alive ativo: %s a cada %s s.", url, segundos)
    return True


def parar() -> None:
    """Encerra o laço (usado nos testes; em produção a thread é daemon)."""
    global _thread
    _parar.set()
    with _trava:
        thread, _thread = _thread, None
    if thread is not None:
        thread.join(timeout=5)
    _parar.clear()
