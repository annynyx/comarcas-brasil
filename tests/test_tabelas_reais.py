"""Confere as tabelas de comarcas cadastradas em dados/fontes/ (sem precisar da malha do IBGE).

A checagem completa (contra a malha oficial) acontece em `make camadas`. Aqui pegamos,
já no pull request, os erros mais comuns: digitação de código, sede fora da própria
comarca, município repetido, fonte ou data faltando.
"""

from __future__ import annotations

import pandas as pd
import pytest

from pipeline.comarcas import ler_tabelas, validar
from pipeline.config import CODIGOS_UF, RAIZ

PASTA = RAIZ / "dados" / "fontes"
UFS = sorted(p.name for p in PASTA.glob("*") if p.is_dir() and not p.name.startswith("_"))


@pytest.mark.parametrize("uf", UFS)
def test_tabela_da_uf(uf, tmp_path):
    (tmp_path / uf).symlink_to(PASTA / uf)
    comarcas, municipios = ler_tabelas(tmp_path)

    # Sem a malha, usamos a própria tabela como referência de nomes e UF.
    referencia = pd.DataFrame({"codigo_ibge": municipios.codigo_ibge,
                               "nome": municipios.municipio, "uf": uf})
    erros = [p for p in validar(comarcas, municipios, referencia) if p.gravidade == "erro"]
    assert not erros, "\n".join(p.mensagem for p in erros)

    # Todo código IBGE de município tem 7 dígitos e começa com o código da UF
    for codigo in municipios.codigo_ibge:
        assert codigo.isdigit() and len(codigo) == 7, f"código inválido: {codigo}"
        assert codigo.startswith(CODIGOS_UF[uf]), f"{codigo} não é de {uf} (prefixo {CODIGOS_UF[uf]})"


def test_roraima_tem_8_comarcas_e_15_municipios():
    comarcas, municipios = ler_tabelas(PASTA)
    assert (comarcas.uf == "RR").sum() == 8
    assert (municipios.pasta == "RR").sum() == 15
