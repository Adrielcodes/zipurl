import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, API calls and short-link redirects go to the Flask server.
export default defineConfig({
  plugins: [react()],
  // Build into /public at the repo root, which Vercel serves from its CDN
  build: { outDir: "../public", emptyOutDir: true },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:5000",
    },
  },
});
