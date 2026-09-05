"""Load the GitHub Pages build in a real browser and check what it actually does.

WHY THIS IS NOT `browser_flow.py`
---------------------------------
`browser_flow.py` drives the whole system - a bill goes in, a model judges it,
a figure comes out. This drives the opposite case: the build that has no
backend at all, served the way GitHub Pages serves it.

Everything that breaks on Pages breaks *only* on Pages. An asset written
against "/" resolves perfectly against a dev server at the domain root and
404s in production. A router with no basename matches every route locally and
none behind a subpath. A deep link works on any server with a rewrite rule and
dies on Pages, which has none. None of it can be caught by reading the source,
and none of it can be caught by `npm run preview`.

So this serves `frontend/dist` the way Pages does - under /bill-auditor/, with
an unknown path answered by 404.html *and a 404 status* - and then checks what
a browser makes of it. The assertions are made against rendered output and
against the requests the page really issued, never against the source that was
supposed to produce them.

    uv run python tests/e2e/pages_static_check.py            # builds first
    uv run python tests/e2e/pages_static_check.py --no-build # reuse dist/

Named `pages_static_check.py` rather than `test_*.py` for the same reason
`browser_flow.py` is: PyBuilder matches unit tests on filename and cannot
exclude a directory, so a `test_` prefix here would put a browser in the unit
test stage.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"
SERVER = Path(__file__).with_name("pages_server.py")
PREFIX = "/bill-auditor/"

# The figures in frontend/src/data/exampleReport.json, which is exported from an
# eval checkpoint. Repeated here so a report that silently becomes a different
# report fails rather than passing quietly - tests/test_example_report.py holds
# the file itself to the clause index.
EXPECTED_CHARGED = "2,36,000"
EXPECTED_CLAUSES = ("II.1", "II.8", "II.20", "IRDAI-List-I")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Checks:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def __call__(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append((name, bool(ok), detail))
        print(("PASS " if ok else "FAIL ") + name + (f" :: {detail}" if detail else ""))

    @property
    def failed(self) -> list[tuple[str, bool, str]]:
        return [r for r in self.rows if not r[1]]


def wait_for_port(url: str, seconds: int = 10) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except urllib.error.HTTPError:
            return  # answering at all is enough; 404 is a valid answer here
        except OSError:
            time.sleep(0.2)
    raise SystemExit(f"nothing answered {url} within {seconds}s")


def run(headless: bool, base: str, check: Checks) -> None:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1200")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)

    def console_errors(ignore_document_404: str | None = None) -> list[dict]:
        """Severe console messages. get_log drains, so call this once per page.

        Pages answers a deep link with 404.html *and* a 404 status, and Chrome
        logs that against the document. That entry is the fallback working, so
        it is excluded by name rather than by lowering the bar for the rest.
        """
        entries = [e for e in driver.get_log("browser") if e["level"] == "SEVERE"]
        if ignore_document_404:
            entries = [
                e
                for e in entries
                if not (e["message"].startswith(ignore_document_404) and "404" in e["message"])
            ]
        return entries

    def requests_made() -> list[str]:
        return driver.execute_script(
            "return performance.getEntriesByType('resource').map(e => e.name)"
        )

    def settled(selector: str) -> None:
        """Wait for an entrance animation to finish.

        The report arrives with `animation-fill-mode: both`, so its first
        frames are at opacity 0 - and Selenium reads an opacity-0 element as
        neither shown nor having any text. Without this the figures come back
        empty and the failure looks like missing data rather than timing.
        """
        wait.until(
            lambda drv: drv.execute_script(
                "return [...document.querySelectorAll(arguments[0])]"
                ".every(n => getComputedStyle(n).opacity === '1');",
                selector,
            )
        )

    def click(selector: str):
        """Scroll to an element and click it.

        behavior:'instant' on purpose - styles.css sets scroll-behavior:smooth,
        so the default animates and the click lands where the element was.
        """
        element = driver.find_element(By.CSS_SELECTOR, selector)
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', behavior:'instant'});", element
        )
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
        element.click()
        return element

    try:
        # ------------------------------------------------------------ landing
        driver.get(base + "/")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#root > *")))
        text = driver.find_element(By.TAG_NAME, "body").text
        check("landing renders", len(text) > 400, f"{len(text)} chars of text")

        local = [r for r in requests_made() if "127.0.0.1" in r]
        check(
            "every local asset resolves under /bill-auditor/",
            len(local) >= 2 and all(PREFIX in r for r in local),
            ", ".join(r.split("//", 1)[-1].split("/", 1)[-1] for r in local),
        )
        empty = driver.execute_script(
            """
            return performance.getEntriesByType('resource')
              .filter(e => e.transferSize === 0 && e.decodedBodySize === 0)
              .map(e => e.name);
            """
        )
        check("no asset came back empty", not empty, str(empty))
        errors = console_errors()
        check(
            "no severe console errors on the landing page",
            not errors,
            json.dumps([e["message"][:300] for e in errors]),
        )

        # ---------------------------------------------------------- deep link
        # Loaded directly rather than navigated to. This is the hard refresh,
        # and the server answers it with 404.html under a 404 status.
        driver.get(base + "/audit")
        form = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='bill-form']"))
        )
        check("a hard refresh on /bill-auditor/audit renders the form", form.is_displayed())
        check(
            "and stays on that URL",
            driver.current_url.endswith("/bill-auditor/audit"),
            driver.current_url,
        )
        errors = console_errors(ignore_document_404=base + "/audit")
        check(
            "no severe console errors on /audit",
            not errors,
            json.dumps([e["message"][:300] for e in errors]),
        )

        # ----------------------------------------------------- the form's state
        note = driver.find_element(By.CSS_SELECTOR, "[data-testid='static-note']")
        check("the form explains why it cannot run", note.is_displayed())
        check(
            "the explanation says where to run it instead",
            "uvicorn" in note.text and "npm run dev" in note.text,
        )
        submit = driver.find_element(By.CSS_SELECTOR, "[data-testid='submit']")
        check("submit is disabled", not submit.is_enabled())

        insurers = driver.find_elements(By.CSS_SELECTOR, "#policy option")
        check(
            "the insurer dropdown still has its three policies",
            len(insurers) == 3,
            ", ".join(o.text for o in insurers),
        )
        check(
            "uploading a policy is not offered",
            all("upload" not in o.text.lower() for o in insurers),
        )

        before = len(requests_made())
        driver.execute_script(
            "document.querySelector(\"[data-testid='bill-form']\").requestSubmit();"
        )
        time.sleep(1)
        posted = [r for r in requests_made()[before:] if "127.0.0.1" in r]
        check("submitting anyway issues no request", not posted, str(posted))

        # ----------------------------------------------------- example report
        click("[data-testid='show-example']")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='report']")))
        settled("[data-testid='report']")
        check(
            "the example report renders",
            driver.find_element(By.CSS_SELECTOR, "[data-testid='report']").is_displayed(),
        )

        charged = driver.find_element(By.CSS_SELECTOR, "[data-testid='total-charged']").text
        allowed = driver.find_element(By.CSS_SELECTOR, "[data-testid='total-allowed']").text
        flagged = driver.find_element(By.CSS_SELECTOR, "[data-testid='flagged-count']").text
        check(
            "it carries the recorded figures",
            EXPECTED_CHARGED in charged.replace(" ", ""),
            f"charged={charged} payable={allowed} flagged={flagged}",
        )

        settled("table.lines tbody tr")
        rows = [e.text for e in driver.find_elements(By.CSS_SELECTOR, "table.lines tbody tr")]
        cited = [c for c in EXPECTED_CLAUSES if any(c in row for row in rows)]
        check(
            "the clause citations are the recorded ones",
            len(cited) == len(EXPECTED_CLAUSES),
            ", ".join(cited),
        )
        check(
            "the report says it is a recorded run, not a live one",
            driver.find_element(By.CSS_SELECTOR, "[data-testid='recorded-note']").is_displayed(),
        )
        check(
            "compare, which needs the backend, is not offered",
            not driver.find_elements(By.CSS_SELECTOR, "[data-testid='compare']"),
        )

        # ---------------------------------------------------- nothing private
        everything = requests_made()
        private = [
            r
            for r in everything
            if any(h in r for h in ("localhost", "0.0.0.0", "192.168.", ":8000"))
        ]
        check("no request to localhost or any private host", not private, str(private))
        hosts = sorted({r.split("/")[2] for r in everything if "//" in r})
        print(f"    hosts contacted: {hosts}")

        # --------------------------------------------------------- navigation
        click(f"a[href='{PREFIX}']")
        wait.until(lambda d: d.current_url.rstrip("/").endswith("/bill-auditor"))
        check("navigation back to the landing page works", True, driver.current_url)
    finally:
        driver.quit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true", help="reuse frontend/dist as it is")
    parser.add_argument("--headed", action="store_true", help="show the browser")
    args = parser.parse_args()

    if not args.no_build:
        print("building with --mode pages")
        subprocess.run(["npm", "ci"], cwd=FRONTEND, check=True)
        subprocess.run(["npm", "run", "build:pages"], cwd=FRONTEND, check=True)
    if not (DIST / "index.html").is_file():
        raise SystemExit(f"{DIST} holds no build; run without --no-build")

    port = free_port()
    base = f"http://127.0.0.1:{port}{PREFIX.rstrip('/')}"
    server = subprocess.Popen(
        [sys.executable, str(SERVER), str(DIST), PREFIX, str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_port(f"{base}/")
        check = Checks()
        run(not args.headed, base, check)
    finally:
        server.terminate()
        server.wait(timeout=5)

    print()
    print(f"{len(check.rows) - len(check.failed)}/{len(check.rows)} checks passed")
    return 1 if check.failed else 0


if __name__ == "__main__":
    sys.exit(main())
