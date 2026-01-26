import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    rollupOptions: {
      output: {
        manualChunks: {
          // Vendor chunks
          "react-vendor": ["react", "react-dom"],
          "router": ["@tanstack/react-router"],
          "query": ["@tanstack/react-query"],
          "react-flow": ["@xyflow/react"]
        }
      }
    },
    chunkSizeWarningLimit: 600
  }
});
