"""Dinheiro em centavos, CEP, frete e cálculo do total (RN03, RN05, RN06, RN07)."""

from __future__ import annotations

import pytest

from modelos.pedido import FRETE_ENTREGA, FRETE_RETIRADA, PAGAMENTO_PIX
from servicos.cep import normalizar_cep, regiao_do_cep, uf_do_cep
from servicos.dinheiro import centavos_de_texto, formatar_brl, percentual, valor_parcela
from servicos.frete import cotar_entrega, opcao_por_tipo, opcao_retirada
from servicos.totais import AVISO_CUPOM_VENCEU, AVISO_PIX_VENCEU, CupomAplicado, calcular_totais

NBSP = " "


class TestDinheiro:
    @pytest.mark.parametrize(
        ("centavos", "texto"),
        [(18990, "R$ 189,90"), (5, "R$ 0,05"), (123456789, "R$ 1.234.567,89"), (-1549, "-R$ 15,49")],
    )
    def test_formata_em_reais(self, centavos: int, texto: str) -> None:
        assert formatar_brl(centavos) == texto.replace(" ", NBSP)

    @pytest.mark.parametrize(
        ("texto", "centavos"),
        [("189,90", 18990), ("R$ 1.234,56", 123456), ("189", 18900), ("189.9", 18990), ("0,5", 50)],
    )
    def test_le_o_que_o_admin_digita(self, texto: str, centavos: int) -> None:
        assert centavos_de_texto(texto) == centavos

    @pytest.mark.parametrize("texto", ["", "abc", "1,234", "12,3,4"])
    def test_recusa_valor_invalido(self, texto: str) -> None:
        with pytest.raises(ValueError):
            centavos_de_texto(texto)

    def test_percentual_arredonda_meio_centavo_para_cima(self) -> None:
        assert percentual(30980, 5) == 1549
        assert percentual(10010, 5) == 501  # 500,5 -> 501

    def test_parcela_nunca_cobra_a_menos(self) -> None:
        assert valor_parcela(18990, 3) == 6330
        assert valor_parcela(10000, 3) == 3334
        assert valor_parcela(10000, 3) * 3 >= 10000


class TestCepEFrete:
    def test_normaliza_cep(self) -> None:
        assert normalizar_cep("01310-100") == "01310100"
        assert normalizar_cep("1310-100") is None

    @pytest.mark.parametrize(
        ("cep", "uf", "regiao"),
        [
            ("01310-100", "SP", "Sudeste"),
            ("20040-020", "RJ", "Sudeste"),
            ("90010-150", "RS", "Sul"),
            ("70040-010", "DF", "Centro-Oeste"),
            ("40020-000", "BA", "Nordeste"),
            ("69005-070", "AM", "Norte"),
            ("69900-000", "AC", "Norte"),
        ],
    )
    def test_uf_e_regiao_pela_faixa_do_cep(self, cep: str, uf: str, regiao: str) -> None:
        assert uf_do_cep(cep) == uf
        assert regiao_do_cep(cep) == regiao

    def test_entrega_usa_a_tabela_da_regiao(self) -> None:
        sudeste, norte = cotar_entrega("01310100"), cotar_entrega("69005070")
        assert sudeste is not None and norte is not None
        assert (sudeste.tipo, sudeste.valor) == (FRETE_ENTREGA, 1990)
        assert norte.valor > sudeste.valor

    def test_retirar_na_loja_e_gratis(self) -> None:  # RN05
        assert opcao_retirada().valor == 0
        retirada = opcao_por_tipo(FRETE_RETIRADA, None)
        assert retirada is not None and retirada.valor == 0

    def test_cep_invalido_nao_tem_frete(self) -> None:
        assert cotar_entrega("00000000") is None


class TestTotais:
    def test_exemplo_do_prototipo(self) -> None:
        """Sacola R$ 309,80 + frete R$ 19,90 no Pix: 5% só sobre os produtos (RN03)."""
        totais = calcular_totais(30980, 1990, PAGAMENTO_PIX)
        assert totais.desconto_pix == 1549
        assert totais.total == 30980 - 1549 + 1990 == 31421

    def test_sem_pix_nao_ha_desconto(self) -> None:
        totais = calcular_totais(30980, 1990, None)
        assert totais.desconto == 0
        assert totais.total == 32970

    def test_pix_nao_desconta_o_frete(self) -> None:
        com_frete = calcular_totais(10000, 3490, PAGAMENTO_PIX)
        sem_frete = calcular_totais(10000, 0, PAGAMENTO_PIX)
        assert com_frete.desconto_pix == sem_frete.desconto_pix == 500

    def test_cupom_maior_que_pix_vence_quando_nao_acumula(self) -> None:  # RN06
        cupom = CupomAplicado("DEZ", desconto=1000, acumula_pix=False)
        totais = calcular_totais(10000, 1990, PAGAMENTO_PIX, cupom)
        assert (totais.desconto_cupom, totais.desconto_pix) == (1000, 0)
        assert totais.total == 10000 - 1000 + 1990
        assert totais.aviso == AVISO_CUPOM_VENCEU

    def test_pix_maior_que_cupom_vence_quando_nao_acumula(self) -> None:
        cupom = CupomAplicado("TRES", desconto=300, acumula_pix=False)
        totais = calcular_totais(10000, 0, PAGAMENTO_PIX, cupom)
        assert (totais.desconto_cupom, totais.desconto_pix) == (0, 500)
        assert totais.aviso == AVISO_PIX_VENCEU

    def test_cupom_acumulavel_soma_com_pix_sobre_o_valor_ja_descontado(self) -> None:
        cupom = CupomAplicado("DEZ", desconto=1000, acumula_pix=True)
        totais = calcular_totais(10000, 0, PAGAMENTO_PIX, cupom)
        assert (totais.desconto_cupom, totais.desconto_pix) == (1000, 450)
        assert totais.total == 8550

    def test_cupom_sem_pix_aplica_direto(self) -> None:
        cupom = CupomAplicado("DEZ", desconto=1000, acumula_pix=False)
        totais = calcular_totais(10000, 1990, None, cupom)
        assert totais.desconto_cupom == 1000
        assert totais.aviso is None

    def test_cupom_nunca_deixa_produtos_negativos(self) -> None:
        cupom = CupomAplicado("GRANDE", desconto=50000, acumula_pix=False)
        totais = calcular_totais(10000, 1990, None, cupom)
        assert totais.desconto_cupom == 10000
        assert totais.total == 1990


class TestUrlDoBanco:
    @pytest.mark.parametrize(
        ("recebida", "usada"),
        [
            (
                "postgresql://u:s@host:5432/db?sslmode=require",
                "postgresql+psycopg2://u:s@host:5432/db?sslmode=require",
            ),
            ("postgres://u:s@host/db", "postgresql+psycopg2://u:s@host/db"),
            ("postgresql+psycopg2:///lojalirio", "postgresql+psycopg2:///lojalirio"),
            ("sqlite:///teste.db", "sqlite:///teste.db"),
        ],
    )
    def test_usa_sempre_o_psycopg2(self, recebida: str, usada: str) -> None:
        from config import url_banco

        assert url_banco(recebida) == usada
