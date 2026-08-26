import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@fontsource/fira-sans/latin-400.css";
import "@fontsource/fira-sans/latin-500.css";
import "@fontsource/fira-sans/latin-600.css";
import "@fontsource/fira-sans/latin-700.css";
import { App } from "./app";
import "./fonts.css";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (
          error instanceof Error &&
          "status" in error &&
          Number(error.status) < 500
        )
          return false;
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
      staleTime: 15_000,
    },
    mutations: { retry: false },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
