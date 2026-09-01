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

## 4. The published accuracy numbers come from 10 bills, not all 44

Every result recorded in `eval/results.md` uses the `--quick` setting, which
runs the first 10 bills (82 individual lines). All 44 bills exist and their
correct answers are written down, but a full run takes around 45 minutes.

**Why this matters when reading the numbers.** Some categories have only 6 or 7
lines in them, so one line being right or wrong moves that category's score by
14 percentage points. Treat small category swings as noise, not as progress.
