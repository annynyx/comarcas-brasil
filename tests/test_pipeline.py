"""Roda o pipeline inteiro sobre o Brasil de mentira (veja conftest.py) e confere o resultado."""

from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd
import pytest

from pipeline import camadas, exportar, qualidade, rasters, web


@pytest.fixture
def construido(projeto):
    camadas.executar(projeto)
    rasters.executar(projeto)
    exportar.executar(projeto)
    web.executar(projeto)
    qualidade.executar(projeto)
    return projeto


def camada(projeto, nome):
    return gpd.read_file(projeto.dist / "brasil.gpkg", layer=nome)


def test_hierarquia_de_areas(construido):
    pais, regioes, ufs = (camada(construido, n) for n in ("pais", "regioes", "ufs"))
    municipios = camada(construido, "municipios")

    assert len(pais) == 1 and len(regioes) == 1  # SE e AL são do Nordeste
    assert regioes.nome.iloc[0] == "Nordeste"
    assert sorted(ufs.uf) == ["AL", "SE"]
    assert set(ufs.nome) == {"Alagoas", "Sergipe"}

    # A lagoa entra no contorno do estado, mas não é município
    assert "2799999" not in set(municipios.codigo_ibge)
    assert len(municipios) == 7
    assert ufs.set_index("uf").n_municipios.to_dict() == {"AL": 3, "SE": 4}

    # Área e população somam exatamente
    assert pais.area_km2.iloc[0] == pytest.approx(ufs.area_km2.sum())
    assert pais.populacao.iloc[0] == municipios.populacao.sum()
    al = ufs.set_index("uf").loc["AL"]
    assert al.populacao == 50_000 + 60_000 + 70_000


def test_comarcas(construido):
    comarcas = camada(construido, "comarcas").set_index("comarca_id")
    assert sorted(comarcas.index) == ["2800001", "2800004"]
    aracaju = comarcas.loc["2800001"]
    assert aracaju.n_municipios == 2
    assert aracaju.sede == "Aracaju"
    assert aracaju.populacao == 10_000 + 20_000
    assert aracaju.geometry.geom_type == "Polygon"  # dois quadrados vizinhos viram um só

    ligacao = pd.read_csv(construido.dist / "tabelas" / "municipio_comarca.csv", dtype=str)
    assert ligacao.set_index("codigo_ibge").comarca.to_dict()["2800002"] == "Aracaju"
    assert ligacao.loc[ligacao.uf == "AL", "comarca_id"].isna().all()  # AL ainda sem tabela


def test_cidades(construido):
    cidades = camada(construido, "cidades").set_index("codigo_ibge")
    assert len(cidades) == 7
    assert bool(cidades.loc["2800004"].e_sede_comarca) is True
    assert bool(cidades.loc["2800002"].e_sede_comarca) is False
    assert cidades.loc["2700001"].capital
    assert cidades.loc["2800001"].altitude_sede > 0


def test_estatisticas_dos_rasters(construido):
    municipios = camada(construido, "municipios").set_index("codigo_ibge")
    # O relevo de teste sobe para oeste: o município mais a oeste é o mais alto
    assert municipios.loc["2800001"].altitude_media > municipios.loc["2700002"].altitude_media
    # A temperatura de teste aumenta para o sul
    assert municipios.loc["2800003"].temperatura_media > municipios.loc["2800001"].temperatura_media
    assert municipios[["altitude_media", "temperatura_media"]].notna().all().all()
    assert camada(construido, "comarcas").temperatura_media.notna().all()


def test_arquivos_web(construido):
    pasta = construido.web_dados
    catalogo = json.loads((pasta / "catalogo.json").read_text())
    assert [c["id"] for c in catalogo["camadas"]] == ["pais", "regioes", "ufs", "comarcas", "municipios", "cidades"]
    assert {r["id"] for r in catalogo["rasters"]} == {"relevo", "temperatura"}
    for raster in catalogo["rasters"]:
        assert (pasta / raster["imagem"]).exists()
        assert raster["minimo"] < raster["maximo"]

    for resolucao in ("media", "baixa"):
        topo = json.loads((pasta / f"brasil_{resolucao}.topojson").read_text())
        assert topo["type"] == "Topology"
        assert set(topo["objects"]) == {"pais", "regioes", "ufs", "comarcas", "municipios"}
        props = [g["properties"] for g in topo["objects"]["municipios"]["geometries"]]
        assert {p["codigo_ibge"] for p in props} == {"2800001", "2800002", "2800003", "2800004",
                                                     "2700001", "2700002", "2700003"}
        assert all("temperatura_media" in p for p in props)

    cidades = json.loads((pasta / "cidades.geojson").read_text())
    assert len(cidades["features"]) == 7


def test_relatorio_de_qualidade(construido):
    itens = {i["metrica"]: i for i in json.loads((construido.dist / "relatorio_qualidade.json").read_text())}
    assert itens["A1"]["valor"] == "1/2"  # só SE tem tabela
    assert itens["B1"]["valor"] == 0
    assert itens["B3"]["status"] == "ok"
    assert itens["B5"]["valor"] == 0
    assert (construido.dist / "relatorio_qualidade.md").exists()


def test_build_para_com_erro_nas_comarcas(projeto):
    arquivo = projeto.tabelas_comarcas / "SE" / "municipios.csv"
    arquivo.write_text(arquivo.read_text().replace("2800003,Estancia,2800004\n", ""))
    with pytest.raises(SystemExit, match="erro"):
        camadas.executar(projeto)


def test_funciona_sem_nenhuma_tabela_de_comarcas(projeto):
    """Situação inicial do projeto: nenhum estado cadastrado ainda."""
    import shutil
    shutil.rmtree(projeto.tabelas_comarcas / "SE")
    camadas.executar(projeto)
    exportar.executar(projeto)
    web.executar(projeto)
    qualidade.executar(projeto)

    municipios = camada(projeto, "municipios")
    assert municipios.comarca_id.isna().all()
    assert not municipios.e_sede_comarca.any()
    catalogo = json.loads((projeto.web_dados / "catalogo.json").read_text())
    assert "comarcas" not in [c["id"] for c in catalogo["camadas"]]
    assert catalogo["rasters"] == []  # rasters não foram gerados neste teste
