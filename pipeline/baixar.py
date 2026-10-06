"""Etapa 1 — baixar as fontes externas para `dados/brutos/`.

Cada download é registrado em `dados/brutos/manifesto.json` com o endereço, o tamanho
e o hash SHA-256 do arquivo. Isso permite provar, depois, exatamente quais insumos
geraram uma versão do mapa (métrica D3).

O relevo não é baixado aqui: ele é lido direto da nuvem, em resolução reduzida, na
etapa `rasters` (baixar os blocos em resolução total ocuparia vários GB).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import Projeto

# nome local → seção do config/fontes.toml que tem a URL
ARQUIVOS = {
    "malha_municipal.zip": "malha_municipal",
    "populacao.json": "populacao",
    "cidades.csv": "cidades",
    "temperatura.zip": "temperatura",
}


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def baixar_arquivo(url: str, destino: Path) -> None:
    """Baixa em partes (não carrega o arquivo inteiro na memória) e só grava no fim."""
    temporario = destino.with_suffix(destino.suffix + ".parcial")
    with requests.get(url, stream=True, timeout=120) as resposta:
        resposta.raise_for_status()
        total = int(resposta.headers.get("content-length", 0))
        recebido = 0
        with open(temporario, "wb") as f:
            for bloco in resposta.iter_content(chunk_size=1 << 20):
                f.write(bloco)
                recebido += len(bloco)
                if total:
                    print(f"\r  {destino.name}: {recebido / total:5.1%}", end="", flush=True)
    print()
    temporario.replace(destino)


def baixar(projeto: Projeto, refazer: bool = False) -> None:
    projeto.brutos.mkdir(parents=True, exist_ok=True)
    caminho_manifesto = projeto.brutos / "manifesto.json"
    manifesto = json.loads(caminho_manifesto.read_text()) if caminho_manifesto.exists() else {}

    for nome, secao in ARQUIVOS.items():
        url = projeto.fontes[secao]["url"]
        destino = projeto.brutos / nome
        mesma_origem = manifesto.get(nome, {}).get("url") == url
        if destino.exists() and mesma_origem and not refazer:
            print(f"- {nome}: já existe, pulando (use --refazer para baixar de novo)")
            continue
        print(f"- {nome}: baixando de {url}")
        baixar_arquivo(url, destino)
        manifesto[nome] = {
            "url": url,
            "bytes": destino.stat().st_size,
            "sha256": sha256(destino),
            "baixado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        caminho_manifesto.write_text(json.dumps(manifesto, indent=2, ensure_ascii=False))
