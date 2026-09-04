# Known limitations

What this system gets wrong today, in plain language.

**What the system does, in one line:** you give it a hospital bill and a
policy; it goes through the bill line by line and says how much the insurer
should pay for each line, quoting the exact policy clause that decided it. If
it cannot find a clause, it flags the line for a human instead of guessing.

---

## 1. It flags lines that should simply be paid in full

**Example.** Bill B03 is a cataract operation on a Niva Bupa policy. Six lines:
the room, the surgery package, the lens, the surgeon, medicines, tests. The
correct answer is that all six are paid in full - this policy puts no cap on
any of them.

The system flags five of the six and says "I could not find a clause."

**Why.** For each line the system searches the policy for a clause that *limits*
that line. Two results are possible:

- it finds a limit, e.g. "ambulance is capped at Rs 750" → it applies the cap
- it finds nothing → it flags the line

The problem is that "nothing" has two very different meanings:

| What is true | What the system sees |
|---|---|
| There is no cap, so pay the full amount | nothing found |
| There is a cap and the search missed it | nothing found |

It cannot tell these apart, so it plays safe and flags. For the lens line, the
best clause it found scored 0.02 out of 1 for relevance - effectively nothing
in the policy is about intraocular lenses, because nothing limits them.

**Why this is not a quick fix.** The system would have to ask a different
question: not *"what limits this line?"* but *"is this line covered at all?"*
That means changing what the AI model is asked to return, and changing what
counts as an acceptable answer. The danger is the direction it fails in. Today
a missed clause becomes a flag, which a human then checks. After such a change,
a missed clause could become "no limit found, pay in full" - the system would
quietly overpay and nobody would notice. That trade needs its own testing
before it goes in.

**So for now:** flagging is wrong, but it is wrong in the safe direction. A
flagged line gets looked at by a person. A wrongly paid line does not.

---

## 2. Star Health bills are not checked against the 24-month disease list

**Background.** Health policies do not cover certain planned operations -
cataract, hernia, knee replacement and similar - until you have held the policy
for 24 months. This is called a *waiting period*. If someone claims for a
hernia four months into their policy, the insurer pays nothing.

To apply that rule the system needs two things from the policy document: the
period (24 months) and the list of conditions it applies to.

**The problem.** For Star Health, the list is missing. Its clause III.2 states
the 24 months and then ends with the words *"f. List of specific
diseases/procedures;"* - the list is on the following page of the PDF and did
not survive the text extraction. HDFC Ergo and Niva Bupa both have their lists
inside the clause text, so they work fine.

**What the system does about it.** It refuses to apply the rule unless it can
actually see the condition named in the policy's own text. So a Star Health
hernia claim inside the waiting period will be paid rather than excluded.

That is a mistake, but the alternative is worse: zeroing an entire hospital
bill based on a list the system cannot read, while displaying a clause number
that makes it look verified.

**Fix.** Find where that list ends up when the PDF is split into clauses and
attach it to III.2. Roughly half a day, mostly in the PDF-splitting code.

---

## 3. It never applies the pre-existing disease rule

Policies also exclude conditions you already had before buying the policy,
usually for 36 months. The system reads that rule and reports it, but never
applies it.

**Why.** Nothing on a hospital bill says whether a condition existed before the
policy started, and nothing the user types into this system says so either. The
only way to apply the rule would be to assume the answer. So the system records
the rule and the clause in its notes, and leaves the judgement to the human
reviewer who has the medical history.

---

## 4. The version-to-version numbers come from 10 bills, not all 44

The whole set has now been run: **59.5% line accuracy over 44 bills and 328
lines**, recorded in `eval/results.md` as `v5-full - 2026-09-02`. That is the
number to quote.

The v0 to v5 comparison rows are still the `--quick` setting, which runs the
first 10 bills (82 lines), because a full run takes around 45 minutes and that
is too slow to sit between one version and the next. The subset is held constant
so a change between two versions is attributable to the change rather than to a
different sample.

**Why this matters when reading the numbers.** The two are different
denominators and must not be put on one ladder: v5 scores 68.3% on the ten and
59.5% on the forty-four, because the other 34 bills are harder. And on the
subset some categories hold only 6 or 7 lines, so one line moves that category
by 14 percentage points. Treat small category swings there as noise.

## 5. Ten bills still need a person to check the answer key

`eval/answer_key_provenance.md` lists ten bills whose derivations need checking
against the source PDFs by a human, and **that check has not been done.** The
key was written by a language model reading policy documents and the judge is
also a language model reading policy documents; reading whole pages by a
separate route removes the shared plumbing but not the shared reader. The same
file records an unresolved conflict on B43 - whether HDFC's "At Actuals" is a
stated default or a deferral to the schedule - which needs a decision before
that bill's row means anything.

## 6. The eval measures agreement between two implementations, not correctness

This is the most serious limitation in the file, and it is not about a category
or a bill. It is about what the headline number means.

**The key's substance came from a model reading the same PDFs the judge reads.**
`eval/derive_key.py` is genuinely independent of the pipeline's *plumbing*: it
imports no retriever, no judge, no audit code, and it makes no model call. That
is real, and it is the failure most eval harnesses have. But it is independence
of the wiring, not of the reading. Every policy figure in it - the room-rent
table, the cataract sub-limits, the definition of associated medical expenses,
the 24-month list - is a constant typed into the source file, put there by a
language model reading the three policy documents. The judge is a language model
reading the same three documents. Different route, same reader. A misreading
available to one was available to the other, and **nothing re-checks either
against the PDF.**

Worth being exact about: `derive_key.py` does not open the PDFs. Its whole
runtime input is `eval/bills/*.json` and `data/non_payable.json`. The docstring's
claim that rules were "read off the PDF pages directly with pdfplumber"
describes where the constants came from when someone wrote them, not what the
script does. It imports `argparse, json, re, sys, datetime, pathlib`, and
nothing else.

**The key and `core/` share a taxonomy.** This is the part that cannot be fixed
by being careful. The key decides that a surgeon's fee is an associated medical
expense with its own `AME_RE`; `core/second_pass.py` decides the same thing with
its own `AME_RE`. The key routes room lines with `ROOM_RE`; `core/agent.py`
routes them with `RULE_PATTERNS`. Two separate regex sets, written by the same
process, cutting bill lines into the same categories with the same vocabulary.

Where that cut is wrong, **both sides are wrong in the same direction and the
eval scores the line correct.** No amount of running the eval can surface it,
because the eval is the thing that shares the error. Only reading the policy can.

**So what the number is.** 51.5% line accuracy is a real, deterministic,
reproducible measurement of how often the pipeline agrees with a second
implementation of the same beliefs. It will catch a regression in the splitter,
the retriever, the reranker or the judge - that is what it is for, and it has
done so more than once. It will not catch a misreading of the policy. Read it as
*agreement*, not as *correctness*, and do not describe it as accuracy against
the documents anywhere it could be mistaken for one.

**What is on the correct side of that line.** Exactly two things.
`eval/build_answer_key_review.py` goes back to the PDFs and locates quoted text
on real pages; it prepares a check by a person, and that check has not been
performed. And `tests/test_tables_golden.py` pins the extracted text of every
table in all four documents, which is the one place a policy figure is verified
against the source rather than against a second opinion about the source.

`eval/answer_key_todo.md` is the shortlist that would close the gap: **72 rows
in 5 questions**, each one naming the page to open.

### What was checked, and what it showed

`eval/repair_answer_key.py` takes the text each derivation puts in quotation
marks and searches every clause of that policy for it. Where exactly one clause
contains every quote, that clause is the citation. It never reads a verdict, a
report or a checkpoint.

It moved **nothing**. Of 261 cited lines, 189 already point at a clause that
contains every quote they use; 59 are table derivations with no quoted text to
search for; 13 quote text that is in no clause of their policy at all.

Those 13 are one question. Every one cites `star_health III.2`, the
specified-disease waiting period, and quotes *"Expenses related to the treatment
of the listed conditions"*. That text is in `hdfc_ergo C.1` and `niva_bupa 5.1.2`
but not in star_health's own III.2 - whose indexed text begins **"E xpenses
related to the treatment of the following listed Conditions"**. The split word
is a PDF extraction artefact; there are **48 of them across 33 clauses**, and
BM25 cannot match a term that is broken in half. The citation is probably right
and the evidence chain is broken, which is a different problem from a wrong
citation and needs the same PDF to settle.

The "37 of 93 entries cite a clause that does not contain the text they quote"
figure in `answer_key_review.md` is **stale**. Those rows were the associated
medical expenses citing the room-rent cap, and decision D-12 moved 85 of them by
hand to `I.Def45` / `A.1.2.Def5` - which is exactly where their quotes live. The
repair found nothing because the repair had already been made as a decision.

**`eval/derive_key.py` no longer reproduces the key**, and running it with
`--write` would have reverted 87 of those decisions in one command. `--write` is
now refused, and `tests/test_derive_key_divergence.py` pins the disagreement
line by line against a golden file so it cannot grow unnoticed.

## 7. A fabricated figure attached to a real clause passed every check

Until v11 the system could tell an insured that an expense was not payable,
cite a real clause for it, and nothing anywhere would notice.

The guardrail that exists to stop invented citations - guardrail 2 - asks one
question: is this clause id in the index? `star_health II.1` is. It is the
in-patient coverage clause, and it opens *"We will cover the following Medical
Expenses"*. On B41 and B42 the judge returned a limit of **Rs 0** citing it, for
anaesthetist charges. `money.allowed_for_line` did exactly what it is built to
do and returned zero. The report showed Rs 26,000 struck out, with `II.1` beside
it as the authority.

**Every check passed.** The clause was real, the model was confident, the
arithmetic was correct, and the citation resolved to a clause a reader could
look up and find. The only thing wrong was that the clause did not say it.

Measured across the whole 44-bill eval: **8 zero limits, all 8 wrong**, 7 of
them landing as a confident `Rs 0` on a line the answer key pays in full.

The gap was structural, not a slip. The project's hard rule is that the model
never does arithmetic - it reports a limit and a clause id, and Python computes
the money. That removes one class of error entirely and, until now, quietly
assumed the *limit* was as trustworthy as the arithmetic. It is not. The clause
id was checked against the index from the start; the figure attached to it was
checked against nothing.

**What v11 closes, and what it does not.** A limit of zero is now rejected
unless the cited clause contains exclusionary language, because zero is not a
small number - it is the claim that the policy excludes the expense, and it is
the most damaging thing this system can say short of citing a clause that does
not exist. Every other figure is still unverified. A limit of Rs 5,000 read out
of a clause that states Rs 50,000 would pass today exactly as the zero did.

And three of the eight still get through, for a reason worth stating plainly:
`hdfc_ergo E.2.1` is headed "Not Covered" and `star_health II.20` says "Not
Available" in its benefit table, so both satisfy a rule that only asks whether
the clause excludes *anything*. Neither excludes the line being judged. Closing
that needs the exclusion tied to this expense, which is the general case - and
the general case is where false rejections start costing correct answers.

The honest summary: **the citation is verified, the figure is not, and only the
worst figure is.**
