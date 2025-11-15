import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  Grid,
  LinearProgress,
  Stack,
  Typography
} from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { Bar, BarChart, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis, Cell } from "recharts";
import { API_BASE } from "../api/client";
import { useProject } from "../context/ProjectContext";

type ChunkStats = {
  total: number;
  avg_len?: number;
  min_len?: number;
  max_len?: number;
  p50_len?: number;
  p90_len?: number;
  without_module?: number;
  duplicates?: number;
  by_kind?: Record<string, number>;
};

type SymbolsStats = {
  total: number;
  by_kind: Record<string, number>;
};

type FeedbackStats = {
  positive?: number;
  negative?: number;
  total?: number;
  ctr_positive?: number;
};

type HealthResponse = {
  code_chunks: ChunkStats;
  doc_chunks: ChunkStats & { by_kind: Record<string, number> };
  symbols: SymbolsStats;
  symbol_refs: Record<string, number>;
  edges: Record<string, number>;
  feedback: FeedbackStats;
  near_duplicates: { pairs: number; note?: string };
  jobs?: {
    total: number;
    by_status: Record<string, number>;
    latest?: {
      job_id?: string;
      name?: string;
      status?: string;
      started_at?: string;
    } | null;
  };
};

async function fetchHealth(project: string): Promise<HealthResponse> {
  const resp = await fetch(`${API_BASE}/health/index?project=${encodeURIComponent(project)}`);
  if (!resp.ok) throw new Error("Failed to load health metrics");
  return (await resp.json()) as HealthResponse;
}

function StatCard({ title, value, subtitle }: { title: string; value: string | number; subtitle?: string }): JSX.Element {
  return (
    <Card>
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary">
          {title}
        </Typography>
        <Typography variant="h5">{value}</Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

function KeyValueList({ data }: { data: Record<string, number> }): JSX.Element {
  const entries = Object.entries(data || {});
  if (!entries.length) {
    return <Typography variant="body2">—</Typography>;
  }
  return (
    <Stack spacing={0.5}>
      {entries.map(([key, value]) => (
        <Box key={key} display="flex" justifyContent="space-between">
          <Typography variant="body2" color="text.secondary">
            {key}
          </Typography>
          <Typography variant="body2">{value}</Typography>
        </Box>
      ))}
    </Stack>
  );
}

function ProgressStat({ label, current, max }: { label: string; current: number; max: number }): JSX.Element {
  const percent = max > 0 ? Math.min(100, Math.round((current / max) * 100)) : 0;
  return (
    <Box>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
      <LinearProgress value={percent} variant="determinate" sx={{ my: 0.5, borderRadius: 4 }} />
      <Typography variant="caption" color="text.secondary">
        {current}/{max} ({percent}%)
      </Typography>
    </Box>
  );
}

function IndexHealthPage(): JSX.Element {
  const { project } = useProject();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["health", project],
    queryFn: () => fetchHealth(project),
    refetchInterval: 60000
  });

  const docKinds = data?.doc_chunks?.by_kind ?? {};
  const symbolKinds = data?.symbols?.by_kind ?? {};

  const withoutModuleRatio = useMemo(() => {
    if (!data?.code_chunks?.total) return 0;
    return Math.round(((data.code_chunks.without_module ?? 0) / data.code_chunks.total) * 100);
  }, [data]);

  const nearDupRatio = useMemo(() => {
    const pairs = data?.near_duplicates?.pairs ?? 0;
    const total = data?.code_chunks?.total ?? 0;
    if (!pairs || !total) return 0;
    return Math.min(100, Math.round(((pairs * 2) / total) * 100));
  }, [data]);

  const feedbackChart = useMemo(
    () => [
      { name: "Positive", value: data?.feedback?.positive ?? 0 },
      { name: "Negative", value: data?.feedback?.negative ?? 0 }
    ],
    [data?.feedback?.positive, data?.feedback?.negative]
  );

  if (isLoading) return <CircularProgress />;
  if (isError) return <Alert severity="error">{(error as Error).message}</Alert>;

  return (
    <Stack spacing={3}>
      <Typography variant="h4">Index Health</Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={3}>
          <StatCard title="Code chunks" value={data?.code_chunks?.total ?? 0} subtitle={`p50 ${data?.code_chunks?.p50_len ?? 0} - p90 ${data?.code_chunks?.p90_len ?? 0}`} />
        </Grid>
        <Grid item xs={12} md={3}>
          <StatCard title="Doc chunks" value={data?.doc_chunks?.total ?? 0} subtitle={`p50 ${data?.doc_chunks?.p50_len ?? 0} - p90 ${data?.doc_chunks?.p90_len ?? 0}`} />
        </Grid>
        <Grid item xs={12} md={3}>
          <StatCard title="Symbols" value={data?.symbols?.total ?? 0} subtitle={`kinds ${Object.keys(symbolKinds).length}`} />
        </Grid>
        <Grid item xs={12} md={3}>
          <StatCard
            title="Near duplicates"
            value={data?.near_duplicates?.pairs ?? 0}
            subtitle={data?.near_duplicates?.note ?? `${nearDupRatio}% от кодовых чанков в парах`}
          />
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6">Code chunks details</Typography>
              <Divider sx={{ my: 2 }} />
              <Stack spacing={2}>
                <Typography variant="body2">Length avg {Math.round(data?.code_chunks?.avg_len ?? 0)}</Typography>
                <ProgressStat label="Without module" current={data?.code_chunks?.without_module ?? 0} max={data?.code_chunks?.total ?? 1} />
                <Typography variant="body2">Duplicates {data?.code_chunks?.duplicates ?? 0}</Typography>
                <ProgressStat label="Near-dup ratio" current={nearDupRatio} max={100} />
              </Stack>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6">Doc chunks (by kind)</Typography>
              <Divider sx={{ my: 2 }} />
              <KeyValueList data={docKinds} />
              <Box sx={{ height: 220, mt: 2 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={Object.entries(docKinds).map(([name, value]) => ({ name, value }))} barSize={28}>
                    <XAxis dataKey="name" />
                    <YAxis allowDecimals={false} />
                    <RechartsTooltip />
                    <Bar dataKey="value">
                      {Object.entries(docKinds).map(([name], idx) => (
                        <Cell key={`doc-${name}`} fill={["#4dabf5", "#ce93d8", "#81c784", "#ffb74d"][idx % 4]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6">Symbol kinds</Typography>
              <Divider sx={{ my: 2 }} />
              <KeyValueList data={symbolKinds} />
              <Box sx={{ height: 220, mt: 2 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={Object.entries(symbolKinds).map(([name, value]) => ({ name, value }))} barSize={28}>
                    <XAxis dataKey="name" />
                    <YAxis allowDecimals={false} />
                    <RechartsTooltip />
                    <Bar dataKey="value">
                      {Object.entries(symbolKinds).map(([name], idx) => (
                        <Cell key={`sym-${name}`} fill={["#64b5f6", "#f48fb1", "#a1887f", "#90a4ae"][idx % 4]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6">Symbol references</Typography>
              <Divider sx={{ my: 2 }} />
              <KeyValueList data={data?.symbol_refs ?? {}} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6">Edges</Typography>
              <Divider sx={{ my: 2 }} />
              <KeyValueList data={data?.edges ?? {}} />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6">Feedback</Typography>
              <Divider sx={{ my: 2 }} />
              <Stack spacing={1}>
                <Typography variant="body2">Positive: {data?.feedback?.positive ?? 0}</Typography>
                <Typography variant="body2">Negative: {data?.feedback?.negative ?? 0}</Typography>
                <Typography variant="body2">Total: {data?.feedback?.total ?? 0}</Typography>
                <Typography variant="body2">CTR+: {Math.round((data?.feedback?.ctr_positive ?? 0) * 100)}%</Typography>
              </Stack>
              <Box sx={{ height: 220, mt: 2 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={feedbackChart} barSize={36}>
                    <XAxis dataKey="name" />
                    <YAxis allowDecimals={false} />
                    <RechartsTooltip />
                    <Bar dataKey="value">
                      {feedbackChart.map((entry, idx) => (
                        <Cell key={`fb-${entry.name}`} fill={["#4caf50", "#e53935"][idx % 2]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {data?.jobs && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" alignItems={{ md: "center" }}>
                  <Typography variant="h6">Background Jobs</Typography>
                  <Button component={RouterLink} to="/jobs" size="small" variant="outlined">
                    Открыть Jobs
                  </Button>
                </Stack>
                <Divider sx={{ my: 2 }} />
                <Stack spacing={1}>
                  <Typography variant="body2">Всего записей: {data.jobs.total}</Typography>
                  <KeyValueList data={data.jobs.by_status} />
                  {data.jobs.latest && (
                    <Typography variant="body2" color="text.secondary">
                      Последний: {data.jobs.latest.name ?? data.jobs.latest.job_id ?? "unknown"} — {data.jobs.latest.status ?? "unknown"}
                      {data.jobs.latest.started_at ? ` • ${new Date(data.jobs.latest.started_at).toLocaleString()}` : ""}
                    </Typography>
                  )}
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Stack>
  );
}

export default IndexHealthPage;
