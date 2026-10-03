"""Configuração da aplicação, lida do ambiente (arquivo .env na raiz)."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from typing import Any, ClassVar

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _texto(nome: str, padrao: str = "") -> str:
    return os.environ.get(nome, padrao).strip()


def _inteiro(nome: str, padrao: int) -> int:
    valor = _texto(nome)
    return int(valor) if valor else padrao


AMBIENTE = _texto("AMBIENTE", "desenvolvimento")
EM_PRODUCAO = AMBIENTE == "producao"


class Config:
    AMBIENTE = AMBIENTE
    EM_PRODUCAO = EM_PRODUCAO
    TESTING = False

    SECRET_KEY = _texto("SECRET_KEY") or ("" if EM_PRODUCAO else "dev-inseguro-troque-no-env")

    SQLALCHEMY_DATABASE_URI = _texto("DATABASE_URL", "postgresql+psycopg2:///lojalirio")
    SQLALCHEMY_ENGINE_OPTIONS: ClassVar[dict[str, Any]] = {"pool_pre_ping": True}

    # Endereço público da loja (usado no webhook do Mercado Pago, sitemap e Open Graph).
    URL_BASE = _texto("URL_BASE", "http://127.0.0.1:5000").rstrip("/")

    # Sessão e cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = EM_PRODUCAO
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = EM_PRODUCAO
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)
    PREFERRED_URL_SCHEME = "https" if EM_PRODUCAO else "http"

    WTF_CSRF_TIME_LIMIT = None  # o token vale enquanto a sessão existir

    # Uploads (fotos do admin)
    MAX_CONTENT_LENGTH = 30 * 1024 * 1024
    PASTA_UPLOADS = BASE_DIR / "static" / "uploads"

    # Limite de tentativas (login/cadastro)
    RATELIMIT_STORAGE_URI = _texto("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    # Mercado Pago (sem token, a loja usa o gateway simulado fora de produção)
    MP_ACCESS_TOKEN = _texto("MP_ACCESS_TOKEN")
    MP_WEBHOOK_SECRET = _texto("MP_WEBHOOK_SECRET")
    PIX_EXPIRACAO_MINUTOS = _inteiro("PIX_EXPIRACAO_MINUTOS", 30)

    # Supabase Storage para as fotos. Sem URL e chave secreta, as fotos vão para static/uploads.
    SUPABASE_URL = _texto("SUPABASE_URL").rstrip("/")
    SUPABASE_SECRET_KEY = _texto("SUPABASE_SECRET_KEY")
    SUPABASE_BUCKET = _texto("SUPABASE_BUCKET", "loja")

    # Login com Google (o botão só aparece com as duas chaves)
    GOOGLE_CLIENT_ID = _texto("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = _texto("GOOGLE_CLIENT_SECRET")

    # E-mail (sem SMTP_HOST, as mensagens vão para o log)
    SMTP_HOST = _texto("SMTP_HOST")
    SMTP_PORTA = _inteiro("SMTP_PORTA", 587)
    SMTP_USUARIO = _texto("SMTP_USUARIO")
    SMTP_SENHA = _texto("SMTP_SENHA")
    EMAIL_REMETENTE = _texto("EMAIL_REMETENTE", "nao-responda@exemplo.com")

    # Usuário administrador criado pelo seed
    ADMIN_EMAIL = _texto("ADMIN_EMAIL", "admin@exemplo.com")
    ADMIN_SENHA = _texto("ADMIN_SENHA")


class ConfigTeste(Config):
    TESTING = True
    SECRET_KEY = "chave-de-teste"  # noqa: S105 — só nos testes
    SQLALCHEMY_DATABASE_URI = _texto("DATABASE_URL_TESTE", "postgresql+psycopg2:///lojalirio_test")
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    MP_ACCESS_TOKEN = ""
    MP_WEBHOOK_SECRET = ""
    GOOGLE_CLIENT_ID = ""
    GOOGLE_CLIENT_SECRET = ""
    SUPABASE_URL = ""
    SUPABASE_SECRET_KEY = ""
    SMTP_HOST = ""
    URL_BASE = "http://localhost"
