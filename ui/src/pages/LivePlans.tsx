import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Stack, Typography } from "@mui/material";
import { apiGet } from "../api/client";
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
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const { data, isLoading, error, isRefetching, refetch } = useQuery({
    queryKey: ["admin-plans-live", project, offset, limit],
    queryFn: () =>
      apiGet<{ plans: PlanItem[]; limit: number; offset: number; total: number }>(
        `/api/admin/plans?limit=${limit}&offset=${offset}&project=${encodeURIComponent(project)}`
      ),
    refetchInterval: 5000,
  });

  const plans = useMemo(() => data?.plans ?? [], [data?.plans]);
  const total = data?.total ?? plans.length;
  const hasPrev = offset > 0;
  const hasNext = offset + plans.length < total;

  if (isLoading) return <CircularProgress />;
  if (error) return <Alert severity="error">{(error as Error).message}</Alert>;

  return (
    <Box display="flex" flexDirection="column" gap={2}>
      <Stack direction="row" spacing={2} alignItems="center">
        <Typography variant="h4">Live Plans</Typography>
        <Button
          size="small"
          variant="outlined"
          onClick={() => refetch()}
          disabled={isRefetching}
        >
          {isRefetching ? "Refreshing..." : "Refresh"}
        </Button>
        <Button
          size="small"
          disabled={!hasPrev}
          onClick={() => setOffset(Math.max(0, offset - limit))}
        >
          Prev
        </Button>
        <Button
          size="small"
          disabled={!hasNext}
          onClick={() => setOffset(offset + limit)}
        >
          Next
        </Button>
        <Typography variant="body2" color="text.secondary">
          {offset + 1}–{offset + plans.length} из {total}
        </Typography>
      </Stack>
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
