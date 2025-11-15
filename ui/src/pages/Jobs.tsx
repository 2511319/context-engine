import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  Stack,
  Typography
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { apiGet, API_BASE } from "../api/client";
import { useSearchParams } from "react-router-dom";
import { useProject } from "../context/ProjectContext";

export type JobItem = {
  job_id: string;
  name: string;
  command?: string[];
  project: string;
  plan_id: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  exit_code?: number | null;
  error?: string | null;
  log_path?: string | null;
};

async function fetchJobs(project: string): Promise<JobItem[]> {
  const data = await apiGet<{ jobs: JobItem[] }>(`/jobs?project=${encodeURIComponent(project)}`);
  return data.jobs ?? [];
}

async function fetchLog(jobId: string): Promise<string> {
  const resp = await fetch(`${API_BASE}/jobs/${jobId}/log`);
  if (!resp.ok) throw new Error("Failed to fetch log");
  return await resp.text();
}

function JobCard({ job, onSelect }: { job: JobItem; onSelect: (job: JobItem) => void }): JSX.Element {
  const statusColor = job.status === "success" ? "success" : job.status === "failed" ? "error" : "info";
  return (
    <Card onClick={() => onSelect(job)} sx={{ cursor: "pointer" }}>
      <CardContent>
        <Stack spacing={1}>
          <Stack direction="row" alignItems="center" spacing={1} justifyContent="space-between">
            <Typography variant="subtitle1">{job.name}</Typography>
            <Chip label={job.status} color={statusColor as any} size="small" />
          </Stack>
          <Typography variant="body2" color="text.secondary">
            Job {job.job_id.slice(0, 8)} - project {job.project}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Plan {job.plan_id.slice(0, 8)}
          </Typography>
          <Typography variant="body2">
            Started: {job.started_at ? new Date(job.started_at).toLocaleString() : "—"}
          </Typography>
          <Typography variant="body2">
            Finished: {job.finished_at ? new Date(job.finished_at).toLocaleString() : "—"}
          </Typography>
          {job.error && (
            <Typography variant="body2" color="error">
              {job.error}
            </Typography>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}

function JobsPage(): JSX.Element {
  const { project } = useProject();
  const [selectedJob, setSelectedJob] = useState<JobItem | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const jobQuery = searchParams.get("job");
  const { data: jobs = [], isLoading, error } = useQuery({
    queryKey: ["jobs", project],
    queryFn: () => fetchJobs(project),
    refetchInterval: 5000
  });

  useEffect(() => {
    if (!jobQuery || selectedJob) {
      return;
    }
    const found = jobs.find((job) => job.job_id === jobQuery);
    if (found) {
      setSelectedJob(found);
    }
  }, [jobQuery, jobs, selectedJob]);

  useEffect(() => {
    if (!jobQuery) {
      return;
    }
    if (jobs.some((job) => job.job_id === jobQuery)) {
      return;
    }
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("job");
      return next;
    });
  }, [jobQuery, jobs, setSearchParams]);

  useEffect(() => {
    setSelectedJob(null);
    setSearchParams((prev) => {
      if (!prev.get("job")) {
        return prev;
      }
      const next = new URLSearchParams(prev);
      next.delete("job");
      return next;
    });
  }, [project, setSearchParams]);

  const handleSelectJob = (job: JobItem): void => {
    setSelectedJob(job);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("job", job.job_id);
      return next;
    });
  };

  const selectedLogQuery = useQuery({
    queryKey: ["job-log", selectedJob?.job_id],
    queryFn: async () => await fetchLog(selectedJob!.job_id),
    enabled: Boolean(selectedJob?.job_id)
  });

  if (isLoading) return <CircularProgress />;
  if (error) return <Alert severity="error">{(error as Error).message}</Alert>;

  return (
    <Grid container spacing={3}>
      <Grid item xs={12} md={4}>
        <Stack spacing={2}>
          <Typography variant="h4">Background Jobs</Typography>
          {jobs.length === 0 && <Typography>No jobs yet</Typography>}
          {jobs.map((job) => (
            <JobCard key={job.job_id} job={job} onSelect={handleSelectJob} />
          ))}
        </Stack>
      </Grid>
      <Grid item xs={12} md={8}>
        {selectedJob ? (
          <Card>
            <CardContent>
              <Typography variant="h6">Job {selectedJob.job_id}</Typography>
              <Divider sx={{ my: 2 }} />
              <Stack spacing={1}>
                <Typography variant="body2">Plan: {selectedJob.plan_id}</Typography>
                <Typography variant="body2">
                  Command: {selectedJob.command?.join(" ") ?? selectedJob.name}
                </Typography>
                <Typography variant="body2">Status: {selectedJob.status}</Typography>
                <Typography variant="body2">Exit code: {selectedJob.exit_code ?? "—"}</Typography>
              </Stack>
              <Divider sx={{ my: 2 }} />
              {selectedLogQuery.isLoading && <CircularProgress size={20} />}
              {selectedLogQuery.error && (
                <Alert severity="error">{(selectedLogQuery.error as Error).message}</Alert>
              )}
              {selectedLogQuery.data && (
                <Box component="pre" sx={{ maxHeight: 400, overflow: "auto" }}>
                  {selectedLogQuery.data}
                </Box>
              )}
            </CardContent>
          </Card>
        ) : (
          <Alert severity="info">Select a job to view details</Alert>
        )}
      </Grid>
    </Grid>
  );
}

export default JobsPage;
