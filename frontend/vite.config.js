import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// VITE_BASE: dev defaults to "/"; Docker build sets it to "/teck_dashboard/" for cloud deploy
const base = process.env.VITE_BASE || "/";

export default defineConfig({
  base,
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8002",
        changeOrigin: true,
      },
    },
  },
});
