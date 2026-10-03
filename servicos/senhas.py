"""Hash de senha com argon2id (RNF04)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

TAMANHO_MINIMO = 8


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


def conferir(senha_hash: str | None, senha: str) -> bool:
    if not senha_hash:
        return False
    try:
        return _hasher.verify(senha_hash, senha)
    except (VerificationError, InvalidHashError):
        return False


def precisa_atualizar(senha_hash: str) -> bool:
    return _hasher.check_needs_rehash(senha_hash)
