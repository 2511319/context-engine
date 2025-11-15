import { useQuery } from "@tanstack/react-query";
import { Alert, Card, CardContent, CircularProgress, Typography } from "@mui/material";
import { apiGet } from "../api/client";

type ConfigResponse = {
  project: string;
  checksum: string;
  ttl_seconds: number;
  raw: Record<string, unknown>;
  file_text: string;
};

async function fetchConfig(): Promise<ConfigResponse> {
  return await apiGet<ConfigResponse>("/config");
}

function ConfigPage(): JSX.Element {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["config"],
    queryFn: fetchConfig,
    refetchInterval: 30000
  });

  if (isLoading) return <CircularProgress />;
  if (isError) return <Alert severity="error">{(error as Error).message}</Alert>;

  return (
    <Card>
      <CardContent>
        <Typography variant="h4" gutterBottom>
          Active Config
        </Typography>
        <Typography variant="body2">Project: {data?.project}</Typography>
        <Typography variant="body2">Checksum: {data?.checksum}</Typography>
        <Typography variant="body2">TTL: {data?.ttl_seconds}s</Typography>
        <Typography variant="h6" sx={{ mt: 3 }}>
          engine.yml
        </Typography>
        <pre>{data?.file_text}</pre>
      </CardContent>
    </Card>
  );
}

export default ConfigPage;
