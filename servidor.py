"""Fábrica da aplicação Flask. Em desenvolvimento: `python servidor.py`."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import click
from flask import Flask, Response, g, render_template, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from sqlalchemy import select

import config_loja
from config import Config
from extensoes import csrf, db, limiter, login_manager, migrate, oauth
from modelos import Categoria, Usuario
from servicos import sacola as servico_sacola
from servicos.armazenamento import url_publica
from servicos.cep import formatar_cep
from servicos.dinheiro import formatar_brl, valor_parcela
from servicos.pagamentos import FUSO_BRASILIA

CSP = "; ".join(
    [
        "default-src 'self'",
        "img-src 'self' data: https:",
        "style-src 'self' 'unsafe-inline'",
        "script-src 'self'",
        "connect-src 'self' https://viacep.com.br",
        "font-src 'self'",
        "form-action 'self' https://accounts.google.com",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "object-src 'none'",
    ]
)


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Defina SECRET_KEY no .env (obrigatório em produção).")

    logging.basicConfig(level=logging.INFO)
    if app.config["EM_PRODUCAO"] and not (app.config["SUPABASE_URL"] and app.config["SUPABASE_SECRET_KEY"]):
        app.logger.warning(
            "SUPABASE_URL/SUPABASE_SECRET_KEY ausentes: as fotos vão para o disco local, "
            "que serviços como o Render apagam a cada deploy."
        )

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    _configurar_login(app)
    _configurar_google(app)
    _registrar_blueprints(app)
    _registrar_templates(app)
    _registrar_respostas(app)
    _registrar_comandos(app)
    return app


def _configurar_login(app: Flask) -> None:
    login_manager.init_app(app)
    login_manager.login_view = "conta.entrar"
    login_manager.login_message = "Entre na sua conta para continuar."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def carregar_usuario(identificador: str) -> Usuario | None:
        usuario_id, _, versao = identificador.partition(":")
        if not usuario_id.isdigit():
            return None
        usuario = db.session.get(Usuario, int(usuario_id))
        if usuario is None or str(usuario.versao_sessao) != versao:
            return None
        return usuario


def _configurar_google(app: Flask) -> None:
    oauth.init_app(app)
    if app.config["GOOGLE_CLIENT_ID"] and app.config["GOOGLE_CLIENT_SECRET"]:
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )


def _registrar_blueprints(app: Flask) -> None:
    from blueprints.admin_bp import admin_bp
    from blueprints.checkout_bp import checkout_bp
    from blueprints.conta_bp import conta_bp
    from blueprints.loja_bp import loja_bp
    from blueprints.pagamentos_bp import pagamentos_bp
    from blueprints.sacola_bp import sacola_bp

    for blueprint in (loja_bp, sacola_bp, checkout_bp, conta_bp, pagamentos_bp, admin_bp):
        app.register_blueprint(blueprint)


def _formatar_data(valor: datetime | None, formato: str = "%d/%m/%Y %H:%M") -> str:
    if valor is None:
        return ""
    return valor.astimezone(FUSO_BRASILIA).strftime(formato)


def _registrar_templates(app: Flask) -> None:
    app.jinja_env.filters["brl"] = formatar_brl
    app.jinja_env.filters["cep"] = formatar_cep
    app.jinja_env.filters["data"] = _formatar_data
    app.jinja_env.filters["imagem"] = url_publica
    app.jinja_env.filters["parcela"] = valor_parcela

    def categorias_menu() -> list[Categoria]:
        if "categorias_menu" not in g:
            g.categorias_menu = db.session.scalars(
                select(Categoria).order_by(Categoria.ordem, Categoria.nome)
            ).all()
        return list(g.categorias_menu)

    def estatico(caminho: str) -> str:
        """URL de arquivo estático com a data de modificação (renova o cache do navegador)."""
        arquivo = Path(app.static_folder or "static") / caminho
        versao = int(arquivo.stat().st_mtime) if arquivo.exists() else 0
        return url_for("static", filename=caminho, v=versao)

    # Globais (e não context_processor) para valerem também dentro de macros importadas.
    app.jinja_env.globals.update(
        loja=config_loja,
        current_user=current_user,
        contador_sacola=servico_sacola.contar_itens,
        categorias_menu=categorias_menu,
        google_ativo="google" in oauth._registry,
        em_producao=app.config["EM_PRODUCAO"],
        estatico=estatico,
    )


def _registrar_respostas(app: Flask) -> None:
    @app.after_request
    def depois(resposta: Response) -> Response:
        servico_sacola.gravar_cookie(resposta)
        resposta.headers.setdefault("Content-Security-Policy", CSP)
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resposta.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if app.config["EM_PRODUCAO"]:
            resposta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return resposta

    def erro(codigo: int, titulo: str, texto: str) -> tuple[str, int]:
        return render_template("erro.html", codigo=codigo, titulo=titulo, texto=texto), codigo

    @app.errorhandler(403)
    def proibido(_: Exception) -> tuple[str, int]:
        return erro(403, "Acesso restrito", "Você não tem permissão para ver esta página.")

    @app.errorhandler(404)
    def nao_encontrado(_: Exception) -> tuple[str, int]:
        return erro(404, "Página não encontrada", "O endereço pode ter mudado ou a peça saiu da loja.")

    @app.errorhandler(429)
    def muitas_tentativas(_: Exception) -> tuple[str, int]:
        return erro(429, "Muitas tentativas", "Aguarde um minuto e tente de novo.")

    @app.errorhandler(CSRFError)
    def csrf_invalido(_: CSRFError) -> tuple[str, int]:
        return erro(400, "Formulário expirado", "Volte, recarregue a página e envie de novo.")

    @app.errorhandler(500)
    def erro_interno(_: Exception) -> tuple[str, int]:
        db.session.rollback()
        return erro(500, "Algo deu errado", "Tente de novo em instantes.")


def _registrar_comandos(app: Flask) -> None:
    @app.cli.command("seed")
    def seed() -> None:
        """Popula o banco com categorias, produtos, banner, cupom e o admin."""
        from seed import executar

        executar()

    pedidos_cli = click.Group("pedidos", help="Rotinas de pedidos.")

    @pedidos_cli.command("expirar")
    def expirar() -> None:
        """Cancela pedidos com Pix vencido e devolve o estoque (rodar no cron)."""
        from servicos.pedidos import expirar_vencidos

        quantidade = expirar_vencidos()
        db.session.commit()
        click.echo(f"{quantidade} pedido(s) expirado(s).")

    app.cli.add_command(pedidos_cli)


if __name__ == "__main__":
    create_app().run(debug=True)
