"""Modelos do banco. Importar daqui garante que todas as tabelas estejam registradas."""

from modelos.banner import Banner
from modelos.categoria import Categoria
from modelos.cupom import TIPO_PERCENTUAL, TIPO_VALOR, Cupom
from modelos.endereco import Endereco
from modelos.favorito import Favorito
from modelos.pagamento_simulado import PagamentoSimulado
from modelos.pedido import (
    FRETE_ENTREGA,
    FRETE_RETIRADA,
    PAGAMENTO_BOLETO,
    PAGAMENTO_CARTAO,
    PAGAMENTO_PIX,
    ItemPedido,
    Pedido,
    StatusPedido,
)
from modelos.produto import ImagemProduto, Produto, Variacao
from modelos.sacola import ItemSacola, Sacola
from modelos.usuario import PAPEL_ADMIN, PAPEL_CLIENTE, Usuario

__all__ = [
    "FRETE_ENTREGA",
    "FRETE_RETIRADA",
    "PAGAMENTO_BOLETO",
    "PAGAMENTO_CARTAO",
    "PAGAMENTO_PIX",
    "PAPEL_ADMIN",
    "PAPEL_CLIENTE",
    "TIPO_PERCENTUAL",
    "TIPO_VALOR",
    "Banner",
    "Categoria",
    "Cupom",
    "Endereco",
    "Favorito",
    "ImagemProduto",
    "ItemPedido",
    "ItemSacola",
    "PagamentoSimulado",
    "Pedido",
    "Produto",
    "Sacola",
    "StatusPedido",
    "Usuario",
    "Variacao",
]
