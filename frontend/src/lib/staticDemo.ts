import type { AuditReport, PolicyOption } from "../types";

/**
 * What the app does when there is no backend behind it.
 *
 * The published site at https://pavansai2608.github.io/bill-auditor/ is static
 * files and nothing else. The audit is not a web service that happens to be
 * switched off - it is a retrieval pipeline over a 402-clause index and an 8B
 * model running locally, and none of that can be put on a CDN.
 *
 * So the site has exactly two honest options: say so, or lie. This is the
 * first. `STATIC_DEMO` is set only by frontend/.env.pages, so `npm run dev`,
 * the nginx image and the E2E stage all keep the real form and never take this
 * path at all.
 *
 * The rule this file follows: **nothing here fabricates a result.** The policy
 * list is the real one, copied because a dropdown with no options is a broken
 * page rather than a disabled one. The example report is a recorded run, not a
 * mock - see src/data/exampleReport.json and eval/export_example_report.py.
 */
export const STATIC_DEMO = import.meta.env.VITE_STATIC_DEMO === "true";

/**
 * The three indexed policies, exactly as `GET /policies` reports them.
 *
 * Clause counts are the real ones - star_health 153, hdfc_ergo 144,
 * niva_bupa 105, 402 in all - and star_health's sums insured are the rows of
 * its own room rent table, which is why its list is longer than the other two.
 * The dropdowns are filled so the form still reads as a form; the submit path
 * is disabled either way.
 */
export const STATIC_POLICIES: PolicyOption[] = [
  {
    id: "hdfc_ergo",
    name: "HDFC ERGO",
    clauses: 144,
    sum_insured_options: [300000, 500000, 1000000, 2500000],
  },
  {
    id: "niva_bupa",
    name: "Niva Bupa",
    clauses: 105,
    sum_insured_options: [300000, 500000, 1000000, 2500000],
  },
  {
    id: "star_health",
    name: "Star Health",
    clauses: 153,
    sum_insured_options: [
      100000, 200000, 300000, 400000, 500000, 1000000, 1500000, 2000000, 2500000,
    ],
  },
];

/** Where the bundled report came from, so the page can name its own source. */
export interface ExampleProvenance {
  run: string;
  bill_id: string;
  recorded_at: string;
  backend: string;
  model: string;
}

interface ExampleFile {
  recorded: ExampleProvenance;
  report: AuditReport;
}

/**
 * The recorded report, fetched only when someone asks to see it.
 *
 * A dynamic import so the 27 KB of report and trace becomes its own chunk
 * rather than weight on the landing page, which is the one screen most
 * visitors will ever load.
 */
export async function loadExampleReport(): Promise<ExampleFile> {
  const module = await import("../data/exampleReport.json");
  return module.default as unknown as ExampleFile;
}
