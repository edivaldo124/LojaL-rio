"""Conta administradora: criada ou corrigida a partir de ADMIN_EMAIL e ADMIN_SENHA.

Roda no `flask admin` (a cada deploy) e no `flask seed`. Sem shell no servidor, é assim que a dona troca a
senha do painel: muda ADMIN_SENHA nas variáveis do Render e faz um novo deploy.
"""

from __future__ import annotations

import secrets

from sqlalchemy import func, select

from extensoes import db
from modelos import PAPEL_ADMIN, Usuario
from servicos import senhas

# Mais longa que a senha das clientes: quem entra no painel mexe em preços, estoque e pedidos.
TAMANHO_MINIMO_ADMIN = 12


class ErroAdmin(Exception):
    """Configuração do admin que não pode ser aplicada (a mensagem explica o que fazer)."""


def garantir_admin(email: str, senha: str, em_producao: bool) -> str:
    """Deixa a conta `email` como admin com a `senha`, se informada. Devolve o que foi feito.

    - Sem a conta: cria. Sem senha, gera uma (só fora de produção, para não cair no log do servidor).
    - Conta existente com senha diferente de ADMIN_SENHA: troca a senha e derruba as sessões abertas.
    - Conta de cliente com esse e-mail: só vira admin com ADMIN_SENHA definida. O cadastro não confirma o
      e-mail, então a senha e o login Google que estavam nela são descartados.
    """
    email = email.strip().lower()
    if not email:
        raise ErroAdmin("Defina ADMIN_EMAIL.")
    if senha and len(senha) < TAMANHO_MINIMO_ADMIN:
        raise ErroAdmin(f"ADMIN_SENHA precisa ter pelo menos {TAMANHO_MINIMO_ADMIN} caracteres.")

    usuario = db.session.scalar(select(Usuario).where(func.lower(Usuario.email) == email))
    if usuario is None:
        if not senha:
            if em_producao:
                raise ErroAdmin("Defina ADMIN_SENHA para criar o admin em produção.")
            senha = secrets.token_urlsafe(12)
            origem = f"gerada: {senha}"
        else:
            origem = "definida em ADMIN_SENHA"
        senha_hash = senhas.gerar_hash(senha)
        db.session.add(Usuario(nome="Administradora", email=email, senha_hash=senha_hash, papel=PAPEL_ADMIN))
        db.session.commit()
        return f"Admin criado: {email} — senha {origem}"

    if not usuario.is_admin:
        if not senha:
            raise ErroAdmin(f"{email} é uma conta de cliente. Defina ADMIN_SENHA para torná-la admin.")
        usuario.papel = PAPEL_ADMIN
        usuario.google_sub = None
        usuario.senha_hash = senhas.gerar_hash(senha)
        usuario.versao_sessao += 1
        db.session.commit()
        return f"{email} agora é admin, com a senha de ADMIN_SENHA."

    if senha and not senhas.conferir(usuario.senha_hash, senha):
        usuario.senha_hash = senhas.gerar_hash(senha)
        usuario.versao_sessao += 1
        db.session.commit()
        return f"Senha do admin {email} atualizada pela ADMIN_SENHA."
    return f"Admin {email} em dia."
