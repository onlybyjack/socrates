// Copies VAD model, worklet and onnxruntime wasm into public/vad so they are served locally (no CDN).
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const vadDir = dirname(require.resolve("@ricky0123/vad-web"));
// Use the exact onnxruntime-web build that vad-web itself imports, so wasm and JS versions match.
const ortDir = dirname(require.resolve("onnxruntime-web/wasm", { paths: [vadDir] }));
const out = new URL("../public/vad/", import.meta.url).pathname;
mkdirSync(out, { recursive: true });
for (const f of ["silero_vad_legacy.onnx", "silero_vad_v5.onnx", "vad.worklet.bundle.min.js"]) copyFileSync(join(vadDir, f), join(out, f));
for (const f of ["ort-wasm-simd-threaded.wasm", "ort-wasm-simd-threaded.mjs"]) copyFileSync(join(ortDir, f), join(out, f));
console.log("VAD assets copied to", out);
