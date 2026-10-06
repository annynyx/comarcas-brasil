"""Etapa 3 — rasters de relevo e temperatura recortados para o Brasil.

Vetor x raster, em uma frase: as camadas anteriores são POLÍGONOS (linhas que fecham uma
área); relevo e temperatura são GRADES de pixels, cada pixel com um número (metros ou °C).

Saídas em `dist/rasters/` (GeoTIFF, EPSG:4326, fora do Brasil = sem dado):
- relevo.tif — altitude em metros (Copernicus GLO-90, reamostrado)
- temperatura_media_anual.tif — °C (WorldClim 2.1, BIO1)
"""

from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.warp import reproject
from shapely.geometry import box
from shapely.prepared import prep

from . import camadas as mod_camadas
from .config import Projeto

NODATA = -9999.0

# Evita que o GDAL liste diretórios remotos a cada arquivo aberto (muito mais rápido na nuvem).
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")


def grade(limites: tuple[float, float, float, float], resolucao: float):
    """Grade regular que cobre `limites`, com bordas em múltiplos exatos da resolução."""
    oeste, sul, leste, norte = limites
    oeste = math.floor(oeste / resolucao) * resolucao
    sul = math.floor(sul / resolucao) * resolucao
    leste = math.ceil(leste / resolucao) * resolucao
    norte = math.ceil(norte / resolucao) * resolucao
    largura = round((leste - oeste) / resolucao)
    altura = round((norte - sul) / resolucao)
    return from_origin(oeste, norte, resolucao, resolucao), largura, altura


def salvar_tif(destino: Path, dados: np.ndarray, transform) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    perfil = dict(driver="GTiff", dtype="float32", count=1, width=dados.shape[1],
                  height=dados.shape[0], crs="EPSG:4326", transform=transform, nodata=NODATA,
                  compress="deflate", predictor=3, tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(destino, "w", **perfil) as dst:
        dst.write(dados.astype("float32"), 1)


def recortar(dados: np.ndarray, transform, contorno) -> np.ndarray:
    """Apaga (vira NODATA) tudo o que estiver fora do contorno do Brasil."""
    fora = geometry_mask([contorno], out_shape=dados.shape, transform=transform)
    dados[fora] = NODATA
    return dados


# ----------------------------------------------------------------------------- relevo

def nome_bloco(lat: int, lon: int) -> str:
    """Nome do bloco Copernicus de 1°×1° cujo canto sudoeste é (lat, lon)."""
    ns = "N" if lat >= 0 else "S"
    lo = "E" if lon >= 0 else "W"
    return f"Copernicus_DSM_COG_30_{ns}{abs(lat):02d}_00_{lo}{abs(lon):03d}_00_DEM"


def ler_texto(url_ou_caminho: str) -> str:
    if url_ou_caminho.startswith("http"):
        resposta = requests.get(url_ou_caminho, timeout=60)
        resposta.raise_for_status()
        return resposta.text
    return Path(url_ou_caminho).read_text()


def construir_relevo(projeto: Projeto, contorno) -> Path:
    cfg = projeto.fontes["relevo"]
    base, resolucao = cfg["url_base"], cfg["resolucao_graus"]
    # Grade alinhada a graus inteiros, para cada bloco de 1° caber exatamente nela
    o, s, l, n = (math.floor(v) if i < 2 else math.ceil(v) for i, v in enumerate(contorno.bounds))
    transform, largura, altura = grade((o, s, l, n), resolucao)
    px_por_grau = round(1 / resolucao)

    # Só os blocos que tocam o Brasil e que existem (no oceano não há bloco)
    existentes = set(ler_texto(f"{base}/tileList.txt").split())
    contorno_preparado = prep(contorno)
    blocos = [(lat, lon)
              for lat in range(s, n)
              for lon in range(o, l)
              if nome_bloco(lat, lon) in existentes
              and contorno_preparado.intersects(box(lon, lat, lon + 1, lat + 1))]
    print(f"  relevo: lendo {len(blocos)} blocos de 1°×1° a ~{resolucao * 111:.1f} km/pixel")

    def ler_bloco(lat_lon):
        lat, lon = lat_lon
        nome = nome_bloco(lat, lon)
        with rasterio.open(f"{base}/{nome}/{nome}.tif") as ds:
            # Pedir uma grade pequena faz o GDAL usar as "overviews" internas do arquivo:
            # só os bytes da versão reduzida trafegam pela rede.
            return lat, lon, ds.read(1, out_shape=(px_por_grau, px_por_grau),
                                     resampling=Resampling.average)

    mosaico = np.full((altura, largura), NODATA, dtype="float32")
    with ThreadPoolExecutor(max_workers=16) as executor:
        for i, (lat, lon, dados) in enumerate(executor.map(ler_bloco, blocos), start=1):
            linha = (n - (lat + 1)) * px_por_grau
            coluna = (lon - o) * px_por_grau
            mosaico[linha:linha + px_por_grau, coluna:coluna + px_por_grau] = dados
            if i % 50 == 0 or i == len(blocos):
                print(f"\r  relevo: {i}/{len(blocos)} blocos", end="", flush=True)
    print()

    destino = projeto.pasta_rasters / "relevo.tif"
    salvar_tif(destino, recortar(mosaico, transform, contorno), transform)
    return destino


# ------------------------------------------------------------------------ temperatura

def construir_temperatura(projeto: Projeto, contorno) -> Path:
    cfg = projeto.fontes["temperatura"]
    caminho = f"zip://{projeto.brutos / 'temperatura.zip'}!{cfg['arquivo_no_zip']}"
    with rasterio.open(caminho) as src:
        transform, largura, altura = grade(contorno.bounds, src.res[0])
        dados = np.full((altura, largura), NODATA, dtype="float32")
        # Mesma resolução e grade alinhada → "nearest" só copia os pixels, sem inventar valores.
        reproject(rasterio.band(src, 1), dados, dst_transform=transform, dst_crs="EPSG:4326",
                  dst_nodata=NODATA, resampling=Resampling.nearest)
    destino = projeto.pasta_rasters / "temperatura_media_anual.tif"
    salvar_tif(destino, recortar(dados, transform, contorno), transform)
    return destino


def executar(projeto: Projeto, apenas: str | None = None) -> None:
    pais = mod_camadas.ler(projeto)["pais"].to_crs("EPSG:4326")
    contorno = pais.geometry.iloc[0]
    if apenas in (None, "relevo"):
        print("Relevo…")
        construir_relevo(projeto, contorno)
    if apenas in (None, "temperatura"):
        print("Temperatura…")
        construir_temperatura(projeto, contorno)
