import type { AuditFormValues, CompareStatus, JobStatus, PolicyOption } from "../types";

// One place for the API address. `npm run dev` talks to a local uvicorn,
// docker-compose sets this to the gateway, minikube sets it to the service.
export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      // FastAPI's 422 shape: a list of field errors.
      return body.detail.map((d: { msg: string }) => d.msg).join("; ");
    }
    return JSON.stringify(body);
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

export async function fetchPolicies(): Promise<PolicyOption[]> {
  const response = await fetch(`${API_BASE}/policies`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

function formData(values: AuditFormValues, withPolicy: boolean): FormData {
  const form = new FormData();
  if (withPolicy) form.set("policy", values.policy);
  form.set("sum_insured", String(values.sumInsured));
  if (values.billFile) form.set("bill", values.billFile);
  else form.set("bill_text", values.billText);
  if (values.policyStartDate) form.set("policy_start_date", values.policyStartDate);
  if (values.admissionDate) form.set("admission_date", values.admissionDate);
  // Blank is a valid answer here: it makes the audit abstain on room-rent
  // lines rather than invent a limit, so an empty field is never sent as 0.
  if (values.roomLimitPerDay.trim()) form.set("room_limit_per_day", values.roomLimitPerDay.trim());
  if (values.roomCategory.trim()) form.set("room_category", values.roomCategory.trim());
  return form;
}

export async function startAudit(values: AuditFormValues): Promise<string> {
  const response = await fetch(`${API_BASE}/audit`, {
    method: "POST",
    body: formData(values, true),
  });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()).job_id;
}

export async function startCompare(values: AuditFormValues): Promise<string> {
  const response = await fetch(`${API_BASE}/compare`, {
    method: "POST",
    body: formData(values, false),
  });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()).job_id;
}

export async function fetchJob(kind: "audit" | "compare", jobId: string): Promise<JobStatus | CompareStatus> {
  const response = await fetch(`${API_BASE}/${kind}/${jobId}`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function uploadPolicy(file: File): Promise<{ job_id: string; policy: string }> {
  const form = new FormData();
  form.set("file", file);
  const response = await fetch(`${API_BASE}/policies/upload`, { method: "POST", body: form });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}
