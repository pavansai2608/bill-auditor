import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";

import { fetchJob, startAudit, startCompare } from "../lib/api";
import type { AuditFormValues, CompareStatus, JobStatus } from "../types";

export const POLL_INTERVAL_MS = 2000;
/** An audit is 30-60s. Five minutes means something is wrong, not slow. */
export const GIVE_UP_AFTER_MS = 5 * 60 * 1000;

export interface AuditJob {
  jobId: string | null;
  kind: "audit" | "compare";
  status: JobStatus | CompareStatus | undefined;
  /** Set while the job is running, so the caller can show a real progress bar. */
  progress: { done: number; total: number } | null;
  isStarting: boolean;
  error: string | null;
  start: (values: AuditFormValues) => void;
  compare: (values: AuditFormValues) => void;
  reset: () => void;
}

/**
 * Owns everything about running one audit: starting it, polling it, knowing
 * when to stop, and knowing when to give up.
 *
 * The polling rules are here rather than in a component because they are the
 * awkward part. The API answers in milliseconds and the work takes a minute,
 * so the interesting states are "running with progress", "done", "failed" and
 * "taking so long that something must be broken".
 */
export function useAuditJob(): AuditJob {
  const [jobId, setJobId] = useState<string | null>(null);
  const [kind, setKind] = useState<"audit" | "compare">("audit");
  const [error, setError] = useState<string | null>(null);
  const startedAt = useRef<number>(0);
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["job", kind, jobId],
    queryFn: () => fetchJob(kind, jobId as string),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return POLL_INTERVAL_MS;
      // Stop the moment there is nothing left to wait for.
      if (data.status === "done" || data.status === "failed") return false;
      if (Date.now() - startedAt.current > GIVE_UP_AFTER_MS) return false;
      return POLL_INTERVAL_MS;
    },
    // A poll that fails once should not throw the report away; the next one
    // usually succeeds.
    retry: 2,
  });

  const begin = useCallback(
    (nextKind: "audit" | "compare") => (values: AuditFormValues) => {
      setError(null);
      setKind(nextKind);
      startedAt.current = Date.now();
      const starter = nextKind === "audit" ? startAudit : startCompare;
      return starter(values);
    },
    [],
  );

  const startMutation = useMutation({
    mutationFn: begin("audit"),
    onSuccess: setJobId,
    onError: (err: Error) => setError(err.message),
  });

  const compareMutation = useMutation({
    mutationFn: begin("compare"),
    onSuccess: setJobId,
    onError: (err: Error) => setError(err.message),
  });

  const reset = useCallback(() => {
    setJobId(null);
    setError(null);
    queryClient.removeQueries({ queryKey: ["job"] });
  }, [queryClient]);

  const data = query.data;
  const timedOut =
    jobId !== null &&
    data !== undefined &&
    data.status !== "done" &&
    data.status !== "failed" &&
    Date.now() - startedAt.current > GIVE_UP_AFTER_MS;

  const progress =
    data && (data.status === "running" || data.status === "queued")
      ? { done: data.done, total: data.total }
      : null;

  return {
    jobId,
    kind,
    status: data,
    progress,
    isStarting: startMutation.isPending || compareMutation.isPending,
    error:
      error ??
      (timedOut
        ? "This audit has been running for over five minutes. The model has probably stopped responding — check that Ollama is up, then try again."
        : query.error
          ? (query.error as Error).message
          : data?.status === "failed"
            ? data.error
            : null),
    start: startMutation.mutate,
    compare: compareMutation.mutate,
    reset,
  };
}
