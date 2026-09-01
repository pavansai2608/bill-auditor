"""Capture both screens at both widths, for the README.

Not a test - a small driver script. Run it with the API and the frontend up:

    uv run python tests/e2e/capture_screenshots.py

It writes four PNGs into frontend/design/screenshots/. The report screenshots
run a real audit, so the first run takes a minute and later ones are quick
because the model calls are cached.
"""

import sys
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.e2e.test_flow import APP, BILL, why_not_running

OUT = ROOT / "frontend" / "design" / "screenshots"
WIDTHS = {"1440": (1440, 1000), "390": (390, 844)}


def full_height(driver) -> int:
    return driver.execute_script(
        "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);"
    )


def shoot(driver, name: str, width: int) -> None:
    """Grow the window to the whole page, so nothing is cut off."""
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
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='bill-form']"))
            )
            shoot(driver, f"screen-1-audit-a-bill-{label}", width)

            driver.find_element(By.CSS_SELECTOR, "[data-testid='toggle-input-mode']").click()
            wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='bill-text']"))
            ).send_keys(BILL)
            Select(driver.find_element(By.CSS_SELECTOR, "[data-testid='policy']")).select_by_value(
                "star_health"
            )
            Select(
                driver.find_element(By.CSS_SELECTOR, "[data-testid='sum-insured']")
            ).select_by_value("300000")
            driver.find_element(By.CSS_SELECTOR, "[data-testid='submit']").click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='report']")))
            driver.find_element(By.CSS_SELECTOR, "[data-testid='trace-toggle-0']").click()
            wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='trace-0']"))
            )
            shoot(driver, f"screen-2-audit-report-{label}", width)
        finally:
            driver.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
