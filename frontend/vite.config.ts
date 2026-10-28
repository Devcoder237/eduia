/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Configuration Vite.
 * - Dev : /api et /health sont proxifiés vers VITE_DEV_PROXY (défaut http://localhost:8080).
 * - Build de production : VITE_API_URL est OBLIGATOIRE (URL Render), sauf VITE_ALLOW_SAME_ORIGIN=true
 *   (déploiement derrière un reverse proxy). Cela évite de publier un front qui appelle localhost.
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  if (mode === "production" && !env.VITE_API_URL && env.VITE_ALLOW_SAME_ORIGIN !== "true") {
    throw new Error(
      "VITE_API_URL est manquant : définissez l'URL de l'API (ex. https://eduia-api.onrender.com) " +
        "dans les variables de build, ou VITE_ALLOW_SAME_ORIGIN=true pour un déploiement same-origin.",
    );
  }
  const target = env.VITE_DEV_PROXY || "http://localhost:8080";
  return {
    plugins: [react()],
    server: { port: 5173, proxy: { "/api": target, "/health": target } },
    build: { target: "es2020", sourcemap: false, chunkSizeWarningLimit: 600 },
    test: { environment: "jsdom", include: ["src/**/*.test.ts", "src/**/*.test.tsx"] },
  };
});
