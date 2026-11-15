import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173, // must match CORS_ORIGINS in the backend
    // With VITE_API_URL=/api the dev server forwards API calls (and WebSockets) to the
    // backend, the same way nginx does in production (frontend/nginx.conf).
    proxy: {
      "/api": {
        target: process.env.API_PROXY_TARGET ?? "http://localhost:8000",
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
