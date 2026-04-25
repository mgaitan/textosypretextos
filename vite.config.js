import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [tailwindcss()],
  publicDir: false,
  build: {
    outDir: "static/assets",
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: "src/scripts/site.js",
      output: {
        entryFileNames: "site.js",
        chunkFileNames: "site.js",
        assetFileNames: (assetInfo) => {
          if ((assetInfo.names || []).some((name) => name.endsWith(".css"))) {
            return "site.css";
          }
          return "[name][extname]";
        }
      }
    }
  }
});
