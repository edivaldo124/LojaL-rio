"""Conta da cliente: login, cadastro, Google, senha, pedidos, endereços e exclusão (RF06)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import delete, func, select
from werkzeug.wrappers import Response as RespostaWerkzeug

from extensoes import db, limiter, oauth
from formularios.checkout import FormEndereco
from formularios.conta import (
    FormCadastro,
    FormEsqueciSenha,
    FormExcluirConta,
    FormLogin,
    FormNovaSenha,
)
from formularios.sacola import FormVazio
from modelos import Endereco, Favorito, Pedido, Sacola, StatusPedido, Usuario
from servicos import email, senhas
from servicos import pedidos as servico_pedidos
from servicos import sacola as servico_sacola
from servicos.pagamentos import pix_simulado_ativo

conta_bp = Blueprint("conta", __name__, url_prefix="/conta")

VALIDADE_LINK_SENHA = 60 * 60  # 1 hora
STATUS_EM_ANDAMENTO = (
    StatusPedido.AGUARDANDO_PAGAMENTO,
    StatusPedido.PAGO,
    StatusPedido.EM_SEPARACAO,
    StatusPedido.ENVIADO,
    StatusPedido.PRONTO_RETIRADA,
)


def destino_seguro(destino: str, padrao: str) -> str:
    """Aceita só caminhos internos. Recusa '//host', '/\\host' (o navegador lê como '//host'),
    esquemas e caracteres de controle."""
    if not destino or "\\" in destino or any(ord(c) < 32 or ord(c) == 127 for c in destino):
        return padrao
    partes = urlsplit(destino)
    if destino.startswith("/") and not destino.startswith("//") and not partes.scheme and not partes.netloc:
        return destino
    return padrao


def _destino_seguro(padrao: str) -> str:
    return destino_seguro(request.args.get("next") or request.form.get("next") or "", padrao)


def _entrar(usuario: Usuario, lembrar: bool = True) -> None:
    servico_sacola.unificar_no_login(usuario)
    login_user(usuario, remember=lembrar)
    session.permanent = True
    db.session.commit()


def _buscar_por_email(endereco: str) -> Usuario | None:
    return db.session.scalar(select(Usuario).where(func.lower(Usuario.email) == endereco.lower()))


# ---------------------------------------------------------------- entrar / cadastrar


@conta_bp.route("/entrar", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def entrar() -> str | RespostaWerkzeug:
    if current_user.is_authenticated:
        return redirect(_destino_seguro(url_for("conta.painel")))
    form = FormLogin()
    if form.validate_on_submit():
        usuario = _buscar_por_email(form.email.data or "")
        if usuario is not None and senhas.conferir(usuario.senha_hash, form.senha.data or ""):
            if usuario.senha_hash and senhas.precisa_atualizar(usuario.senha_hash):
                usuario.senha_hash = senhas.gerar_hash(form.senha.data or "")
            _entrar(usuario, bool(form.lembrar.data))
            padrao = url_for("admin.painel") if usuario.is_admin else url_for("conta.painel")
            return redirect(_destino_seguro(padrao))
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("conta/entrar.html", form=form, proximo=_destino_seguro(""))


@conta_bp.route("/cadastrar", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def cadastrar() -> str | RespostaWerkzeug:
    if current_user.is_authenticated:
        return redirect(url_for("conta.painel"))
    form = FormCadastro()
    if form.validate_on_submit():
        if _buscar_por_email(form.email.data or "") is not None:
            form.email.errors.append("Já existe uma conta com este e-mail. Que tal entrar?")
        else:
            usuario = Usuario(
                nome=form.nome.data or "",
                email=form.email.data or "",
                telefone=form.telefone.data or None,
                senha_hash=senhas.gerar_hash(form.senha.data or ""),
            )
            db.session.add(usuario)
            db.session.flush()
            _entrar(usuario)
            flash(f"Boas-vindas, {usuario.primeiro_nome}!", "sucesso")
            return redirect(_destino_seguro(url_for("conta.painel")))
    return render_template("conta/cadastrar.html", form=form, proximo=_destino_seguro(""))


@conta_bp.post("/sair")
def sair() -> RespostaWerkzeug:
    if FormVazio().validate_on_submit():
        logout_user()
        session.clear()
    return redirect(url_for("loja.inicio"))


# ---------------------------------------------------------------- Google


@conta_bp.get("/google")
def google() -> RespostaWerkzeug:
    cliente = oauth.create_client("google")
    if cliente is None:
        abort(404)
    session["google_next"] = _destino_seguro("")
    return cliente.authorize_redirect(url_for("conta.google_retorno", _external=True))


@conta_bp.get("/google/retorno")
def google_retorno() -> RespostaWerkzeug:
    cliente = oauth.create_client("google")
    if cliente is None:
        abort(404)
    try:
        token: dict[str, Any] = cliente.authorize_access_token()
    except Exception:
        current_app.logger.exception("Falha no retorno do Google")
        flash("Não foi possível entrar com o Google. Tente de novo.", "erro")
        return redirect(url_for("conta.entrar"))

    dados = token.get("userinfo") or {}
    if not dados.get("sub") or not dados.get("email") or dados.get("email_verified") is not True:
        flash("Sua conta Google precisa ter um e-mail verificado.", "erro")
        return redirect(url_for("conta.entrar"))

    usuario, senha_invalidada = usuario_do_google(dados)
    _entrar(usuario)
    if senha_invalidada:
        flash(
            "Sua conta foi ligada ao Google. Por segurança, a senha anterior deixou de valer; "
            "se quiser entrar também com senha, use “Esqueci minha senha”.",
            "info",
        )
    destino = destino_seguro(session.pop("google_next", ""), url_for("conta.painel"))
    return redirect(destino)


def usuario_do_google(dados: dict[str, Any]) -> tuple[Usuario, bool]:
    """Acha ou cria a conta do login com Google. Devolve (usuário, senha_invalidada).

    O cadastro por e-mail e senha não confirma o e-mail. Então, ao ligar o Google a uma conta que
    já existia com o mesmo e-mail, a senha antiga é apagada e as sessões abertas caem: quem
    cadastrou o e-mail de outra pessoa antes dela não mantém o acesso.
    """
    usuario = db.session.scalar(select(Usuario).where(Usuario.google_sub == dados["sub"]))
    if usuario is not None:
        return usuario, False

    senha_invalidada = False
    usuario = _buscar_por_email(dados["email"])
    if usuario is None:
        nome = dados.get("name") or dados["email"].split("@")[0]
        usuario = Usuario(nome=nome, email=dados["email"].lower())
        db.session.add(usuario)
    elif usuario.senha_hash:
        usuario.senha_hash = None
        usuario.versao_sessao += 1
        senha_invalidada = True
    usuario.google_sub = dados["sub"]
    db.session.flush()
    return usuario, senha_invalidada


# ---------------------------------------------------------------- senha


def _serializador() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="redefinir-senha")


@conta_bp.route("/esqueci-senha", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def esqueci_senha() -> str | RespostaWerkzeug:
    form = FormEsqueciSenha()
    if form.validate_on_submit():
        usuario = _buscar_por_email(form.email.data or "")
        if usuario is not None:
            token = _serializador().dumps({"id": usuario.id, "v": usuario.versao_sessao})
            link = url_for("conta.redefinir_senha", token=token, _external=True)
            email.enviar(
                usuario.email,
                "Redefinir sua senha",
                f"Olá, {usuario.primeiro_nome}!\n\nPara criar uma nova senha, abra o link abaixo "
                f"(vale por 1 hora):\n\n{link}\n\nSe não foi você, ignore este e-mail.",
            )
        # Mesma resposta exista ou não a conta (não revela e-mails cadastrados).
        flash("Se o e-mail estiver cadastrado, você vai receber um link para criar uma nova senha.", "info")
        return redirect(url_for("conta.entrar"))
    return render_template("conta/esqueci_senha.html", form=form)


@conta_bp.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def redefinir_senha(token: str) -> str | RespostaWerkzeug:
    try:
        dados = _serializador().loads(token, max_age=VALIDADE_LINK_SENHA)
    except BadSignature:
        dados = None
    usuario = db.session.get(Usuario, dados["id"]) if dados else None
    if usuario is None or dados is None or usuario.versao_sessao != dados.get("v"):
        flash("Este link expirou ou já foi usado. Peça um novo.", "erro")
        return redirect(url_for("conta.esqueci_senha"))

    form = FormNovaSenha()
    if form.validate_on_submit():
        usuario.senha_hash = senhas.gerar_hash(form.senha.data or "")
        usuario.versao_sessao += 1  # derruba sessões antigas e invalida o link
        db.session.commit()
        flash("Senha alterada. Entre com a nova senha.", "sucesso")
        return redirect(url_for("conta.entrar"))
    return render_template("conta/redefinir_senha.html", form=form)


# ---------------------------------------------------------------- área da cliente


@conta_bp.get("")
def painel() -> str | RespostaWerkzeug:
    if not current_user.is_authenticated:
        return redirect(url_for("conta.entrar"))
    ultimo = db.session.scalar(
        select(Pedido).where(Pedido.usuario_id == current_user.id).order_by(Pedido.id.desc()).limit(1)
    )
    return render_template("conta/painel.html", ultimo=ultimo, form_vazio=FormVazio())


@conta_bp.get("/pedidos")
@login_required
def pedidos() -> str:
    lista = db.session.scalars(
        select(Pedido).where(Pedido.usuario_id == current_user.id).order_by(Pedido.id.desc())
    ).all()
    return render_template("conta/pedidos.html", pedidos=lista)


def _pedido_da_cliente(numero: str) -> Pedido:
    pedido = db.session.scalar(select(Pedido).where(Pedido.numero == numero))
    if pedido is None or pedido.usuario_id != current_user.id:
        abort(404)
    if pedido.aguardando_pagamento and pedido.expira_em and pedido.expira_em < servico_pedidos.agora():
        servico_pedidos.cancelar(pedido, "Pagamento expirado")
        db.session.commit()
    return pedido


@conta_bp.get("/pedidos/<numero>")
@login_required
def pedido(numero: str) -> str:
    pedido = _pedido_da_cliente(numero)
    simulado = pedido.aguardando_pagamento and pix_simulado_ativo()
    return render_template(
        "conta/pedido.html",
        pedido=pedido,
        novo=request.args.get("novo") == "1",
        simulado=simulado,
        form_vazio=FormVazio(),
    )


@conta_bp.get("/pedidos/<numero>/status.json")
@login_required
def pedido_status(numero: str) -> Response:
    pedido = _pedido_da_cliente(numero)
    return jsonify(status=pedido.status, rotulo=pedido.rotulo_status)


@conta_bp.route("/enderecos", methods=["GET", "POST"])
@login_required
def enderecos() -> str | RespostaWerkzeug:
    form = FormEndereco()
    if form.validate_on_submit():
        endereco = Endereco(usuario_id=current_user.id)
        form.populate_obj(endereco)
        db.session.add(endereco)
        db.session.commit()
        flash("Endereço salvo.", "sucesso")
        return redirect(url_for("conta.enderecos"))
    return render_template("conta/enderecos.html", form=form, form_vazio=FormVazio())


@conta_bp.post("/enderecos/<int:endereco_id>/remover")
@login_required
def remover_endereco(endereco_id: int) -> RespostaWerkzeug:
    endereco = db.session.get(Endereco, endereco_id)
    if endereco is None or endereco.usuario_id != current_user.id:
        abort(404)
    if FormVazio().validate_on_submit():
        db.session.delete(endereco)
        db.session.commit()
        flash("Endereço removido.", "info")
    return redirect(url_for("conta.enderecos"))


@conta_bp.route("/excluir", methods=["GET", "POST"])
@login_required
def excluir() -> str | RespostaWerkzeug:
    """LGPD (RNF05): apaga os dados pessoais e mantém só o histórico fiscal dos pedidos."""
    form = FormExcluirConta()
    em_andamento = db.session.scalar(
        select(func.count(Pedido.id)).where(
            Pedido.usuario_id == current_user.id, Pedido.status.in_(STATUS_EM_ANDAMENTO)
        )
    )
    if em_andamento:
        flash("Você tem pedidos em andamento. A conta pode ser excluída depois da entrega.", "erro")
        return redirect(url_for("conta.painel"))
    if form.validate_on_submit():
        usuario: Usuario = current_user._get_current_object()
        if usuario.is_admin:
            abort(403)
        db.session.execute(delete(Favorito).where(Favorito.usuario_id == usuario.id))
        db.session.execute(delete(Sacola).where(Sacola.usuario_id == usuario.id))
        usuario.enderecos.clear()
        usuario.nome = "Conta excluída"
        usuario.email = f"excluida-{usuario.id}@conta-excluida.invalid"
        usuario.telefone = None
        usuario.senha_hash = None
        usuario.google_sub = None
        usuario.versao_sessao += 1
        db.session.commit()
        logout_user()
        session.clear()
        flash("Sua conta foi excluída.", "info")
        return redirect(url_for("loja.inicio"))
    return render_template("conta/excluir.html", form=form)
