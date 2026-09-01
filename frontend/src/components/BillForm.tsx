import { useQuery } from "@tanstack/react-query";
import { useId, useRef, useState } from "react";

import { useAudit } from "../context/AuditContext";
import { fetchPolicies, uploadPolicy } from "../lib/api";

const UPLOAD_OWN = "__upload__";

function lakhs(value: number): string {
  return `${(value / 100000).toLocaleString("en-IN", { maximumFractionDigits: 2 })}L`;
}

/** Screen 1. A bill, a policy, two dates, and one optional number. */
export function BillForm() {
  const { form, setForm, job } = useAudit();
  const [mode, setMode] = useState<"upload" | "paste">("upload");
  const [dragging, setDragging] = useState(false);
  const [uploadNote, setUploadNote] = useState<string | null>(null);
  const policyFileRef = useRef<HTMLInputElement>(null);
  const helpId = useId();

  const policies = useQuery({ queryKey: ["policies"], queryFn: fetchPolicies });
  const selected = policies.data?.find((p) => p.id === form.policy);
  const sumInsuredOptions = selected?.sum_insured_options ?? [300000, 500000, 1000000, 2500000];

  const hasBill = mode === "upload" ? form.billFile !== null : form.billText.trim().length > 0;
  const canSubmit = hasBill && !job.isStarting && form.policy !== UPLOAD_OWN;

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
      data-testid="bill-form"
      onSubmit={(event) => {
        event.preventDefault();
        job.start(form);
      }}
    >
      <section className="panel">
        <h2>Your bill</h2>
        <p className="panel-note">A hospital bill as text. Nothing is stored after the audit.</p>

        {mode === "upload" ? (
          <div
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
            <strong>{form.billFile ? form.billFile.name : "Drag the bill here"}</strong>
            <span>a .txt file of the itemised bill</span>
            <input
              type="file"
              accept=".txt,text/plain"
              aria-label="bill file"
              data-testid="bill-file"
              onChange={(event) => setForm({ billFile: event.target.files?.[0] ?? null })}
            />
          </div>
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

      <section className="panel">
        <h2>Your policy</h2>
        <p className="panel-note">
          These four answers are on the policy schedule the insurer sent you.
        </p>

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

        <div className="grid-2">
          <div className="field">
            <label htmlFor="policy-start">Policy start date</label>
            <input
              id="policy-start"
              type="date"
              data-testid="policy-start"
              value={form.policyStartDate}
              onChange={(event) => setForm({ policyStartDate: event.target.value })}
            />
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
          </div>
        </div>

        <div className="field">
          <label htmlFor="room-limit">Room limit per day as per your policy schedule (optional)</label>
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
          <p className="help" id={helpId}>
            Leaving this blank is fine. Two of the three policies put the room limit on your
            schedule rather than in the wording, and if it is blank the audit says so on the
            affected lines instead of assuming a figure.
          </p>
        </div>
      </section>

      <div className="actions actions--end">
        <button type="submit" className="btn-primary" data-testid="submit" disabled={!canSubmit}>
          {job.isStarting ? "Starting…" : "Audit this bill"}
        </button>
      </div>
    </form>
  );
}
