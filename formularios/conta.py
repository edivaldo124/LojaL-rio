from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, EmailField, PasswordField, StringField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp

from servicos.senhas import TAMANHO_MINIMO

MSG_OBRIGATORIO = "Preencha este campo."


def _email() -> EmailField:
    return EmailField(
        "E-mail",
        validators=[
            DataRequired(MSG_OBRIGATORIO),
            Email("Informe um e-mail válido.", check_deliverability=False),
            Length(max=254),
        ],
        filters=[lambda v: v.strip().lower() if v else v],
        render_kw={"autocomplete": "email", "placeholder": "seuemail@exemplo.com"},
    )


def _nova_senha(rotulo: str = "Senha") -> PasswordField:
    return PasswordField(
        rotulo,
        validators=[
            DataRequired(MSG_OBRIGATORIO),
            Length(
                min=TAMANHO_MINIMO,
                max=128,
                message=f"A senha precisa ter pelo menos {TAMANHO_MINIMO} caracteres.",
            ),
        ],
        render_kw={"autocomplete": "new-password"},
    )


class FormLogin(FlaskForm):
    email = _email()
    senha = PasswordField(
        "Senha",
        validators=[DataRequired(MSG_OBRIGATORIO), Length(max=128)],
        render_kw={"autocomplete": "current-password", "placeholder": "••••••••"},
    )
    lembrar = BooleanField("Manter conectada", default=True)


class FormCadastro(FlaskForm):
    nome = StringField(
        "Nome completo",
        validators=[DataRequired(MSG_OBRIGATORIO), Length(min=2, max=120)],
        filters=[lambda v: " ".join(v.split()) if v else v],
        render_kw={"autocomplete": "name"},
    )
    email = _email()
    telefone = StringField(
        "Celular (opcional)",
        validators=[
            Optional(),
            Regexp(r"^[\d\s()+-]{10,20}$", message="Informe um celular válido, com DDD."),
        ],
        render_kw={"autocomplete": "tel", "inputmode": "tel", "placeholder": "(00) 00000-0000"},
    )
    senha = _nova_senha()
    confirmar = PasswordField(
        "Confirme a senha",
        validators=[DataRequired(MSG_OBRIGATORIO), EqualTo("senha", "As senhas não conferem.")],
        render_kw={"autocomplete": "new-password"},
    )
    aceite = BooleanField(
        "Li e aceito a política de privacidade",
        validators=[DataRequired("É preciso aceitar a política de privacidade.")],
    )


class FormEsqueciSenha(FlaskForm):
    email = _email()


class FormNovaSenha(FlaskForm):
    senha = _nova_senha("Nova senha")
    confirmar = PasswordField(
        "Confirme a nova senha",
        validators=[DataRequired(MSG_OBRIGATORIO), EqualTo("senha", "As senhas não conferem.")],
        render_kw={"autocomplete": "new-password"},
    )


class FormExcluirConta(FlaskForm):
    confirmacao = StringField(
        'Digite "EXCLUIR" para confirmar',
        validators=[
            DataRequired(MSG_OBRIGATORIO),
            Regexp(r"^EXCLUIR$", message="Digite EXCLUIR em maiúsculas."),
        ],
    )
