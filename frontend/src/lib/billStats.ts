/**
 * A reading of the pasted bill, for the person pasting it.
 *
 * This is feedback, not parsing. `core/bill.py` is the parser, it runs on the
 * server, and it is the only thing whose count means anything. This exists so
 * that pasting a bill answers "did it understand me?" immediately rather than
 * a minute later in a report.
 *
 * It is therefore deliberately conservative: a line counts only if it ends in
 * a figure that is written like money - comma-grouped, or with two decimal
 * places. "Chennai - 600 034" ends in digits and is not an amount; a bill line
 * ending "40,000.00" is. Being shy costs the user nothing; being eager would
 * put a wrong count under their bill and teach them not to trust the number
 * further down the page.
 */

export interface BillStats {
  items: number;
  total: number;
}

/** One charge, as this reading of the bill understood it. */
export interface BillItem {
  description: string;
  amount: number;
}

/**
 * The figure at the end of a line, in one of the two shapes that mean money.
 *
 * Either it is written like money - comma-grouped (1,200 / 2,36,000.00) or
 * carrying paise (800.00) - or it is a plain integer sitting in its own
 * column, which is what the two-space run before it means.
 *
 * The column rule is what earns plain integers. "Surgical Gloves   1200" is a
 * charge; "Chennai - 600 034" is a postcode, and the single space before its
 * last group is the whole difference. Accepting bare integers without it
 * counts addresses as items.
 */
const AMOUNT = /(?:\s{2,}|^)(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d{2})?)\s*$/;

/**
 * A summing line, matched against the description alone and only when the
 * description is nothing but the keyword.
 *
 * Testing the whole line for a leading "total" drops B27's "Total Knee
 * Replacement - Surgeon Fee", which is a Rs 1,45,000 charge and the largest
 * line on that bill. A word that begins a total also begins real procedures.
 */
const SUMMING_LINE = /^(grand\s+total|total|sub\s*-?\s*total|net\s+payable|amount\s+payable)\s*[:.\-–]*$/i;

/**
 * The quantity column, which sits between the description and the amount.
 *
 * Stripped only for display. "Room Rent (Single A/C) 8,000 x 5 days     5"
 * names the item and then states a quantity of 5 in its own column, and
 * showing that trailing 5 in a list of item names reads as a typo. The 2+
 * spaces are what make it a column rather than part of the description: "8,000
 * x 5 days" is single-spaced and survives, exactly as it should.
 */
const TRAILING_QTY = /\s{2,}\d+$/;

/**
 * The charges this reading finds, in the order they are written.
 *
 * Order is the whole reason this returns a list rather than a count: the
 * server audits the bill top to bottom, so "checked 4 of 10" and the fourth
 * item in this list are the same line, and the running panel can name the work
 * instead of only counting it.
 *
 * It is still the shy reader described above. It can find fewer items than the
 * server does - `core/bill.py` is the parser - so the panel that uses this
 * must degrade to the server's own count when the two disagree rather than
 * claiming a line it cannot name.
 */
export function readBillItems(text: string): BillItem[] {
  const items: BillItem[] = [];

  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    // Rules, and the patient block, which is metadata rather than charges.
    if (/^[-=_*]+$/.test(line)) continue;
    if (line.includes(":")) continue;

    const found = AMOUNT.exec(line);
    if (!found) continue;

    // Something has to be being charged for. A bare figure on its own line is
    // a total someone forgot to label.
    const description = line.slice(0, found.index).trim();
    if (description.replace(/[^a-z]/gi, "").length < 3) continue;
    if (SUMMING_LINE.test(description)) continue;

    const amount = Number(found[1].replace(/,/g, ""));
    if (!Number.isFinite(amount) || amount <= 0) continue;

    // The count and the total are taken from the untrimmed description above,
    // so stripping the quantity here cannot change what `readBill` reports.
    items.push({ description: description.replace(TRAILING_QTY, "").trim(), amount });
  }

  return items;
}

export function readBill(text: string): BillStats {
  const items = readBillItems(text);
  return {
    items: items.length,
    total: items.reduce((sum, item) => sum + item.amount, 0),
  };
}

/** Indian grouping, no paise: the figures on these bills are whole rupees. */
export function rupees(value: number): string {
  return value.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}
