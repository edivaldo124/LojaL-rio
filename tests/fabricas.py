"""Atalhos para criar dados nos testes (gravam com flush; quem chama decide o commit)."""

from __future__ import annotations

from flask.testing import FlaskClient

from extensoes import db
from modelos import (
    PAPEL_ADMIN,
    TIPO_PERCENTUAL,
    Categoria,
    Cupom,
    Endereco,
    ItemSacola,
    Produto,
    Sacola,
    Usuario,
    Variacao,
)
from servicos import senhas
from servicos.slugs import slugify

SENHA = "senha-de-teste-123"


def categoria(nome: str = "Vestidos") -> Categoria:
    existente = db.session.query(Categoria).filter_by(slug=slugify(nome)).one_or_none()
    if existente:
        return existente
    nova = Categoria(nome=nome, slug=slugify(nome), ordem=1)
    db.session.add(nova)
    db.session.flush()
    return nova


def produto(
    nome: str = "Vestido teste",
    preco: int = 10000,
    promocional: int | None = None,
    estoques: dict[tuple[str, str], int] | None = None,
    ativo: bool = True,
) -> Produto:
    item = Produto(
        nome=nome,
        slug=slugify(nome),
        categoria=categoria(),
        preco=preco,
        preco_promocional=promocional,
        ativo=ativo,
    )
    for (cor, tamanho), quantidade in (estoques or {("Rosa", "M"): 5}).items():
        item.variacoes.append(
            Variacao(
                cor=cor,
                cor_hex="#E8B4BC",
                tamanho=tamanho,
                sku=f"{slugify(nome)}-{slugify(cor)}-{tamanho}".upper(),
                estoque=quantidade,
            )
        )
    db.session.add(item)
    db.session.flush()
    return item


def usuario(email: str = "cliente@exemplo.com", admin: bool = False) -> Usuario:
    novo = Usuario(
        nome="Ana Cliente" if not admin else "Admin Loja",
        email=email,
        senha_hash=senhas.gerar_hash(SENHA),
        papel=PAPEL_ADMIN if admin else "CLIENTE",
    )
    db.session.add(novo)
    db.session.flush()
    return novo


def endereco(dono: Usuario, cep: str = "01310100", uf: str = "SP") -> Endereco:
    novo = Endereco(
        usuario_id=dono.id,
        apelido="Casa",
        cep=cep,
        rua="Avenida Paulista",
        numero="1000",
        bairro="Bela Vista",
        cidade="São Paulo",
        uf=uf,
    )
    db.session.add(novo)
    db.session.flush()
    return novo


def sacola(dono: Usuario, itens: list[tuple[Variacao, int]], cupom: str | None = None) -> Sacola:
    nova = Sacola(usuario_id=dono.id, cupom_codigo=cupom)
    for variacao, quantidade in itens:
        nova.itens.append(ItemSacola(variacao=variacao, quantidade=quantidade))
    db.session.add(nova)
    db.session.flush()
    return nova


def cupom(codigo: str = "DEZ", tipo: str = TIPO_PERCENTUAL, valor: int = 10, **campos: object) -> Cupom:
    novo = Cupom(codigo=codigo, tipo=tipo, valor=valor, **campos)
    db.session.add(novo)
    db.session.flush()
    return novo


def entrar(cliente: FlaskClient, email: str) -> None:
    resposta = cliente.post("/conta/entrar", data={"email": email, "senha": SENHA})
    assert resposta.status_code == 302, resposta.get_data(as_text=True)[:500]
