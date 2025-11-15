import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Typography
} from "@mui/material";
import { API_BASE } from "../api/client";
import { useProject } from "../context/ProjectContext";

type PlanItem = {
  plan_id: string;
  ts: string;
  project: string;
  module: string | null;
  status: string;
  route?: string | null;
  latency_ms?: number | null;
  source_latencies?: Record<string, number>;
  result_sizes?: Record<string, number>;
};

function LivePlansPage(): JSX.Element {
  const { project } = useProject();
  const [plans, setPlans] = useState<PlanItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let retryHandle: ReturnType<typeof setTimeout> | null = null;
    setPlans([]);
    setLoading(true);
    const fetchInitial = async (): Promise<void> => {
      try {
        const resp = await fetch(
          `${API_BASE}/plans?limit=10&project=${encodeURIComponent(project)}`
        );
        if (!resp.ok) throw new Error("Failed to load plans");
        const data = (await resp.json()) as PlanItem[];
        setPlans(data);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    };

    const subscribe = (): void => {
      const streamUrl = new URL(`${API_BASE}/plans/stream`);
      streamUrl.searchParams.set("project", project);
      eventSource = new EventSource(streamUrl.toString());
      eventSource.addEventListener("plan", (event) => {
        const payload = JSON.parse((event as MessageEvent).data) as PlanItem;
        setPlans((prev) => {
          const filtered = prev.filter((p) => p.plan_id !== payload.plan_id);
          return [payload, ...filtered].slice(0, 20);
        });
      });
      eventSource.onerror = () => {
        setError("Lost connection to live stream");
        eventSource?.close();
        retryHandle = window.setTimeout(subscribe, 3000);
      };
    };

    void fetchInitial();
    subscribe();

    return () => {
      eventSource?.close();
      if (retryHandle) {
        clearTimeout(retryHandle);
      }
    };
  }, [project]);

  if (loading) return <CircularProgress />;
  if (error) return <Alert severity="error">{error}</Alert>;

  return (
    <Box display="flex" flexDirection="column" gap={2}>
      <Typography variant="h4">Live Plans</Typography>
      {plans.map((plan) => (
        <Card key={plan.plan_id}>
          <CardContent>
            <Typography variant="subtitle2" color="text.secondary">
              {new Date(plan.ts).toLocaleString()}
            </Typography>
            <Typography variant="h6">{plan.plan_id}</Typography>
            <Typography variant="body2" color="text.secondary">
              {plan.project} - {plan.module ?? "no module"}
            </Typography>
            <Box mt={1} display="flex" gap={1} flexWrap="wrap" alignItems="center">
              <Typography variant="body2">{plan.status}</Typography>
              {plan.route && (
                <Typography variant="caption" color="text.secondary">
                  {plan.route}
                </Typography>
              )}
              {plan.latency_ms != null && (
                <Chip size="small" label={`latency ${plan.latency_ms} ms`} color="primary" />
              )}
              {plan.result_sizes && (
                <>
                  {Object.entries(plan.result_sizes).map(([type, count]) => (
                    <Chip key={`${plan.plan_id}-${type}`} size="small" label={`${type}: ${count}`} />
                  ))}
                </>
              )}
            </Box>
          </CardContent>
        </Card>
      ))}
    </Box>
  );
}

export default LivePlansPage;
