from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable


def slugify(texto: str) -> str:
    """'Vestido Midi Floral' -> 'vestido-midi-floral'."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower()
    return slug or "item"


def slug_unico(texto: str, existe: Callable[[str], bool]) -> str:
    base = slugify(texto)
    candidato, n = base, 2
    while existe(candidato):
        candidato = f"{base}-{n}"
        n += 1
    return candidato
