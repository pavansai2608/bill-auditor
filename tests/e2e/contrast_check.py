"""Contrast and focus-ring audit of both screens, in a real browser.

Not a unit test - a driver script, like `capture_screenshots.py`. It needs the
frontend served, because contrast is a property of what the browser actually
paints and not of what `tokens.json` says. A token pair can be perfectly legal
and still never appear together; another can be illegal and appear everywhere.
Reading the computed styles off the rendered page is the only way to know
which.

    cd frontend && npm run build && npx vite preview --port 5173
    uv run python tests/e2e/contrast_check.py

Two things are checked, and both are pass/fail rather than advisory:

* **Contrast.** Every element with its own visible text, against the first
  ancestor that actually paints a background. WCAG AA: 4.5:1 for body text,
  3:1 for large text (24px, or 18.66px at weight 700 and above).
* **Focus rings.** Every tab stop, in tab order, must paint something visible
  when it is focused - an outline, a box-shadow or a border that changes.
  `:focus { outline: none }` with nothing to replace it is the failure this
  catches, and it is invisible to a contrast checker.

Exit status is 0 only when both are at zero failures.
"""

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

ROOT = Path(__file__).resolve().parents[2]
APP = os.environ.get("BA_E2E_APP", "http://localhost:5173")
PAGES = [("landing", APP), ("audit", f"{APP}/audit")]
HEADLESS = os.environ.get("BA_E2E_HEADLESS", "1") == "1"
WIDTHS = {"1440": (1440, 1000), "390": (390, 844)}

# WCAG 2.1 AA. Large text is 24px, or 18.66px at 700 and above.
AA_NORMAL = 4.5
AA_LARGE = 3.0

CONTRAST_JS = r"""
const luminance = (rgb) => {
  const [r, g, b] = rgb.map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const parse = (value) => {
  const m = value.match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const parts = m[1].split(/[,\s/]+/).filter(Boolean).map(Number);
  return { rgb: parts.slice(0, 3), alpha: parts.length > 3 ? parts[3] : 1 };
};
const over = (top, bottom) =>
  top.rgb.map((c, i) => c * top.alpha + bottom[i] * (1 - top.alpha));

// The first ancestor that actually paints. A transparent background is not a
// background, and compositing a translucent one over what is behind it is the
// only way to get the colour a reader really sees.
const backgroundOf = (element) => {
  let node = element;
  let stack = [];
  while (node) {
    const paint = parse(getComputedStyle(node).backgroundColor);
    if (paint && paint.alpha > 0) {
      if (paint.alpha >= 1) {
        return stack.reduceRight((acc, layer) => over(layer, acc), paint.rgb);
      }
      stack.push(paint);
    }
    node = node.parentElement;
  }
  return stack.reduceRight((acc, layer) => over(layer, acc), [255, 255, 255]);
};

const hasOwnText = (element) =>
  Array.from(element.childNodes).some(
    (n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim().length > 0,
  );

const findings = [];
for (const element of document.querySelectorAll("body *")) {
  if (!hasOwnText(element)) continue;
  const style = getComputedStyle(element);
  if (style.visibility === "hidden" || style.display === "none") continue;
  if (Number(style.opacity) === 0) continue;
  const box = element.getBoundingClientRect();
  if (box.width === 0 || box.height === 0) continue;

  const foreground = parse(style.color);
  if (!foreground) continue;
  // From the element itself, not its parent: a button paints its own
  // background, and starting a level up reads the page behind it instead.
  const background = backgroundOf(element);
  const rgb = foreground.alpha >= 1 ? foreground.rgb : over(foreground, background);

  const a = luminance(rgb);
  const b = luminance(background);
  const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);

  const size = parseFloat(style.fontSize);
  const weight = Number(style.fontWeight) || 400;
  const large = size >= 24 || (size >= 18.66 && weight >= 700);

  findings.push({
    tag: element.tagName.toLowerCase(),
    cls: element.className && element.className.toString().slice(0, 40),
    text: element.textContent.trim().slice(0, 46),
    color: style.color,
    background: `rgb(${background.map(Math.round).join(", ")})`,
    size,
    weight,
    large,
    ratio: Math.round(ratio * 100) / 100,
  });
}
return findings;
"""

# What counts as a visible focus indicator.
#
# The ring does not have to be on the focused element. A file input is 1x1 and
# invisible by design - its own outline would be invisible too - so audit.css
# puts the ring on the label that wraps it, with `:has(input:focus-visible)`.
# That is correct, and a checker that only looked at the focused node itself
# would call it a failure. So the search walks up: somewhere in the chain from
# the focused control to the page, something must paint.
FOCUS_JS = r"""
const element = document.activeElement;
if (!element || element === document.body) return null;

const paints = (node) => {
  const style = getComputedStyle(node);
  const outlined = (parseFloat(style.outlineWidth) || 0) > 0 && style.outlineStyle !== "none";
  return outlined || (style.boxShadow !== "none" && style.boxShadow !== "");
};

let ringOn = null;
for (let node = element; node && node !== document.body; node = node.parentElement) {
  if (paints(node)) {
    ringOn = node === element ? "self" : node.tagName.toLowerCase() + "." + node.className;
    break;
  }
}

const style = getComputedStyle(element);
const box = element.getBoundingClientRect();
return {
  tag: element.tagName.toLowerCase(),
  type: element.getAttribute("type") || "",
  label: (element.getAttribute("aria-label") || element.textContent || element.name || "")
    .trim()
    .slice(0, 46),
  size: `${Math.round(box.width)}x${Math.round(box.height)}`,
  ringOn,
  outline: `${style.outlineWidth} ${style.outlineStyle}`,
  boxShadow: style.boxShadow,
};
"""


def reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status == 200
    except urllib.error.URLError, OSError:
        return False


def driver_for(width: int, height: int):
    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument(f"--window-size={width},{height}")
    # Deterministic rendering: a device pixel ratio other than 1 rounds font
    # sizes, and the large-text threshold is decided on a font size.
    options.add_argument("--force-device-scale-factor=1")
    driver = webdriver.Chrome(options=options)
    driver.set_window_size(width, height)
    return driver


def check_contrast(driver, page: str, width: str) -> list[str]:
    failures = []
    for row in driver.execute_script(CONTRAST_JS):
        need = AA_LARGE if row["large"] else AA_NORMAL
        if row["ratio"] < need:
            failures.append(
                f"{page}@{width}  {row['ratio']:.2f}:1 (needs {need})  "
                f"<{row['tag']} class={row['cls']!r}> {row['size']:.0f}px/{row['weight']}  "
                f"{row['color']} on {row['background']}  {row['text']!r}"
            )
    return failures


def check_focus_rings(driver, page: str, width: str, stops: int = 40) -> list[str]:
    """Tab through the page and read what each stop paints when focused.

    Consecutive stops on the same element are one control, not several. An
    `<input type="date">` has three internal tab stops - day, month, year -
    and `document.activeElement` stays the input for all three, while the
    host's `:focus-visible` only matches on the way in. Counting the inner
    stops as their own tab stops reported a missing ring on a control that
    plainly has one.
    """
    failures = []
    body = driver.find_element(By.TAG_NAME, "body")
    body.click()
    seen = 0
    previous = None
    for _ in range(stops):
        body.send_keys(Keys.TAB)
        state = driver.execute_script(FOCUS_JS)
        if state is None:
            break
        here = driver.execute_script("return document.activeElement")
        if here == previous:
            continue
        previous = here
        seen += 1
        if state["ringOn"] is None:
            failures.append(
                f"{page}@{width}  no focus indicator on "
                f"<{state['tag']} type={state['type']!r} {state['size']}> {state['label']!r} "
                f"(outline {state['outline']}, box-shadow {state['boxShadow']})"
            )
    print(f"  {page}@{width}: {seen} tab stops")
    return failures


def main() -> int:
    if not reachable(APP):
        print(
            f"the frontend is not answering at {APP}. Start it with:\n"
            "    cd frontend && npm run build && npx vite preview --port 5173"
        )
        return 2

    contrast: list[str] = []
    focus: list[str] = []
    for width, (w, h) in WIDTHS.items():
        driver = driver_for(w, h)
        try:
            for page, url in PAGES:
                driver.get(url)
                driver.implicitly_wait(2)
                # The landing page reveals sections on scroll; an unrevealed
                # section is opacity 0 and would be skipped, so bring them all in.
                driver.execute_script(
                    "document.querySelectorAll('.reveal').forEach(e =>"
                    " e.classList.add('is-shown'));"
                )
                contrast += check_contrast(driver, page, width)
                focus += check_focus_rings(driver, page, width)
        finally:
            driver.quit()

    print(f"\ncontrast failures: {len(contrast)}")
    for line in contrast:
        print("  " + line)
    print(f"focus-ring failures: {len(focus)}")
    for line in focus:
        print("  " + line)
    return 1 if contrast or focus else 0


if __name__ == "__main__":
    sys.exit(main())
