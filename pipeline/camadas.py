"""Etapa 2 — montar as camadas vetoriais em resolução total.

Todas as camadas de área nascem da MESMA malha municipal do IBGE:

    municípios ──dissolve por comarca──▶ comarcas
        │
        ├──dissolve por UF──────────────▶ estados (ufs)
        ├──dissolve por região──────────▶ regiões
        └──dissolve tudo────────────────▶ país

Por isso as bordas de todas as camadas coincidem exatamente: a divisa entre dois estados
é literalmente a mesma linha que separa os municípios vizinhos.

Saída: `dados/intermediario/camadas.gpkg` (uma camada por mapa) + `problemas.json`.
"""

from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd

from . import comarcas as tab_comarcas
from .config import NOMES_UF, REGIOES, Projeto

CRS_OFICIAL = "EPSG:4674"  # SIRGAS 2000


def ler_malha(projeto: Projeto) -> gpd.GeoDataFrame:
    malha = gpd.read_file(projeto.brutos / "malha_municipal.zip")
    obrigatorias = {"CD_MUN", "NM_MUN", "SIGLA_UF", "AREA_KM2"}
    faltando = obrigatorias - set(malha.columns)
    if faltando:
        raise ValueError(f"A malha do IBGE não tem as colunas esperadas: {sorted(faltando)}")

    malha = malha.rename(columns={"CD_MUN": "codigo_ibge", "NM_MUN": "nome",
                                  "SIGLA_UF": "uf", "AREA_KM2": "area_km2"})
    malha = malha[["codigo_ibge", "nome", "uf", "area_km2", "geometry"]].to_crs(CRS_OFICIAL)
    malha["codigo_ibge"] = malha.codigo_ibge.astype(str)
    malha["regiao"] = malha.codigo_ibge.str[0].map(REGIOES)
    malha["e_municipio"] = ~malha.codigo_ibge.isin(projeto.fontes["malha_municipal"]["nao_municipios"])

    invalidas = ~malha.geometry.is_valid
    if invalidas.any():
        print(f"  aviso: corrigindo {int(invalidas.sum())} geometria(s) inválida(s) da malha")
        malha.loc[invalidas, "geometry"] = malha.loc[invalidas, "geometry"].make_valid()
    return malha


def ler_populacao(projeto: Projeto) -> pd.DataFrame:
    """Lê a resposta da API de agregados do IBGE (SIDRA v3)."""
    dados = json.loads((projeto.brutos / "populacao.json").read_text(encoding="utf-8"))
    linhas = []
    for serie in dados[0]["resultados"][0]["series"]:
        valor = next(iter(serie["serie"].values()))
        linhas.append((serie["localidade"]["id"], valor))
    tabela = pd.DataFrame(linhas, columns=["codigo_ibge", "populacao"])
    # O SIDRA usa "-", "..." etc. para valores ausentes → viram NaN
    tabela["populacao"] = pd.to_numeric(tabela.populacao, errors="coerce")
    return tabela


def ler_cidades(projeto: Projeto, municipios: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Cidade = sede do município (um ponto). Município = o território inteiro (um polígono)."""
    tabela = pd.read_csv(projeto.brutos / "cidades.csv", dtype={"codigo_ibge": str})
    cidades = gpd.GeoDataFrame(
        {"codigo_ibge": tabela.codigo_ibge, "nome": tabela.nome,
         "capital": tabela.capital.astype(int).astype(bool)},
        geometry=gpd.points_from_xy(tabela.longitude, tabela.latitude),
        crs="EPSG:4326",
    ).to_crs(CRS_OFICIAL)

    atributos = municipios[["codigo_ibge", "uf", "populacao", "comarca_id", "e_sede_comarca"]]
    sem_municipio = ~cidades.codigo_ibge.isin(atributos.codigo_ibge)
    if sem_municipio.any():
        print(f"  aviso: {int(sem_municipio.sum())} cidade(s) sem município correspondente na malha (descartadas)")
    cidades = cidades.merge(atributos, on="codigo_ibge", how="inner")
    return cidades[["codigo_ibge", "nome", "uf", "capital", "populacao", "comarca_id",
                    "e_sede_comarca", "geometry"]]


def agregar(base: gpd.GeoDataFrame, chave: str) -> gpd.GeoDataFrame:
    """Dissolve por `chave`, somando área, população e nº de municípios."""
    camada = base.assign(n_municipios=base.e_municipio.astype(int)).dissolve(
        by=chave, aggfunc={"area_km2": "sum", "populacao": tab_comarcas.soma_estrita, "n_municipios": "sum"},
    ).reset_index()
    camada["densidade"] = (camada.populacao / camada.area_km2).round(2)
    return camada


def montar(projeto: Projeto) -> dict[str, gpd.GeoDataFrame]:
    print("Lendo a malha municipal…")
    malha = ler_malha(projeto)
    malha = malha.merge(ler_populacao(projeto), on="codigo_ibge", how="left")
    malha.loc[~malha.e_municipio, "populacao"] = 0  # lagoas não têm habitantes

    print("Validando as tabelas de comarcas…")
    comarcas, vinculos = tab_comarcas.ler_tabelas(projeto.tabelas_comarcas)
    so_municipios = malha[malha.e_municipio]
    problemas = tab_comarcas.validar(comarcas, vinculos, so_municipios[["codigo_ibge", "nome", "uf"]])
    sem_populacao = so_municipios.loc[so_municipios.populacao.isna(), "codigo_ibge"]
    if len(sem_populacao):
        problemas.append(tab_comarcas.Problema(
            "populacao", "aviso", f"{len(sem_populacao)} município(s) sem população: {', '.join(sem_populacao[:10])}"))

    projeto.intermediario.mkdir(parents=True, exist_ok=True)
    (projeto.intermediario / "problemas.json").write_text(
        json.dumps([p.como_dict() for p in problemas], indent=2, ensure_ascii=False), encoding="utf-8")
    erros = [p for p in problemas if p.gravidade == "erro"]
    for p in problemas:
        print(f"  [{p.gravidade} {p.regra}] {p.mensagem}")
    if erros:
        raise SystemExit(f"{len(erros)} erro(s) nas tabelas de comarcas — corrija antes de continuar.")

    print("Montando camadas…")
    municipios = so_municipios.merge(vinculos[["codigo_ibge", "comarca_id"]], on="codigo_ibge", how="left")
    municipios["e_sede_comarca"] = municipios.codigo_ibge.isin(comarcas.comarca_id)
    municipios["nome_uf"] = municipios.uf.map(NOMES_UF)
    municipios["densidade"] = (municipios.populacao / municipios.area_km2).round(2)

    ufs = agregar(malha, "uf")
    ufs["nome"] = ufs.uf.map(NOMES_UF)
    ufs["regiao"] = ufs.uf.map(malha.drop_duplicates("uf").set_index("uf").regiao)
    ufs["tem_comarcas"] = ufs.uf.isin(comarcas.uf)

    camadas = {
        "pais": agregar(malha.assign(nome="Brasil"), "nome"),
        "regioes": agregar(malha, "regiao").rename(columns={"regiao": "nome"}),
        "ufs": ufs[["uf", "nome", "regiao", "n_municipios", "area_km2", "populacao", "densidade",
                    "tem_comarcas", "geometry"]],
        "municipios": municipios[["codigo_ibge", "nome", "uf", "nome_uf", "regiao", "comarca_id",
                                  "e_sede_comarca", "area_km2", "populacao", "densidade", "geometry"]],
    }
    if len(comarcas):
        camadas["comarcas"] = tab_comarcas.montar_camada(municipios, comarcas, vinculos)
    else:
        print("  aviso: nenhuma tabela de comarcas em dados/fontes/ — camada 'comarcas' não será gerada")
    camadas["cidades"] = ler_cidades(projeto, municipios)
    return camadas


def salvar(projeto: Projeto, camadas: dict[str, gpd.GeoDataFrame]) -> None:
    destino = projeto.camadas_gpkg
    destino.unlink(missing_ok=True)
    for nome, camada in camadas.items():
        camada.to_file(destino, layer=nome, driver="GPKG")
        print(f"  {nome}: {len(camada)} feições")


def ler(projeto: Projeto) -> dict[str, gpd.GeoDataFrame]:
    import pyogrio
    return {nome: gpd.read_file(projeto.camadas_gpkg, layer=nome)
            for nome, _ in pyogrio.list_layers(projeto.camadas_gpkg)}


def executar(projeto: Projeto) -> None:
    salvar(projeto, montar(projeto))
