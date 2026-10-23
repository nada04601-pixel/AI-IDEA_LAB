import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

// 웹 데모: npm run web(개발 서버), npm run build:web(→ dist-web/, GitHub Pages의 dropship/에 배포)
export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  base: "./",
  build: { outDir: fileURLToPath(new URL("../dist-web", import.meta.url)), emptyOutDir: true },
});
