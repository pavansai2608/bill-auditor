import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import { useAuditJob, type AuditJob } from "../hooks/useAuditJob";
import type { AuditFormValues } from "../types";

const TODAY = new Date().toISOString().slice(0, 10);

export const EMPTY_FORM: AuditFormValues = {
  billText: "",
  billFile: null,
  policy: "star_health",
  sumInsured: 300000,
  policyStartDate: "",
  admissionDate: TODAY,
  // Blank by default and blank is a valid answer: it makes the audit abstain
  // on room-rent lines rather than guess a limit.
  roomLimitPerDay: "",
  roomCategory: "",
};

interface AuditState {
  form: AuditFormValues;
  setForm: (update: Partial<AuditFormValues>) => void;
  job: AuditJob;
}

const AuditContext = createContext<AuditState | null>(null);

/** The form values and the running job, shared without prop drilling. */
export function AuditProvider({ children }: { children: ReactNode }) {
  const [form, setFormState] = useState<AuditFormValues>(EMPTY_FORM);
  const job = useAuditJob();

  const value = useMemo<AuditState>(
    () => ({
      form,
      setForm: (update) => setFormState((current) => ({ ...current, ...update })),
      job,
    }),
    [form, job],
  );

  return <AuditContext.Provider value={value}>{children}</AuditContext.Provider>;
}

export function useAudit(): AuditState {
  const value = useContext(AuditContext);
  if (value === null) throw new Error("useAudit must be used inside an AuditProvider");
  return value;
}
