import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 5173 is the default, not a requirement. It used to be pinned because the API
// allowed exactly that origin through CORS; tests/e2e/run_stage.sh now sets
// BA_CORS_ORIGINS from the port it actually uses and passes --port to match, so
// the CLI flag overrides both of these. Do not re-describe 5173 as fixed: on an
// agent where Docker Desktop holds it, the stage runs on another port entirely.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  preview: { port: 5173, strictPort: true },
});
