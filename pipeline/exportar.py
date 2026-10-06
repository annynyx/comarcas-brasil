"""Etapa 4 — juntar estatísticas e gravar os arquivos finais em `dist/`.

    dist/brasil.gpkg             todas as camadas, resolução total (QGIS, ArcGIS)
    dist/parquet/<camada>.parquet  GeoParquet, resolução total (pandas, DuckDB, BigQuery)
    dist/tabelas/<camada>.csv    só os atributos, sem geometria (Excel, BI)
    dist/tabelas/municipio_comarca.csv  a tabela de ligação para cruzar qualquer dado
"""

from __future__ import annotations

import geopandas as gpd

from . import camadas as mod_camadas
from . import estatisticas
from .config import Projeto

# Coluna que identifica cada feição, por camada
CHAVES = {
    "pais": "nome",
    "regioes": "nome",
    "ufs": "uf",
    "comarcas": "comarca_id",
    "municipios": "codigo_ibge",
    "cidades": "codigo_ibge",
}


def rasters_disponiveis(projeto: Projeto) -> dict:
    candidatos = {
        "relevo": projeto.pasta_rasters / "relevo.tif",
        "temperatura": projeto.pasta_rasters / "temperatura_media_anual.tif",
    }
    return {nome: caminho for nome, caminho in candidatos.items() if caminho.exists()}


def com_estatisticas(projeto: Projeto) -> dict[str, gpd.GeoDataFrame]:
    camadas = mod_camadas.ler(projeto)
    rasters = rasters_disponiveis(projeto)
    if not rasters:
        print("  aviso: nenhum raster em dist/rasters/ — rode `make rasters` para ter altitude e temperatura")
        return camadas
    for nome, camada in camadas.items():
        print(f"  estatísticas de {', '.join(rasters)} para {nome}…")
        if nome == "cidades":
            extra = estatisticas.por_ponto(camada, rasters)
            camadas[nome] = camada.join(extra)
        else:
            extra = estatisticas.por_area(camada, CHAVES[nome], rasters)
            camadas[nome] = camada.merge(extra, on=CHAVES[nome], how="left")
    return camadas


def executar(projeto: Projeto) -> None:
    camadas = com_estatisticas(projeto)
    (projeto.dist / "parquet").mkdir(parents=True, exist_ok=True)
    (projeto.dist / "tabelas").mkdir(parents=True, exist_ok=True)
    gpkg = projeto.dist / "brasil.gpkg"
    gpkg.unlink(missing_ok=True)

    for nome, camada in camadas.items():
        camada = camada[[c for c in camada.columns if c != "geometry"] + ["geometry"]]
        camada.to_file(gpkg, layer=nome, driver="GPKG")
        camada.to_parquet(projeto.dist / "parquet" / f"{nome}.parquet")
        camada.drop(columns="geometry").to_csv(projeto.dist / "tabelas" / f"{nome}.csv", index=False)
        print(f"  {nome}: {len(camada)} feições")

    municipios = camadas["municipios"]
    ligacao = municipios[["codigo_ibge", "nome", "uf", "comarca_id"]].rename(columns={"nome": "municipio"})
    if "comarcas" in camadas:
        nomes = camadas["comarcas"].set_index("comarca_id")["nome"]
        ligacao["comarca"] = ligacao.comarca_id.map(nomes)
    ligacao.to_csv(projeto.dist / "tabelas" / "municipio_comarca.csv", index=False)
