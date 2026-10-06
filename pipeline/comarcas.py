"""Tabelas município → comarca: leitura e validação.

As tabelas ficam em `dados/fontes/<UF>/` (veja o modelo em `dados/fontes/_modelo/`).
Um estado só entra no mapa de comarcas quando a sua tabela está completa: um mapa
com metade dos municípios de um estado seria enganoso.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

COLUNAS_COMARCAS = ["comarca_id", "nome", "uf", "tribunal", "entrancia", "fonte", "data_verificacao"]
COLUNAS_OPCIONAIS = ["observacao"]  # ex.: comarca criada por lei mas não instalada
COLUNAS_MUNICIPIOS = ["codigo_ibge", "municipio", "comarca_id"]
VALIDADE_DIAS = 365  # métrica A9


@dataclass
class Problema:
    regra: str       # código da métrica em docs/02-metricas.md (ex.: "A2")
    gravidade: str   # "erro" interrompe o build; "aviso" só aparece no relatório
    mensagem: str

    def como_dict(self) -> dict:
        return asdict(self)


def ler_tabelas(pasta: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Junta as tabelas de todas as UFs. Pastas que começam com "_" são ignoradas."""
    comarcas, vinculos = [], []
    pastas_uf = sorted(p for p in pasta.glob("*") if p.is_dir() and not p.name.startswith("_"))
    for pasta_uf in pastas_uf:
        c = pd.read_csv(pasta_uf / "comarcas.csv", dtype=str, keep_default_na=False)
        m = pd.read_csv(pasta_uf / "municipios.csv", dtype=str, keep_default_na=False)
        comarcas.append(c.assign(pasta=pasta_uf.name))
        vinculos.append(m.assign(pasta=pasta_uf.name))
    if not comarcas:
        return (pd.DataFrame(columns=COLUNAS_COMARCAS + COLUNAS_OPCIONAIS + ["pasta"]),
                pd.DataFrame(columns=COLUNAS_MUNICIPIOS + ["pasta"]))
    juntas = pd.concat(comarcas, ignore_index=True)
    for coluna in COLUNAS_OPCIONAIS:
        juntas[coluna] = juntas.get(coluna, pd.Series(dtype=str)).fillna("")
    return juntas, pd.concat(vinculos, ignore_index=True)


def normalizar_nome(texto: str) -> str:
    """'Olho-d'Água das Flores' → 'olhodaguadasflores' (para comparar grafias)."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def validar(comarcas: pd.DataFrame, vinculos: pd.DataFrame, municipios_ibge: pd.DataFrame,
            hoje: date | None = None) -> list[Problema]:
    """Confere as tabelas contra a malha do IBGE.

    `municipios_ibge` precisa das colunas codigo_ibge, nome e uf.
    """
    hoje = hoje or date.today()
    problemas: list[Problema] = []

    def erro(regra, msg):
        problemas.append(Problema(regra, "erro", msg))

    def aviso(regra, msg):
        problemas.append(Problema(regra, "aviso", msg))

    for nome, tabela, colunas in (("comarcas.csv", comarcas, COLUNAS_COMARCAS),
                                  ("municipios.csv", vinculos, COLUNAS_MUNICIPIOS)):
        faltando = set(colunas) - set(tabela.columns)
        if faltando:
            erro("esquema", f"{nome}: faltam as colunas {sorted(faltando)}")
    if problemas:
        return problemas

    ibge = municipios_ibge.set_index("codigo_ibge")

    # --- comarcas.csv ---
    for _, c in comarcas.iterrows():
        rotulo = f"{c.pasta}/comarcas.csv, comarca {c.comarca_id or '?'} ({c.nome})"
        if c.uf != c.pasta:
            erro("esquema", f"{rotulo}: uf '{c.uf}' diferente da pasta '{c.pasta}'")
        if not c.fonte.strip():
            erro("A8", f"{rotulo}: coluna 'fonte' vazia")
        try:
            verificado = date.fromisoformat(c.data_verificacao)
            if (hoje - verificado).days > VALIDADE_DIAS:
                aviso("A9", f"{rotulo}: verificada em {verificado}, há mais de {VALIDADE_DIAS} dias")
        except ValueError:
            erro("A8", f"{rotulo}: data_verificacao '{c.data_verificacao}' não está no formato AAAA-MM-DD")
        if c.comarca_id not in ibge.index:
            erro("A3", f"{rotulo}: comarca_id não é um código IBGE de município")
        elif ibge.at[c.comarca_id, "uf"] != c.uf:
            erro("A3", f"{rotulo}: o município-sede fica em {ibge.at[c.comarca_id, 'uf']}, não em {c.uf}")

    for cid in comarcas.loc[comarcas.comarca_id.duplicated(), "comarca_id"].unique():
        erro("esquema", f"comarca_id {cid} aparece mais de uma vez em comarcas.csv")

    # --- municipios.csv ---
    for cod in vinculos.loc[vinculos.codigo_ibge.duplicated(), "codigo_ibge"].unique():
        pastas = ", ".join(vinculos.loc[vinculos.codigo_ibge == cod, "pasta"])
        erro("A2", f"município {cod} aparece mais de uma vez ({pastas})")

    ids_comarcas = set(comarcas.comarca_id)
    for _, m in vinculos.iterrows():
        rotulo = f"{m.pasta}/municipios.csv, município {m.codigo_ibge} ({m.municipio})"
        if m.codigo_ibge not in ibge.index:
            erro("A3", f"{rotulo}: código não existe na malha do IBGE")
            continue
        if ibge.at[m.codigo_ibge, "uf"] != m.pasta:
            erro("A3", f"{rotulo}: o município fica em {ibge.at[m.codigo_ibge, 'uf']}")
        if m.comarca_id not in ids_comarcas:
            erro("esquema", f"{rotulo}: comarca_id {m.comarca_id} não existe em comarcas.csv")
        nome_ibge = ibge.at[m.codigo_ibge, "nome"]
        if normalizar_nome(m.municipio) != normalizar_nome(nome_ibge):
            aviso("A10", f"{rotulo}: no IBGE o nome é '{nome_ibge}'")

    # A4 — a sede pertence à própria comarca; A5 — nenhuma comarca vazia
    comarca_do_municipio = dict(zip(vinculos.codigo_ibge, vinculos.comarca_id))
    comarcas_com_municipio = set(vinculos.comarca_id)
    for cid in sorted(ids_comarcas):
        if comarca_do_municipio.get(cid) != cid:
            erro("A4", f"a sede da comarca {cid} não está vinculada à própria comarca em municipios.csv")
        if cid not in comarcas_com_municipio:
            erro("A5", f"a comarca {cid} não tem nenhum município")

    # A1 — cobertura completa em cada UF que tem tabela
    for uf in sorted(set(comarcas.pasta) | set(vinculos.pasta)):
        esperados = set(municipios_ibge.loc[municipios_ibge.uf == uf, "codigo_ibge"])
        faltando = sorted(esperados - set(vinculos.loc[vinculos.pasta == uf, "codigo_ibge"]))
        if faltando:
            exemplos = ", ".join(faltando[:10]) + (" …" if len(faltando) > 10 else "")
            erro("A1", f"{uf}: {len(faltando)} município(s) sem comarca: {exemplos}")

    return problemas


def soma_estrita(valores: pd.Series) -> float:
    """Soma que vira "sem dado" (NaN) se faltar qualquer parcela.

    O `sum()` do pandas trata valor ausente como zero: uma comarca com um município sem
    população apareceria com população menor do que a real, sem nenhum aviso.
    """
    return valores.sum() if valores.notna().all() else float("nan")


def montar_camada(municipios: gpd.GeoDataFrame, comarcas: pd.DataFrame,
                  vinculos: pd.DataFrame) -> gpd.GeoDataFrame:
    """Dissolve os polígonos dos municípios de cada comarca num polígono só."""
    base = municipios.merge(vinculos[["codigo_ibge", "comarca_id"]].rename(
        columns={"comarca_id": "_comarca"}), on="codigo_ibge", how="inner")
    camada = base.dissolve(
        by="_comarca",
        aggfunc={"area_km2": "sum", "populacao": soma_estrita, "codigo_ibge": "count"},
    ).reset_index().rename(columns={"_comarca": "comarca_id", "codigo_ibge": "n_municipios"})

    nomes_sede = municipios.set_index("codigo_ibge")["nome"]
    atributos = comarcas[["comarca_id", "nome", "uf", "tribunal", "entrancia", "observacao", "data_verificacao"]]
    camada = camada.merge(atributos, on="comarca_id", how="left")
    camada["sede"] = camada.comarca_id.map(nomes_sede)
    camada["densidade"] = (camada.populacao / camada.area_km2).round(2)
    colunas = ["comarca_id", "nome", "uf", "tribunal", "entrancia", "sede", "n_municipios",
               "area_km2", "populacao", "densidade", "observacao", "data_verificacao", "geometry"]
    return camada[colunas]
