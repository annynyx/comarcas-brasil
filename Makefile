# Atalhos para o pipeline. `make tudo` refaz o mapa inteiro do zero.
# Cada etapa lê o resultado da anterior, então dá para rodar uma etapa isolada.

PY := uv run python -m pipeline

.PHONY: instalar baixar camadas rasters exportar web qualidade tudo testar visualizar build-web limpar

instalar:     ## instala dependências travadas (Python via uv, Node via npm)
	uv sync
	npm ci

baixar:       ## fontes externas → dados/brutos/
	$(PY) baixar

camadas:      ## valida comarcas e monta as camadas vetoriais
	$(PY) camadas

rasters:      ## relevo e temperatura recortados para o Brasil
	$(PY) rasters

exportar:     ## estatísticas por área + GeoPackage/GeoParquet/CSV em dist/
	$(PY) exportar

web:          ## versões simplificadas + imagens para o visualizador
	$(PY) web

qualidade:    ## relatório de métricas em dist/relatorio_qualidade.md
	$(PY) qualidade

tudo: baixar camadas rasters exportar web qualidade

testar:       ## testes automáticos com dados sintéticos (não usa internet)
	uv run pytest -q

visualizar:   ## abre o visualizador em http://localhost:5173
	npm run dev

build-web:    ## gera o site estático em web/dist/
	npm run build

limpar:       ## apaga tudo que é gerado (mantém os downloads)
	rm -rf dados/intermediario dist web/public/dados web/dist
