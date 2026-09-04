import react from "@vitejs/plugin-react-swc";
import path from "path";
import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "::",
    // Use 5173 (Vite's default) to avoid colliding with FastAPI on port 8080.
    // The dev proxy below forwards /media and /task-status etc. to the agent.
    port: 5173,
    proxy: {
      // Forward all backend API calls to FastAPI so the browser doesn't see
      // CORS errors during local development.
      "/chat": "http://localhost:8080",
      "/upload-video": "http://localhost:8080",
      "/process-video": "http://localhost:8080",
      "/task-status": "http://localhost:8080",
      "/reset-memory": "http://localhost:8080",
      "/health": "http://localhost:8080",
      "/media": "http://localhost:8080",
    },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
