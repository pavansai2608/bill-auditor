import { STATIC_DEMO, STATIC_POLICIES } from "./staticDemo";
import type { AuditFormValues, CompareStatus, JobStatus, PolicyOption } from "../types";

// One place for the API address. `npm run dev` talks to a local uvicorn,
// docker-compose sets this to the gateway, minikube sets it to the service.
//
// The static build has no API at all, and the localhost default is worse than
// useless there: it is a private host baked into a public bundle, so every
// visitor's browser would try to reach a server on their own machine. Blanked
// deliberately, and the callers below refuse to run rather than posting to a
// relative URL on the CDN.
export const API_BASE = STATIC_DEMO ? "" : (import.meta.env.VITE_API_BASE ?? "http://localhost:8000");

/**
 * The one place that turns "there is no backend" into an error.
 *
 * Every call below goes through it, so a path added later cannot quietly
 * become the one that posts into nothing from the published site.
 */
function refuseWithoutBackend(): never {
  throw new Error(
    "This is the static build of Bill Auditor. The audit runs a local retrieval " +
      "pipeline and a local model, neither of which is deployed publicly, so there " +
      "is nothing to send this to.",
  );
}

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
  // The dropdowns are the only thing on the form that needs the server just to
  // render. On the static build they read a copy of the same three rows, so
  // the form looks like itself while the submit path stays disabled.
  if (STATIC_DEMO) return STATIC_POLICIES;
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
  if (STATIC_DEMO) refuseWithoutBackend();
  const response = await fetch(`${API_BASE}/audit`, {
    method: "POST",
    body: formData(values, true),
  });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()).job_id;
}

export async function startCompare(values: AuditFormValues): Promise<string> {
  if (STATIC_DEMO) refuseWithoutBackend();
  const response = await fetch(`${API_BASE}/compare`, {
    method: "POST",
    body: formData(values, false),
  });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()).job_id;
}

export async function fetchJob(kind: "audit" | "compare", jobId: string): Promise<JobStatus | CompareStatus> {
  if (STATIC_DEMO) refuseWithoutBackend();
  const response = await fetch(`${API_BASE}/${kind}/${jobId}`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function uploadPolicy(file: File): Promise<{ job_id: string; policy: string }> {
  if (STATIC_DEMO) refuseWithoutBackend();
  const form = new FormData();
  form.set("file", file);
  const response = await fetch(`${API_BASE}/policies/upload`, { method: "POST", body: form });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}
