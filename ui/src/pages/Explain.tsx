import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  ButtonGroup,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  LinearProgress,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  MenuItem,
  TextField,
  Stack,
  Typography
} from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis
} from "recharts";
import { API_BASE, apiGet } from "../api/client";
import { useProject } from "../context/ProjectContext";
import { useSearchParams } from "react-router-dom";

type PlanListItem = {
  plan_id: string;
  ts: string;
  project: string;
  module: string | null;
  status: string;
  route?: string | null;
  latency_ms?: number | null;
};

type Artifact = {
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

type TokenBudget = {
  budget: number;
  total_tokens: number;
  code_tokens: number;
  doc_tokens: number;
  truncated_code: number;
  truncated_docs: number;
};

type PlanDetail = PlanListItem & {
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

const CHART_COLORS = ["#4dabf5", "#ce93d8", "#ffb74d", "#81c784", "#f48fb1", "#64b5f6"];

const scorePercent = (score: number | undefined, max: number): number => {
  if (!score || max <= 0) return 0;
  return Math.min(100, Math.round((score / max) * 100));
};

const downloadBlob = (filename: string, content: BlobPart, type = "application/json"): void => {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const artifactsToCsv = (artifacts: Artifact[], kind: "code" | "doc"): string => {
  const headers = ["kind", "path_or_doc", "uri", "score", "sim_vec", "sim_bm25", "bias_pin", "penalty_neg"];
  const rows = artifacts.map((art) => [
    kind,
    kind === "code" ? art.path ?? "" : `${art.doc ?? ""}#${art.section ?? ""}`,
    art.uri ?? "",
    art.score ?? "",
    art.sim_vec ?? "",
    art.sim_bm25 ?? "",
    art.bias_pin ?? "",
    art.penalty_neg ?? ""
  ]);
  return [headers, ...rows]
    .map((line) => line.map((value) => `"${String(value ?? "").replace(/"/g, '""')}"`).join(","))
    .join("\n");
};

function ArtifactList({ title, items }: { title: string; items: Artifact[] }): JSX.Element {
  const maxScore = useMemo(() => Math.max(...items.map((a) => a.score ?? 0), 1), [items]);

  if (!items.length) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Нет артефактов
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title} ({items.length})
        </Typography>
        <Stack spacing={2}>
          {items.map((art, idx) => (
            <Box key={`${title}-${idx}`} p={2} bgcolor="background.paper" borderRadius={2} border="1px solid rgba(255,255,255,0.05)">
              <Typography variant="subtitle2">
                {art.path || art.uri || `${art.doc}#${art.section}`}
              </Typography>
              <LinearProgress
                variant="determinate"
                value={scorePercent(art.score, maxScore)}
                sx={{ my: 1, height: 8, borderRadius: 5 }}
              />
              <Stack direction="row" spacing={1} flexWrap="wrap">
                <Chip label={`score ${art.score?.toFixed(3) ?? "n/a"}`} size="small" />
                <Chip label={`vec ${art.sim_vec?.toFixed(2) ?? "n/a"}`} size="small" />
                <Chip label={`bm25 ${art.sim_bm25?.toFixed(2) ?? "n/a"}`} size="small" />
                {art.bias_pin && art.bias_pin > 0 && (
                  <Chip label={`pin +${art.bias_pin.toFixed(2)}`} color="success" size="small" />
                )}
                {art.penalty_neg && art.penalty_neg > 0 && (
                  <Chip label={`forget -${art.penalty_neg.toFixed(2)}`} color="error" size="small" />
                )}
              </Stack>
            </Box>
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}

function ExplainPage(): JSX.Element {
  const { project } = useProject();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [formState, setFormState] = useState({
    maxCode: 8,
    maxDoc: 5,
    graphDepth: 3,
    tokenBudget: 6000,
    mode: "hybrid",
    vectorWeight: 0.7,
    bm25Weight: 0.3,
    vectorK: 120,
    bm25K: 120,
  });

  const modeTips: Record<string, string> = {
    hybrid: "Сбалансированный режим: объединяет vector + BM25, подходит для большинства задач",
    vector: "Векторный поиск: лучше работает на коде с семантикой, но требует актуальных эмбеддингов",
    lexical: "Лексический режим: быстрый по ключевым словам, полезен для документации/спек"
  };
  const [rerunStatus, setRerunStatus] = useState<"idle" | "running" | "error" | "success">("idle");
  const [rerunResult, setRerunResult] = useState<any>(null);
  const [rerunError, setRerunError] = useState<string | null>(null);
  const [rerunHistory, setRerunHistory] = useState<
    { timestamp: string; summary: string; jobId?: string; payload: any }[]
  >([]);

  const {
    data: plans = [],
    isLoading: plansLoading,
    error: plansError
  } = useQuery<PlanListItem[]>({
    queryKey: ["plan-list", project],
    queryFn: async () => await apiGet<PlanListItem[]>(`/plans?limit=40&project=${encodeURIComponent(project)}`)
  });

  useEffect(() => {
    const qp = searchParams.get("plan");
    if (qp && qp !== selectedPlan) {
      setSelectedPlan(qp);
      return;
    }
    if (!selectedPlan && plans.length > 0) {
      setSelectedPlan(plans[0].plan_id);
    }
  }, [plans, selectedPlan, searchParams]);

  useEffect(() => {
    setSelectedPlan(null);
    setSearchParams((prev) => {
      if (!prev.get("plan")) return prev;
      const next = new URLSearchParams(prev);
      next.delete("plan");
      return next;
    });
  }, [project, setSearchParams]);

  const {
    data: planDetail,
    isLoading: detailLoading,
    error: detailError
  } = useQuery<PlanDetail>({
    queryKey: ["plan-detail", project, selectedPlan],
    queryFn: async () => await apiGet<PlanDetail>(`/plans/${selectedPlan}`),
    enabled: Boolean(selectedPlan)
  });

  const explain = planDetail?.detail?.explain;
  const codeArtifacts = planDetail?.detail?.code ?? [];
  const docArtifacts = planDetail?.detail?.docs ?? [];
  const tokenBudget = planDetail?.token_budget;
  const sourceLatencies = planDetail?.source_latencies ?? {};
  const resultSizes = planDetail?.result_sizes ?? {};
  const params = planDetail?.params || explain?.params || {};
  const rerunTask = params?.task as string | undefined;

  const derivedFormDefaults = useMemo(
    () => ({
      maxCode: params?.max_code_chunks ?? 8,
      maxDoc: params?.max_doc_chunks ?? 5,
      graphDepth: params?.graph_depth ?? 3,
      tokenBudget: planDetail?.token_budget?.budget ?? 6000,
      mode: params?.retrieval?.mode ?? explain?.params?.retrieval?.mode ?? "hybrid",
      vectorWeight: params?.retrieval?.weights?.vector ?? explain?.params?.retrieval?.weights?.vector ?? 0.7,
      bm25Weight: params?.retrieval?.weights?.bm25 ?? explain?.params?.retrieval?.weights?.bm25 ?? 0.3,
      vectorK: params?.retrieval?.candidates?.vector_k ?? explain?.params?.retrieval?.candidates?.vector_k ?? 120,
      bm25K: params?.retrieval?.candidates?.bm25_k ?? explain?.params?.retrieval?.candidates?.bm25_k ?? 120,
    }),
    [params, planDetail?.token_budget?.budget, explain?.params?.retrieval]
  );

  useEffect(() => {
    setFormState(derivedFormDefaults);
    setRerunStatus("idle");
    setRerunResult(null);
    setRerunError(null);
    setRerunHistory([]);
  }, [derivedFormDefaults, selectedPlan]);

  const tokenChartData = useMemo(
    () =>
      tokenBudget
        ? [
            { name: "Code", value: tokenBudget.code_tokens ?? 0 },
            { name: "Docs", value: tokenBudget.doc_tokens ?? 0 }
          ]
        : [],
    [tokenBudget]
  );

  const weightsData = useMemo(
    () => [
      { name: "Vector", value: params?.retrieval?.weights?.vector ?? 0 },
      { name: "BM25", value: params?.retrieval?.weights?.bm25 ?? 0 }
    ],
    [params?.retrieval?.weights?.bm25, params?.retrieval?.weights?.vector]
  );

  const candidateData = useMemo(
    () => [
      { name: "vector_k", value: params?.retrieval?.candidates?.vector_k ?? 0 },
      { name: "bm25_k", value: params?.retrieval?.candidates?.bm25_k ?? 0 }
    ],
    [params?.retrieval?.candidates?.bm25_k, params?.retrieval?.candidates?.vector_k]
  );

  const feedbackStats = useMemo(() => {
    const positive = [...codeArtifacts, ...docArtifacts].filter((art) => (art.bias_pin ?? 0) > 0).length;
    const negative = [...codeArtifacts, ...docArtifacts].filter((art) => (art.penalty_neg ?? 0) > 0).length;
    return { positive, negative };
  }, [codeArtifacts, docArtifacts]);

  const handleFormChange = (field: keyof typeof formState, value: number | string) => {
    setFormState((prev) => ({ ...prev, [field]: value }));
  };

  useEffect(() => {
    if (!planDetail) return;
    if (planDetail?.params?.retrieval?.mode && planDetail.params.retrieval.mode !== formState.mode) {
      setFormState((prev) => ({ ...prev, mode: planDetail.params?.retrieval?.mode }));
    }
  }, [planDetail]);

  const rerunSummaryFor = (result: any): string => {
    if (!result) return "";
    const detail = result as { code?: Array<unknown>; docs?: Array<unknown>; status?: string };
    const codeCount = detail.code?.length ?? 0;
    const docCount = detail.docs?.length ?? 0;
    return `status ${detail.status ?? ""} - code ${codeCount} - docs ${docCount}`;
  };

  const handleRerun = async (): Promise<void> => {
    if (!planDetail || !rerunTask) {
      setRerunError("Не удалось определить исходное задание для rerun.");
      setRerunStatus("error");
      return;
    }
    setRerunStatus("running");
    setRerunError(null);
    setRerunResult(null);
    try {
      const payload = {
        project,
        task: rerunTask,
        max_code_chunks: formState.maxCode,
        max_doc_chunks: formState.maxDoc,
        graph_depth: formState.graphDepth,
        token_budget: formState.tokenBudget,
        retrieval: {
          mode: formState.mode,
          weights: { vector: formState.vectorWeight, bm25: formState.bm25Weight },
          candidates: { vector_k: formState.vectorK, bm25_k: formState.bm25K },
        },
      };
      const resp = await fetch(`${API_BASE}/tools/get_context`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        throw new Error((await resp.text()) || "get_context failed");
      }
      const json = await resp.json();
      setRerunResult(json);
      setRerunStatus("success");
      setRerunHistory((prev) => [
        {
          timestamp: new Date().toISOString(),
          summary: rerunSummaryFor(json),
          payload,
        },
        ...prev,
      ]);
    } catch (err) {
      setRerunError((err as Error).message);
      setRerunStatus("error");
    }
  };

  const rerunSummary = useMemo(() => {
    if (!rerunResult) return null;
    return rerunSummaryFor(rerunResult);
  }, [rerunResult]);

  const pinnedArtifacts = useMemo(
    () =>
      [...codeArtifacts, ...docArtifacts]
        .filter((art) => (art.bias_pin ?? 0) > 0)
        .sort((a, b) => (b.bias_pin ?? 0) - (a.bias_pin ?? 0))
        .slice(0, 3),
    [codeArtifacts, docArtifacts]
  );

  const forgottenArtifacts = useMemo(
    () =>
      [...codeArtifacts, ...docArtifacts]
        .filter((art) => (art.penalty_neg ?? 0) > 0)
        .sort((a, b) => (b.penalty_neg ?? 0) - (a.penalty_neg ?? 0))
        .slice(0, 3),
    [codeArtifacts, docArtifacts]
  );

  const handleExportJson = () => {
    if (!planDetail) return;
    downloadBlob(`plan-${planDetail.plan_id}.json`, JSON.stringify(planDetail, null, 2));
  };

  const handleExportCsv = () => {
    const csv = `${artifactsToCsv(codeArtifacts, "code")}\n${artifactsToCsv(docArtifacts, "doc")}`;
    downloadBlob(`plan-${planDetail?.plan_id}-artifacts.csv`, csv, "text/csv");
  };

  return (
    <Grid container spacing={3}>
      <Grid item xs={12} md={3}>
        <Card sx={{ height: "100%" }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Plans
            </Typography>
            {plansLoading && <CircularProgress size={24} />}
            {plansError && <Alert severity="error">{(plansError as Error).message}</Alert>}
            <List dense>
              {plans.map((plan) => (
                <ListItem key={plan.plan_id} disablePadding>
                  <ListItemButton
                    selected={plan.plan_id === selectedPlan}
                    onClick={() => setSelectedPlan(plan.plan_id)}
                  >
                    <ListItemText
                      primary={plan.plan_id.slice(0, 8)}
                      secondary={
                        <>
                          {new Date(plan.ts).toLocaleTimeString()}
                          {" - "}
                          {plan.module ?? "no module"}
                          {plan.latency_ms != null ? ` - ${plan.latency_ms} ms` : ""}
                        </>
                      }
                    />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12} md={9}>
        {detailLoading && <CircularProgress />}
        {detailError && <Alert severity="error">{(detailError as Error).message}</Alert>}
        {planDetail && (
          <Stack spacing={3}>
            <Card>
              <CardContent>
                <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
                  <Typography variant="h5">Plan {planDetail.plan_id}</Typography>
                  <Chip label={planDetail.status} color={planDetail.status === "ok" ? "success" : "error"} />
                  <Typography variant="body2" color="text.secondary">
                    {new Date(planDetail.ts).toLocaleString()}
                  </Typography>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Button size="small" variant="outlined" onClick={() => navigator.clipboard?.writeText(planDetail.plan_id)}>
                      Copy plan_id
                    </Button>
                    <Button size="small" variant="text" component={RouterLink} to="/">
                      Open Live Plans
                    </Button>
                    <Button size="small" variant="text" component={RouterLink} to={`/jobs?plan=${planDetail.plan_id}`}>
                      View jobs
                    </Button>
                  </Stack>
                </Stack>
                <Stack direction={{ xs: "column", md: "row" }} spacing={2} mt={1} flexWrap="wrap">
                  <Typography variant="body2" color="text.secondary">
                    Module: {planDetail.module ?? "auto"}
                  </Typography>
                  {planDetail.route && (
                    <Typography variant="body2" color="text.secondary">
                      Route: {planDetail.route}
                    </Typography>
                  )}
                  {planDetail.latency_ms != null && (
                    <Typography variant="body2" color="text.secondary">
                      Latency: {planDetail.latency_ms} ms
                    </Typography>
                  )}
                </Stack>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={1} mt={2}>
                  <ButtonGroup variant="outlined" size="small">
                    <Button onClick={handleExportJson} disabled={!planDetail}>
                      Export JSON
                    </Button>
                    <Button onClick={handleExportCsv} disabled={!planDetail}>
                      Artifacts CSV
                    </Button>
                  </ButtonGroup>
                </Stack>
                {Object.keys(sourceLatencies).length > 0 && (
                  <Stack direction="row" spacing={1} flexWrap="wrap" mt={2}>
                    {Object.entries(sourceLatencies).map(([key, value]) => (
                      <Chip key={key} label={`${key}: ${value} ms`} size="small" />
                    ))}
                  </Stack>
                )}
                {tokenBudget && tokenChartData.length > 0 && (
                  <Grid container spacing={2} mt={1}>
                    <Grid item xs={12} md={6}>
                      <Typography variant="subtitle2">Token Budget</Typography>
                      <LinearProgress
                        variant="determinate"
                        value={Math.min(
                          100,
                          Math.round(((tokenBudget.total_tokens ?? 0) / tokenBudget.budget) * 100)
                        )}
                        sx={{ height: 10, borderRadius: 5, my: 1 }}
                      />
                      <Typography variant="body2" color="text.secondary">
                        {tokenBudget.total_tokens}/{tokenBudget.budget} tokens - code {tokenBudget.code_tokens}, docs{" "}
                        {tokenBudget.doc_tokens}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} md={6} sx={{ height: 160 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={tokenChartData} barSize={32}>
                          <XAxis dataKey="name" />
                          <YAxis allowDecimals={false} />
                          <RechartsTooltip />
                          <Bar dataKey="value">
                            {tokenChartData.map((entry, index) => (
                              <Cell
                                key={`token-cell-${entry.name}`}
                                fill={CHART_COLORS[index % CHART_COLORS.length]}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </Grid>
                  </Grid>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Rerun get_context
                </Typography>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Task: {rerunTask ?? "n/a"}
                </Typography>
                {rerunError && (
                  <Alert severity="error" sx={{ my: 2 }}>
                    {rerunError}
                  </Alert>
                )}
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6} md={3}>
                    <TextField
                      label="Mode"
                      select
                      value={formState.mode}
                      onChange={(e) => handleFormChange("mode", e.target.value)}
                      fullWidth
                      helperText={modeTips[formState.mode]}
                    >
                      <MenuItem value="hybrid">hybrid — баланс vector/BM25</MenuItem>
                      <MenuItem value="vector">vector — упор на семантику</MenuItem>
                      <MenuItem value="lexical">lexical — текстовые ключи</MenuItem>
                    </TextField>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <TextField
                      label="max_code_chunks"
                      type="number"
                      value={formState.maxCode}
                      onChange={(e) => handleFormChange("maxCode", Number(e.target.value))}
                      fullWidth
                    />
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <TextField
                      label="max_doc_chunks"
                      type="number"
                      value={formState.maxDoc}
                      onChange={(e) => handleFormChange("maxDoc", Number(e.target.value))}
                      fullWidth
                    />
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <TextField
                      label="graph_depth"
                      type="number"
                      value={formState.graphDepth}
                      onChange={(e) => handleFormChange("graphDepth", Number(e.target.value))}
                      fullWidth
                    />
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <TextField
                      label="token_budget"
                      type="number"
                      value={formState.tokenBudget}
                      onChange={(e) => handleFormChange("tokenBudget", Number(e.target.value))}
                      fullWidth
                    />
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <TextField
                      label="vector weight"
                      type="number"
                      inputProps={{ step: 0.05, min: 0, max: 1 }}
                      value={formState.vectorWeight}
                      onChange={(e) => handleFormChange("vectorWeight", Number(e.target.value))}
                      fullWidth
                    />
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <TextField
                      label="bm25 weight"
                      type="number"
                      inputProps={{ step: 0.05, min: 0, max: 1 }}
                      value={formState.bm25Weight}
                      onChange={(e) => handleFormChange("bm25Weight", Number(e.target.value))}
                      fullWidth
                    />
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <TextField
                      label="vector_k"
                      type="number"
                      value={formState.vectorK}
                      onChange={(e) => handleFormChange("vectorK", Number(e.target.value))}
                      fullWidth
                    />
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <TextField
                      label="bm25_k"
                      type="number"
                      value={formState.bm25K}
                      onChange={(e) => handleFormChange("bm25K", Number(e.target.value))}
                      fullWidth
                    />
                  </Grid>
                </Grid>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={2} mt={2} alignItems="center">
                  <Button
                    variant="contained"
                    disabled={rerunStatus === "running" || !rerunTask}
                    onClick={handleRerun}
                  >
                    {rerunStatus === "running" ? "Running..." : "Run get_context"}
                  </Button>
                  {rerunStatus === "success" && rerunSummary && (
                    <Typography variant="body2" color="success.main">
                      {rerunSummary}
                    </Typography>
                  )}
                </Stack>
                {rerunResult && (
                  <Box component="pre" sx={{ mt: 2, maxHeight: 240, overflow: "auto" }}>
                    {JSON.stringify(rerunResult, null, 2)}
                  </Box>
                )}
                {rerunHistory.length > 0 && (
                  <Box mt={3}>
                    <Typography variant="subtitle2" gutterBottom>
                      Rerun History
                    </Typography>
                    <List dense>
                      {rerunHistory.map((entry, idx) => (
                        <ListItem key={`${entry.timestamp}-${idx}`} disablePadding>
                          <ListItemText
                            primary={new Date(entry.timestamp).toLocaleString()}
                            secondary={entry.summary}
                          />
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                )}
              </CardContent>
            </Card>

            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <ArtifactList title="Code" items={codeArtifacts} />
              </Grid>
              <Grid item xs={12} md={6}>
                <ArtifactList title="Docs" items={docArtifacts} />
              </Grid>
            </Grid>

            <Card>
              <CardContent>
                <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" alignItems={{ md: "center" }}>
                  <Typography variant="h6">Retrieval Parameters</Typography>
                  {params?.config_checksum && (
                    <Typography variant="caption" color="text.secondary">
                      Config checksum: {params.config_checksum}
                    </Typography>
                  )}
                </Stack>
                <Divider sx={{ my: 2 }} />
                <Grid container spacing={2}>
                  <Grid item xs={12} md={3}>
                    <Typography variant="subtitle2">Mode</Typography>
                    <Typography>{params?.retrieval?.mode ?? "hybrid"}</Typography>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Typography variant="subtitle2">max_code_chunks</Typography>
                    <Typography>{params?.max_code_chunks ?? "-"}</Typography>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Typography variant="subtitle2">max_doc_chunks</Typography>
                    <Typography>{params?.max_doc_chunks ?? "-"}</Typography>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Typography variant="subtitle2">graph_depth</Typography>
                    <Typography>{params?.graph_depth ?? "-"}</Typography>
                  </Grid>
                </Grid>

                <Grid container spacing={2} mt={1}>
                  <Grid item xs={12} md={6} sx={{ height: 220 }}>
                    <Typography variant="subtitle2">Weights</Typography>
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={weightsData}
                          dataKey="value"
                          nameKey="name"
                          innerRadius={40}
                          outerRadius={80}
                          paddingAngle={4}
                        >
                          {weightsData.map((entry, index) => (
                            <Cell key={`weights-${entry.name}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                          ))}
                        </Pie>
                        <RechartsTooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </Grid>
                  <Grid item xs={12} md={6} sx={{ height: 220 }}>
                    <Typography variant="subtitle2">Candidate limits</Typography>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={candidateData} barSize={32}>
                        <XAxis dataKey="name" />
                        <YAxis allowDecimals={false} />
                        <RechartsTooltip />
                        <Bar dataKey="value" fill={CHART_COLORS[2]}>
                          {candidateData.map((entry, index) => (
                            <Cell key={`cand-${entry.name}`} fill={CHART_COLORS[(index + 2) % CHART_COLORS.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </Grid>
                </Grid>

                {Object.keys(resultSizes).length > 0 && (
                  <>
                    <Divider sx={{ my: 2 }} />
                    <Typography variant="subtitle2">Result Sizes</Typography>
                    <Stack direction="row" spacing={1} flexWrap="wrap" mt={1}>
                      {Object.entries(resultSizes).map(([key, value]) => (
                        <Chip key={key} label={`${key}: ${value}`} size="small" />
                      ))}
                    </Stack>
                  </>
                )}
              </CardContent>
            </Card>


            <Card>
              <CardContent>
                <Typography variant="h6">Feedback & Bias</Typography>
                <Divider sx={{ my: 2 }} />
                <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
                  <Box>
                    <Typography variant="subtitle2">Positive pins</Typography>
                    <Typography variant="h4">{feedbackStats.positive}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="subtitle2">Negative (forget)</Typography>
                    <Typography variant="h4">{feedbackStats.negative}</Typography>
                  </Box>
                </Stack>
                <Grid container spacing={2} mt={1}>
                  <Grid item xs={12} md={6}>
                    <Typography variant="subtitle2">Top pins</Typography>
                    {pinnedArtifacts.length === 0 ? (
                      <Typography variant="body2" color="text.secondary">
                        нет данных
                      </Typography>
                    ) : (
                      <List dense>
                        {pinnedArtifacts.map((art, idx) => (
                          <ListItem key={`pin-${idx}`} disablePadding>
                            <ListItemText
                              primary={art.path || art.uri || `${art.doc}#${art.section}`}
                              secondary={`bias +${art.bias_pin?.toFixed(2) ?? "0"}`}
                            />
                          </ListItem>
                        ))}
                      </List>
                    )}
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="subtitle2">Top forgets</Typography>
                    {forgottenArtifacts.length === 0 ? (
                      <Typography variant="body2" color="text.secondary">
                        нет данных
                      </Typography>
                    ) : (
                      <List dense>
                        {forgottenArtifacts.map((art, idx) => (
                          <ListItem key={`forget-${idx}`} disablePadding>
                            <ListItemText
                              primary={art.path || art.uri || `${art.doc}#${art.section}`}
                              secondary={`penalty -${art.penalty_neg?.toFixed(2) ?? "0"}`}
                            />
                          </ListItem>
                        ))}
                      </List>
                    )}
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Stack>
        )}
      </Grid>
    </Grid>
  );
}

export default ExplainPage;
