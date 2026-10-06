import { defineConfig } from "vite";

export default defineConfig({
  // Caminhos relativos: o site funciona em qualquer subpasta (ex.: GitHub Pages)
  base: "./",
  // O MapLibre sozinho tem ~800 kB; o aviso padrão (500 kB) não ajuda aqui
  build: { chunkSizeWarningLimit: 1200 },
});
