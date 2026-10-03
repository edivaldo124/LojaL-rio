from __future__ import annotations

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    Field,
    IntegerField,
    MultipleFileField,
    SelectField,
    SelectMultipleField,
    StringField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, Regexp, ValidationError
from wtforms.widgets import CheckboxInput, ListWidget

import config_loja
from servicos.dinheiro import centavos_de_texto

MSG_OBRIGATORIO = "Preencha este campo."
IMAGENS = ["jpg", "jpeg", "png", "webp", "gif", "avif", "heic"]


def _validar_dinheiro(campo: Field, obrigatorio: bool) -> None:
    if not campo.data:
        if obrigatorio:
            raise ValidationError(MSG_OBRIGATORIO)
        return
    try:
        centavos = centavos_de_texto(campo.data)
    except ValueError as erro:
        raise ValidationError("Use o formato 189,90.") from erro
    if centavos <= 0:
        raise ValidationError("O valor precisa ser maior que zero.")


class FormProduto(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(MSG_OBRIGATORIO), Length(max=120)])
    categoria_id = SelectField("Categoria", coerce=int, validators=[DataRequired(MSG_OBRIGATORIO)])
    preco = StringField("Preço (R$)", render_kw={"inputmode": "decimal", "placeholder": "189,90"})
    preco_promocional = StringField(
        "Preço promocional (R$, opcional)",
        render_kw={"inputmode": "decimal", "placeholder": "149,90"},
    )
    descricao = TextAreaField("Descrição", validators=[Length(max=5000)], render_kw={"rows": 5})
    composicao = StringField(
        "Composição do tecido",
        validators=[Length(max=200)],
        render_kw={"placeholder": "100% viscose"},
    )
    ativo = BooleanField("Ativo (aparece na loja)", default=True)

    def validate_preco(self, campo: Field) -> None:
        _validar_dinheiro(campo, obrigatorio=True)

    def validate_preco_promocional(self, campo: Field) -> None:
        _validar_dinheiro(campo, obrigatorio=False)
        if campo.data and self.preco.data:
            try:
                if centavos_de_texto(campo.data) >= centavos_de_texto(self.preco.data):
                    raise ValidationError("O preço promocional precisa ser menor que o preço.")
            except ValueError:
                return


class FormFotos(FlaskForm):
    fotos = MultipleFileField(
        "Fotos",
        validators=[DataRequired("Escolha ao menos uma foto.")],
        render_kw={"accept": "image/*", "multiple": True},
    )


class FormAltFoto(FlaskForm):
    alt = StringField("Texto alternativo", validators=[Length(max=200)])


class _CheckboxesMultiplos(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class FormNovaCor(FlaskForm):
    cor = StringField(
        "Cor",
        validators=[DataRequired(MSG_OBRIGATORIO), Length(max=40)],
        render_kw={"placeholder": "Rosa"},
    )
    cor_hex = StringField(
        "Amostra",
        default="#C97B84",
        validators=[Regexp(r"^#[0-9A-Fa-f]{6}$", message="Escolha uma cor.")],
        render_kw={"type": "color"},
    )
    tamanhos = _CheckboxesMultiplos(
        "Tamanhos",
        choices=[(t, t) for t in config_loja.TAMANHOS],
        validators=[DataRequired("Marque ao menos um tamanho.")],
    )
    estoque = IntegerField(
        "Estoque inicial de cada tamanho",
        default=0,
        validators=[NumberRange(min=0, max=99999, message="Informe um número de 0 a 99999.")],
    )


class FormVariacao(FlaskForm):
    sku = StringField("SKU", validators=[DataRequired(MSG_OBRIGATORIO), Length(max=60)])
    cor_hex = StringField(
        "Amostra",
        validators=[Regexp(r"^#[0-9A-Fa-f]{6}$", message="Escolha uma cor.")],
        render_kw={"type": "color"},
    )
    estoque = IntegerField("Estoque", validators=[NumberRange(min=0, max=99999, message="De 0 a 99999.")])


class FormCategoria(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(MSG_OBRIGATORIO), Length(max=60)])
    ordem = IntegerField(
        "Ordem de exibição",
        default=0,
        validators=[NumberRange(min=0, max=999, message="De 0 a 999.")],
    )
    imagem = FileField("Imagem (opcional)", validators=[FileAllowed(IMAGENS, "Envie uma imagem.")])


class FormStatusPedido(FlaskForm):
    status = SelectField("Novo status", validators=[DataRequired("Escolha o novo status.")])
    rastreio = StringField(
        "Código de rastreio",
        validators=[Optional(), Length(max=60)],
        render_kw={"placeholder": "AA123456789BR"},
    )
