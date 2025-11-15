import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, afterEach, expect, test, vi } from "vitest";
import ExplainPage from "../../pages/Explain";
import { ProjectProvider } from "../../context/ProjectContext";

let queryClient: QueryClient;

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false }
    }
  });

const planList = [
  {
    plan_id: "plan-1234",
    ts: new Date("2024-01-01T12:00:00Z").toISOString(),
    project: "context_engine",
    module: "core",
    status: "ok",
    route: "test-route",
    latency_ms: 120
  }
];

const planDetail = {
  ...planList[0],
  source_latencies: { postgres: 80 },
  result_sizes: { code: 2, docs: 1 },
  params: { task: "demo task", max_code_chunks: 8, graph_depth: 3 },
  token_budget: {
    budget: 6000,
    total_tokens: 2000,
    code_tokens: 1500,
    doc_tokens: 500,
    truncated_code: 0,
    truncated_docs: 0
  },
  detail: {
    explain: { plan_id: planList[0].plan_id },
    code: [{ path: "file.py", score: 0.9 }],
    docs: [{ doc: "README", section: "Intro", score: 0.7 }]
  }
};

beforeEach(() => {
  queryClient = createTestQueryClient();
  const fetchMock = vi.fn(async (url: string | URL) => {
    const href = typeof url === "string" ? url : url.toString();
    // eslint-disable-next-line no-console
    console.log("fetch stub called:", href);
    if (href.includes("/plans?")) {
      return {
        ok: true,
        json: async () => planList
      } as Response;
    }
    if (href.includes(`/plans/${planList[0].plan_id}`)) {
      return {
        ok: true,
        json: async () => planDetail
      } as Response;
    }
    throw new Error(`Unhandled fetch ${href}`);
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  queryClient.clear();
  vi.restoreAllMocks();
});

function renderExplain(): void {
  render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ProjectProvider>
          <ExplainPage />
        </ProjectProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

test("renders plan list and rerun controls", async () => {
  renderExplain();
  // Ensure rendering progressed
  // eslint-disable-next-line no-console
  console.log("Explain page rendered");
  expect(await screen.findByText(/plan-123/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Run get_context/i })).toBeInTheDocument();
  expect(screen.getByText(/demo task/i)).toBeInTheDocument();
});
