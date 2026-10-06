"""Regras de validação das tabelas de comarcas (métricas A1–A10)."""

from __future__ import annotations

from datetime import date

import pandas as pd

from pipeline.comarcas import normalizar_nome, soma_estrita, validar

IBGE = pd.DataFrame({
    "codigo_ibge": ["2800001", "2800002", "2800003", "2700001"],
    "nome": ["Aracaju", "Barra dos Coqueiros", "Estância", "Maceió"],
    "uf": ["SE", "SE", "SE", "AL"],
})


def tabelas(comarcas_linhas, municipios_linhas):
    comarcas = pd.DataFrame(comarcas_linhas, columns=["comarca_id", "nome", "uf", "tribunal", "entrancia",
                                                      "fonte", "data_verificacao"])
    municipios = pd.DataFrame(municipios_linhas, columns=["codigo_ibge", "municipio", "comarca_id"])
    return comarcas.assign(pasta=comarcas.uf), municipios.assign(pasta="SE")


VALIDA = (
    [("2800001", "Aracaju", "SE", "TJSE", "final", "lei X", "2026-10-01")],
    [("2800001", "Aracaju", "2800001"), ("2800002", "Barra dos Coqueiros", "2800001"),
     ("2800003", "Estância", "2800001")],
)


def regras(problemas, gravidade="erro"):
    return sorted({p.regra for p in problemas if p.gravidade == gravidade})


def test_tabela_valida_nao_tem_problemas():
    assert validar(*tabelas(*VALIDA), IBGE, hoje=date(2026, 10, 6)) == []


def test_municipio_faltando_e_erro_de_cobertura():
    comarcas, municipios = tabelas(VALIDA[0], VALIDA[1][:2])
    assert regras(validar(comarcas, municipios, IBGE, hoje=date(2026, 10, 6))) == ["A1"]


def test_municipio_duplicado():
    comarcas, municipios = tabelas(VALIDA[0], VALIDA[1] + [("2800003", "Estância", "2800001")])
    assert "A2" in regras(validar(comarcas, municipios, IBGE, hoje=date(2026, 10, 6)))


def test_codigo_inexistente_e_municipio_de_outra_uf():
    comarcas, municipios = tabelas(VALIDA[0], VALIDA[1] + [("9999999", "Nada", "2800001"),
                                                           ("2700001", "Maceió", "2800001")])
    assert regras(validar(comarcas, municipios, IBGE, hoje=date(2026, 10, 6))) == ["A3"]


def test_sede_fora_da_propria_comarca():
    comarcas, municipios = tabelas(
        VALIDA[0] + [("2800003", "Estância", "SE", "TJSE", "inicial", "lei X", "2026-10-01")],
        [("2800001", "Aracaju", "2800001"), ("2800002", "Barra dos Coqueiros", "2800001"),
         ("2800003", "Estância", "2800001")],
    )
    assert regras(validar(comarcas, municipios, IBGE, hoje=date(2026, 10, 6))) == ["A4", "A5"]


def test_fonte_e_data_obrigatorias():
    comarcas, municipios = tabelas([("2800001", "Aracaju", "SE", "TJSE", "final", " ", "01/10/2026")], VALIDA[1])
    assert regras(validar(comarcas, municipios, IBGE, hoje=date(2026, 10, 6))) == ["A8"]


def test_avisos_de_nome_e_de_verificacao_antiga():
    comarcas, municipios = tabelas(
        [("2800001", "Aracaju", "SE", "TJSE", "final", "lei X", "2024-01-01")],
        [("2800001", "Aracaju", "2800001"), ("2800002", "Barra do Coqueiro", "2800001"),
         ("2800003", "ESTANCIA", "2800001")],
    )
    problemas = validar(comarcas, municipios, IBGE, hoje=date(2026, 10, 6))
    assert regras(problemas) == []
    assert regras(problemas, "aviso") == ["A10", "A9"]
    assert sum(p.regra == "A10" for p in problemas) == 1  # "ESTANCIA" = "Estância"


def test_normalizar_nome():
    assert normalizar_nome("Olho-d'Água das Flores") == normalizar_nome("OLHO D AGUA DAS FLORES")


def test_soma_estrita_nao_esconde_valor_faltando():
    assert soma_estrita(pd.Series([1.0, 2.0])) == 3.0
    assert pd.isna(soma_estrita(pd.Series([1.0, None])))
