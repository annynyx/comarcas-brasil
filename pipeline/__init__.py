"""Pipeline que gera o mapa base do Brasil (país, regiões, estados, comarcas, municípios,
cidades, relevo e temperatura) a partir de fontes públicas.

Etapas, na ordem: baixar → camadas → rasters → exportar → web → qualidade.
Rode `python -m pipeline --help` para ver todas.
"""
