import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// @ts-expect-error type error without @types/node package
import process from "node:process";
// @ts-expect-error type error without @types/node package
import { createReadStream, existsSync } from "node:fs";
const host = process.env.TAURI_DEV_HOST;

const VAD_TYPES: Record<string, string> = {
  mjs: "text/javascript",
  js: "text/javascript",
  wasm: "application/wasm",
  onnx: "application/octet-stream",
};

/**
 * Dev only: serve public/vad/* as plain files. onnxruntime dynamically imports
 * /vad/ort-wasm-simd-threaded.mjs, and Vite's dev server refuses JS imports from /public,
 * so voice answers failed in `tauri dev`. The packaged app serves these statically and is unaffected.
 */
const serveVadRaw = {
  name: "serve-vad-raw",
  configureServer(server: { middlewares: { use: (fn: (req: any, res: any, next: () => void) => void) => void } }) {
    server.middlewares.use((req, res, next) => {
      const path = String(req.url || "").split("?")[0];
      if (!path.startsWith("/vad/") || path.includes("..")) return next();
      const file = new URL(`./public${path}`, import.meta.url).pathname;
      if (!existsSync(file)) return next();
      res.setHeader("Content-Type", VAD_TYPES[path.split(".").pop() || ""] || "application/octet-stream");
      res.setHeader("Cache-Control", "no-cache");
      createReadStream(file).pipe(res);
    });
  },
};

// https://vite.dev/config/
export default defineConfig(() => ({
  plugins: [react(), serveVadRaw],

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      // 3. tell Vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },
  },
}));
