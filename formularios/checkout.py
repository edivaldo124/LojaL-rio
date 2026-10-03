from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import Field, RadioField, SelectField, StringField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from modelos.pedido import FRETE_ENTREGA, FRETE_RETIRADA, PAGAMENTO_PIX
from servicos.cep import UFS, normalizar_cep, uf_do_cep

MSG_OBRIGATORIO = "Preencha este campo."


def _limpar(valor: str | None) -> str | None:
    return " ".join(valor.split()) if valor else valor


class FormEndereco(FlaskForm):
    apelido = StringField(
        "Apelido",
        validators=[DataRequired(MSG_OBRIGATORIO), Length(max=40)],
        filters=[_limpar],
        render_kw={"placeholder": "Casa, Trabalho…"},
    )
    cep = StringField(
        "CEP",
        validators=[DataRequired(MSG_OBRIGATORIO)],
        render_kw={
            "inputmode": "numeric",
            "autocomplete": "postal-code",
            "placeholder": "00000-000",
            "data-cep": "",
        },
    )
    rua = StringField(
        "Rua",
        validators=[DataRequired(MSG_OBRIGATORIO), Length(max=160)],
        filters=[_limpar],
        render_kw={"autocomplete": "address-line1", "data-cep-campo": "logradouro"},
    )
    numero = StringField(
        "Número",
        validators=[DataRequired(MSG_OBRIGATORIO), Length(max=20)],
        filters=[_limpar],
        render_kw={"inputmode": "numeric"},
    )
    complemento = StringField(
        "Complemento (opcional)",
        validators=[Optional(), Length(max=80)],
        filters=[_limpar],
        render_kw={"autocomplete": "address-line2"},
    )
    bairro = StringField(
        "Bairro",
        validators=[DataRequired(MSG_OBRIGATORIO), Length(max=80)],
        filters=[_limpar],
        render_kw={"data-cep-campo": "bairro"},
    )
    cidade = StringField(
        "Cidade",
        validators=[DataRequired(MSG_OBRIGATORIO), Length(max=80)],
        filters=[_limpar],
        render_kw={"autocomplete": "address-level2", "data-cep-campo": "localidade"},
    )
    uf = SelectField(
        "UF",
        choices=[("", "UF"), *[(uf, uf) for uf in UFS]],
        validators=[DataRequired(MSG_OBRIGATORIO)],
        render_kw={"data-cep-campo": "uf"},
    )

    def validate_cep(self, campo: Field) -> None:
        cep = normalizar_cep(campo.data)
        if cep is None or uf_do_cep(cep) is None:
            raise ValidationError("Informe um CEP válido com 8 dígitos.")
        campo.data = cep

    def validate_uf(self, campo: Field) -> None:
        cep = normalizar_cep(self.cep.data)
        if cep and uf_do_cep(cep) not in (None, campo.data):
            raise ValidationError(f"Este CEP é de {uf_do_cep(cep)}.")


class FormEntrega(FlaskForm):
    endereco_id = RadioField("Endereço", coerce=int, validate_choice=False, validators=[Optional()])
    tipo_frete = RadioField(
        "Frete",
        choices=[(FRETE_ENTREGA, "Entrega"), (FRETE_RETIRADA, "Retirar na loja")],
        validators=[DataRequired("Escolha o frete.")],
    )


class FormPagamento(FlaskForm):
    tipo_frete = RadioField(
        "Frete",
        choices=[(FRETE_ENTREGA, "Entrega"), (FRETE_RETIRADA, "Retirar na loja")],
        validators=[DataRequired("Escolha o frete.")],
    )
    forma_pagamento = RadioField(
        "Pagamento",
        choices=[(PAGAMENTO_PIX, "Pix")],  # cartão e boleto: Fase 2
        validators=[DataRequired("Escolha a forma de pagamento.")],
    )
