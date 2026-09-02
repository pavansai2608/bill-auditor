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


class AuditFlowTest(unittest.TestCase):
    """The whole path a patient takes: paste a bill, get a cited report."""

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
        cls.driver = webdriver.Chrome(options=options)
        cls.driver.implicitly_wait(0)  # explicit waits only

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "driver", None):
            cls.driver.quit()

    def wait(self, timeout: int = PAGE_TIMEOUT) -> WebDriverWait:
        return WebDriverWait(self.driver, timeout)

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

    def test_a_pasted_bill_produces_a_cited_report(self):
        driver = self.driver
        driver.get(APP)

        self.wait().until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='bill-form']"))
        )

        # The form opens on the upload dropzone; switch it to the textarea.
        driver.find_element(By.CSS_SELECTOR, "[data-testid='toggle-input-mode']").click()
        textarea = self.wait().until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='bill-text']"))
        )
        textarea.send_keys(BILL)

        self.select_option("policy", "star_health")
        self.select_option("sum-insured", "300000")

        # Selenium 4 relative locators. The submit button is the one below the
        # optional room-limit field - which also asserts the form's order, since
        # that field has to come before the button a user presses.
        room_limit = driver.find_element(By.CSS_SELECTOR, "[data-testid='room-limit']")
        submit = driver.find_element(locate_with(By.TAG_NAME, "button").below(room_limit))
        self.assertEqual(submit.get_attribute("data-testid"), "submit")
        submit.click()

        # While it runs, the progress line must say something true rather than
        # spin. This is the state a user stares at for a minute.
        running = self.wait().until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-caption']"))
        )
        self.assertTrue(running.text.strip(), "the running state must say what it is doing")

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

    def test_the_api_docs_open_in_a_second_tab(self):
        """Selenium 4's window API, used for something worth checking.

        The docs page is what a marker or a new developer opens first, and it
        has to be reachable from the same browser session the app runs in - a
        CORS or port mistake shows up here.
        """
        driver = self.driver
        driver.get(APP)
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
