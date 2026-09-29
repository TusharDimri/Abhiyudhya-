import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { AuthProvider } from "./lib/auth";
import { ToastProvider } from "./lib/toast";
import { LocationProvider } from "./lib/location";
import "./theme/theme.css";
import "./theme/layout.css";
import "./theme/design.css";   // the look of the whole app - last, so it has the final say

// A refresh starts the page afresh: filters picked before it are dropped from
// the address (the page's own tab is kept). Links opened any other way keep theirs.
(function dropFiltersOnRefresh() {
  try {
    const nav = performance.getEntriesByType("navigation")[0];
    if (!nav || nav.type !== "reload" || !window.location.search) return;
    const url = new URL(window.location.href);
    const keep = new URLSearchParams();
    for (const k of ["tab", "manage"]) if (url.searchParams.get(k)) keep.set(k, url.searchParams.get(k));
    window.history.replaceState(null, "", url.pathname + (keep.toString() ? `?${keep}` : "") + url.hash);
  } catch { /* an old browser: keep the address as it is */ }
})();

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          <AuthProvider>
            <LocationProvider>
              <App />
            </LocationProvider>
          </AuthProvider>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
