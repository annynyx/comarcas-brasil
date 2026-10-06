# Roraima (TJRR) — notas de verificação

**Situação:** cadastrado em 2026-10-06. 15 municípios, 8 comarcas instaladas.
**Confiança:** média. A composição foi conferida em trechos dos atos oficiais
obtidos por busca; o texto integral não pôde ser aberto no ambiente de
desenvolvimento (sites do TJRR e da Assembleia bloqueados). **Conferir os
documentos abaixo antes de usar em produção.**

## Fontes

- Lei Complementar estadual nº 221/2014 — Código de Organização Judiciária do Estado de
  Roraima (compilado: <https://atos.tjrr.jus.br/files/compilado1320242023010963bc4cd868f21.pdf>;
  Assembleia: <https://sapl.al.rr.leg.br/ta/143/text>).
- Regimento Interno do TJRR — Resolução TJRR/TP nº 27, de 25/10/2023
  (<https://atos.tjrr.jus.br/files/original1142062023122065830b4eda1d0.pdf>).
- Página de comarcas do TJRR: <https://www.tjrr.jus.br/index.php/comarcastjrr>.

## Composição

| Comarca | Municípios (termos judiciários) |
|---|---|
| Boa Vista | Boa Vista, Cantá |
| Caracaraí | Caracaraí |
| São Luiz do Anauá | São Luiz, São João da Baliza, Caroebe |
| Mucajaí | Mucajaí, Iracema |
| Rorainópolis | Rorainópolis |
| Alto Alegre | Alto Alegre |
| Pacaraima | Pacaraima, Amajari, Uiramutã |
| Bonfim | Bonfim, Normandia |

Entrância: **única** (o Judiciário de Roraima não tem divisão por entrâncias).

## Decisão: Cantá dentro de Boa Vista

A LC 221/2014 lista nove comarcas, incluindo a **Comarca do Cantá**. Mas os atos do TJRR
encontrados (Regimento Interno de 2023 e Diários da Justiça de 2025–2026, que tratam do
rodízio de oficiais de justiça para "a zona rural de Boa Vista e o Município do Cantá")
indicam que Cantá é atendido pela **Comarca de Boa Vista**: criada por lei, mas não
instalada.

O mapa mostra a jurisdição **em funcionamento**. Por isso Cantá está ligado a Boa Vista,
e a coluna `observacao` registra a existência legal da Comarca do Cantá. Se ela for
instalada, basta incluir a linha `1400175,Cantá,…` em `comarcas.csv` e mudar o
`comarca_id` de Cantá em `municipios.csv`.

## Pendências

- [ ] Ler o artigo da LC 221/2014 que lista as comarcas e confirmar a grafia oficial
  ("São Luiz do Anauá" ou "São Luiz").
- [ ] Confirmar que a Comarca do Cantá continua não instalada.
- [ ] Rodar `make camadas` com a malha oficial do IBGE (A1 e A3 contra a malha real).
