# Mapa base do Brasil — comarcas, estados, municípios, cidades, relevo e temperatura

Projeto **replicável e aberto** que gera, com um comando, os mapas do Brasil mais
usados em análises estatísticas, divisão de territórios e visualização de limites.
Também traz um visualizador web pronto para ser embutido em outros sistemas.

## O que vem pronto

| Mapa | Tipo | Para quê |
|---|---|---|
| País, Regiões, Estados | áreas | recortes clássicos de estatística |
| **Comarcas** | áreas | Justiça Estadual: divisão de territórios, jurimetria |
| Municípios | áreas | menor unidade com dados públicos |
| Cidades (sedes municipais) | pontos | marcadores, mapas de bolhas |
| Relevo | raster (~1 km) | altitude; também vira métrica por área |
| Temperatura média anual | raster (~9 km) | clima; também vira métrica por área |

Toda área já sai com **área, população, densidade, altitude média/mín./máx. e temperatura
média**. Qualquer outro dado com código IBGE se cruza em uma linha
([exemplos](docs/03-como-usar.md)).

## Ideia em uma frase

Mantemos uma **tabela** dizendo a qual comarca pertence cada município e **geramos** os
polígonos (comarcas, estados, regiões, país) a partir da malha municipal oficial do IBGE.
Nada é desenhado à mão, e as bordas de todas as camadas coincidem.

## Começando

Requisitos: [uv](https://docs.astral.sh/uv/), Node.js 20+ e `make`.

```bash
make instalar     # dependências com versões travadas
make tudo         # baixa as fontes e gera tudo em dist/ e web/public/dados/
make visualizar   # http://localhost:5173
make testar       # testes automáticos (não usam internet)
```

## Situação

- ✅ Pipeline completo, com 19 testes automáticos e relatório de qualidade.
- ✅ Visualizador web (claro/escuro, celular, tabela acessível).
- 🟡 **Comarcas:** Roraima cadastrada (piloto: 8 comarcas, 15 municípios). Os demais
  estados aparecem em cinza no mapa de comarcas até ganharem tabela. Veja
  [`dados/fontes/README.md`](dados/fontes/README.md).
- ⏳ Rodar com as fontes oficiais de IBGE e WorldClim (o ambiente de desenvolvimento não tinha acesso a esses sites; o relevo do Copernicus já foi testado de verdade).

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/01-arquitetura.md](docs/01-arquitetura.md) | Catálogo de mapas, tecnologias e por quê, fluxo, formatos, exceções, roteiro |
| [docs/02-metricas.md](docs/02-metricas.md) | Como saber se o mapa está certo + indicadores embutidos |
| [docs/03-como-usar.md](docs/03-como-usar.md) | Receitas: Python, SQL, Excel, QGIS, web, React, D3 |
| [dados/fontes/README.md](dados/fontes/README.md) | Como cadastrar as comarcas de um estado |

## Fontes de dados e créditos

- Limites municipais e áreas territoriais: IBGE, malha municipal 2024
- População: IBGE, Censo Demográfico 2022
- Composição das comarcas: leis de organização judiciária e portais dos Tribunais de Justiça
- Sedes municipais: [kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros) (MIT)
- Relevo: Copernicus DEM GLO-90 — © DLR e.V. 2010-2014 e © Airbus Defence and Space GmbH 2014-2018, programa Copernicus (UE/ESA)
- Temperatura: WorldClim 2.1 — Fick & Hijmans (2017), CC BY 4.0
- Referência para conferência: CNJ, *Justiça em Números*

## Licença

Código: [MIT](LICENSE). Dados produzidos pelo projeto: [CC BY 4.0](LICENSE-DADOS.md),
respeitando os termos das fontes de terceiros listadas acima.
