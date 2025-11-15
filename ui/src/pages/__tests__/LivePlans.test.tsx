import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import LivePlansPage from "../../pages/LivePlans";
import { ProjectProvider } from "../../context/ProjectContext";

let queryClient: QueryClient;

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false }
    }
  });

beforeEach(() => {
  queryClient = createTestQueryClient();
  vi.stubGlobal(
    "EventSource",
    class {
      addEventListener() {}
      close() {}
    }
  );
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => []
    })
  );
});

afterEach(() => {
  queryClient.clear();
  vi.restoreAllMocks();
});

function renderWithProviders() {
  render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ProjectProvider>
          <LivePlansPage />
        </ProjectProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

test("renders Live Plans heading", async () => {
  renderWithProviders();
  expect(await screen.findByText(/Live Plans/i)).toBeInTheDocument();
});
