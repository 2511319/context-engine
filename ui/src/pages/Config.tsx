import { useQuery } from "@tanstack/react-query";
import { Alert, Card, CardContent, CircularProgress, Grid, Typography } from "@mui/material";
import { apiGet } from "../api/client";
import { useProject } from "../context/ProjectContext";

type ConfigFile = {
  project: string;
  checksum: string;
  ttl_seconds: number;
  source: string;
  raw: Record<string, unknown>;
  file_text: string;
};

type ConfigResponse = {
  project: string;
  engine: ConfigFile;
  policy: ConfigFile;
};

async function fetchConfig(project: string): Promise<ConfigResponse> {
  return await apiGet<ConfigResponse>(`/api/admin/config?project=${encodeURIComponent(project)}`);
}

function ConfigCard({ title, cfg }: { title: string; cfg: ConfigFile }): JSX.Element {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Проект: {cfg.project} • TTL {cfg.ttl_seconds}s • checksum {cfg.checksum}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Source: {cfg.source}
        </Typography>
        <Typography variant="subtitle2" sx={{ mt: 2 }}>
          Raw
        </Typography>
        <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(cfg.raw, null, 2)}</pre>
        <Typography variant="subtitle2" sx={{ mt: 2 }}>
          File text
        </Typography>
        <pre style={{ whiteSpace: "pre-wrap" }}>{cfg.file_text}</pre>
      </CardContent>
    </Card>
  );
}

function ConfigPage(): JSX.Element {
  const { project } = useProject();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["admin-config", project],
    queryFn: () => fetchConfig(project),
    refetchInterval: 30000
  });

  if (isLoading) return <CircularProgress />;
  if (isError) return <Alert severity="error">{(error as Error).message}</Alert>;

  if (!data) return <Alert severity="warning">Нет данных конфигурации</Alert>;

  return (
    <Grid container spacing={3}>
      <Grid item xs={12}>
        <Typography variant="h4" gutterBottom>
          Config / Policy (read-only)
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Project context: {data.project}
        </Typography>
      </Grid>
      <Grid item xs={12} md={6}>
        <ConfigCard title="engine.yml" cfg={data.engine} />
      </Grid>
      <Grid item xs={12} md={6}>
        <ConfigCard title="policy.yml" cfg={data.policy} />
      </Grid>
    </Grid>
  );
}

export default ConfigPage;
