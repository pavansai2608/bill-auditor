import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Port 5173 is fixed because the API allows exactly that origin through CORS,
// and the Selenium test drives that URL.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  preview: { port: 5173, strictPort: true },
});
