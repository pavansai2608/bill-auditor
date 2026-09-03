import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useCountUp, useReveal } from "../hooks/useReveal";
import "./landing.css";

/**
 * The front door.
 *
 * Written for someone holding a bill and a settlement letter they did not
 * expect, who is not in the mood to be sold to. So: no gradients, no stock
 * photography, no claims about the technology. The worked example sits second
 * because a real bill with real figures answers "what is this" faster than any
 * paragraph, and the section admitting what the tool cannot do sits fourth
 * because it is the reason to believe the rest.
 *
 * Every figure on this page comes from eval/results.md or from an actual audit
 * of eval/bills/B01.json. Nothing here is illustrative.
 */

/** Star Health, sum insured Rs 3,00,000, five days in a single A/C room. */
const EXAMPLE_LINES = [
  {
    item: "Room Rent (Single A/C) 8,000 x 5 days",
    charged: "40,000",
    allowed: "25,000",
    allowedValue: 25000,
    clause: "II.1",
    tone: "cut" as const,
    note: "capped at Rs 5,000 a day",
  },
  {
    item: "Surgical Gloves",
    charged: "1,200",
    allowed: "0",
    allowedValue: 0,
    clause: "IRDAI-List-I",
    tone: "cut" as const,
    note: "not payable",
  },
  {
    item: "Medicines and Drugs",
    charged: "38,000",
    allowed: "38,000",
    allowedValue: 38000,
    clause: "II.16",
    tone: "paid" as const,
    note: "paid in full",
  },
  {
    item: "Disposable Syringes",
    charged: "800",
    allowed: null,
    allowedValue: null,
    clause: null,
    tone: "flag" as const,
    note: "no clause clearly applies",
  },
];

const STEPS = [
  {
    title: "Reads the bill",
    body: "Line items, amounts and days, from pasted text. Patient name, phone and ID are removed before anything else runs.",
  },
  {
    title: "Finds the clauses",
    body: "Searches the policy document itself, by wording and by meaning at once, and ranks the clauses that bear on the line.",
  },
  {
    title: "Computes in Python, never in the model",
    body: "The model reports the limit it read and the clause it came from. Every multiplication and subtraction is ordinary code.",
  },
  {
    title: "Cites the clause, or says it cannot decide",
    body: "A deduction with no clause behind it is not shown as a deduction. It is flagged for a person to check.",
  },
];

const NOT_FOR = [
  {
    title: "Cashless denials",
    body: "Why a pre-authorisation was refused at the desk is a different process, decided before the bill exists.",
  },
  {
    title: "Settlement delays",
    body: "Nothing here can tell you where a claim is sitting, or make it move faster.",
  },
  {
    title: "Disputes about treatment",
    body: "Whether a procedure was necessary, or was coded correctly, is a clinical question and not a reading of the policy.",
  },
  {
    title: "Whether the hospital's rates were fair",
    body: "It checks the bill against your policy, not against what the treatment should have cost.",
  },
];

/**
 * Straight from eval/results.md. Each row carries its bill count because the
 * quick runs score ten bills and the full run scores all 44 - putting those
 * two numbers in one column without saying so would flatter the result.
 *
 * results.md holds no v1, v2 or v3 section, so none is shown.
 */
const RESULTS = [
  { version: "v0", what: "naive baseline", bills: 10, lines: 82, accuracy: "24.4%" },
  { version: "v4", what: "room limit read from the table", bills: 10, lines: 82, accuracy: "59.8%" },
  { version: "v5", what: "waiting periods by date", bills: 10, lines: 82, accuracy: "68.3%" },
  { version: "v5", what: "every bill in the set", bills: 44, lines: 328, accuracy: "59.5%" },
];

const BILL_TEXT = `DESCRIPTION                        QTY     AMOUNT
Room Rent (Single A/C) 8,000 x 5     5  40,000.00
Surgical Gloves                     20   1,200.00
Medicines and Drugs                  1  38,000.00
Disposable Syringes                 40     800.00`;

/**
 * A section that rises into place the first time it is seen.
 *
 * `--reveal-delay` staggers children within a section; the wrapper itself
 * carries no delay, so the first thing a reader looks at is never the last
 * thing to arrive.
 */
function Reveal({
  children,
  as: Tag = "section",
  className = "",
  delay = 0,
  ...rest
}: {
  children: ReactNode;
  as?: "section" | "div" | "li";
  className?: string;
  delay?: number;
} & Record<string, unknown>) {
  const { ref, shown, armed } = useReveal<HTMLElement>();
  return (
    <Tag
      ref={ref as never}
      className={`${className} reveal${armed ? " is-armed" : ""}${shown ? " is-shown" : ""}`}
      style={{ "--reveal-delay": `${delay}ms` } as React.CSSProperties}
      {...rest}
    >
      {children}
    </Tag>
  );
}

/**
 * The product, in the hero, before a word is read.
 *
 * Decorative and aria-hidden on purpose: the same bill and the same verdicts
 * are a readable table two sections down, and a screen reader should meet them
 * there once rather than here twice.
 */
function HeroPlate() {
  return (
    <div className="hero-plate" aria-hidden="true">
      <div className="plate plate--bill">
        <span className="plate-label">Bill</span>
        <pre className="plate-bill">{BILL_TEXT}</pre>
      </div>
      <div className="plate plate--report">
        <span className="plate-label">Audited</span>
        <ul className="plate-lines">
          {EXAMPLE_LINES.map((line) => (
            <li key={line.item}>
              <span className="plate-item">{line.item.split(" (")[0]}</span>
              <span className={`plate-amount plate-amount--${line.tone}`}>
                {line.allowed ?? "flagged"}
              </span>
              <span className="plate-clause">{line.clause ?? "—"}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function Landing() {
  const { ref: exampleRef, shown: exampleShown } = useReveal<HTMLDivElement>();
  const roomRent = useCountUp(25000, exampleShown);

  return (
    <div className="landing">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <header className="landing-masthead">
        <span className="mark" aria-hidden="true" />
        <span className="landing-wordmark">Bill Auditor</span>
      </header>

      <main id="main">
        <section className="landing-hero" aria-labelledby="hero-heading">
          <h1 id="hero-heading">
            Check a hospital bill against the policy that is meant to pay it, line by line.
          </h1>
          <div className="hero-row">
            <div className="hero-copy">
              <p className="landing-lead">
                Insurers deduct against clauses most people never see. This shows you which clause
                took which rupee, so you can tell a rule from a mistake.
              </p>
              <Link className="landing-cta" to="/audit">
                Audit a bill
              </Link>
              <p className="landing-cta-note">
                No account, no email address. Three policies built in.
              </p>
            </div>
            <HeroPlate />
          </div>
        </section>

        <Reveal className="landing-section" aria-labelledby="example-heading">
          <h2 id="example-heading">A bill, and what came back</h2>
          <p className="landing-section-note">
            Four lines of a ten-line bill. Star Health, sum insured Rs 3,00,000, five days as an
            inpatient.
          </p>

          <div className="example-grid" ref={exampleRef}>
            <div className="example-panel">
              <h3 className="example-label">What went in</h3>
              <pre className="example-bill" aria-label="The pasted hospital bill">
                {BILL_TEXT}
              </pre>
            </div>

            <div className="example-panel">
              <h3 className="example-label">What came back</h3>
              <table className="example-table">
                <caption className="visually-hidden">
                  Each bill line with the amount allowed and the clause that decided it
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Line</th>
                    <th scope="col" className="num">
                      Charged
                    </th>
                    <th scope="col" className="num">
                      Allowed
                    </th>
                    <th scope="col">Clause</th>
                  </tr>
                </thead>
                <tbody>
                  {EXAMPLE_LINES.map((line) => (
                    <tr key={line.item} className={`row-${line.tone}`}>
                      <th scope="row">{line.item}</th>
                      <td className="num charged">{line.charged}</td>
                      <td className={`num amount amount-${line.tone}`}>
                        {line.allowed === null ? (
                          <span className="flagged">flagged</span>
                        ) : line.allowedValue === 25000 ? (
                          roomRent.toLocaleString("en-IN")
                        ) : (
                          line.allowed
                        )}
                      </td>
                      <td>
                        <span className="clause">{line.clause ?? "—"}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="example-legend">
                {EXAMPLE_LINES.map((line) => `${line.item.split(" (")[0]}: ${line.note}`).join(". ")}
                .
              </p>
            </div>
          </div>

          <details className="example-detail" open>
            <summary>Why the room rent came down by Rs 15,000</summary>
            <div className="example-detail-body">
              <p className="clause-quote">
                <span className="clause-id">Star Health II.1</span> — the room rent table, read at
                the row for a sum insured of Rs 3,00,000: <strong>up to Rs 5,000 per day</strong>.
              </p>
              <p className="clause-maths">
                Charged Rs 8,000 a day for 5 days = Rs 40,000. Eligible 5 × Rs 5,000 ={" "}
                <strong>Rs 25,000</strong>.
              </p>
              <p className="clause-consequence">
                One breached room limit does not stop at the room line. The policy reduces the
                associated medical expenses in the same proportion — 5,000 ÷ 8,000 — so the
                surgeon's fee and the theatre charge fall too, while medicines, consumables and ICU
                are left alone. That is the deduction people find hardest to see coming, because
                nothing on those lines mentions the room.
              </p>
            </div>
          </details>
        </Reveal>

        <Reveal className="landing-section" aria-labelledby="how-heading">
          <h2 id="how-heading">How it works</h2>
          <ol className="steps">
            {STEPS.map((step, index) => (
              <Reveal as="li" key={step.title} delay={index * 70}>
                <span className="step-number" aria-hidden="true">
                  {index + 1}
                </span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.body}</p>
                </div>
              </Reveal>
            ))}
          </ol>
        </Reveal>

        <Reveal className="landing-section" aria-labelledby="not-heading">
          <h2 id="not-heading">What it does not do</h2>
          <p className="landing-section-note">
            It reads one bill against one policy document. Everything below is outside that, and
            saying so is more use to you than pretending otherwise.
          </p>
          <ul className="not-list">
            {NOT_FOR.map((item, index) => (
              <Reveal as="li" key={item.title} delay={index * 70}>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </Reveal>
            ))}
          </ul>
          <p className="not-footnote">
            It also declines to answer. Where no clause clearly applies, the line is flagged for a
            person rather than given a confident figure — 21 of 82 lines in the last scored run.
          </p>
        </Reveal>

        <Reveal className="landing-section" aria-labelledby="results-heading">
          <h2 id="results-heading">How well it does</h2>
          <p className="landing-section-note">
            Scored against an answer key written by hand from the policy PDFs. Nothing here is
            judged by another model.
          </p>
          <table className="results-table">
            <caption className="visually-hidden">
              Line accuracy and fabricated citations by version
            </caption>
            <thead>
              <tr>
                <th scope="col">Version</th>
                <th scope="col" className="col-what">
                  What changed
                </th>
                <th scope="col" className="num">
                  Bills
                </th>
                <th scope="col" className="num col-lines">
                  Lines
                </th>
                <th scope="col" className="num">
                  Line accuracy
                </th>
                <th scope="col" className="num">
                  Fabricated
                </th>
              </tr>
            </thead>
            <tbody>
              {RESULTS.map((row) => (
                <tr key={`${row.version}-${row.bills}`}>
                  <th scope="row">{row.version}</th>
                  <td className="col-what">{row.what}</td>
                  <td className="num">{row.bills}</td>
                  <td className="num col-lines">{row.lines}</td>
                  <td className="num accuracy">{row.accuracy}</td>
                  <td className="num zero">0</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="results-note">
            A fabricated citation — a clause id that is not in the policy — is the worst thing this
            system could produce, because it is a wrong answer wearing the costume of a right one.
            It has stayed at zero at every version, and it is the metric watched hardest.
          </p>
          <p className="results-note">
            The two v5 rows are the same system on different sets: ten bills and all 44. The lower
            number is the more honest one to plan around.
          </p>
        </Reveal>

        <Reveal className="landing-closing" aria-labelledby="closing-heading">
          <h2 id="closing-heading">Ready when you are</h2>
          <p>
            Paste the bill, choose the policy and the sum insured, and read the clause behind every
            line.
          </p>
          <Link className="landing-cta" to="/audit">
            Audit a bill
          </Link>
        </Reveal>
      </main>

      <footer className="landing-footer">
        <p>
          <a href="https://github.com/pavansai2608/bill-auditor">Source on GitHub</a>
        </p>
        <p className="landing-disclaimer">
          A personal project, not financial or legal advice. Check anything that matters against
          your own policy document and your insurer.
        </p>
      </footer>
    </div>
  );
}
