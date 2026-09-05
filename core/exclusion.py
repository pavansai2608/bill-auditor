"""Does this clause exclude anything at all?

One question, asked of a clause's own text, so that a verdict claiming an
expense is not payable can be checked against the document it cites.

**The defect this exists for.** On B41 and B42 the judge returned
`limits=[{amount: 0.0}]` citing `star_health II.1`. II.1 is the in-patient
coverage clause - "We will cover the following Medical Expenses" - and states
no zero limit, no exclusion and nothing about anaesthetists. Guardrail 2 passed,
because II.1 exists. `money.allowed_for_line` did what it is told and returned
zero. The report told the insured that Rs 26,000 of anaesthetist fees was not
payable, with a clause reference beside it, and **nothing in the system could
see it**: a fabricated figure attached to a real clause passed every check.

Across the 44-bill eval every single zero limit the judge produced was wrong -
eight of them, seven of which became a confident `Rs 0` on a line the answer key
pays in full. Zero is not one wrong number among many. It is the claim that the
policy excludes the expense, and it is the most damaging thing this system can
say short of citing a clause that does not exist.

**Deliberately not the general case.** Verifying every rupee figure against its
clause is a much larger problem - percentages, "10% of Sum Insured or Rs
1,00,000 whichever is less", figures computed from a table - and one with real
false-rejection risk. This module answers only the narrow question, and only
zero limits are checked against it.

**What counts.** The clause text as a whole, tables included. A limit stated in
a table row is still the policy saying it: `star_health II.20` grants shared
accommodation "Not Available" at the two lowest sums insured, and a zero read
off that row is a correct reading. Requiring the exclusion to appear in prose
would catch one more bad verdict in the current eval and would reject that
correct one, so the whole clause is what is searched.
"""

import re

from core.models import Clause

# Exclusionary language, as these three documents actually write it.
#
# Every alternative below was taken from a clause in `data/clauses.json` rather
# than invented: the IRDAI code form ("Code Excl02"), the standard exclusion
# wording ("shall be excluded until the expiry of"), the benefit-table form
# ("Not Available", "Not Covered"), and the definition form ("does not include
# cost of pharmacy and consumables").
#
# The list is permissive on purpose. A pattern that is too narrow rejects an
# honest verdict, which costs a correct answer; a pattern that is too wide lets
# a fabricated zero through, which costs nothing that was not already lost.
# Erring wide is the safe direction for a rule that only ever *blocks*.
EXCLUSION_RE = re.compile(
    r"not\s+(?:be\s+)?(?:payable|covered|available|admissible|indemnifiable)"
    r"|(?:shall|will|does|do)\s+not\s+(?:be\s+liable|pay|indemnify|include)"
    r"|(?:is|are|shall\s+be)\s+excluded"
    r"|\bexclusions?\b"
    r"|code\s*[-\s]*excl\s*\d*"
    r"|\bexcl\s*\d"
    r"|\bnil\b"
    r"|no\s+(?:claim|benefit|amount)\s+(?:shall|will|is)\s+(?:be\s+)?payable",
    re.I,
)


def states_an_exclusion(clause: Clause) -> bool:
    """True when this clause's own text excludes something.

    The title is searched with the body because a heading is part of what the
    clause says. On this index it changes no answer: `split_clauses` writes the
    heading line as the first line of `text`, so every clause that matches in
    the title matches in the body too - **0 of 402 match on the title alone**.
    `hdfc_ergo E.2.1` is headed "Not Covered" and its body carries the words
    twice, the heading line being one of them. The title stays in the search
    because nothing guarantees that a future heading will be repeated in the
    body, not because any clause here needs it.
    """
    return bool(EXCLUSION_RE.search(f"{clause.title}\n{clause.text}"))


def is_zero(limit) -> bool:
    """A limit that allows nothing.

    A zero percentage is the same claim as a zero amount - nothing is payable -
    and both reach `money.allowed_for_line` as a cap of zero rupees.
    """
    return limit.amount == 0.0 or limit.percentage == 0.0
