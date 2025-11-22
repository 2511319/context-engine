import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Grid, Stack, Typography } from "@mui/material";
import { API_BASE } from "../api/client";
import { useProject } from "../context/ProjectContext";
import RefreshIcon from "@mui/icons-material/Refresh";

type ComponentStatus = {
  name: string;
  status: string;
  message?: string;
  checked_at?: string;
};

type DownEvent = {
  component: string;
  error_code?: string;
  plan_id?: string;
  ts?: string;
};

type HealthResponse = {
  project: string;
  components: ComponentStatus[];
  recent_down_events: DownEvent[];
};

async function fetchHealth(project: string): Promise<HealthResponse> {
  const resp = await fetch(
    `${API_BASE}/api/admin/health?project=${encodeURIComponent(project)}&include_mcp=true`
  );
  if (!resp.ok) throw new Error("Failed to load health status");
  return (await resp.json()) as HealthResponse;
}

function StatusCard({ comp }: { comp: ComponentStatus }): JSX.Element {
  const color = comp.status === "ok" ? "success" : comp.status === "degraded" ? "warning" : "error";
  return (
    <Card>
      <CardContent>
        <Stack spacing={1}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography variant="subtitle1">{comp.name}</Typography>
            <Chip label={comp.status} color={color as any} size="small" />
          </Stack>
          {comp.message && (
            <Typography variant="body2" color="text.secondary">
              {comp.message}
            </Typography>
          )}
          {comp.checked_at && (
            <Typography variant="caption" color="text.secondary">
              {new Date(comp.checked_at).toLocaleString()}
            </Typography>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}

function DownEvents({ events }: { events: DownEvent[] }): JSX.Element {
  if (!events.length) {
    return <Typography variant="body2">Сбоев не зафиксировано</Typography>;
  }
  return (
    <Stack spacing={1}>
      {events.map((ev, idx) => (
        <Card key={`${ev.plan_id ?? idx}-${ev.ts ?? idx}`}>
          <CardContent>
            <Stack spacing={0.5}>
              <Typography variant="subtitle2">{ev.component}</Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                {ev.error_code && <Chip size="small" label={ev.error_code} color="error" />}
                {ev.plan_id && <Chip size="small" label={`plan ${ev.plan_id.slice(0, 8)}`} />}
              </Stack>
              {ev.ts && (
                <Typography variant="caption" color="text.secondary">
                  {new Date(ev.ts).toLocaleString()}
                </Typography>
              )}
            </Stack>
          </CardContent>
        </Card>
      ))}
    </Stack>
  );
}

function IndexHealthPage(): JSX.Element {
  const { project } = useProject();
  const { data, isLoading, isError, error, refetch, isRefetching } = useQuery({
    queryKey: ["admin-health", project],
    queryFn: () => fetchHealth(project),
    refetchInterval: 30000
  });

  const grouped = useMemo(() => data?.components ?? [], [data?.components]);

  if (isLoading) return <CircularProgress />;
  if (isError) return <Alert severity="error">{(error as Error).message}</Alert>;

  return (
    <Stack spacing={3}>
      <Stack direction="row" spacing={2} alignItems="center">
        <Typography variant="h4">Admin Health</Typography>
        <Button
          variant="outlined"
          size="small"
          startIcon={<RefreshIcon fontSize="small" />}
          onClick={() => refetch()}
          disabled={isRefetching}
        >
          {isRefetching ? "Обновление..." : "Обновить"}
        </Button>
      </Stack>
      <Grid container spacing={2}>
        {grouped.map((comp) => (
          <Grid item xs={12} md={6} lg={3} key={comp.name}>
            <StatusCard comp={comp} />
          </Grid>
        ))}
      </Grid>
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Недавние сбои
          </Typography>
          <DownEvents events={data?.recent_down_events ?? []} />
        </CardContent>
      </Card>
    </Stack>
  );
}

export default IndexHealthPage;
