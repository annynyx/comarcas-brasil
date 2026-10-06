"""Etapa 5 — versões leves para a web.

1. Simplifica todas as camadas de área JUNTAS com o mapshaper. Como elas compartilham as
   mesmas linhas (arcos), a divisa simplificada entre dois estados continua sendo
   exatamente a borda simplificada dos municípios dali: nada de frestas ou sobreposições.
2. Gera imagens (WebP) de relevo e temperatura projetadas em Web Mercator, a projeção
   usada pelos mapas da web.
3. Escreve `catalogo.json`, que descreve camadas, métricas e fontes para o visualizador.

Saída completa em `dist/web/`; o que o visualizador usa é copiado para `web/public/dados/`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
from affine import Affine
from PIL import Image
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

from .config import RAIZ, Projeto
from .exportar import CHAVES
from .rasters import NODATA

CAMADAS_DE_AREA = ["pais", "regioes", "ufs", "comarcas", "municipios"]

TITULOS = {
    "pais": "País",
    "regioes": "Regiões",
    "ufs": "Estados",
    "comarcas": "Comarcas",
    "municipios": "Municípios",
    "cidades": "Cidades (sedes municipais)",
}

# coluna → (rótulo, unidade). Só entram no catálogo as que existirem na camada.
METRICAS = {
    "populacao": ("População (Censo 2022)", "hab."),
    "densidade": ("Densidade demográfica", "hab./km²"),
    "area_km2": ("Área", "km²"),
    "n_municipios": ("Nº de municípios", ""),
    "altitude_media": ("Altitude média", "m"),
    "temperatura_media": ("Temperatura média anual", "°C"),
}

RASTERS = {
    "relevo": {"arquivo": "relevo.tif", "titulo": "Relevo (altitude)", "unidade": "m", "sombrear": True},
    "temperatura": {"arquivo": "temperatura_media_anual.tif", "titulo": "Temperatura média anual",
                    "unidade": "°C", "sombrear": False},
}


# ------------------------------------------------------------------ vetores (mapshaper)

def mapshaper() -> str:
    binario = RAIZ / "node_modules" / ".bin" / "mapshaper-xl"
    if not binario.exists():
        raise SystemExit("mapshaper não encontrado — rode `npm ci` na raiz do projeto.")
    return str(binario)


def propriedades(camada: gpd.GeoDataFrame) -> dict[str, dict]:
    """id → atributos, já em tipos que o JSON aceita (NaN vira null)."""
    tabela = pd.DataFrame(camada.drop(columns="geometry"))
    tabela = tabela.astype(object).where(tabela.notna(), None)
    chave = CHAVES[camada.attrs["nome"]]
    return {str(linha[chave]): linha for linha in tabela.to_dict("records")}


def simplificar(projeto: Projeto, camadas: dict[str, gpd.GeoDataFrame], destino: Path) -> dict[str, Path]:
    temporario = projeto.intermediario / "web"
    shutil.rmtree(temporario, ignore_errors=True)
    temporario.mkdir(parents=True)

    entradas = []
    for nome in CAMADAS_DE_AREA:
        if nome not in camadas:
            continue
        camada = camadas[nome]
        # Só o id vai para o mapshaper; os atributos voltam depois (evita o limite de
        # 10 caracteres nos nomes de coluna do shapefile).
        so_id = gpd.GeoDataFrame({"id": camada[CHAVES[nome]].astype(str)},
                                 geometry=camada.geometry).to_crs("EPSG:4326")
        caminho = temporario / f"{nome}.shp"
        so_id.to_file(caminho, driver="ESRI Shapefile")
        entradas.append(str(caminho))

    saidas = {}
    for resolucao, metros in projeto.fontes["web"]["resolucoes"].items():
        topojson = destino / f"brasil_{resolucao}.topojson"
        pasta_geojson = destino / resolucao
        pasta_geojson.mkdir(parents=True, exist_ok=True)
        comando = [
            mapshaper(), "-i", *entradas, "combine-files",
            "-simplify", f"interval={metros}", "keep-shapes",
            "-o", "format=topojson", "quantization=100000", str(topojson),
            "-o", "format=geojson", "precision=0.00001", "extension=.geojson", f"{pasta_geojson}/",
        ]
        print(f"  mapshaper ({resolucao}, bordas movem no máximo ~{metros} m)")
        subprocess.run(comando, check=True, capture_output=True, text=True)
        saidas[resolucao] = topojson

        # Recoloca os atributos completos em cada feição
        tabelas = {nome: propriedades(camadas[nome]) for nome in CAMADAS_DE_AREA if nome in camadas}
        topo = json.loads(topojson.read_text())
        for nome, objeto in topo["objects"].items():
            for geometria in objeto["geometries"]:
                geometria["properties"] = tabelas[nome][geometria["properties"]["id"]]
        topojson.write_text(json.dumps(topo, ensure_ascii=False, separators=(",", ":")))
        for nome in tabelas:
            arquivo = pasta_geojson / f"{nome}.geojson"
            geo = json.loads(arquivo.read_text())
            for feicao in geo["features"]:
                feicao["properties"] = tabelas[nome][feicao["properties"]["id"]]
            arquivo.write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")))
    return saidas


def salvar_cidades(cidades: gpd.GeoDataFrame, destino: Path) -> Path:
    cidades = cidades.to_crs("EPSG:4326")
    feicoes = []
    for (_, linha), ponto in zip(pd.DataFrame(cidades.drop(columns="geometry")).iterrows(), cidades.geometry):
        props = {k: (None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)) for k, v in linha.items()}
        feicoes.append({"type": "Feature", "properties": props,
                        "geometry": {"type": "Point", "coordinates": [round(ponto.x, 5), round(ponto.y, 5)]}})
    arquivo = destino / "cidades.geojson"
    arquivo.write_text(json.dumps({"type": "FeatureCollection", "features": feicoes},
                                  ensure_ascii=False, separators=(",", ":")))
    return arquivo


# ------------------------------------------------------------------- rasters (imagens)

def colorir(valores: np.ndarray, paleta: list[str], minimo: float, maximo: float) -> np.ndarray:
    """Interpola linearmente entre as cores da paleta (claro = mínimo, escuro = máximo)."""
    cores = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in paleta], dtype=float)
    posicao = np.clip((valores - minimo) / (maximo - minimo), 0, 1) * (len(paleta) - 1)
    baixo = np.floor(posicao).astype(int)
    alto = np.minimum(baixo + 1, len(paleta) - 1)
    fracao = (posicao - baixo)[..., None]
    return cores[baixo] * (1 - fracao) + cores[alto] * fracao


def sombreamento(altitude: np.ndarray, transform: Affine, exagero: float = 4.0) -> np.ndarray:
    """Relevo sombreado (luz vinda do noroeste, 45° acima do horizonte). Retorna 0–1.

    Em Web Mercator o pixel "estica" longe do Equador; corrigimos multiplicando o
    tamanho do pixel pelo cosseno da latitude de cada linha.
    """
    linhas = np.arange(altitude.shape[0])
    y_merc = transform.f + (linhas + 0.5) * transform.e
    latitude = np.degrees(2 * np.arctan(np.exp(y_merc / 6378137.0)) - np.pi / 2)
    escala = np.cos(np.radians(latitude))[:, None]
    dz_dx = np.gradient(altitude, axis=1) / (transform.a * escala)
    dz_dy = np.gradient(altitude, axis=0) / (-transform.e * escala)  # para o sul
    declividade = np.arctan(exagero * np.hypot(dz_dx, dz_dy))
    orientacao = np.arctan2(dz_dy, -dz_dx)
    azimute, zenite = np.radians(360 - 315 + 90), np.radians(90 - 45)
    luz = (np.cos(zenite) * np.cos(declividade)
           + np.sin(zenite) * np.sin(declividade) * np.cos(azimute - orientacao))
    return np.clip(luz, 0, 1)


def imagem_web(tif: Path, destino: Path, paleta: list[str], largura: int, sombrear: bool) -> dict:
    with rasterio.open(tif) as src:
        transform, w, h = calculate_default_transform(src.crs, "EPSG:3857", src.width, src.height,
                                                      *src.bounds)
        altura = round(h * largura / w)
        transform = transform @ Affine.scale(w / largura, h / altura)
        dados = np.full((altura, largura), NODATA, dtype="float32")
        reproject(rasterio.band(src, 1), dados, dst_transform=transform, dst_crs="EPSG:3857",
                  src_nodata=NODATA, dst_nodata=NODATA, resampling=Resampling.average)

    valido = dados != NODATA
    # Percentis 1–99: um pico isolado não "achata" as cores do resto do país
    minimo, maximo = (float(v) for v in np.percentile(dados[valido], [1, 99]))
    rgb = colorir(dados, paleta, minimo, maximo)
    if sombrear:
        luz = sombreamento(np.where(valido, dados, 0), transform)
        rgb = rgb * (0.45 + 0.55 * luz)[..., None]
    rgba = np.dstack([np.clip(rgb, 0, 255), valido * 255]).astype("uint8")
    Image.fromarray(rgba, "RGBA").save(destino, "WEBP", quality=85, method=6)

    para_lonlat = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    oeste, norte = para_lonlat.transform(transform.c, transform.f)
    leste, sul = para_lonlat.transform(transform.c + largura * transform.a, transform.f + altura * transform.e)
    return {
        "imagem": destino.name,
        # cantos: superior-esquerdo, superior-direito, inferior-direito, inferior-esquerdo
        "coordenadas": [[oeste, norte], [leste, norte], [leste, sul], [oeste, sul]],
        "minimo": round(minimo, 1),
        "maximo": round(maximo, 1),
        "paleta": paleta,
    }


# ------------------------------------------------------------------------------ catálogo

def atribuicoes(projeto: Projeto, tem_rasters: set[str]) -> list[str]:
    f = projeto.fontes
    itens = [f"Limites: IBGE, malha municipal {f['malha_municipal']['ano']}",
             "População: IBGE, Censo 2022",
             "Comarcas: Tribunais de Justiça (tabelas do projeto)",
             "Cidades: kelvins/municipios-brasileiros"]
    if "relevo" in tem_rasters:
        itens.append("Relevo: Copernicus DEM GLO-90 © DLR e.V. / Airbus, programa Copernicus")
    if "temperatura" in tem_rasters:
        itens.append("Temperatura: WorldClim 2.1 (Fick & Hijmans, 2017)")
    return itens


def executar(projeto: Projeto) -> None:
    gpkg = projeto.dist / "brasil.gpkg"
    camadas = {}
    for nome, _ in pyogrio.list_layers(gpkg):
        camadas[nome] = gpd.read_file(gpkg, layer=nome)
        camadas[nome].attrs["nome"] = nome

    destino = projeto.dist / "web"
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)

    topojsons = simplificar(projeto, camadas, destino)
    cidades = salvar_cidades(camadas["cidades"], destino)

    catalogo = {"resolucoes": {r: p.name for r, p in topojsons.items()}, "camadas": [], "rasters": []}
    for nome in [*CAMADAS_DE_AREA, "cidades"]:
        if nome not in camadas:
            continue
        colunas = camadas[nome].columns
        catalogo["camadas"].append({
            "id": nome,
            "titulo": TITULOS[nome],
            "tipo": "ponto" if nome == "cidades" else "area",
            "chave": CHAVES[nome],
            "metricas": [{"coluna": c, "rotulo": r, "unidade": u}
                         for c, (r, u) in METRICAS.items() if c in colunas],
        })

    for nome, cfg in RASTERS.items():
        tif = projeto.pasta_rasters / cfg["arquivo"]
        if not tif.exists():
            continue
        print(f"  imagem web: {nome}")
        info = imagem_web(tif, destino / f"{nome}.webp", projeto.paletas[nome],
                          projeto.fontes["web"]["largura_imagem_raster"], cfg["sombrear"])
        catalogo["rasters"].append({"id": nome, "titulo": cfg["titulo"], "unidade": cfg["unidade"], **info})

    catalogo["paleta_metricas"] = projeto.paletas["metricas"]
    catalogo["atribuicoes"] = atribuicoes(projeto, {r["id"] for r in catalogo["rasters"]})
    (destino / "catalogo.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=2))

    # O visualizador só precisa destes arquivos
    shutil.rmtree(projeto.web_dados, ignore_errors=True)
    projeto.web_dados.mkdir(parents=True)
    for arquivo in [*topojsons.values(), cidades, destino / "catalogo.json",
                    *(destino / r["imagem"] for r in catalogo["rasters"])]:
        shutil.copy2(arquivo, projeto.web_dados / arquivo.name)
    print(f"  arquivos do visualizador em {projeto.web_dados}")

