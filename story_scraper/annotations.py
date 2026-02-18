"""Schema for site annotations (selectors from the labeler)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class SiteAnnotations:
    """Saved selectors for one story site (from labeler)."""
    base_url: str
    # Контейнер основного текста рассказа (CSS selector или XPath)
    story_text_selector: str = ""
    # Заголовок рассказа
    story_title_selector: str = ""
    # Ссылка/кнопка «следующая страница» (может быть пустой)
    next_page_selector: str = ""
    # Контейнер списка ссылок на рассказы (одна страница списка)
    story_list_container_selector: str = ""
    # Внутри контейнера: селектор ссылки на рассказ (относительно контейнера)
    story_link_selector: str = "a"
    # Селектор кнопки/ссылки «следующая страница списка» (пагинация списка)
    story_list_next_page_selector: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "story_text_selector": self.story_text_selector,
            "story_title_selector": self.story_title_selector,
            "next_page_selector": self.next_page_selector,
            "story_list_container_selector": self.story_list_container_selector,
            "story_link_selector": self.story_link_selector,
            "story_list_next_page_selector": self.story_list_next_page_selector,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SiteAnnotations":
        return cls(
            base_url=data.get("base_url", ""),
            story_text_selector=data.get("story_text_selector", ""),
            story_title_selector=data.get("story_title_selector", ""),
            next_page_selector=data.get("next_page_selector", ""),
            story_list_container_selector=data.get("story_list_container_selector", ""),
            story_link_selector=data.get("story_link_selector", "a"),
            story_list_next_page_selector=data.get("story_list_next_page_selector", ""),
        )

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if yaml is None:
            raise RuntimeError("PyYAML required. pip install pyyaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.to_dict(), f, allow_unicode=True, default_flow_style=False)

    @classmethod
    def load(cls, path: str | Path) -> "SiteAnnotations":
        path = Path(path)
        if not path.is_file():
            return cls(base_url="")
        if yaml is None:
            raise RuntimeError("PyYAML required. pip install pyyaml")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.from_dict(data)


def _is_xpath(s: str) -> bool:
    return s.strip().startswith("/") or s.strip().startswith("(")


def find_by_selector(driver, selector: str, root=None):
    """Find one element by CSS or XPath. root = parent WebElement or None for driver."""
    from selenium.webdriver.common.by import By
    parent = root or driver
    if not selector:
        return None
    by = By.XPATH if _is_xpath(selector) else By.CSS_SELECTOR
    return parent.find_element(by, selector)


def find_all_by_selector(driver, selector: str, root=None):
    """Find all elements by CSS or XPath."""
    from selenium.webdriver.common.by import By
    parent = root or driver
    if not selector:
        return []
    by = By.XPATH if _is_xpath(selector) else By.CSS_SELECTOR
    return parent.find_elements(by, selector)
