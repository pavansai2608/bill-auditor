import { useQuery } from "@tanstack/react-query";
import { useId, useRef, useState } from "react";

import { useAudit } from "../context/AuditContext";
import { fetchPolicies, uploadPolicy } from "../lib/api";
import { EXAMPLE_BILL } from "../lib/exampleBill";

const UPLOAD_OWN = "__upload__";

function lakhs(value: number): string {
  return `${(value / 100000).toLocaleString("en-IN", { maximumFractionDigits: 2 })}L`;
}

/**
 * Everything still standing between this form and an audit, in the order a
 * person would fix it.
 *
 * A disabled button that does not say why is the most common way a form wastes
 * someone's time: they can see it is dead and cannot see what to do about it.
 */
function missing(hasBill: boolean, startDate: string, dateError: string | null): string[] {
  const wanted: string[] = [];
  if (!hasBill) wanted.push("a bill");
  if (!startDate) wanted.push("a policy start date");
  if (dateError) wanted.push("a start date before the admission date");
  return wanted;
}

function sentence(parts: string[]): string {
  if (parts.length === 1) return `Add ${parts[0]}.`;
  return `Add ${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}.`;
}

/** Screen 1. A bill, a policy, two dates, and one optional number. */
export function BillForm() {
  const { form, setForm, job } = useAudit();
  const [mode, setMode] = useState<"upload" | "paste">("upload");
  const [dragging, setDragging] = useState(false);
  const [uploadNote, setUploadNote] = useState<string | null>(null);
  const policyFileRef = useRef<HTMLInputElement>(null);
  const helpId = useId();
  const missingId = useId();
  const dateErrorId = useId();

  const policies = useQuery({ queryKey: ["policies"], queryFn: fetchPolicies });
  const selected = policies.data?.find((p) => p.id === form.policy);
  const sumInsuredOptions = selected?.sum_insured_options ?? [300000, 500000, 1000000, 2500000];

  const hasBill = mode === "upload" ? form.billFile !== null : form.billText.trim().length > 0;

  // Caught here rather than by the backend: a start date after the admission
  // date makes every waiting period negative, and the audit that comes back is
  // wrong in a way that looks like a system fault rather than a typo.
  const dateError =
    form.policyStartDate && form.admissionDate && form.policyStartDate > form.admissionDate
      ? "The policy cannot start after the admission. Check both dates."
      : null;

  const outstanding = missing(hasBill, form.policyStartDate, dateError);
  const canSubmit = outstanding.length === 0 && !job.isStarting && form.policy !== UPLOAD_OWN;

  function loadExample() {
    setMode("paste");
    setForm({
      billText: EXAMPLE_BILL.text,
      billFile: null,
      policy: EXAMPLE_BILL.policy,
      sumInsured: EXAMPLE_BILL.sumInsured,
      policyStartDate: EXAMPLE_BILL.policyStartDate,
      admissionDate: EXAMPLE_BILL.admissionDate,
      roomLimitPerDay: "",
    });
  }

  async function onPolicyPdf(file: File) {
    setUploadNote("indexing that policy — this takes a few minutes");
    try {
      const { policy } = await uploadPolicy(file);
      setUploadNote(`stored as "${policy}". It appears in the list once indexing finishes.`);
      await policies.refetch();
    } catch (error) {
      setUploadNote((error as Error).message);
    }
  }

  return (
    <form
      className="audit-form"
      data-testid="bill-form"
      onSubmit={(event) => {
        event.preventDefault();
        job.start(form);
      }}
    >
      <section className="form-group">
        <div className="form-group-head">
          <div>
            <h2>Your bill</h2>
            <p className="form-note">A hospital bill as text. Nothing is stored after the audit.</p>
          </div>
          <button
            type="button"
            className="btn-quiet"
            data-testid="load-example"
            onClick={loadExample}
          >
            Try it with an example
          </button>
        </div>

        {mode === "upload" ? (
          <label
            className={dragging ? "dropzone is-over" : "dropzone"}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              const file = event.dataTransfer.files[0];
              if (file) setForm({ billFile: file });
            }}
          >
            <strong>{form.billFile ? form.billFile.name : "Drop a bill here, or choose a file"}</strong>
            <span>a .txt file of the itemised bill</span>
            {/* The input is the whole area: the native button is small, ugly,
                and says "No file chosen" next to itself forever. */}
            <input
              type="file"
              accept=".txt,text/plain"
              aria-label="bill file"
              data-testid="bill-file"
              onChange={(event) => setForm({ billFile: event.target.files?.[0] ?? null })}
            />
          </label>
        ) : (
          <div className="field">
            <label htmlFor="bill-text">Paste the bill</label>
            <textarea
              id="bill-text"
              data-testid="bill-text"
              value={form.billText}
              placeholder={"Room Rent (Single A/C) 8,000 x 5 days   40000\nSurgeon Fee   80000"}
              onChange={(event) => setForm({ billText: event.target.value })}
            />
          </div>
        )}

        <button
          type="button"
          className="btn-link"
          data-testid="toggle-input-mode"
          onClick={() => setMode(mode === "upload" ? "paste" : "upload")}
        >
          {mode === "upload" ? "or paste it instead" : "or upload a file instead"}
        </button>
      </section>

      <section className="form-group">
        <div className="form-group-head">
          <div>
            <h2>Your policy</h2>
            <p className="form-note">
              These four answers are on the policy schedule the insurer sent you.
            </p>
          </div>
        </div>

        <div className="grid-2">
          <div className="field">
            <label htmlFor="policy">Insurer</label>
            <select
              id="policy"
              data-testid="policy"
              value={form.policy}
              onChange={(event) => setForm({ policy: event.target.value })}
            >
              {policies.data?.map((policy) => (
                <option key={policy.id} value={policy.id}>
                  {policy.name}
                </option>
              ))}
              <option value={UPLOAD_OWN}>upload my own policy…</option>
            </select>
          </div>

          <div className="field">
            <label htmlFor="sum-insured">Sum insured</label>
            <select
              id="sum-insured"
              data-testid="sum-insured"
              value={form.sumInsured}
              onChange={(event) => setForm({ sumInsured: Number(event.target.value) })}
            >
              {sumInsuredOptions.map((value) => (
                <option key={value} value={value}>
                  {lakhs(value)} — Rs {value.toLocaleString("en-IN")}
                </option>
              ))}
            </select>
          </div>
        </div>

        {form.policy === UPLOAD_OWN && (
          <div className="field">
            <label htmlFor="policy-pdf">Your policy PDF</label>
            <input
              id="policy-pdf"
              type="file"
              accept="application/pdf"
              ref={policyFileRef}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void onPolicyPdf(file);
              }}
            />
            {uploadNote && <p className="help">{uploadNote}</p>}
          </div>
        )}

        <p className="field-lede">Used to check waiting periods.</p>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="policy-start">Policy start date</label>
            <input
              id="policy-start"
              type="date"
              data-testid="policy-start"
              value={form.policyStartDate}
              max={form.admissionDate || undefined}
              aria-invalid={dateError !== null}
              aria-describedby={dateError ? dateErrorId : undefined}
              onChange={(event) => setForm({ policyStartDate: event.target.value })}
            />
            <p className="help">The date on the schedule, not the renewal.</p>
          </div>
          <div className="field">
            <label htmlFor="admission">Admission date</label>
            <input
              id="admission"
              type="date"
              data-testid="admission"
              value={form.admissionDate}
              onChange={(event) => setForm({ admissionDate: event.target.value })}
            />
            <p className="help">The day the hospital admitted you.</p>
          </div>
        </div>
        {dateError && (
          <p className="field-error" id={dateErrorId} role="alert" data-testid="date-error">
            {dateError}
          </p>
        )}

        <div className="field">
          <label htmlFor="room-limit">Room limit per day, from your policy schedule</label>
          <input
            id="room-limit"
            type="text"
            inputMode="numeric"
            data-testid="room-limit"
            aria-describedby={helpId}
            placeholder="e.g. 5000"
            value={form.roomLimitPerDay}
            onChange={(event) => setForm({ roomLimitPerDay: event.target.value })}
          />
          {/* A div, not a p: <details> is flow content and cannot sit inside a
              paragraph. */}
          <div className="help" id={helpId}>
            Optional. Blank is fine.{" "}
            <details className="why">
              <summary>why?</summary>
              <p>
                Two of the three policies put the room limit on your schedule rather than in the
                wording. If it is blank the audit says so on the affected lines instead of assuming
                a figure.
              </p>
            </details>
          </div>
        </div>
      </section>

      <div className="actions">
        <button type="submit" className="btn-primary" data-testid="submit" disabled={!canSubmit}>
          {job.isStarting ? "Starting…" : "Audit this bill"}
        </button>
        {outstanding.length > 0 && (
          <p className="actions-note" id={missingId} data-testid="submit-blocked" aria-live="polite">
            {sentence(outstanding)}
          </p>
        )}
      </div>
    </form>
  );
}
