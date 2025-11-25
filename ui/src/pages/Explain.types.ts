export type PlanListItem = {
  plan_id: string;
  ts: string;
  project: string;
  module: string | null;
  status: string;
  route?: string | null;
  latency_ms?: number | null;
};

export type Artifact = {
  uri?: string;
  path?: string;
  doc?: string;
  section?: string;
  score?: number;
  sim_vec?: number;
  sim_bm25?: number;
  bm25_rank_pos?: number | null;
  bias_pin?: number;
  penalty_neg?: number;
};

export type TokenBudget = {
  budget: number;
  total_tokens: number;
  code_tokens: number;
  doc_tokens: number;
  truncated_code: number;
  truncated_docs: number;
};

export type PlanDetail = PlanListItem & {
  source_latencies?: Record<string, number>;
  result_sizes?: Record<string, number>;
  params?: Record<string, any>;
  token_budget?: TokenBudget | null;
  detail: {
    explain?: Record<string, any>;
    code?: Artifact[];
    docs?: Artifact[];
  };
};
