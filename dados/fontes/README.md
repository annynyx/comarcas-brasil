# Tabelas de comarcas (fonte da verdade)

Cada estado tem uma pasta com a sigla da UF (ex.: `MG/`) contendo dois arquivos.
Copie os modelos de `_modelo/` para começar. Pastas que começam com `_` são ignoradas.

## `comarcas.csv` — uma linha por comarca

| Coluna | Exemplo | Regra |
|---|---|---|
| `comarca_id` | `3106200` | Código IBGE (7 dígitos) do município-sede |
| `nome` | `Belo Horizonte` | Nome usado pelo TJ |
| `uf` | `MG` | Igual ao nome da pasta |
| `tribunal` | `TJMG` | |
| `entrancia` | `especial` | Como o TJ escreve |
| `fonte` | `https://…` ou `LC 59/2001, anexo I` | Obrigatória |
| `data_verificacao` | `2026-10-06` | Obrigatória, formato AAAA-MM-DD |

## `municipios.csv` — uma linha por município da UF (todos!)

| Coluna | Exemplo | Regra |
|---|---|---|
| `codigo_ibge` | `3106200` | Deve existir na malha do IBGE |
| `municipio` | `Belo Horizonte` | Só para leitura; conferido com o IBGE (aviso se diferente) |
| `comarca_id` | `3106200` | Deve existir em `comarcas.csv` |

Um estado só entra no mapa quando **todos** os seus municípios estão na tabela.
Rode `make camadas`: se houver erro, a mensagem diz a linha e a regra violada.
