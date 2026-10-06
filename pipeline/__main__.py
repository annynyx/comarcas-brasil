"""Linha de comando do pipeline: `python -m pipeline <etapa>` (ou `make <etapa>`)."""

from __future__ import annotations

import argparse
import time

from . import baixar, camadas, exportar, qualidade, rasters, web
from .config import Projeto

ETAPAS = {
    "baixar": "baixa malha do IBGE, população, cidades e temperatura para dados/brutos/",
    "camadas": "valida as tabelas de comarcas e monta país, regiões, estados, comarcas, municípios e cidades",
    "rasters": "gera relevo e temperatura recortados para o Brasil (dist/rasters/)",
    "exportar": "calcula altitude/temperatura por área e grava dist/ (GeoPackage, GeoParquet, CSV)",
    "web": "simplifica as camadas e gera os arquivos do visualizador (dist/web/ e web/public/dados/)",
    "qualidade": "mede o resultado e escreve dist/relatorio_qualidade.md",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline",
        description="Gera o mapa base do Brasil a partir de fontes públicas.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Etapas, na ordem:\n" + "\n".join(f"  {e:<10} {d}" for e, d in ETAPAS.items())
               + "\n  tudo       todas as etapas acima, na ordem",
    )
    parser.add_argument("etapa", choices=[*ETAPAS, "tudo"])
    parser.add_argument("--refazer", action="store_true", help="baixar de novo mesmo se o arquivo já existir")
    parser.add_argument("--apenas", choices=["relevo", "temperatura"], help="na etapa rasters, gerar só um deles")
    args = parser.parse_args()

    projeto = Projeto.padrao()
    funcoes = {
        "baixar": lambda: baixar.baixar(projeto, refazer=args.refazer),
        "camadas": lambda: camadas.executar(projeto),
        "rasters": lambda: rasters.executar(projeto, apenas=args.apenas),
        "exportar": lambda: exportar.executar(projeto),
        "web": lambda: web.executar(projeto),
        "qualidade": lambda: qualidade.executar(projeto),
    }
    for etapa in (ETAPAS if args.etapa == "tudo" else [args.etapa]):
        inicio = time.perf_counter()
        print(f"\n== {etapa} ==")
        funcoes[etapa]()
        print(f"   ({time.perf_counter() - inicio:.0f} s)")


if __name__ == "__main__":
    main()
