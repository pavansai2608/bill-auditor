import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AuditProvider } from "./context/AuditContext";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // The report does not change once it is done, so nothing needs refetching
      // when the tab regains focus. The polling interval is set per query.
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        {/* import.meta.env.BASE_URL is whatever `base` the build used: "/"
            for dev, the nginx image and the E2E stage, "/bill-auditor/" for
            the GitHub Pages build. Without it every route on Pages resolves
            against the domain root and 404s. Reading it from the build rather
            than repeating the literal means the two cannot drift apart. */}
        <BrowserRouter basename={import.meta.env.BASE_URL}>
          <AuditProvider>
            <App />
          </AuditProvider>
        </BrowserRouter>
      </ErrorBoundary>
    </QueryClientProvider>
  </StrictMode>,
);
