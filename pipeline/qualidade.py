"""Etapa 6 — relatório de qualidade (as métricas de docs/02-metricas.md).

Gera `dist/relatorio_qualidade.md` (para ler) e `dist/relatorio_qualidade.json` (para
máquinas/CI). Os erros graves de dados já interromperam o build na etapa `camadas`;
aqui medimos o resultado final.
"""

from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

import geopandas as gpd
import pyogrio

from .config import ALBERS_BRASIL, Projeto

# CNJ, Justiça em Números 2025 (ano-base 2024): municípios que são sede de comarca
SEDES_CNJ = 2564

LIMITES = {
    "B3_desvio_area_total_pct": 0.01,
    "B4_desvio_area_simplificada_pct": 1.0,
    "C1_baixa_gzip_mb": 1.0,
    "C2_media_gzip_mb": 3.0,
}


def tamanho_gzip_mb(arquivo: Path) -> float:
    return round(len(gzip.compress(arquivo.read_bytes(), compresslevel=6)) / 1e6, 2)


def desvio_area_pct(ufs: gpd.GeoDataFrame) -> float:
    """Maior diferença (%) entre a área medida do polígono e a área oficial somada do IBGE."""
    medida = ufs.to_crs(ALBERS_BRASIL).area / 1e6
    return round(float(((medida - ufs.area_km2).abs() / ufs.area_km2 * 100).max()), 4)


def medir(projeto: Projeto) -> list[dict]:
    gpkg = projeto.dist / "brasil.gpkg"
    camadas = {nome: gpd.read_file(gpkg, layer=nome) for nome, _ in pyogrio.list_layers(gpkg)}
    itens = []

    def item(codigo, descricao, valor, ok: bool | None, detalhe=""):
        status = "info" if ok is None else ("ok" if ok else "atenção")
        itens.append({"metrica": codigo, "descricao": descricao, "valor": valor,
                      "status": status, "detalhe": detalhe})

    # --- A. Dados
    problemas = json.loads((projeto.intermediario / "problemas.json").read_text(encoding="utf-8"))
    avisos = Counter(p["regra"] for p in problemas if p["gravidade"] == "aviso")
    ufs = camadas["ufs"]
    com_comarcas = sorted(ufs.loc[ufs.tem_comarcas.astype(bool), "uf"])
    item("A1", "UFs com tabela de comarcas completa", f"{len(com_comarcas)}/{len(ufs)}",
         len(com_comarcas) == len(ufs), ", ".join(com_comarcas) or "nenhuma ainda")
    item("A2–A5, A8", "Erros nas tabelas de comarcas", 0, True, "o build para se houver qualquer erro")
    for regra, descricao in (("A9", "Comarcas com verificação vencida (> 12 meses)"),
                             ("A10", "Nomes de município diferentes do IBGE")):
        item(regra, descricao, avisos.get(regra, 0), avisos.get(regra, 0) == 0)
    if "comarcas" in camadas:
        sedes = len(camadas["comarcas"])
        item("A7", "Sedes de comarca × CNJ (Justiça em Números 2025)", f"{sedes} / {SEDES_CNJ}", None,
             "só comparável quando as 27 UFs estiverem completas")
    sem_pop = int(camadas["municipios"].populacao.isna().sum())
    item("pop", "Municípios sem população", sem_pop, sem_pop == 0)

    # --- B. Geometria
    invalidas = {n: int((~c.geometry.is_valid).sum()) for n, c in camadas.items()}
    item("B1", "Geometrias inválidas (resolução total)", sum(invalidas.values()),
         sum(invalidas.values()) == 0, ", ".join(f"{n}: {v}" for n, v in invalidas.items() if v))
    desvio = desvio_area_pct(ufs)
    item("B3", "Maior desvio de área por UF, resolução total (%)", desvio,
         desvio < LIMITES["B3_desvio_area_total_pct"])
    for resolucao in projeto.fontes["web"]["resolucoes"]:
        arquivo = projeto.dist / "web" / resolucao / "ufs.geojson"
        if arquivo.exists():
            desvio = desvio_area_pct(gpd.read_file(arquivo))
            item("B4", f"Maior desvio de área por UF, resolução {resolucao} (%)", desvio,
                 desvio < LIMITES["B4_desvio_area_simplificada_pct"])
    if "comarcas" in camadas:
        partes = camadas["comarcas"].geometry.apply(lambda g: len(getattr(g, "geoms", [g])))
        separadas = camadas["comarcas"].loc[partes > 1, "nome"].tolist()
        item("B5", "Comarcas em mais de um pedaço (revisar: ilha ou erro?)", len(separadas),
             len(separadas) == 0, ", ".join(separadas[:20]))

    # --- C. Entrega
    for codigo, resolucao, limite in (("C1", "baixa", "C1_baixa_gzip_mb"), ("C2", "media", "C2_media_gzip_mb")):
        arquivo = projeto.dist / "web" / f"brasil_{resolucao}.topojson"
        if arquivo.exists():
            mb = tamanho_gzip_mb(arquivo)
            item(codigo, f"brasil_{resolucao}.topojson comprimido (MB)", mb, mb <= LIMITES[limite],
                 f"meta ≤ {LIMITES[limite]} MB")

    # --- D. Reprodutibilidade
    manifesto = projeto.brutos / "manifesto.json"
    entradas = json.loads(manifesto.read_text()) if manifesto.exists() else {}
    item("D3", "Insumos com hash registrado", len(entradas), len(entradas) > 0,
         ", ".join(f"{k} ({v['sha256'][:12]}…)" for k, v in entradas.items()))
    return itens


def executar(projeto: Projeto) -> None:
    itens = medir(projeto)
    (projeto.dist / "relatorio_qualidade.json").write_text(
        json.dumps(itens, indent=2, ensure_ascii=False), encoding="utf-8")

    simbolo = {"ok": "✅", "atenção": "⚠️", "info": "ℹ️"}
    linhas = ["# Relatório de qualidade", "",
              "Métricas definidas em `docs/02-metricas.md`.", "",
              "| Métrica | Descrição | Valor | Status | Detalhe |", "|---|---|---|---|---|"]
    for i in itens:
        linhas.append(f"| {i['metrica']} | {i['descricao']} | {i['valor']} | "
                      f"{simbolo[i['status']]} {i['status']} | {i['detalhe']} |")
    texto = "\n".join(linhas) + "\n"
    (projeto.dist / "relatorio_qualidade.md").write_text(texto, encoding="utf-8")
    print(texto)
