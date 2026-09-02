"""Capture both screens at both widths, for the README.

Not a test - a small driver script. Run it with the API and the frontend up:

    uv run python tests/e2e/capture_screenshots.py

It writes six PNGs into frontend/design/screenshots/ - the landing page,
the form and the report, each at 1440 and 390 - and copies the 1440 form shot
to docs/audit-1440.png, which is the one the README embeds. The report
screenshots run a real audit, so the first run takes a minute and later ones
are quick because the model calls are cached.
"""

import shutil
import sys
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.e2e.test_flow import APP, AUDIT_APP, BILL, why_not_running

OUT = ROOT / "frontend" / "design" / "screenshots"
WIDTHS = {"1440": (1440, 1000), "390": (390, 844)}

# The README embeds one of these six. It is copied rather than linked into
# frontend/design/ so that moving the design folder cannot silently blank the
# image at the top of the README.
README_SHOT = ("screen-1-audit-a-bill-1440", ROOT / "docs" / "audit-1440.png")


def set_date(driver, testid: str, value: str) -> None:
    """The same React-aware date fill the E2E test uses; see test_flow.py."""
    element = driver.find_element(By.CSS_SELECTOR, f"[data-testid='{testid}']")
    driver.execute_script(
        """
        const [el, value] = arguments;
        const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value').set;
        setter.call(el, value);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        """,
        element,
        value,
    )


def full_height(driver) -> int:
    return driver.execute_script(
        "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);"
    )


def settle_reveals(driver, timeout: int = 15) -> None:
    """Scroll the page like a reader, so every reveal-on-scroll section arrives.

    Two things make this necessary. The sections start hidden and are shown by
    an IntersectionObserver, so a screenshot taken before the callbacks run
    catches a mostly blank page. And the observer deliberately ignores the
    bottom 12% of the viewport, so simply growing the window to the full page
    height leaves whatever sits in that band still hidden - which is exactly
    what the closing section did.

    So the window is grown taller than the page before waiting - every section
    is then inside the viewport at once, clear of that band. Scrolling in steps
    does not work here: a loop of scrollTo calls runs in one task, so the
    observer only ever sees the final position.
    """
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script(
            "return document.querySelectorAll('.reveal.is-armed:not(.is-shown)').length === 0;"
        )
    )
    driver.execute_script("window.scrollTo(0, 0);")
    # The transition is 520ms plus up to 210ms of stagger. This is the one
    # place a fixed wait is honest: there is no event for "the paint after the
    # transition finished", and it is awaited in the page rather than slept in
    # the test process.
    driver.execute_script(
        "return new Promise(r => setTimeout(() => requestAnimationFrame(r), 800));"
    )


def shoot(driver, name: str, width: int) -> None:
    """Grow the window to the whole page, so nothing is cut off."""
    # Deliberately overshoot first: the reveal observer ignores the bottom of
    # the viewport, so the page has to be comfortably shorter than the window
    # for every section to count as seen.
    driver.set_window_size(width, int(full_height(driver) * 1.35) + 400)
    settle_reveals(driver)
    # Measure at a normal height, never at the oversized one: scrollHeight is
    # the larger of the content and the viewport, so measuring inside a very
    # tall window returns the window and the shot ends in blank page.
    driver.set_window_size(width, 900)
    driver.set_window_size(width, full_height(driver) + 120)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    driver.save_screenshot(str(path))
    print(f"wrote {path.relative_to(ROOT)}")


def run() -> int:
    problem = why_not_running()
    if problem:
        print(problem)
        return 1

    for label, (width, height) in WIDTHS.items():
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument(f"--window-size={width},{height}")
        options.add_argument("--force-device-scale-factor=2")
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 300)
        try:
            driver.get(APP)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".landing-hero")))
            shoot(driver, f"screen-0-landing-{label}", width)

            driver.get(AUDIT_APP)
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='bill-form']"))
            )
            shoot(driver, f"screen-1-audit-a-bill-{label}", width)

            wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='bill-text']"))
            ).send_keys(BILL)
            Select(driver.find_element(By.CSS_SELECTOR, "[data-testid='policy']")).select_by_value(
                "star_health"
            )
            Select(
                driver.find_element(By.CSS_SELECTOR, "[data-testid='sum-insured']")
            ).select_by_value("300000")
            set_date(driver, "policy-start", "2022-06-15")
            driver.find_element(By.CSS_SELECTOR, "[data-testid='submit']").click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='report']")))
            driver.find_element(By.CSS_SELECTOR, "[data-testid='trace-toggle-0']").click()
            wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='trace-0']"))
            )
            shoot(driver, f"screen-2-audit-report-{label}", width)
        finally:
            driver.quit()

    name, destination = README_SHOT
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT / f"{name}.png", destination)
    print(f"wrote {destination.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
