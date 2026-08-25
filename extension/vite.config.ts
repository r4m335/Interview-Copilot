import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: resolve(__dirname, "src/popup/index.html"),
        offscreen: resolve(__dirname, "src/offscreen/offscreen.html"),
        "service-worker": resolve(
          __dirname,
          "src/background/service-worker.ts"
        ),
        "meeting-detector": resolve(
          __dirname,
          "src/content/meeting-detector.ts"
        ),
      },
      output: {
        entryFileNames: (chunk) => {
          // Service worker and content scripts need predictable names
          if (
            chunk.name === "service-worker" ||
            chunk.name === "meeting-detector"
          ) {
            return "[name].js";
          }
          return "assets/[name]-[hash].js";
        },
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash].[ext]",
      },
    },
  },
  // Copy manifest.json and audio worklet to dist
  publicDir: "public",
});
