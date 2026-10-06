/**
 * Módulo reutilizável do mapa base do Brasil.
 *
 * Não depende de framework: funciona em HTML puro, React, Vue, Angular…
 *
 *   const mapa = await MapaBrasil.criar(document.getElementById("mapa")!, { urlDados: "/dados/" });
 *   mapa.mostrarCamada("comarcas");
 *   const legenda = mapa.colorirPor("populacao");
 *   mapa.mostrarFundo("relevo");
 *
 * Os dados (TopoJSON, imagens, catalogo.json) são gerados por `make web`.
 */

import {
  AttributionControl,
  Map as MapLibre,
  NavigationControl,
  setWorkerUrl,
  type ExpressionSpecification,
  type GeoJSONSource,
  type MapGeoJSONFeature,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";

// Arquivos copiados por web/scripts/copiar-maplibre.mjs (roda antes do dev e do build)
setWorkerUrl(`${import.meta.env.BASE_URL}maplibre/maplibre-gl-worker.mjs`);

// ------------------------------------------------------------------ tipos do catálogo

export interface Metrica {
  coluna: string;
  rotulo: string;
  unidade: string;
}

export interface CamadaCatalogo {
  id: string;
  titulo: string;
  tipo: "area" | "ponto";
  chave: string;
  metricas: Metrica[];
}

export interface RasterCatalogo {
  id: string;
  titulo: string;
  unidade: string;
  imagem: string;
  coordenadas: [[number, number], [number, number], [number, number], [number, number]];
  minimo: number;
  maximo: number;
  paleta: string[];
}

export interface Catalogo {
  resolucoes: Record<string, string>;
  camadas: CamadaCatalogo[];
  rasters: RasterCatalogo[];
  paleta_metricas: string[];
  atribuicoes: string[];
}

export interface ClasseLegenda {
  cor: string;
  rotulo: string;
}

export interface Legenda {
  titulo: string;
  classes: ClasseLegenda[];
}

export interface InfoFeicao {
  camada: string;
  propriedades: Record<string, unknown>;
}

export interface OpcoesMapa {
  /** Pasta com catalogo.json e os demais arquivos de `web/public/dados/`. */
  urlDados: string;
  camadaInicial?: string;
}

type Ouvinte = (info: InfoFeicao | null, evento?: { x: number; y: number }) => void;
type Colecao = GeoJSON.FeatureCollection<GeoJSON.Geometry, Record<string, unknown>>;

// ------------------------------------------------------------------------ utilidades

export const formatarNumero = (valor: number, casas = 1) =>
  new Intl.NumberFormat("pt-BR", { maximumFractionDigits: casas }).format(valor);

/** Quebras por quantis: cada classe fica com ~o mesmo número de feições. */
export function quebrasQuantis(valores: number[], classes: number): number[] {
  const v = valores.filter(Number.isFinite).sort((a, b) => a - b);
  if (v.length === 0) return [];
  const quebras: number[] = [];
  for (let i = 1; i < classes; i++) quebras.push(v[Math.floor((i * v.length) / classes)]);
  return [...new Set(quebras)].filter((q) => q > v[0]);
}

/** Escolhe `n` cores espaçadas igualmente na paleta (do claro ao escuro). */
function amostrarPaleta(paleta: string[], n: number): string[] {
  if (n === 1) return [paleta[Math.floor(paleta.length / 2)]];
  return Array.from({ length: n }, (_, i) => paleta[Math.round((i * (paleta.length - 1)) / (n - 1))]);
}

function token(nome: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
}

const temaEscuro = () =>
  document.documentElement.dataset.theme === "dark" ||
  (document.documentElement.dataset.theme !== "light" &&
    matchMedia("(prefers-color-scheme: dark)").matches);

// ----------------------------------------------------------------------------- classe

export class MapaBrasil {
  readonly mapa: MapLibre;
  readonly catalogo: Catalogo;
  camadaAtual: string;
  metricaAtual: string | null = null;
  fundoAtual: string | null = null;

  private colecoes = new Map<string, Colecao>();
  private ouvintes: Record<"passar" | "clicar", Ouvinte[]> = { passar: [], clicar: [] };
  private emFoco: { camada: string; id: string | number } | null = null;
  private resolucaoCarregada = "baixa";
  private contornoEstados = true;

  private constructor(mapa: MapLibre, catalogo: Catalogo, camadaInicial: string) {
    this.mapa = mapa;
    this.catalogo = catalogo;
    this.camadaAtual = camadaInicial;
  }

  static async criar(container: HTMLElement, opcoes: OpcoesMapa): Promise<MapaBrasil> {
    const base = opcoes.urlDados.endsWith("/") ? opcoes.urlDados : `${opcoes.urlDados}/`;
    const catalogo: Catalogo = await (await fetch(`${base}catalogo.json`)).json();
    const ids = catalogo.camadas.filter((c) => c.tipo === "area").map((c) => c.id);
    const inicial = opcoes.camadaInicial && ids.includes(opcoes.camadaInicial) ? opcoes.camadaInicial : "ufs";

    const mapa = new MapLibre({
      container,
      style: { version: 8, sources: {}, layers: [{ id: "fundo", type: "background", paint: { "background-color": token("--superficie") } }] },
      bounds: [[-74, -34], [-34, 5.5]],
      fitBoundsOptions: { padding: 16 },
      attributionControl: false,
      renderWorldCopies: false,
    });
    mapa.addControl(new NavigationControl({ showCompass: false }), "top-right");
    mapa.addControl(new AttributionControl({ compact: true, customAttribution: catalogo.atribuicoes.join(" · ") }));
    await mapa.once("load");

    const instancia = new MapaBrasil(mapa, catalogo, inicial);
    await instancia.carregar(base);
    return instancia;
  }

  // ------------------------------------------------------------- montagem das camadas

  private async carregarTopojson(base: string, resolucao: string): Promise<void> {
    const topo: Topology = await (await fetch(`${base}${this.catalogo.resolucoes[resolucao]}`)).json();
    for (const [id, objeto] of Object.entries(topo.objects)) {
      this.colecoes.set(id, feature(topo, objeto as GeometryCollection) as unknown as Colecao);
    }
  }

  private async carregar(base: string): Promise<void> {
    const { mapa, catalogo } = this;
    await this.carregarTopojson(base, "baixa");

    for (const raster of catalogo.rasters) {
      mapa.addSource(`raster-${raster.id}`, { type: "image", url: `${base}${raster.imagem}`, coordinates: raster.coordenadas });
      mapa.addLayer({ id: `raster-${raster.id}`, type: "raster", source: `raster-${raster.id}`, layout: { visibility: "none" }, paint: { "raster-opacity": 1, "raster-fade-duration": 0 } });
    }

    const areas = catalogo.camadas.filter((c) => c.tipo === "area");
    for (const camada of areas) {
      mapa.addSource(camada.id, { type: "geojson", data: this.colecoes.get(camada.id)!, promoteId: camada.chave });
      mapa.addLayer({ id: `${camada.id}-preenchimento`, type: "fill", source: camada.id, layout: { visibility: "none" } });
    }
    // Estados sem tabela de comarcas aparecem em cinza quando o recorte é "comarcas"
    mapa.addLayer({ id: "ufs-sem-comarcas", type: "fill", source: "ufs", filter: ["==", ["get", "tem_comarcas"], false], layout: { visibility: "none" } });
    for (const camada of areas) {
      mapa.addLayer({ id: `${camada.id}-borda`, type: "line", source: camada.id, layout: { visibility: "none", "line-join": "round" } });
    }
    mapa.addLayer({ id: "contorno-ufs", type: "line", source: "ufs", layout: { "line-join": "round" } });

    const cidades = catalogo.camadas.find((c) => c.id === "cidades");
    if (cidades) {
      const dados: Colecao = await (await fetch(`${base}cidades.geojson`)).json();
      this.colecoes.set("cidades", dados);
      mapa.addSource("cidades", { type: "geojson", data: dados, promoteId: "codigo_ibge" });
      mapa.addLayer({ id: "cidades", type: "circle", source: "cidades", layout: { visibility: "none" } });
    }

    this.aplicarEstilo();
    this.ligarEventos();
    this.mostrarCamada(this.camadaAtual);

    // Resolução média só quando o usuário aproxima (economiza download na visão nacional)
    mapa.on("zoomend", async () => {
      if (mapa.getZoom() >= 5.5 && this.resolucaoCarregada === "baixa" && this.catalogo.resolucoes.media) {
        this.resolucaoCarregada = "media";
        await this.carregarTopojson(base, "media");
        for (const camada of areas) (mapa.getSource(camada.id) as GeoJSONSource).setData(this.colecoes.get(camada.id)!);
      }
    });
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => this.aplicarEstilo());
  }

  /** Reaplica cores a partir das variáveis CSS (troca de tema claro/escuro). */
  aplicarEstilo(): void {
    const { mapa } = this;
    mapa.setPaintProperty("fundo", "background-color", token("--superficie"));
    const tinta = token("--tinta");
    for (const camada of this.catalogo.camadas.filter((c) => c.tipo === "area")) {
      const detalhe = camada.id === "municipios";
      mapa.setPaintProperty(`${camada.id}-borda`, "line-color", ["case", ["boolean", ["feature-state", "foco"], false], tinta, token("--borda")]);
      mapa.setPaintProperty(`${camada.id}-borda`, "line-width", ["case", ["boolean", ["feature-state", "foco"], false], 2.5, detalhe ? 0.4 : 0.8]);
    }
    mapa.setPaintProperty("ufs-sem-comarcas", "fill-color", token("--sem-dado"));
    mapa.setPaintProperty("contorno-ufs", "line-color", token("--tinta-2"));
    mapa.setPaintProperty("contorno-ufs", "line-width", 1.2);
    if (mapa.getLayer("cidades")) {
      mapa.setPaintProperty("cidades", "circle-color", tinta);
      mapa.setPaintProperty("cidades", "circle-stroke-color", token("--superficie"));
      mapa.setPaintProperty("cidades", "circle-stroke-width", 1);
      mapa.setPaintProperty("cidades", "circle-radius", ["interpolate", ["linear"], ["sqrt", ["coalesce", ["get", "populacao"], 0]], 0, 2.5, 3500, 10]);
    }
    this.colorirPor(this.metricaAtual);
  }

  private ligarEventos(): void {
    const { mapa } = this;
    const camadasInterativas = () => [
      `${this.camadaAtual}-preenchimento`,
      ...(this.visivel("ufs-sem-comarcas") ? ["ufs-sem-comarcas"] : []),
      ...(this.visivel("cidades") ? ["cidades"] : []),
    ];

    mapa.on("mousemove", (e) => {
      const [alvo] = mapa.queryRenderedFeatures(e.point, { layers: camadasInterativas() });
      this.focar(alvo ?? null);
      mapa.getCanvas().style.cursor = alvo ? "pointer" : "";
      this.emitir("passar", alvo ? this.info(alvo) : null, e.point);
    });
    mapa.on("mouseout", () => {
      this.focar(null);
      this.emitir("passar", null);
    });
    mapa.on("click", (e) => {
      const [alvo] = mapa.queryRenderedFeatures(e.point, { layers: camadasInterativas() });
      this.emitir("clicar", alvo ? this.info(alvo) : null, e.point);
    });
  }

  private info(f: MapGeoJSONFeature): InfoFeicao {
    return { camada: f.source, propriedades: f.properties };
  }

  private focar(f: MapGeoJSONFeature | null): void {
    if (this.emFoco) this.mapa.setFeatureState({ source: this.emFoco.camada, id: this.emFoco.id }, { foco: false });
    this.emFoco = f && f.id !== undefined ? { camada: f.source, id: f.id } : null;
    if (this.emFoco) this.mapa.setFeatureState({ source: this.emFoco.camada, id: this.emFoco.id }, { foco: true });
  }

  private emitir(evento: "passar" | "clicar", info: InfoFeicao | null, ponto?: { x: number; y: number }) {
    for (const fn of this.ouvintes[evento]) fn(info, ponto);
  }

  private visivel(camada: string): boolean {
    return this.mapa.getLayoutProperty(camada, "visibility") !== "none";
  }

  private exibir(camada: string, visivel: boolean): void {
    this.mapa.setLayoutProperty(camada, "visibility", visivel ? "visible" : "none");
  }

  // -------------------------------------------------------------------- API pública

  on(evento: "passar" | "clicar", fn: Ouvinte): void {
    this.ouvintes[evento].push(fn);
  }

  camada(id: string): CamadaCatalogo | undefined {
    return this.catalogo.camadas.find((c) => c.id === id);
  }

  /** Feições da camada (resolução carregada no momento), úteis para tabelas. */
  feicoes(id: string): Colecao["features"] {
    return this.colecoes.get(id)?.features ?? [];
  }

  mostrarCamada(id: string): void {
    this.camadaAtual = id;
    for (const c of this.catalogo.camadas.filter((c) => c.tipo === "area")) {
      this.exibir(`${c.id}-preenchimento`, c.id === id);
      this.exibir(`${c.id}-borda`, c.id === id);
    }
    this.exibir("ufs-sem-comarcas", id === "comarcas");
    this.exibir("contorno-ufs", this.contornoEstados && ["comarcas", "municipios"].includes(id));
    if (this.metricaAtual && !this.camada(id)?.metricas.some((m) => m.coluna === this.metricaAtual)) {
      this.metricaAtual = null;
    }
    this.colorirPor(this.metricaAtual);
  }

  mostrarContornoEstados(visivel: boolean): void {
    this.contornoEstados = visivel;
    this.mostrarCamada(this.camadaAtual);
  }

  /** Mapa coroplético: pinta cada área conforme a métrica. `null` = sem cor. */
  colorirPor(coluna: string | null): Legenda | null {
    this.metricaAtual = coluna;
    const camada = this.camadaAtual;
    const preenchimento = `${camada}-preenchimento`;
    const transparenteSobreFundo = this.fundoAtual ? 0 : 1;

    if (!coluna) {
      this.mapa.setPaintProperty(preenchimento, "fill-color", token("--preenchimento"));
      this.mapa.setPaintProperty(preenchimento, "fill-opacity", transparenteSobreFundo);
      return null;
    }

    const valores = this.feicoes(camada).map((f) => f.properties[coluna]).filter((v): v is number => typeof v === "number");
    const quebras = quebrasQuantis(valores, 7);
    // No tema escuro a rampa inverte: "pouco" fica escuro, perto da superfície
    const paleta = temaEscuro() ? [...this.catalogo.paleta_metricas].reverse() : this.catalogo.paleta_metricas;
    const cores = amostrarPaleta(paleta, quebras.length + 1);
    const degraus: (string | number)[] = [cores[0]];
    quebras.forEach((q, i) => degraus.push(q, cores[i + 1]));
    const expressao: ExpressionSpecification = [
      "case",
      ["==", ["typeof", ["get", coluna]], "number"],
      ["step", ["get", coluna], ...degraus] as unknown as ExpressionSpecification,
      token("--sem-dado"),
    ];
    this.mapa.setPaintProperty(preenchimento, "fill-color", expressao);
    this.mapa.setPaintProperty(preenchimento, "fill-opacity", this.fundoAtual ? 0.8 : 1);

    const metrica = this.camada(camada)?.metricas.find((m) => m.coluna === coluna);
    const unidade = metrica?.unidade ? ` ${metrica.unidade}` : "";
    const limites = [Math.min(...valores), ...quebras, Math.max(...valores)];
    const classes: ClasseLegenda[] = cores.map((cor, i) => ({
      cor,
      rotulo: `${formatarNumero(limites[i])} – ${formatarNumero(limites[i + 1])}${unidade}`,
    }));
    if (valores.length < this.feicoes(camada).length) classes.push({ cor: token("--sem-dado"), rotulo: "sem dado" });
    return { titulo: metrica?.rotulo ?? coluna, classes };
  }

  mostrarFundo(id: string | null): void {
    this.fundoAtual = id;
    for (const r of this.catalogo.rasters) this.exibir(`raster-${r.id}`, r.id === id);
    this.colorirPor(this.metricaAtual);
  }

  mostrarCidades(visivel: boolean, apenasSedesComarca = false): void {
    if (!this.mapa.getLayer("cidades")) return;
    this.exibir("cidades", visivel);
    this.mapa.setFilter("cidades", apenasSedesComarca ? ["==", ["get", "e_sede_comarca"], true] : null);
  }

  destruir(): void {
    this.mapa.remove();
  }
}
