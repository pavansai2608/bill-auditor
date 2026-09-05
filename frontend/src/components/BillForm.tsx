import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";

import { useAudit } from "../context/AuditContext";
import { prefersReducedMotion } from "../hooks/useReveal";
import { fetchPolicies, uploadPolicy } from "../lib/api";
import { readBill, rupees } from "../lib/billStats";
import { EXAMPLE_BILL } from "../lib/exampleBill";
import { STATIC_DEMO } from "../lib/staticDemo";

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

/**
 * A section that rises into place on load, staggered behind the one before it.
 *
 * On load, deliberately - not on scroll. Both panels are the page; there is
 * nothing below the fold to reveal, and an IntersectionObserver that does not
 * fire would leave the whole form at `opacity: 0`. That is a dead screen
 * rather than a missed animation, and it flaked exactly that way once under
 * load before this was changed.
 *
 * `armed` turns on only after the first paint, so the stylesheet that hides a
 * section can never apply unless this component is running to show it again.
 * Reduced motion skips the whole thing and renders shown from the start.
 */
function Reveal({
  delay,
  className,
  children,
}: {
  delay: number;
  className: string;
  children: React.ReactNode;
}) {
  const [state, setState] = useState<"still" | "armed" | "shown">(() =>
    prefersReducedMotion() ? "shown" : "still",
  );

  useEffect(() => {
    if (state === "shown") return;
    // Two frames: one to apply the hidden state, one to transition out of it.
    // Setting both in the same frame gives no transition at all.
    let second = 0;
    const first = requestAnimationFrame(() => {
      setState("armed");
      second = requestAnimationFrame(() => setState("shown"));
    });
    return () => {
      cancelAnimationFrame(first);
      cancelAnimationFrame(second);
    };
    // Runs once: the entrance is a mount event, not a state machine.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const classes = [
    "audit-reveal",
    state !== "still" ? "is-armed" : "",
    state === "shown" ? "is-shown" : "",
    className,
  ];
  return (
    <div
      className={classes.filter(Boolean).join(" ")}
      style={{ "--reveal-delay": `${delay}ms` } as React.CSSProperties}
    >
      {children}
    </div>
  );
}

/**
 * What sits under the dead button on the published site.
 *
 * The rule the whole project runs on is that it never states something it
 * cannot support, and a form that posts into nothing breaks that rule at the
 * front door. So the button is disabled and this says exactly why, what the
 * missing half actually is, and how to run it - and then offers the one thing
 * a static file can honestly show: a report the system really produced.
 */
function StaticDemoNote({ onShowExample }: { onShowExample: () => void }) {
  return (
    <div className="static-note" data-testid="static-note">
      <h4>This copy cannot run an audit</h4>
      <p>
        You are looking at the front end on GitHub Pages — static files, with nothing behind them.
        The audit is not a service that is switched off: it searches a 402-clause index built from
        the policy PDFs, reranks the results with a cross-encoder and puts every line to an 8B model.
        That needs a machine, so it runs on yours, not on a CDN.
      </p>
      <p>From a clone of the repository:</p>
      <pre className="static-note-code">
        <code>
          {"uv sync\n"}
          {"uv run uvicorn api.main:app --reload\n"}
          {"cd frontend && npm ci && npm run dev"}
        </code>
      </pre>
      <p className="static-note-aside">
        Ollama has to be running with <code>qwen3:8b</code> pulled. The first audit takes 30–60
        seconds; every model call is cached to disk after that.
      </p>
      <button
        type="button"
        className="btn-secondary"
        data-testid="show-example"
        onClick={onShowExample}
      >
        See a report it produced
      </button>
      <p className="static-note-aside">
        Bill B01 against Star Health, from a recorded evaluation run. Every figure and every clause
        reference below is that run&rsquo;s own output — nothing on the next screen is illustrative.
      </p>
    </div>
  );
}

/** Screen 1. A bill, a policy, two dates, and one optional number. */
export function BillForm() {
  const { form, setForm, job } = useAudit();
  const [dragging, setDragging] = useState(false);
  const [uploadNote, setUploadNote] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const helpId = useId();
  const missingId = useId();
  const dateErrorId = useId();
  const countId = useId();

  const policies = useQuery({ queryKey: ["policies"], queryFn: fetchPolicies });
  const selected = policies.data?.find((p) => p.id === form.policy);
  const sumInsuredOptions = selected?.sum_insured_options ?? [300000, 500000, 1000000, 2500000];

  const stats = readBill(form.billText);
  const hasBill = form.billText.trim().length > 0;

  // A brief settle on the figures whenever the reading changes, so a paste
  // registers as something the page noticed rather than text that appeared.
  const [changing, setChanging] = useState(false);
  useEffect(() => {
    if (stats.items === 0) return;
    setChanging(true);
    const timer = window.setTimeout(() => setChanging(false), 240);
    return () => window.clearTimeout(timer);
  }, [stats.items, stats.total]);

  // Caught here rather than by the backend: a start date after the admission
  // date makes every waiting period negative, and the audit that comes back is
  // wrong in a way that looks like a system fault rather than a typo.
  const dateError =
    form.policyStartDate && form.admissionDate && form.policyStartDate > form.admissionDate
      ? "The policy cannot start after the admission. Check both dates."
      : null;

  const outstanding = missing(hasBill, form.policyStartDate, dateError);
  // STATIC_DEMO is the published site, which has no backend to submit to. The
  // button stays where it is and stays dead, and the panel below it says why.
  const canSubmit =
    outstanding.length === 0 && !job.isStarting && form.policy !== UPLOAD_OWN && !STATIC_DEMO;

  function loadExample() {
    setFileName(null);
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

  /**
   * A dropped or chosen file is read into the document rather than held aside.
   *
   * One surface, not two modes: the person sees the same thing whether they
   * pasted it or dropped it, the reading below updates either way, and they
   * can correct a stray line before submitting. The file was always .txt, so
   * nothing is lost by reading it here.
   */
  function readFile(file: File) {
    const reader = new FileReader();
    reader.onload = () => {
      setFileName(file.name);
      setForm({ billText: String(reader.result ?? ""), billFile: null });
    };
    reader.readAsText(file);
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
      className="audit-columns"
      data-testid="bill-form"
      onSubmit={(event) => {
        event.preventDefault();
        // Belt as well as braces. lib/api.ts already refuses without a
        // backend; this stops the request being attempted at all, including
        // from an Enter key in a text field, which no disabled button catches.
        if (STATIC_DEMO) return;
        job.start(form);
      }}
    >
      <Reveal delay={0} className="bill-panel">
        <div className="bill-panel-head">
          <h2>
            <label htmlFor="bill-text">Your bill</label>
          </h2>
          <span className="bill-choose">Nothing is stored after the audit.</span>
        </div>

        {/* Drop target and paste area are the same surface. */}
        <div
          className={dragging ? "bill-doc is-over" : "bill-doc"}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            const file = event.dataTransfer.files[0];
            if (file) readFile(file);
          }}
        >
          <textarea
            id="bill-text"
            data-testid="bill-text"
            value={form.billText}
            aria-describedby={countId}
            spellCheck={false}
            placeholder={
              "Paste the itemised bill here, or drop a .txt file on it.\n\n" +
              "Room Rent (Single A/C) 8,000 x 5 days      5    40,000.00\n" +
              "Surgeon Fee                                1    80,000.00"
            }
            onChange={(event) => {
              setFileName(null);
              setForm({ billText: event.target.value });
            }}
          />
        </div>

        <div className="bill-foot">
          <p className="bill-count-wrap" id={countId} aria-live="polite">
            {stats.items > 0 ? (
              <span
                className={changing ? "bill-count is-changing" : "bill-count"}
                data-testid="bill-count"
              >
                <strong>
                  {stats.items} {stats.items === 1 ? "item" : "items"}
                </strong>
                <span>Rs {rupees(stats.total)} total</span>
              </span>
            ) : (
              <span className="bill-count-empty">
                {fileName ? `${fileName} — no charges found` : "No bill yet."}
              </span>
            )}
          </p>

          <label className="bill-file-label">
            choose a file
            <input
              type="file"
              accept=".txt,text/plain"
              aria-label="bill file"
              data-testid="bill-file"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) readFile(file);
              }}
            />
          </label>
        </div>

        <div>
          <button
            type="button"
            className="bill-example"
            data-testid="load-example"
            onClick={loadExample}
          >
            Try an example bill
          </button>
        </div>
      </Reveal>

      <Reveal delay={120} className="policy-panel-wrap">
        <div className="policy-panel">
          <h2>Your policy</h2>

          <section className="step">
            <span className="step-n" aria-hidden="true">
              1
            </span>
            <div className="step-body">
              <h3>Who insures you</h3>
              <div className="step-pair">
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
                    {/* Indexing a PDF is a server-side job with a model in
                        it, so on the static build the option is not offered
                        rather than offered and broken. */}
                    {!STATIC_DEMO && <option value={UPLOAD_OWN}>upload my own policy…</option>}
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
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void onPolicyPdf(file);
                    }}
                  />
                  {uploadNote && <p className="help">{uploadNote}</p>}
                </div>
              )}
            </div>
          </section>

          <section className="step">
            <span className="step-n" aria-hidden="true">
              2
            </span>
            <div className="step-body">
              <h3>The dates</h3>
              <p className="step-why">Used to check waiting periods.</p>
              <div className="step-pair">
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
            </div>
          </section>

          <section className="step">
            <span className="step-n" aria-hidden="true">
              3
            </span>
            <div className="step-body">
              <h3>Room limit per day</h3>
              <div className="field">
                <label htmlFor="room-limit" className="visually-hidden">
                  Room limit per day, from your policy schedule
                </label>
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
                {/* A div, not a p: <details> is flow content and cannot sit
                    inside a paragraph. */}
                <div className="help" id={helpId}>
                  Optional — blank is fine.{" "}
                  <details className="why">
                    <summary>why?</summary>
                    <p>
                      Two of the three policies put the room limit on your schedule rather than in
                      the wording. If it is blank the audit says so on the affected lines instead of
                      assuming a figure.
                    </p>
                  </details>
                </div>
              </div>
            </div>
          </section>

          <div className="policy-submit">
            <button
              type="submit"
              className="btn-primary"
              data-testid="submit"
              disabled={!canSubmit}
            >
              {job.isStarting ? "Starting…" : "Audit this bill"}
            </button>
            {STATIC_DEMO ? (
              <StaticDemoNote
                onShowExample={() => {
                  // The form is filled with B01's own inputs first, so the
                  // summary above the report describes the bill the report was
                  // actually produced from rather than an empty form.
                  loadExample();
                  job.showExample();
                }}
              />
            ) : (
              outstanding.length > 0 && (
                <p
                  className="actions-note"
                  id={missingId}
                  data-testid="submit-blocked"
                  aria-live="polite"
                >
                  {sentence(outstanding)}
                </p>
              )
            )}
          </div>
        </div>
      </Reveal>
    </form>
  );
}
