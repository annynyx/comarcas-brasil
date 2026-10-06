/** Página de demonstração: controles em volta do módulo MapaBrasil. */

import "./estilo.css";
import { formatarNumero, MapaBrasil, type InfoFeicao, type Legenda } from "./mapa-brasil";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

// Rótulos legíveis para os atributos mostrados no detalhe
const ROTULOS: Record<string, string> = {
  nome: "Nome", uf: "UF", nome_uf: "Estado", regiao: "Região", sede: "Sede", tribunal: "Tribunal",
  entrancia: "Entrância", comarca_id: "Comarca (código da sede)", codigo_ibge: "Código IBGE",
  e_sede_comarca: "Sede de comarca", capital: "Capital", n_municipios: "Municípios",
  area_km2: "Área (km²)", populacao: "População (2022)", densidade: "Densidade (hab./km²)",
  altitude_media: "Altitude média (m)", altitude_min: "Altitude mínima (m)", altitude_max: "Altitude máxima (m)",
  altitude_sede: "Altitude da sede (m)", temperatura_media: "Temperatura média anual (°C)",
  temperatura_sede: "Temperatura na sede (°C)", tem_comarcas: "Tabela de comarcas", data_verificacao: "Verificado em",
};

function valorLegivel(valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  if (typeof valor === "boolean") return valor ? "sim" : "não";
  if (typeof valor === "number") return formatarNumero(valor);
  return String(valor);
}

function titulo(info: InfoFeicao): string {
  const p = info.propriedades;
  const nome = valorLegivel(p.nome);
  return p.uf && info.camada !== "ufs" ? `${nome} (${p.uf})` : nome;
}

function desenharLegenda(alvo: HTMLElement, legenda: Legenda | null) {
  alvo.replaceChildren();
  if (!legenda) return;
  const lista = document.createElement("ul");
  for (const classe of legenda.classes) {
    const item = document.createElement("li");
    item.innerHTML = `<span class="amostra" style="background:${classe.cor}"></span><span>${classe.rotulo}</span>`;
    lista.append(item);
  }
  alvo.append(lista);
}

function opcao(nome: string, valor: string, texto: string, marcado: boolean): HTMLLabelElement {
  const label = document.createElement("label");
  label.className = "radio";
  label.innerHTML = `<input type="radio" name="${nome}" value="${valor}" ${marcado ? "checked" : ""}/> ${texto}`;
  return label;
}

async function iniciar() {
  const parametros = new URLSearchParams(location.search);
  let mapa: MapaBrasil;
  try {
    mapa = await MapaBrasil.criar($("mapa"), {
      urlDados: `${import.meta.env.BASE_URL}dados/`,
      camadaInicial: parametros.get("camada") ?? undefined,
    });
  } catch (erro) {
    const aviso = $("aviso");
    aviso.hidden = false;
    aviso.textContent = "Não encontrei os dados do mapa. Rode `make tudo` (ou `make web`) para gerá-los.";
    console.error(erro);
    return;
  }

  // --- Recorte (camadas de área)
  const caixaCamadas = $("camadas");
  for (const c of mapa.catalogo.camadas.filter((c) => c.tipo === "area")) {
    caixaCamadas.append(opcao("camada", c.id, c.titulo, c.id === mapa.camadaAtual));
  }

  // --- Métricas disponíveis para o recorte atual
  const seletor = $<HTMLSelectElement>("metrica");
  const preencherMetricas = () => {
    const metricas = mapa.camada(mapa.camadaAtual)?.metricas ?? [];
    seletor.innerHTML = `<option value="">Nenhuma (só limites)</option>` +
      metricas.map((m) => `<option value="${m.coluna}">${m.rotulo}${m.unidade ? ` (${m.unidade})` : ""}</option>`).join("");
    seletor.value = mapa.metricaAtual ?? "";
  };
  const atualizarLegenda = () => desenharLegenda($("legenda"), mapa.colorirPor(seletor.value || null));

  caixaCamadas.addEventListener("change", (e) => {
    mapa.mostrarCamada((e.target as HTMLInputElement).value);
    preencherMetricas();
    atualizarLegenda();
    atualizarTabela();
  });
  seletor.addEventListener("change", () => {
    atualizarLegenda();
    atualizarTabela();
  });
  $<HTMLInputElement>("contorno-ufs").addEventListener("change", (e) =>
    mapa.mostrarContornoEstados((e.target as HTMLInputElement).checked));

  // --- Fundo (rasters)
  const caixaFundos = $("fundos");
  caixaFundos.append(opcao("fundo", "", "Nenhum", true));
  for (const r of mapa.catalogo.rasters) caixaFundos.append(opcao("fundo", r.id, r.titulo, false));
  caixaFundos.addEventListener("change", (e) => {
    const id = (e.target as HTMLInputElement).value || null;
    mapa.mostrarFundo(id);
    atualizarLegenda();
    const raster = mapa.catalogo.rasters.find((r) => r.id === id);
    const alvo = $("legenda-fundo");
    alvo.innerHTML = raster
      ? `<div class="gradiente" style="background:linear-gradient(to right, ${raster.paleta.join(",")})"></div>
         <div class="extremos"><span>${formatarNumero(raster.minimo)} ${raster.unidade}</span><span>${formatarNumero(raster.maximo)} ${raster.unidade}</span></div>`
      : "";
  });

  // --- Cidades
  const cidades = $<HTMLInputElement>("cidades");
  const soSedes = $<HTMLInputElement>("so-sedes-comarca");
  const atualizarCidades = () => {
    soSedes.disabled = !cidades.checked;
    mapa.mostrarCidades(cidades.checked, soSedes.checked);
  };
  cidades.addEventListener("change", atualizarCidades);
  soSedes.addEventListener("change", atualizarCidades);

  // --- Dica ao passar o mouse
  const dica = $("dica");
  mapa.on("passar", (info, ponto) => {
    if (!info || !ponto) {
      dica.hidden = true;
      return;
    }
    const metrica = mapa.metricaAtual;
    const extra = metrica && info.camada !== "cidades"
      ? `<div class="valor">${valorLegivel(info.propriedades[metrica])}</div>` : "";
    const semTabela = mapa.camadaAtual === "comarcas" && info.camada === "ufs"
      ? `<div class="valor">Tabela de comarcas ainda não cadastrada</div>` : "";
    dica.innerHTML = `<strong>${titulo(info)}</strong>${semTabela || extra}`;
    dica.style.transform = `translate(${ponto.x + 14}px, ${ponto.y + 14}px)`;
    dica.hidden = false;
  });

  // --- Detalhe ao clicar
  const detalhe = $("detalhe");
  mapa.on("clicar", (info) => {
    if (!info) {
      detalhe.hidden = true;
      return;
    }
    const linhas = Object.entries(info.propriedades)
      .filter(([chave]) => chave in ROTULOS && chave !== "nome")
      .map(([chave, valor]) => `<tr><th>${ROTULOS[chave]}</th><td>${valorLegivel(valor)}</td></tr>`)
      .join("");
    detalhe.innerHTML = `<h2>${titulo(info)}</h2><table>${linhas}</table>`;
    detalhe.hidden = false;
  });

  // --- Tabela (acessibilidade: os mesmos números sem depender da cor)
  const blocoTabela = $<HTMLDetailsElement>("tabela-bloco");
  function atualizarTabela() {
    if (!blocoTabela.open) return;
    const metrica = mapa.metricaAtual;
    const linhas = mapa.feicoes(mapa.camadaAtual).map((f) => f.properties);
    if (metrica) linhas.sort((a, b) => (Number(b[metrica]) || -Infinity) - (Number(a[metrica]) || -Infinity));
    const rotulo = metrica ? mapa.camada(mapa.camadaAtual)?.metricas.find((m) => m.coluna === metrica)?.rotulo : null;
    $("tabela").innerHTML = `<table><thead><tr><th>Nome</th><th>UF</th>${rotulo ? `<th>${rotulo}</th>` : ""}</tr></thead><tbody>` +
      linhas.map((p) => `<tr><td>${valorLegivel(p.nome)}</td><td>${valorLegivel(p.uf)}</td>${metrica ? `<td class="num">${valorLegivel(p[metrica])}</td>` : ""}</tr>`).join("") +
      "</tbody></table>";
  }
  blocoTabela.addEventListener("toggle", atualizarTabela);

  // Estado inicial vindo da URL (ex.: ?camada=municipios&metrica=altitude_media&fundo=relevo)
  preencherMetricas();
  const metricaInicial = parametros.get("metrica");
  if (metricaInicial && [...seletor.options].some((o) => o.value === metricaInicial)) seletor.value = metricaInicial;
  const fundoInicial = parametros.get("fundo");
  if (fundoInicial) {
    const radio = caixaFundos.querySelector<HTMLInputElement>(`input[value="${fundoInicial}"]`);
    if (radio) {
      radio.checked = true;
      radio.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }
  if (parametros.get("cidades") === "1") {
    cidades.checked = true;
    atualizarCidades();
  }
  atualizarLegenda();
}

iniciar();
