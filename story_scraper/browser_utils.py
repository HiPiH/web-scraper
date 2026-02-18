"""Browser creation and anti-detection helpers (random delays, user-like behavior)."""
from __future__ import annotations

import random
import time
from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import WebDriver

try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    ChromeDriverManager = None


def random_delay(min_sec: float, max_sec: float) -> None:
    """Sleep for a random duration between min and max seconds."""
    time.sleep(random.uniform(min_sec, max_sec))


def create_browser(
    headless: bool = True,
    user_agent: str | None = None,
    window_width: int = 1920,
    window_height: int = 1080,
    page_load_timeout_sec: int = 30,
    implicit_wait_sec: int = 5,
) -> WebDriver:
    """Create Chrome WebDriver with options that reduce bot detection."""
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    if user_agent:
        opts.add_argument(f"--user-agent={user_agent}")
    opts.add_argument("--window-size={},{}".format(window_width, window_height))
    opts.add_argument("--disable-gpu")
    opts.add_argument("--lang=ru-RU,ru")

    if ChromeDriverManager is not None:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
    else:
        driver = webdriver.Chrome(options=opts)

    driver.set_page_load_timeout(page_load_timeout_sec)
    driver.implicitly_wait(implicit_wait_sec)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    })
    return driver


def human_like_delay_before_action(config: dict[str, Any]) -> None:
    """Short random delay before click/scroll (like a user)."""
    random_delay(
        config.get("delay_before_action_min_sec", 0.5),
        config.get("delay_before_action_max_sec", 2.0),
    )


def human_like_delay_between_pages(config: dict[str, Any]) -> None:
    """Delay between loading pages (avoid rate limit)."""
    random_delay(
        config.get("delay_between_pages_min_sec", 1.0),
        config.get("delay_between_pages_max_sec", 4.0),
    )
