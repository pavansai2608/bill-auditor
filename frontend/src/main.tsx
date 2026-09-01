import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

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
        <AuditProvider>
          <App />
        </AuditProvider>
      </ErrorBoundary>
    </QueryClientProvider>
  </StrictMode>,
);
