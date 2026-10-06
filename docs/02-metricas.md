# 02 — Métricas de qualidade e indicadores

> **Status:** em uso. `make qualidade` mede automaticamente A1, A2–A5, A7–A10, B1,
> B3, B4, B5, C1, C2 e D3 e grava `dist/relatorio_qualidade.md`. As demais são
> conferências manuais ou de CI (fase 3).
> Os valores-alvo marcados com *(ajustar)* são palpites iniciais e devem ser
> calibrados quando o pipeline rodar com a malha oficial.

Este documento responde a duas perguntas diferentes:

1. **Como sabemos que o mapa está certo?** → métricas de qualidade (seções A a D).
   Cada uma vira um teste automático ou um item do relatório gerado pelo pipeline.
2. **Que números o mapa já traz pronto para uso estatístico?** → indicadores (seção E).

---

## A. Dados (a tabela município → comarca)

| # | Métrica | Meta | Como medir |
|---|---|---|---|
| A1 | Cobertura: municípios da malha IBGE atribuídos a uma comarca | **100%** (exceto polígonos especiais listados no relatório) | Comparar `municipios.csv` × malha IBGE. |
| A2 | Municípios em mais de uma comarca | **0** | Contagem de `codigo_ibge` duplicado no país todo. |
| A3 | Códigos IBGE inexistentes na malha | **0** | Junção com a malha. |
| A4 | Sede pertence à própria comarca | **100%** | `comarca_id` do município-sede = ele mesmo. |
| A5 | Comarcas sem nenhum município | **0** | Junção. |
| A6 | Nº de comarcas por UF igual à lista oficial do TJ | **diferença 0** por UF | Conferência com a fonte citada. |
| A7 | Total nacional de sedes comparado ao *Justiça em Números* (CNJ) | Diferença **explicada** no relatório | As datas de referência diferem; divergência sem explicação = investigar. |
| A8 | Comarcas com `fonte` e `data_verificacao` preenchidas | **100%** | Validação de esquema. |
| A9 | Idade da verificação | ≤ **12 meses** | `data_verificacao` vs data do build. |
| A10 | Nome do município confere com o IBGE | **100%** | Comparação normalizada (sem acento/caixa). |

## B. Geometria

| # | Métrica | Meta | Como medir |
|---|---|---|---|
| B1 | Geometrias válidas | **100%** | `shapely.is_valid` em todas as resoluções. |
| B2 | Frestas ou sobreposições entre comarcas vizinhas | **0** | Sobreposição par a par + união comparada à UF. |
| B3 | Soma das áreas das comarcas × área oficial da UF (resolução total) | desvio **< 0,01%** | Soma das áreas oficiais municipais do IBGE. |
| B4 | Idem, nas versões simplificadas | desvio **< 1%** *(ajustar)* | Área calculada em projeção de áreas iguais. |
| B5 | Comarcas não contíguas (pedaços separados) | **Toda ocorrência revisada** | Contar partes do multipolígono. Ilhas são legítimas; municípios "soltos" costumam indicar erro na tabela. |
| B6 | Deslocamento máximo da borda após simplificação (distância de Hausdorff) | resolução **média ≤ 200 m**, **baixa ≤ 2 km** *(ajustar)* | Comparar com a resolução total. |

> **B3 na prática:** no teste de fumaça com um espelho não oficial da malha, B3 acusou
> 26% de desvio no RJ. A causa eram polígonos com anéis invertidos no arquivo de origem,
> que distorciam a área calculada para ele. É exatamente o tipo de problema que essa
> métrica existe para pegar.

> **Por que B5 é tão útil?** Uma comarca formada por municípios que não se tocam quase
> sempre significa que alguém digitou o código errado na tabela. É um detector de erro
> de digitação "de graça".

## C. Entrega e desempenho

| # | Métrica | Meta | Como medir |
|---|---|---|---|
| C1 | Tamanho de `brasil_baixa.topojson` (todas as camadas, gzip) | ≤ **1 MB** *(ajustar)* | Relatório do build. |
| C2 | Tamanho de `brasil_media.topojson` (todas as camadas, gzip) | ≤ **3 MB** *(ajustar)* | Relatório do build. |
| C3 | Tempo até o mapa aparecer na demo (notebook comum, 4G) | ≤ **3 s** | Lighthouse / DevTools. |
| C4 | Interação (passar o mouse, zoom, clique) | Sem travamento perceptível | DevTools → Performance. |
| C5 | Funciona em celular (largura 360 px) | Sim | Teste manual + Playwright. |

## D. Reprodutibilidade (o "replicável" do projeto)

| # | Métrica | Meta | Como medir |
|---|---|---|---|
| D1 | Build do zero em máquina limpa | **1 comando** (`make tudo`) | CI em máquina nova a cada versão. |
| D2 | Mesmas entradas → mesmas saídas | **Checksums idênticos** | Rodar duas vezes e comparar hashes. |
| D3 | Insumos externos rastreáveis | Ano da malha IBGE fixado + checksum dos downloads | Arquivo de manifesto no `dados/brutos/`. |
| D4 | Versões de dependências travadas | `uv.lock` e `package-lock.json` versionados | Revisão do repositório. |
| D5 | Tempo total do build | ≤ **15 min** *(ajustar)* | CI. |

## E. Indicadores embutidos (para uso estatístico)

O mapa sai com um conjunto **mínimo** de indicadores. Qualquer outro dado entra
cruzando pelo `codigo_ibge` (município) ou pelo `comarca_id`.

| Indicador | Fonte | Agregação município → comarca |
|---|---|---|
| `n_municipios` | Nossa tabela | Contagem |
| `area_km2` | IBGE (área territorial oficial) | **Soma** |
| `populacao` | IBGE, Censo 2022 | **Soma** |
| `densidade` (hab/km²) | Derivado | `populacao / area_km2` **depois** de somar |
| `entrancia`, `tribunal` | TJ | Atributo da comarca |
| `altitude_media`, `altitude_min`, `altitude_max` | Copernicus DEM | Calculada **direto no polígono** de cada camada (média ponderada pela fração de pixel coberta) |
| `temperatura_media` | WorldClim 2.1 (BIO1, normal 1970–2000) | Idem |
| `altitude_sede`, `temperatura_sede` (cidades) | Idem | Valor do pixel no ponto da sede |

### Regra de ouro da agregação (vale para qualquer dado que for cruzado depois)

- **Contagens** (população, nº de processos, nº de habitantes) → **somar**.
- **Taxas e médias** (renda per capita, IDH, taxa de congestionamento) → **nunca tirar a
  média simples** entre municípios. Ou recalcular a partir das contagens (numerador
  somado ÷ denominador somado), ou fazer **média ponderada** pela população.

Exemplo: comarca com município A (1.000 hab, renda per capita R$ 3.000) e município B
(99.000 hab, R$ 1.000). Média simples = R$ 2.000 (errado). Média ponderada = R$ 1.020
(certo), porque quase todo mundo mora em B.
