export interface PolicyOption {
  id: string;
  name: string;
  clauses: number;
  sum_insured_options: number[];
}

export interface LineVerdict {
  item: string;
  charged: number;
  allowed: number | null;
  clause_id: string | null;
  reason: string;
  needs_human: boolean;
  over_limit: boolean;
  limit_per_day: number | null;
}

export interface Assumption {
  assumption: string;
  assumed: boolean;
  statement: string;
  because: string;
  clause_id: string | null;
  clause_text: string | null;
}

export interface TraceEntry {
  node?: string;
  item?: string;
  [key: string]: unknown;
}

export interface AuditReport {
  lines: LineVerdict[];
  total_charged: number;
  total_allowed: number;
  flagged_count: number;
  policy: string;
  trace: TraceEntry[];
  assumptions: Assumption[];
}

export interface ComparisonReport {
  reports: AuditReport[];
  best_policy: string;
  difference: number;
}

/** What GET /audit/{job_id} returns, in its three shapes. */
export type JobStatus =
  | { job_id: string; status: "queued" | "running"; done: number; total: number }
  | { job_id: string; status: "done"; report: AuditReport }
  | { job_id: string; status: "failed"; error: string };

export type CompareStatus =
  | { job_id: string; status: "queued" | "running"; done: number; total: number }
  | { job_id: string; status: "done"; report: ComparisonReport }
  | { job_id: string; status: "failed"; error: string };

export interface AuditFormValues {
  billText: string;
  billFile: File | null;
  policy: string;
  sumInsured: number;
  policyStartDate: string;
  admissionDate: string;
  roomLimitPerDay: string;
  roomCategory: string;
}
