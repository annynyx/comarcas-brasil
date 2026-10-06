"""Estatísticas zonais: resumir um raster dentro de cada polígono.

Exemplo: "altitude média do município X" = média dos pixels de relevo que caem dentro do
polígono X. Usamos o `exactextract`, que considera a FRAÇÃO de cada pixel coberta pelo
polígono. Isso importa para municípios pequenos, menores que um pixel de temperatura
(~9 km): uma ferramenta que só conta pixels "inteiros" devolveria vazio para eles.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import rasterio
from exactextract import exact_extract

# raster → (prefixo da coluna, operações)
OPERACOES = {
    "relevo": ("altitude", {"mean": "media", "min": "min", "max": "max"}),
    "temperatura": ("temperatura", {"mean": "media"}),
}


def por_area(camada: gpd.GeoDataFrame, chave: str, rasters: dict[str, Path]) -> pd.DataFrame:
    vetor = camada[[chave, "geometry"]].to_crs("EPSG:4326")
    resultado = camada[[chave]].copy()
    for nome, caminho in rasters.items():
        prefixo, ops = OPERACOES[nome]
        tabela = exact_extract(str(caminho), vetor, list(ops), include_cols=[chave], output="pandas")
        tabela = tabela.rename(columns={op: f"{prefixo}_{sufixo}" for op, sufixo in ops.items()})
        resultado = resultado.merge(tabela, on=chave, how="left")
    return resultado.round(1)


def por_ponto(pontos: gpd.GeoDataFrame, rasters: dict[str, Path]) -> pd.DataFrame:
    """Valor do pixel exatamente onde fica cada ponto (ex.: altitude da sede da cidade)."""
    geometrias = pontos.to_crs("EPSG:4326").geometry
    xy = list(zip(geometrias.x, geometrias.y))
    resultado = pd.DataFrame(index=pontos.index)
    for nome, caminho in rasters.items():
        prefixo, _ = OPERACOES[nome]
        with rasterio.open(caminho) as src:
            valores = [v[0] for v in src.sample(xy)]
            resultado[f"{prefixo}_sede"] = [None if v == src.nodata else round(float(v), 1)
                                            for v in valores]
    return resultado
