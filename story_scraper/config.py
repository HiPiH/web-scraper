"""Load and validate scraper/labeler config (YAML + env)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Папка в корне проекта, в которой лежат папки сайтов (имя сайта = папка, внутри — annotations.yaml и скачанные данные)
SITES_DIR = "loaded"


def get_site_folder_name(url: str) -> str:
    """Имя папки сайта по URL (домен)."""
    name = urlparse(url).netloc.strip()
    return name or "site"

try:
    import yaml
except ImportError:
    yaml = None


DEFAULT_CONFIG = {
    "headless": True,
    "page_load_timeout_sec": 30,
    "implicit_wait_sec": 5,
    "delay_before_action_min_sec": 0.5,
    "delay_before_action_max_sec": 2.0,
    "delay_between_pages_min_sec": 1.0,
    "delay_between_pages_max_sec": 4.0,
    "window_width": 1920,
    "window_height": 1080,
    "user_agent": None,
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load config from YAML file and merge with defaults."""
    cfg = dict(DEFAULT_CONFIG)
    if path and os.path.isfile(path):
        if yaml is None:
            raise RuntimeError("PyYAML is required for config file. pip install pyyaml")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        cfg.update(data)
    if cfg.get("user_agent") is None:
        import random
        cfg["user_agent"] = random.choice(USER_AGENTS)
    return cfg
