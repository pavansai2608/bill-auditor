import { copyFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";

/**
 * GitHub Pages serves a project site from a subpath - /bill-auditor/ - and
 * has no server in front of it to rewrite anything. Two consequences, both
 * handled here rather than in the app:
 *
 *  - every asset URL has to be written relative to that subpath, or it
 *    resolves to the domain root and 404s in production while working
 *    perfectly on localhost. That is `base`.
 *  - a hard refresh on /bill-auditor/audit asks Pages for a file that is not
 *    there, and Pages answers with its own 404 page. Copying index.html to
 *    404.html is the standard workaround: Pages serves it, the bundle boots,
 *    and the router reads the URL it was actually asked for.
 *
 * Neither applies to the other three ways this app is served - `npm run dev`,
 * the nginx image, and tests/e2e/run_stage.sh - all of which serve from root,
 * and nginx already rewrites unknown paths with try_files. So this is a build
 * mode, not a switch in the source: `vite build` is unchanged and
 * `vite build --mode pages` reads frontend/.env.pages.
 */
function spaFallback(): Plugin {
  let outDir = "dist";
  return {
    name: "ba-spa-404-fallback",
    apply: "build",
    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir);
    },
    closeBundle() {
      const index = join(outDir, "index.html");
      if (!existsSync(index)) return;
      copyFileSync(index, join(outDir, "404.html"));
    },
  };
}

// 5173 is the default, not a requirement. It used to be pinned because the API
// allowed exactly that origin through CORS; tests/e2e/run_stage.sh now sets
// BA_CORS_ORIGINS from the port it actually uses and passes --port to match, so
// the CLI flag overrides both of these. Do not re-describe 5173 as fixed: on an
// agent where Docker Desktop holds it, the stage runs on another port entirely.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  return {
    // "/" everywhere except the Pages build. import.meta.env.BASE_URL carries
    // it into the app, which is what the router basename reads, so the two can
    // never disagree.
    base: env.VITE_BASE_PATH || "/",
    plugins: [react(), ...(env.VITE_SPA_404 === "true" ? [spaFallback()] : [])],
    server: { port: 5173, strictPort: true },
    preview: { port: 5173, strictPort: true },
  };
});
