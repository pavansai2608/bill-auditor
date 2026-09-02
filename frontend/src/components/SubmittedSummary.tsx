import { useAudit } from "../context/AuditContext";

/**
 * What was actually sent, kept on screen while the audit runs.
 *
 * The form used to disappear the moment it was submitted, which left no way to
 * answer the first question anyone asks of a wrong number: "what did I give
 * it?" - and no way to spot the wrong sum insured until the report was already
 * built on it. One line by default, the whole lot on request.
 */
function policyName(id: string): string {
  return id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function billSummary(billText: string, fileName: string | null): string {
  if (fileName) return fileName;
  const lines = billText.trim().split("\n").filter(Boolean).length;
  return `${lines} line${lines === 1 ? "" : "s"} pasted`;
}

export function SubmittedSummary() {
  const { form } = useAudit();
  const bill = billSummary(form.billText, form.billFile?.name ?? null);

  return (
    <details className="submitted" data-testid="submitted-summary">
      <summary>
        <span className="submitted-line">
          {policyName(form.policy)} · Rs {form.sumInsured.toLocaleString("en-IN")} · {bill}
        </span>
        <span className="submitted-more">what was sent</span>
      </summary>
      <dl className="submitted-detail">
        <div>
          <dt>Insurer</dt>
          <dd>{policyName(form.policy)}</dd>
        </div>
        <div>
          <dt>Sum insured</dt>
          <dd className="tabular">Rs {form.sumInsured.toLocaleString("en-IN")}</dd>
        </div>
        <div>
          <dt>Policy start</dt>
          <dd className="tabular">{form.policyStartDate || "not given"}</dd>
        </div>
        <div>
          <dt>Admission</dt>
          <dd className="tabular">{form.admissionDate || "not given"}</dd>
        </div>
        <div>
          <dt>Room limit</dt>
          <dd className="tabular">
            {form.roomLimitPerDay ? `Rs ${form.roomLimitPerDay} a day` : "left blank"}
          </dd>
        </div>
        <div>
          <dt>Bill</dt>
          <dd>{bill}</dd>
        </div>
      </dl>
      {form.billText.trim() && (
        <pre className="submitted-bill" data-testid="submitted-bill">
          {form.billText.trim()}
        </pre>
      )}
    </details>
  );
}
