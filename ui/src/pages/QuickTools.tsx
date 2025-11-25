import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Grid,
  MenuItem,
  Snackbar,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import { API_BASE } from "../api/client";
import { Link as RouterLink } from "react-router-dom";
import { useProject } from "../context/ProjectContext";
type ToolResult = Record<string, unknown> | null;

type ToolName =
  | "search_raw"
  | "ingest"
  | "graphify"
  | "index_repo"
  | "pin"
  | "forget"
  | "explain_plan"
  | "get_context";

type GetContextResult = {
  code?: { path?: string; score?: number }[];
  docs?: { doc?: string; score?: number }[];
  status?: string;
  plan_id?: string;
};

function QuickToolsPage(): JSX.Element {
  const { project } = useProject();
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState("both");
  const [k, setK] = useState(5);
  const [uri, setUri] = useState("");
  const [feedbackTask, setFeedbackTask] = useState("");
  const [planId, setPlanId] = useState("");
  const [lastExplain, setLastExplain] = useState(true);
  const [contextTask, setContextTask] = useState("");
  const [maxCode, setMaxCode] = useState(8);
  const [maxDoc, setMaxDoc] = useState(5);
  const [graphDepth, setGraphDepth] = useState(3);
  const [graphDryRun, setGraphDryRun] = useState(false);
  const emptyResults = (): Record<ToolName, ToolResult> => ({
    search_raw: null,
    ingest: null,
    graphify: null,
    index_repo: null,
    pin: null,
    forget: null,
    explain_plan: null,
    get_context: null
  });

  const [results, setResults] = useState<Record<ToolName, ToolResult>>(() => emptyResults());
  const [error, setError] = useState<string | null>(null);
  const [loadingTool, setLoadingTool] = useState<ToolName | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: "success" | "error" }>({
    open: false,
    message: "",
    severity: "success"
  });

  const callTool = async (tool: ToolName, payload: Record<string, unknown>): Promise<void> => {
    setError(null);
    setLoadingTool(tool);
    try {
      const payloadWithProject = payload.project ? payload : { project, ...payload };
      const cleaned = Object.fromEntries(
        Object.entries(payloadWithProject).filter(([, value]) => value !== undefined && value !== null)
      );
      const resp = await fetch(`${API_BASE}/tools/${tool}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cleaned)
      });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || `${tool} failed`);
      }
      const json = (await resp.json()) as ToolResult;
      setResults((prev) => ({ ...prev, [tool]: json }));
      setSnackbar({
        open: true,
        message: `Успех: ${tool} выполнен`,
        severity: "success"
      });
    } catch (err) {
      setError((err as Error).message);
      setResults((prev) => ({ ...prev, [tool]: null }));
      setSnackbar({
        open: true,
        message: `Ошибка: ${(err as Error).message}`,
        severity: "error"
      });
    } finally {
      setLoadingTool(null);
    }
  };

  const contextSummary = useMemo(() => {
    const detail = results.get_context as GetContextResult | null;
    if (!detail) return null;
    const codeCount = detail.code?.length ?? 0;
    const docCount = detail.docs?.length ?? 0;
    return `status ${detail.status ?? ""} - code ${codeCount} - docs ${docCount}`;
  }, [results.get_context]);

  useEffect(() => {
    setResults(emptyResults());
    setError(null);
  }, [project]);

  const renderJobLink = (tool: ToolName): JSX.Element | null => {
    const payload = results[tool] as { job_id?: string; plan_id?: string } | null;
    if (!payload?.job_id) return null;
    return (
      <Button
        component={RouterLink}
        to={`/jobs?job=${payload.job_id}`}
        variant="text"
        size="small"
      >
        View job
      </Button>
    );
  };

  return (
    <Stack spacing={3}>
      <Typography variant="h4">Quick Tools</Typography>
      <Alert severity="info">Работает с проектом {project}. Изменить можно в шапке приложения.</Alert>

      {error && <Alert severity="error">{error}</Alert>}
      {(() => {
        const gc = results.get_context as GetContextResult | null;
        if (gc?.plan_id) {
          return (
            <Alert severity="success">
              Получен план {gc.plan_id.slice(0, 8)} —
              <Button component={RouterLink} to={`/explain?plan=${gc.plan_id}`} size="small" sx={{ ml: 1 }}>
                Открыть в Explain
              </Button>
            </Alert>
          );
        }
        return null;
      })()}

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                search_raw
              </Typography>
              <Stack spacing={2}>
                <TextField
                  label="Query"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  fullWidth
                />
                <TextField select label="Scope" value={scope} onChange={(e) => setScope(e.target.value)}>
                  <MenuItem value="both">both</MenuItem>
                  <MenuItem value="code">code</MenuItem>
                  <MenuItem value="doc">doc</MenuItem>
                </TextField>
                <TextField
                  label="k"
                  type="number"
                  value={k}
                  onChange={(e) => setK(Number(e.target.value))}
                  inputProps={{ min: 1, max: 50 }}
                />
                <Button
                  variant="contained"
                  disabled={!query || loadingTool === "search_raw"}
                  onClick={() => callTool("search_raw", { project, query, scope, k })}
                >
                  {loadingTool === "search_raw" ? "Running..." : "search_raw"}
                </Button>
                {results.search_raw && (
                  <pre>{JSON.stringify(results.search_raw, null, 2)}</pre>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                ingest
              </Typography>
              <Stack spacing={2}>
                <Button
                  variant="contained"
                  disabled={loadingTool === "ingest"}
                  onClick={() => callTool("ingest", { project })}
                >
                  {loadingTool === "ingest" ? "Running..." : "ingest"}
                </Button>
                {results.ingest && (
                  <>
                    <pre>{JSON.stringify(results.ingest, null, 2)}</pre>
                    {renderJobLink("ingest")}
                  </>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                graphify
              </Typography>
              <Stack spacing={2}>
                <TextField
                  select
                  label="dry_run"
                  value={graphDryRun ? "true" : "false"}
                  onChange={(e) => setGraphDryRun(e.target.value === "true")}
                  sx={{ width: 160 }}
                >
                  <MenuItem value="false">false</MenuItem>
                  <MenuItem value="true">true</MenuItem>
                </TextField>
                <Button
                  variant="contained"
                  disabled={loadingTool === "graphify"}
                  onClick={() => callTool("graphify", { project, dry_run: graphDryRun })}
                >
                  {loadingTool === "graphify" ? "Running..." : "graphify"}
                </Button>
                {results.graphify && (
                  <>
                    <pre>{JSON.stringify(results.graphify, null, 2)}</pre>
                    {renderJobLink("graphify")}
                  </>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                index_repo
              </Typography>
              <Stack spacing={2}>
                <Button
                  variant="contained"
                  disabled={loadingTool === "index_repo"}
                  onClick={() => callTool("index_repo", { project })}
                >
                  {loadingTool === "index_repo" ? "Running..." : "index_repo"}
                </Button>
                {results.index_repo && (
                  <>
                    <pre>{JSON.stringify(results.index_repo, null, 2)}</pre>
                    {renderJobLink("index_repo")}
                  </>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                pin / forget
              </Typography>
              <Stack spacing={2}>
                <TextField label="URI" value={uri} onChange={(e) => setUri(e.target.value)} fullWidth />
                <TextField label="Task" value={feedbackTask} onChange={(e) => setFeedbackTask(e.target.value)} fullWidth />
                <Stack direction="row" spacing={2}>
                  <Button
                    variant="contained"
                    color="success"
                    disabled={!uri || !feedbackTask || loadingTool === "pin"}
                    onClick={() => callTool("pin", { project, uri, task: feedbackTask })}
                  >
                    {loadingTool === "pin" ? "Running..." : "pin"}
                  </Button>
                  <Button
                    variant="contained"
                    color="warning"
                    disabled={!uri || !feedbackTask || loadingTool === "forget"}
                    onClick={() => callTool("forget", { project, uri, task: feedbackTask })}
                  >
                    {loadingTool === "forget" ? "Running..." : "forget"}
                  </Button>
                </Stack>
                {(results.pin || results.forget) && (
                  <pre>{JSON.stringify(results.pin || results.forget, null, 2)}</pre>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                explain_plan
              </Typography>
              <Stack spacing={2}>
                <TextField
                  label="Plan ID"
                  value={planId}
                  onChange={(e) => setPlanId(e.target.value)}
                  fullWidth
                />
                <Box display="flex" alignItems="center" gap={2}>
                  <Typography variant="body2">Last plan if empty ID</Typography>
                  <TextField
                    select
                    label="Last"
                    value={lastExplain ? "true" : "false"}
                    onChange={(e) => setLastExplain(e.target.value === "true")}
                    sx={{ width: 120 }}
                  >
                    <MenuItem value="true">true</MenuItem>
                    <MenuItem value="false">false</MenuItem>
                  </TextField>
                </Box>
                <Button
                  variant="contained"
                  disabled={loadingTool === "explain_plan"}
                  onClick={() =>
                    callTool("explain_plan", { plan_id: planId || undefined, last: lastExplain, project })
                  }
                >
                  {loadingTool === "explain_plan" ? "Running..." : "explain_plan"}
                </Button>
                {results.explain_plan && <pre>{JSON.stringify(results.explain_plan, null, 2)}</pre>}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                get_context
              </Typography>
              <Stack spacing={2}>
                <TextField
                  label="Task"
                  value={contextTask}
                  onChange={(e) => setContextTask(e.target.value)}
                  fullWidth
                />
                <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                  <TextField
                    label="max_code_chunks"
                    type="number"
                    value={maxCode}
                    onChange={(e) => setMaxCode(Number(e.target.value))}
                    inputProps={{ min: 1, max: 20 }}
                  />
                  <TextField
                    label="max_doc_chunks"
                    type="number"
                    value={maxDoc}
                    onChange={(e) => setMaxDoc(Number(e.target.value))}
                    inputProps={{ min: 1, max: 20 }}
                  />
                  <TextField
                    label="graph_depth"
                    type="number"
                    value={graphDepth}
                    onChange={(e) => setGraphDepth(Number(e.target.value))}
                    inputProps={{ min: 1, max: 5 }}
                  />
                </Stack>
                <Button
                  variant="contained"
                  disabled={!contextTask || loadingTool === "get_context"}
                  onClick={() =>
                    callTool("get_context", {
                      project,
                      task: contextTask,
                      max_code_chunks: maxCode,
                      max_doc_chunks: maxDoc,
                      graph_depth: graphDepth
                    })
                  }
                >
                  {loadingTool === "get_context" ? "Running..." : "get_context"}
                </Button>
                {contextSummary && <Typography variant="body2">{contextSummary}</Typography>}
                {results.get_context && <pre>{JSON.stringify(results.get_context, null, 2)}</pre>}
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
          sx={{ width: "100%" }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Stack>
  );
}

export default QuickToolsPage;
