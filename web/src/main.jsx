import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Router } from "wouter";
import App from "./App.jsx";
import { BASE_PATH } from "./constants";
import "@fontsource-variable/inter";
import "@fontsource/bricolage-grotesque/700.css";
import "@fontsource/bricolage-grotesque/800.css";
import "@fontsource/cascadia-code/400.css";
import "./styles/index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, retry: 1 },
  },
});

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <Router base={BASE_PATH.replace(/\/+$/, "")}>
        <App />
      </Router>
    </QueryClientProvider>
  </React.StrictMode>
);
