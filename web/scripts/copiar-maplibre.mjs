// O MapLibre v6 roda parte do trabalho num "web worker" (outra thread do navegador), que
// precisa ser servido como arquivo separado. Copiamos os arquivos do pacote para public/.
import { copyFileSync, mkdirSync } from "node:fs";

const origem = new URL("../../node_modules/maplibre-gl/dist/", import.meta.url);
const destino = new URL("../public/maplibre/", import.meta.url);
mkdirSync(destino, { recursive: true });
for (const arquivo of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(new URL(arquivo, origem), new URL(arquivo, destino));
}
