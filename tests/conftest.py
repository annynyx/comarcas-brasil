"""Um "Brasil de mentira" com o mesmo formato dos arquivos oficiais.

Dois estados lado a lado, cada um com 4 quadrados de 0,5°:

    lon  -38      -37.5     -37      -36.5     -36
    lat -10 ┌────────┬────────┬────────┬────────┐
            │2800001 │2800002 │2700001 │2700002 │
       -10.5├────────┼────────┼────────┼────────┤
            │2800003 │2800004 │2700003 │ lagoa  │
       -11  └────────┴────────┴────────┴────────┘
                  SE (com comarcas)       AL (sem tabela)
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from pipeline.config import ALBERS_BRASIL, RAIZ, Projeto

MUNICIPIOS = [
    # código, nome, UF, coluna, linha
    ("2800001", "Aracaju", "SE", 0, 0),
    ("2800002", "Barra dos Coqueiros", "SE", 1, 0),
    ("2800003", "Estância", "SE", 0, 1),
    ("2800004", "Itabaiana", "SE", 1, 1),
    ("2700001", "Maceió", "AL", 2, 0),
    ("2700002", "Penedo", "AL", 3, 0),
    ("2700003", "Arapiraca", "AL", 2, 1),
    ("2799999", "Lagoa Fictícia", "AL", 3, 1),
]
LAGOA = "2799999"


def quadrado(coluna: int, linha: int):
    oeste, norte = -38 + coluna * 0.5, -10 - linha * 0.5
    return box(oeste, norte - 0.5, oeste + 0.5, norte)


def criar_malha(destino: Path) -> None:
    gdf = gpd.GeoDataFrame(
        {"CD_MUN": [m[0] for m in MUNICIPIOS], "NM_MUN": [m[1] for m in MUNICIPIOS],
         "SIGLA_UF": [m[2] for m in MUNICIPIOS], "NM_UF": ["x"] * len(MUNICIPIOS)},
        geometry=[quadrado(m[3], m[4]) for m in MUNICIPIOS], crs="EPSG:4674",
    )
    gdf["AREA_KM2"] = (gdf.to_crs(ALBERS_BRASIL).area / 1e6).round(3)
    pasta = destino.parent / "shp"
    pasta.mkdir()
    gdf.to_file(pasta / "BR_Municipios_TESTE.shp")
    with zipfile.ZipFile(destino, "w") as z:
        for arquivo in pasta.iterdir():
            z.write(arquivo, arquivo.name)
    shutil.rmtree(pasta)


def criar_populacao(destino: Path) -> None:
    series = [{"localidade": {"id": m[0], "nivel": {"id": "N6"}, "nome": m[1]},
               "serie": {"2022": str(10_000 * (i + 1))}}
              for i, m in enumerate(MUNICIPIOS) if m[0] != LAGOA]
    destino.write_text(json.dumps([{"id": "93", "variavel": "População residente",
                                    "resultados": [{"classificacoes": [], "series": series}]}]))


def criar_cidades(destino: Path) -> None:
    linhas = []
    for m in MUNICIPIOS:
        if m[0] == LAGOA:
            continue
        centro = quadrado(m[3], m[4]).centroid
        capital = int(m[1] in ("Aracaju", "Maceió"))
        linhas.append((m[0], m[1], centro.y, centro.x, capital, m[0][:2], 1, 79, "America/Maceio"))
    pd.DataFrame(linhas, columns=["codigo_ibge", "nome", "latitude", "longitude", "capital",
                                  "codigo_uf", "siafi_id", "ddd", "fuso_horario"]).to_csv(destino, index=False)


def criar_relevo(pasta: Path) -> None:
    """Blocos no padrão Copernicus (1°×1°): altitude cresce para oeste."""
    pasta.mkdir()
    nomes = []
    for lon in (-38, -37, -36):
        nome = f"Copernicus_DSM_COG_30_S11_00_W{abs(lon):03d}_00_DEM"
        nomes.append(nome)
        (pasta / nome).mkdir()
        x = np.linspace(lon, lon + 1, 120)
        dados = np.tile((-36 - x) * 500, (120, 1)).astype("float32")  # 0 m em -36, 1000 m em -38
        with rasterio.open(pasta / nome / f"{nome}.tif", "w", driver="GTiff", width=120, height=120,
                           count=1, dtype="float32", crs="EPSG:4326",
                           transform=from_origin(lon, -10, 1 / 120, 1 / 120)) as dst:
            dst.write(dados, 1)
    (pasta / "tileList.txt").write_text("\n".join(nomes + ["Copernicus_DSM_COG_30_N00_00_E006_00_DEM"]))


def criar_temperatura(destino: Path, nome_no_zip: str) -> None:
    """Grade global alinhada como a do WorldClim (1/12°), cobrindo só a região do teste."""
    res = 1 / 12
    largura, altura = 72, 84  # lon -40…-34, lat -7…-14
    lat = -7 - (np.arange(altura) + 0.5) * res
    dados = np.repeat((20 + (-7 - lat)).astype("float32")[:, None], largura, axis=1)  # mais quente ao sul
    tif = destino.parent / nome_no_zip
    with rasterio.open(tif, "w", driver="GTiff", width=largura, height=altura, count=1,
                       dtype="float32", crs="EPSG:4326", nodata=-3.4e38,
                       transform=from_origin(-40, -7, res, res)) as dst:
        dst.write(dados, 1)
    with zipfile.ZipFile(destino, "w") as z:
        z.write(tif, nome_no_zip)
    tif.unlink()


def criar_comarcas_se(pasta: Path) -> None:
    (pasta / "SE").mkdir(parents=True)
    (pasta / "SE" / "comarcas.csv").write_text(
        "comarca_id,nome,uf,tribunal,entrancia,fonte,data_verificacao\n"
        "2800001,Aracaju,SE,TJSE,final,teste,2026-10-01\n"
        "2800004,Itabaiana,SE,TJSE,intermediaria,teste,2026-10-01\n")
    (pasta / "SE" / "municipios.csv").write_text(
        "codigo_ibge,municipio,comarca_id\n"
        "2800001,Aracaju,2800001\n2800002,Barra dos Coqueiros,2800001\n"
        "2800003,Estancia,2800004\n2800004,Itabaiana,2800004\n")


@pytest.fixture
def projeto(tmp_path: Path) -> Projeto:
    fontes = (RAIZ / "config" / "fontes.toml").read_text(encoding="utf-8")
    fontes = fontes.replace('nao_municipios = ["4300001", "4300002"]', f'nao_municipios = ["{LAGOA}"]')
    fontes = fontes.replace('url_base = "https://copernicus-dem-90m.s3.amazonaws.com"',
                            f'url_base = "{tmp_path / "copernicus"}"')
    fontes = fontes.replace("resolucao_graus = 0.01", "resolucao_graus = 0.05")
    fontes = fontes.replace("largura_imagem_raster = 2048", "largura_imagem_raster = 128")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "fontes.toml").write_text(fontes, encoding="utf-8")
    projeto = Projeto.em(tmp_path, tmp_path / "config")
    assert str(tmp_path) in str(projeto.fontes["relevo"]["url_base"]), "substituição do config falhou"

    projeto.brutos.mkdir(parents=True)
    criar_malha(projeto.brutos / "malha_municipal.zip")
    criar_populacao(projeto.brutos / "populacao.json")
    criar_cidades(projeto.brutos / "cidades.csv")
    criar_temperatura(projeto.brutos / "temperatura.zip", projeto.fontes["temperatura"]["arquivo_no_zip"])
    criar_relevo(tmp_path / "copernicus")
    criar_comarcas_se(projeto.tabelas_comarcas)
    return projeto
