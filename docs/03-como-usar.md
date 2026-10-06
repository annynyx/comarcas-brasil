# 03 — Como usar

Receitas para os usos mais comuns. Todas partem dos arquivos gerados por `make tudo`.

## Gerar tudo do zero

```bash
make instalar     # uv sync + npm ci (versões travadas)
make tudo         # baixar → camadas → rasters → exportar → web → qualidade
make visualizar   # abre o visualizador em http://localhost:5173
```

Leia `dist/relatorio_qualidade.md` no final: ele diz se alguma métrica ficou fora da meta.

## Python: cruzar seus dados com qualquer recorte

Todo dado com código IBGE de município pode ser levado para comarca, estado ou região.

```python
import geopandas as gpd
import pandas as pd

municipios = gpd.read_parquet("dist/parquet/municipios.parquet")
meus = pd.read_csv("meus_dados.csv", dtype={"codigo_ibge": str})  # codigo_ibge, processos
base = municipios.merge(meus, on="codigo_ibge", how="left")

# Contagens SOMAM; taxas são recalculadas a partir das somas (nunca média simples)
por_comarca = base.groupby("comarca_id").agg(processos=("processos", "sum"),
                                             populacao=("populacao", "sum"))
por_comarca["processos_por_mil_hab"] = por_comarca.processos / por_comarca.populacao * 1000

comarcas = gpd.read_parquet("dist/parquet/comarcas.parquet")
mapa = comarcas.merge(por_comarca[["processos_por_mil_hab"]].reset_index(), on="comarca_id")
mapa.plot(column="processos_por_mil_hab", cmap="Blues", legend=True)
```

Para estados ou regiões, troque `comarca_id` por `uf` ou `regiao`.

## SQL (DuckDB), sem instalar nada de GIS

```sql
SELECT uf, count(*) AS comarcas, sum(populacao) AS populacao
FROM 'dist/parquet/comarcas.parquet'
GROUP BY uf ORDER BY populacao DESC;
```

## Excel / BI

- `dist/tabelas/municipio_comarca.csv`: a tabela de ligação (município → comarca).
- `dist/tabelas/<camada>.csv`: atributos de cada camada, inclusive altitude e temperatura.

## QGIS / ArcGIS

Abra `dist/brasil.gpkg`. Cada mapa é uma camada do arquivo (pais, regioes, ufs, comarcas,
municipios, cidades). Os rasters estão em `dist/rasters/`.

## Web: usar o mapa em outro site

O módulo `web/src/mapa-brasil.ts` não depende de framework. Ele precisa de:

1. os dados de `web/public/dados/` (gerados por `make web`);
2. os arquivos do worker do MapLibre em `maplibre/` (copiados por `web/scripts/copiar-maplibre.mjs`).

HTML/TypeScript puro:

```ts
import { MapaBrasil } from "./mapa-brasil";

const mapa = await MapaBrasil.criar(document.getElementById("mapa")!, { urlDados: "/dados/" });
mapa.mostrarCamada("comarcas");            // pais | regioes | ufs | comarcas | municipios
const legenda = mapa.colorirPor("populacao"); // devolve cores e faixas para montar a legenda
mapa.mostrarFundo("relevo");               // relevo | temperatura | null
mapa.mostrarCidades(true, /* só sedes de comarca */ true);
mapa.on("clicar", (info) => console.log(info?.propriedades));
```

React:

```tsx
function Mapa() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let mapa: MapaBrasil | undefined;
    MapaBrasil.criar(ref.current!, { urlDados: "/dados/" }).then((m) => (mapa = m));
    return () => mapa?.destruir();
  }, []);
  return <div ref={ref} style={{ height: 600 }} />;
}
```

### Atalhos de URL da demonstração

`?camada=municipios&metrica=altitude_media&fundo=relevo&cidades=1`

## D3 (mapas estáticos, impressão)

```js
const topo = await d3.json("brasil_baixa.topojson");
const ufs = topojson.feature(topo, topo.objects.ufs);
const projecao = d3.geoMercator().fitSize([800, 800], ufs);
d3.select("svg").selectAll("path").data(ufs.features).join("path")
  .attr("d", d3.geoPath(projecao));
```

## Adicionar uma nova métrica raster (ex.: precipitação)

1. `config/fontes.toml`: nova seção com a URL (o WorldClim tem `wc2.1_5m_bio_12.tif` = chuva anual).
2. `pipeline/rasters.py`: função `construir_<nome>` (copie `construir_temperatura`).
3. `pipeline/estatisticas.py`: inclua o raster em `OPERACOES`.
4. `pipeline/web.py`: inclua em `RASTERS` e `METRICAS`; `config/paletas.json`: uma rampa.
5. `make rasters exportar web` e confira o relatório.

## Adicionar as comarcas de um estado

Siga `dados/fontes/README.md` e rode `make camadas`. Se algo estiver errado, a mensagem
aponta a linha e a regra (A1, A2…) de `docs/02-metricas.md`.
