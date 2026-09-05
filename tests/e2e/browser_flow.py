"""Selenium 4 end-to-end test: fill the form, wait for the report, check a figure.

This is the only test that exercises the browser, the API and the model
together. Everything else in `tests/` stubs something.

The bill it submits is chosen so the expected figure is deterministic. Both
lines are settled without asking the model to judge anything:

* "Room Rent (Single A/C) 8,000 x 5 days" at a 3,00,000 sum insured resolves
  from the star_health table in clause II.1 - 5,000 a day, five days, 25,000.
* "Surgical Gloves" is item 1 on the IRDAI non-payable list, so it is nil.

Payable is therefore exactly Rs 25,000 every run. Only the bill parsing uses
the model, and that is cached after the first run.

Run it with the API and the frontend both up - see README.md in this folder.
Without them the test skips with the commands to start them, unless
BA_E2E_STRICT=1 is set, in which case it fails instead. Jenkins sets that.
"""

import os
import unittest
import urllib.error
import urllib.request

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.relative_locator import locate_with
from selenium.webdriver.support.ui import Select, WebDriverWait

API = os.environ.get("BA_E2E_API", "http://localhost:8000")
APP = os.environ.get("BA_E2E_APP", "http://localhost:5173")
# "/" is the landing page; the form moved here when the landing page landed.
AUDIT_APP = f"{APP}/audit"
STRICT = os.environ.get("BA_E2E_STRICT") == "1"
HEADLESS = os.environ.get("BA_E2E_HEADLESS", "1") == "1"

BILL = "Room Rent (Single A/C) 8,000 x 5 days   40000\nSurgical Gloves   1200"
EXPECTED_PAYABLE = "25,000"

# An audit is 30-60 seconds. The wait is generous because a cold model load is
# slower than a warm one, and a flaky timeout would be worse than a slow test.
REPORT_TIMEOUT = 300
PAGE_TIMEOUT = 20


def reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status == 200
    except urllib.error.URLError, OSError:
        return False


def why_not_running() -> str | None:
    """The exact command to start whichever half is missing."""
    if not reachable(f"{API}/health"):
        return (
            f"the API is not answering at {API}. Start it with:\n"
            "    uv run uvicorn api.main:app --port 8000"
        )
    if not reachable(APP):
        return (
            f"the frontend is not answering at {APP}. Start it with:\n"
            "    cd frontend && npm run dev"
        )
    return None


class BrowserTest(unittest.TestCase):
    """One headless Chrome per class, plus the waits every test here needs.

    A base class rather than a mixin on AuditFlowTest, because subclassing a
    TestCase that already holds tests would re-run them - and the audit flow
    takes minutes.
    """

    driver: webdriver.Chrome

    @classmethod
    def setUpClass(cls):
        problem = why_not_running()
        if problem:
            if STRICT:
                raise AssertionError(f"BA_E2E_STRICT is set and {problem}")
            raise unittest.SkipTest(problem)

        options = Options()
        if HEADLESS:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")
        options.add_argument("--no-sandbox")
        # Reduced motion, and not to make the suite faster.
        #
        # BA-208 put `scroll-behavior: smooth` on `html`. WebDriver clicks a
        # control by scrolling it into view, computing the click point, and
        # dispatching - in that order, without waiting. Against an animated
        # scroll the point is computed while the page is still moving, so the
        # click lands where the control is about to be rather than where it is:
        #
        #   element click intercepted at (123, 889)   [load-example]
        #   element click intercepted at (1226, 1115) [trace-toggle-0]
        #
        # Both y values sit below the 857px viewport this window actually gets.
        # Nothing is covering either control - `document.elementFromPoint` at
        # the load-example centre returns null before the scroll settles and
        # the button itself once it has, and there are no armed `.reveal`
        # elements on this page. The page is not at fault and a user cannot hit
        # this: a human waits for the scroll to finish.
        #
        # So the fix belongs here, and it is this flag rather than a scripted
        # click or a sleep. styles.css already defines the reduced-motion path
        # (`scroll-behavior: auto`), so this exercises a real code path the
        # stylesheet ships, and it makes scroll position deterministic instead
        # of racing an animation. A scripted click would have hidden any real
        # overlay that appeared later; this does not.
        options.add_argument("--force-prefers-reduced-motion")
        cls.driver = webdriver.Chrome(options=options)
        cls.driver.implicitly_wait(0)  # explicit waits only

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "driver", None):
            cls.driver.quit()

    def wait(self, timeout: int = PAGE_TIMEOUT) -> WebDriverWait:
        return WebDriverWait(self.driver, timeout)

    def set_date(self, testid: str, value: str) -> None:
        """Fill a React-controlled date input, in the ISO form the value uses.

        send_keys types into the browser's *display* format, which follows the
        machine's locale - dd/mm/yyyy here, mm/dd/yyyy elsewhere - so a typed
        date is a portability bug waiting to happen. Setting .value directly
        does not work either: React tracks the previous value on the node and
        ignores an assignment it did not make. Going through the prototype
        setter and dispatching input is what React itself listens for.
        """
        element = self.driver.find_element(By.CSS_SELECTOR, f"[data-testid='{testid}']")
        self.driver.execute_script(
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

    def select_option(self, testid: str, value: str) -> None:
        """Choose a dropdown value, waiting for the option to exist first.

        Both dropdowns are filled from the API - the policies from /policies,
        the sums insured from the chosen policy's room rent table - so the
        select element is on the page before its options are. Selecting too
        early raises NoSuchElementException, which only shows up when the
        machine is loaded and reads like a missing option rather than a race.
        """
        self.wait().until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, f"[data-testid='{testid}'] option[value='{value}']")
            )
        )
        Select(
            self.driver.find_element(By.CSS_SELECTOR, f"[data-testid='{testid}']")
        ).select_by_value(value)


class AuditFlowTest(BrowserTest):
    """The whole path a patient takes: paste a bill, get a cited report."""

    def test_a_pasted_bill_produces_a_cited_report(self):
        driver = self.driver
        driver.get(AUDIT_APP)

        self.wait().until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='bill-form']"))
        )

        # The bill area is one surface now - paste and drop are the same box,
        # not two modes behind a link - so there is nothing to switch first.
        textarea = self.wait().until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='bill-text']"))
        )
        textarea.send_keys(BILL)

        # The reading under the document is the page saying it understood the
        # paste. It is the only feedback before a minute of waiting, so it is
        # worth asserting rather than assuming.
        count = self.wait().until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='bill-count']"))
        )
        self.assertIn("items", count.text)

        self.select_option("policy", "star_health")
        self.select_option("sum-insured", "300000")
        # Required since the form started saying what it is waiting for.
        self.set_date("policy-start", "2022-06-15")

        # Selenium 4 relative locators, on the thing this layout actually
        # promises: at 1440 the policy column sits beside the bill, not under
        # it. That is the whole point of the two-column screen, and a silent
        # collapse back to one column would otherwise pass every other check.
        bill_doc = driver.find_element(By.CSS_SELECTOR, ".bill-doc")
        policy = driver.find_element(
            locate_with(By.CSS_SELECTOR, ".policy-panel").to_right_of(bill_doc)
        )
        self.assertTrue(policy.is_displayed())

        # The submit still has to come after the last field. That is document
        # order, and it is asserted as document order: the button is sticky, so
        # geometrically it can sit above the field it follows, and `.below()`
        # reports the layout rather than the form's sequence.
        room_limit = driver.find_element(By.CSS_SELECTOR, "[data-testid='room-limit']")
        submit = driver.find_element(By.CSS_SELECTOR, "[data-testid='submit']")
        follows = driver.execute_script(
            "return !!(arguments[0].compareDocumentPosition(arguments[1]) "
            "& Node.DOCUMENT_POSITION_FOLLOWING);",
            room_limit,
            submit,
        )
        self.assertTrue(follows, "submit must come after the room-limit field")
        submit.click()

        # While it runs, the progress line must say something true rather than
        # spin. This is the state a user stares at for a minute.
        #
        # It is asserted only if it is still on screen, and it is found and read
        # in one evaluation. An audit whose model calls are all cached finishes
        # in about 1.5 seconds - measured, on this very bill - so the report can
        # replace the running state before the driver gets to it. Waiting for
        # the caption then made the test depend on whether `data/llm_cache/`
        # happened to be warm, which is a property of the machine rather than of
        # the page; locating it and asking for its text in two round trips threw
        # StaleElementReference instead, which reads like a broken test rather
        # than a fast one.
        observed = self.wait().until(
            lambda d: d.execute_script(
                "const caption = document.querySelector(\"[data-testid='progress-caption']\");"
                "if (caption) return 'caption:' + caption.textContent.trim();"
                "return document.querySelector(\"[data-testid='report']\") ? 'finished' : null;"
            )
        )
        if observed.startswith("caption:"):
            self.assertTrue(
                observed.removeprefix("caption:").strip(),
                "the running state must say what it is doing",
            )

        self.wait().until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='submitted-summary']"))
        )
        self.wait(REPORT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='report']"))
        )

        payable = driver.find_element(By.CSS_SELECTOR, "[data-testid='total-allowed']")
        self.assertIn(
            EXPECTED_PAYABLE,
            payable.text,
            "the room line resolves from the star_health table at 5,000 a day for five days, "
            "and the gloves are on the IRDAI non-payable list, so payable is exactly 25,000",
        )

        # The deducted figure is the largest number on the screen by design.
        deducted = driver.find_element(By.CSS_SELECTOR, "[data-testid='total-deducted']")
        charged = driver.find_element(By.CSS_SELECTOR, "[data-testid='total-charged']")
        self.assertGreater(
            deducted.size["height"],
            charged.size["height"],
            "the deducted figure is the emotional centre of the report and is set larger",
        )

        # Relative locator again: the assumptions panel sits above the table,
        # so it cannot have been pushed below the fold or hidden behind a toggle.
        table = driver.find_element(By.CSS_SELECTOR, "table.lines")
        assumptions = driver.find_element(
            locate_with(By.CSS_SELECTOR, "[data-testid='assumptions']").above(table)
        )
        self.assertIn("differential billing", assumptions.text)

        # Every deduction must cite a clause. That is the product.
        first_clause = driver.find_element(By.CSS_SELECTOR, "[data-testid='line-0'] .chip")
        self.assertTrue(first_clause.text.strip())

        # Expand the row and check the trace really shows how it was decided.
        driver.find_element(By.CSS_SELECTOR, "[data-testid='trace-toggle-0']").click()
        trace = self.wait().until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='trace-0']"))
        )
        self.assertTrue(trace.text.strip())

    def test_the_example_button_fills_the_whole_form(self):
        """One click has to reach a submittable form, or it is not an example.

        A first-time visitor has no bill to paste and no idea what a valid one
        looks like. This is the shortcut, so it has to leave nothing else to
        fill in - which is exactly what the blocked-submit note now reveals.
        """
        driver = self.driver
        driver.get(AUDIT_APP)
        self.wait().until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='bill-form']"))
        )

        blocked = driver.find_element(By.CSS_SELECTOR, "[data-testid='submit-blocked']")
        self.assertIn("Add", blocked.text)

        driver.find_element(By.CSS_SELECTOR, "[data-testid='load-example']").click()

        text = self.wait().until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='bill-text']"))
        )
        self.assertIn("Room Rent", text.get_attribute("value"))
        self.assertEqual(
            driver.find_element(By.CSS_SELECTOR, "[data-testid='policy-start']").get_attribute(
                "value"
            ),
            "2022-06-15",
        )

        # Nothing outstanding, so the note is gone and the button is live.
        self.wait().until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='submit-blocked']"))
        )
        self.assertTrue(driver.find_element(By.CSS_SELECTOR, "[data-testid='submit']").is_enabled())

    def test_the_api_docs_open_in_a_second_tab(self):
        """Selenium 4's window API, used for something worth checking.

        The docs page is what a marker or a new developer opens first, and it
        has to be reachable from the same browser session the app runs in - a
        CORS or port mistake shows up here.
        """
        driver = self.driver
        driver.get(AUDIT_APP)
        original = driver.current_window_handle

        driver.switch_to.new_window("tab")
        driver.get(f"{API}/docs")
        self.wait().until(EC.title_contains("Bill Auditor"))
        self.assertIn("Swagger", driver.page_source)

        driver.close()
        driver.switch_to.window(original)
        self.assertEqual(driver.current_window_handle, original)


if __name__ == "__main__":
    unittest.main()


class LandingPageTest(BrowserTest):
    """The front door, and the one link off it that matters."""

    def test_the_landing_page_leads_to_the_audit_form(self):
        driver = self.driver
        driver.get(APP)

        heading = self.wait().until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1")))
        self.assertIn("line by line", heading.text)

        # The worked example carries real figures, not placeholders.
        body = driver.find_element(By.TAG_NAME, "body").text
        self.assertIn("25,000", body)
        self.assertIn("II.1", body)

        # Selenium 4 relative locators: the primary action sits below the lead
        # paragraph, which also asserts the hero reads before it is pressed.
        lead = driver.find_element(By.CSS_SELECTOR, ".landing-lead")
        cta = driver.find_element(locate_with(By.CSS_SELECTOR, "a.landing-cta").below(lead))
        cta.click()

        self.wait().until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='bill-form']"))
        )
        self.assertTrue(driver.current_url.rstrip("/").endswith("/audit"))
