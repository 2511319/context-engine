import { useEffect, useMemo, useState } from "react";
import { Alert, Box, Button, CircularProgress, Snackbar, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { API_BASE, apiGet } from "../api/client";
import { useProject } from "../context/ProjectContext";
import { Artifact, PlanDetail, PlanListItem } from "./Explain.types";

const rerunSummaryFor = (result: any): string => {
  if (!result) return "";
  const detail = result as { code?: Artifact[]; docs?: Artifact[]; status?: string };
  const codeCount = detail.code?.length ?? 0;
  const docCount = detail.docs?.length ?? 0;
  return `status ${detail.status ?? ""} - code ${codeCount} - docs ${docCount}`;
};

function ExplainLite(): JSX.Element {
  const { project } = useProject();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: "success" | "error" }>({
    open: false,
    message: "",
    severity: "success"
  });
  const [rerunStatus, setRerunStatus] = useState<"idle" | "running" | "error" | "success">("idle");
  const [rerunResult, setRerunResult] = useState<any>(null);
  const [rerunError, setRerunError] = useState<string | null>(null);

  const {
    data: plansData,
    isLoading: plansLoading,
    error: plansError
  } = useQuery<{ plans: PlanListItem[] }>({
    queryKey: ["plan-list-lite", project],
    queryFn: async () => apiGet<{ plans: PlanListItem[] }>(`/api/admin/plans?project=${encodeURIComponent(project)}`)
  });
  const plans = plansData?.plans ?? [];

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
    queryKey: ["plan-detail-lite", project, selectedPlan],
    queryFn: async () => await apiGet<PlanDetail>(`/api/admin/plans/${selectedPlan}`),
    enabled: Boolean(selectedPlan)
  });

  const rerunTask = useMemo(() => planDetail?.params?.task as string | undefined, [planDetail?.params?.task]);
  const rerunSummary = useMemo(() => rerunSummaryFor(rerunResult), [rerunResult]);

  const handleRerun = async (): Promise<void> => {
    if (!planDetail || !rerunTask) {
      setRerunError("Не удалось определить исходное задание для rerun.");
      setRerunStatus("error");
      return;
    }
    setRerunStatus("running");
    setRerunResult(null);
    setRerunError(null);
    try {
      const payload = { project, task: rerunTask };
      const resp = await fetch(`${API_BASE}/tools/get_context`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!resp.ok) {
        throw new Error((await resp.text()) || "get_context failed");
      }
      const json = await resp.json();
      setRerunResult(json);
      setRerunStatus("success");
      setSnackbar({ open: true, message: "get_context завершён", severity: "success" });
    } catch (error) {
      setRerunStatus("error");
      setRerunError((error as Error).message);
      setSnackbar({ open: true, message: (error as Error).message, severity: "error" });
    }
  };

  if (plansLoading || detailLoading) {
    return <CircularProgress />;
  }
  if (plansError) {
    return <Alert severity="error">{(plansError as Error).message}</Alert>;
  }
  if (detailError) {
    return <Alert severity="error">{(detailError as Error).message}</Alert>;
  }
  if (!planDetail) {
    return <Alert severity="info">Нет данных плана</Alert>;
  }

  return (
    <Stack spacing={2} data-testid="explain-test-shell">
      <Typography variant="h5">Plan {planDetail.plan_id}</Typography>
      <Typography variant="body2" color="text.secondary">
        Task: {rerunTask ?? "n/a"}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Status: {planDetail.status}
      </Typography>
      <Button variant="contained" disabled={rerunStatus === "running" || !rerunTask} onClick={handleRerun}>
        {rerunStatus === "running" ? "Running..." : "Run get_context"}
      </Button>
      {rerunSummary && rerunStatus === "success" && (
        <Typography data-testid="rerun-summary" color="success.main">
          {rerunSummary}
        </Typography>
      )}
      {rerunError && <Alert severity="error">{rerunError}</Alert>}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
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
      {rerunResult && (
        <Box component="pre" sx={{ maxHeight: 240, overflow: "auto" }}>
          {JSON.stringify(rerunResult, null, 2)}
        </Box>
      )}
    </Stack>
  );
}

export default ExplainLite;
