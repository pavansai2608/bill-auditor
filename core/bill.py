"""Bill intake (R1-R5): raw text in, validated line items out.

Hospital bills arrive as pasted text, PDF extractions or photographs of a
printout, in no consistent format. Rather than write a parser per hospital,
the model reads it - but every field it returns is validated by Pydantic
before anything downstream trusts it, and identifiers are stripped before the
text is ever sent.
"""

import re

from pydantic import BaseModel, ValidationError

from core.config import settings
from core.llm import LLMError, complete_structured
from core.logging_conf import get_logger
from core.masking import mask_pii
from core.models import BillLine

log = get_logger(__name__)


class ParsedBill(BaseModel):
    lines: list[BillLine]


PARSE_SYSTEM = """You extract line items from an Indian hospital bill.

Return one entry per charged item:
- item: the description as printed, without the amount
- amount: the total rupee amount for that line, as a number
- qty: units or days if stated, otherwise 1

Rules:
- Amounts are in rupees. Strip commas and currency symbols: "Rs. 1,20,000" is 120000.
- If a line shows a rate and a number of days ("Room Rent 8000 x 5 days = 40000"),
  set amount to the total (40000) and qty to the number of days (5).
- Ignore subtotals, grand totals, taxes shown separately, discounts and
  amounts already paid. Only charged line items.
- Do not invent items that are not on the bill."""


def normalize_item(name: str) -> str:
    """R5 - fold whitespace and case so lookups behave predictably."""
    return re.sub(r"\s+", " ", name).strip().lower()


def parse_bill(bill_text: str) -> list[BillLine]:
    """R2-R5: mask, extract, validate, normalise.

    Masking happens first and on the raw text, so no identifier reaches the
    model, the disk cache, or a trace file.
    """
    masked = mask_pii(bill_text)

    try:
        parsed = complete_structured(
            f"Extract the line items from this bill:\n\n{masked}",
            ParsedBill,
            system=PARSE_SYSTEM,
            retries=settings.structured_output_retries,
        )
    except (LLMError, ValidationError) as exc:
        raise LLMError(f"could not parse the bill: {exc}") from exc

    lines = [
        BillLine(item=normalize_item(line.item), amount=line.amount, qty=line.qty)
        for line in parsed.lines
    ]
    log.info("parsed %d bill lines totalling %.2f", len(lines), sum(x.amount for x in lines))
    return lines
