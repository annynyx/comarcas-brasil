# Comarcas do Brasil

Mapa base, **replicável e aberto**, das comarcas da Justiça Estadual brasileira —
pronto para ser integrado em análises estatísticas, divisão de territórios e
visualização de limites.

## Ideia em uma frase

Mantemos uma **tabela** dizendo a qual comarca pertence cada município e **geramos** os
polígonos das comarcas a partir da malha municipal oficial do IBGE. Nada é desenhado à mão.

## Status

**Fase 0 — definição de tecnologias e métricas.** Ainda não há código.

| Documento | Conteúdo |
|---|---|
| [docs/01-arquitetura.md](docs/01-arquitetura.md) | Tecnologias escolhidas e por quê, formatos de saída, modelo de dados, exceções, roteiro |
| [docs/02-metricas.md](docs/02-metricas.md) | Como saber se o mapa está certo + indicadores embutidos para estatística |

## Stack proposta (resumo)

- **Dados:** Python + GeoPandas (montagem e validação), mapshaper (simplificação sem frestas), uv (dependências travadas)
- **Saídas:** CSV, GeoPackage, GeoParquet, GeoJSON, TopoJSON (PMTiles no futuro)
- **Web:** MapLibre GL JS + TypeScript + Vite, como módulo independente de framework
- **Automação:** Makefile, pytest, GitHub Actions, GitHub Releases/Pages

## Fontes de dados

- Malha municipal e áreas territoriais — IBGE
- População — IBGE, Censo 2022
- Composição das comarcas — leis de organização judiciária e portais de cada Tribunal de Justiça
- Referência para conferência — CNJ, relatório *Justiça em Números*
