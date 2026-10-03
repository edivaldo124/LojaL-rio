from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField
from wtforms.validators import DataRequired, Length, NumberRange

import config_loja


class FormAdicionar(FlaskForm):
    variacao_id = IntegerField(validators=[DataRequired("Escolha a cor e o tamanho.")])
    quantidade = IntegerField(
        default=1,
        validators=[NumberRange(min=1, max=config_loja.QUANTIDADE_MAXIMA_POR_ITEM)],
    )


class FormQuantidade(FlaskForm):
    quantidade = IntegerField(validators=[NumberRange(min=0, max=config_loja.QUANTIDADE_MAXIMA_POR_ITEM)])


class FormCupom(FlaskForm):
    codigo = StringField(
        "Cupom de desconto",
        validators=[DataRequired("Digite o código do cupom."), Length(max=40)],
        render_kw={"placeholder": "Cupom de desconto", "autocapitalize": "characters"},
    )


class FormCep(FlaskForm):
    cep = StringField(
        "CEP",
        validators=[DataRequired("Digite o CEP.")],
        render_kw={"placeholder": "00000-000", "inputmode": "numeric", "autocomplete": "postal-code"},
    )


class FormVazio(FlaskForm):
    """Só o token CSRF (botões de remover, sair etc.)."""
