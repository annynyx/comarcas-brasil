"""Onde ficam os arquivos e quais fontes externas usamos.

Tudo que depende de caminho passa por um objeto `Projeto`. Assim os testes conseguem
rodar o pipeline inteiro numa pasta temporária, com dados de mentira.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Nome de cada UF a partir da sigla. Fixo de propósito: não depende do ano da malha.
NOMES_UF = {
    "RO": "Rondônia", "AC": "Acre", "AM": "Amazonas", "RR": "Roraima", "PA": "Pará",
    "AP": "Amapá", "TO": "Tocantins", "MA": "Maranhão", "PI": "Piauí", "CE": "Ceará",
    "RN": "Rio Grande do Norte", "PB": "Paraíba", "PE": "Pernambuco", "AL": "Alagoas",
    "SE": "Sergipe", "BA": "Bahia", "MG": "Minas Gerais", "ES": "Espírito Santo",
    "RJ": "Rio de Janeiro", "SP": "São Paulo", "PR": "Paraná", "SC": "Santa Catarina",
    "RS": "Rio Grande do Sul", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "GO": "Goiás", "DF": "Distrito Federal",
}

# O primeiro dígito do código IBGE indica a grande região.
REGIOES = {"1": "Norte", "2": "Nordeste", "3": "Sudeste", "4": "Sul", "5": "Centro-Oeste"}

# Projeção cônica de Albers com os parâmetros usados pelo IBGE para o Brasil.
# Preserva áreas — use-a sempre que precisar MEDIR área (nunca em graus).
ALBERS_BRASIL = "+proj=aea +lat_0=-12 +lon_0=-54 +lat_1=-2 +lat_2=-22 +ellps=GRS80 +units=m +no_defs"


@dataclass(frozen=True)
class Projeto:
    fontes: dict
    paletas: dict
    brutos: Path            # downloads (fora do Git)
    tabelas_comarcas: Path  # dados/fontes/<UF>/*.csv (fonte da verdade, no Git)
    intermediario: Path     # resultados entre etapas (fora do Git)
    dist: Path              # arquivos finais para GIS/análise (fora do Git)
    web_dados: Path         # arquivos leves para o visualizador (fora do Git)

    @classmethod
    def padrao(cls) -> "Projeto":
        return cls.em(RAIZ, RAIZ / "config")

    @classmethod
    def em(cls, raiz: Path, pasta_config: Path) -> "Projeto":
        with open(pasta_config / "fontes.toml", "rb") as f:
            fontes = tomllib.load(f)
        paletas = json.loads((RAIZ / "config" / "paletas.json").read_text(encoding="utf-8"))
        return cls(
            fontes=fontes,
            paletas=paletas,
            brutos=raiz / "dados" / "brutos",
            tabelas_comarcas=raiz / "dados" / "fontes",
            intermediario=raiz / "dados" / "intermediario",
            dist=raiz / "dist",
            web_dados=raiz / "web" / "public" / "dados",
        )

    # Arquivos que passam de uma etapa para outra
    @property
    def camadas_gpkg(self) -> Path:
        return self.intermediario / "camadas.gpkg"

    @property
    def pasta_rasters(self) -> Path:
        return self.dist / "rasters"
