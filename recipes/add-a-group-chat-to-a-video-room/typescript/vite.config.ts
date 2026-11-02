import { defineConfig } from "vite";

// The page and the Flask app share one origin in development: Vite serves
// index.html and forwards POST /token to python/app.py on port 8080, so the
// browser never needs the project API token or a second host.
export default defineConfig({
  server: {
    proxy: {
      "/token": process.env["TOKEN_SERVER"] ?? "http://localhost:8080",
    },
  },
});
