"""
Инструмент разметки: видимый браузер, ввод селекторов для областей текста,
заголовка, перехода на следующую страницу и списка ссылок на рассказы.
Аннотация сохраняется в папку по имени сайта (loaded/<домен>/annotations.yaml).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from selenium.common.exceptions import TimeoutException

from .annotations import SiteAnnotations, find_all_by_selector, find_by_selector
from .browser_utils import create_browser
from .config import get_site_folder_name, load_config, SITES_DIR


def _highlight(driver, selector: str, is_xpath: bool) -> int:
    """Подсветить элементы по селектору, вернуть количество найденных."""
    from selenium.webdriver.common.by import By
    try:
        by = By.XPATH if is_xpath else By.CSS_SELECTOR
        elements = driver.find_elements(by, selector)
        for el in elements:
            driver.execute_script(
                "arguments[0].setAttribute('style', arguments[1]);",
                el,
                "outline: 3px solid red; background: rgba(255,0,0,0.2);",
            )
        return len(elements)
    except Exception:
        return 0


def _unhighlight(driver) -> None:
    try:
        driver.execute_script("""
            document.querySelectorAll('[style*="outline"]').forEach(function(el) {
                el.removeAttribute('style');
            });
        """)
    except Exception:
        pass


def _is_xpath(s: str) -> bool:
    return s.strip().startswith("/") or s.strip().startswith("(")


def run_labeler(
    url: str,
    site_folder: str | None = None,
    sites_dir: str | Path = SITES_DIR,
    config_path: str | Path | None = None,
) -> None:
    config = load_config(config_path)
    sites_dir = Path(sites_dir)
    site_name = site_folder or get_site_folder_name(url)
    site_path = sites_dir / site_name
    site_path.mkdir(parents=True, exist_ok=True)
    annotations_path = site_path / "annotations.yaml"

    driver = create_browser(
        headless=False,
        user_agent=config.get("user_agent"),
        window_width=config.get("window_width", 1920),
        window_height=config.get("window_height", 1080),
        page_load_timeout_sec=config.get("page_load_timeout_sec", 30),
        implicit_wait_sec=config.get("implicit_wait_sec", 5),
    )

    path = Path(annotations_path)
    ann = SiteAnnotations.load(path)
    if not ann.base_url:
        ann.base_url = url.rstrip("/")

    try:
        try:
            driver.get(url)
        except TimeoutException as e:
            print(f"\nТаймаут загрузки страницы: {e}")
            print("Введите селекторы вручную (подсветка может не сработать).\n")
        except Exception as e:
            print(f"\nНе удалось загрузить страницу: {e}")
            print("Введите селекторы вручную.\n")

        print("--- Разметка сайта (браузер открыт) ---")
        print("Вводите CSS селектор или XPath (начинается с / или (). Пустая строка — пропуск.\n")

        prompts = [
            ("story_text_selector", "Область текста рассказа (контейнер с текстом):"),
            ("story_title_selector", "Заголовок рассказа:"),
            ("next_page_selector", "Ссылка/кнопка «Следующая страница» (если есть):"),
            ("story_list_container_selector", "Контейнер списка ссылок на рассказы (одна страница списка):"),
            ("story_link_selector", "Селектор ссылки на рассказ внутри контейнера (по умолчанию a):"),
            ("story_list_next_page_selector", "Кнопка/ссылка «Следующая страница списка» (пагинация):"),
        ]

        for key, label in prompts:
            current = getattr(ann, key, "") or ("a" if key == "story_link_selector" else "")
            if current:
                print(f"  Текущее: {current}")
            val = input(f"{label}\n  > ").strip()
            if val:
                setattr(ann, key, val)
                n = _highlight(driver, val, _is_xpath(val))
                print(f"  Найдено элементов: {n}. Проверьте в браузере.")
                input("  Enter чтобы снять подсветку и продолжить...")
                _unhighlight(driver)

        ann.save(path)
        print(f"\nРазметка сохранена в {path}")
        print(f"Папка сайта: {site_path.absolute()}")
    finally:
        driver.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Инструмент разметки сайта с рассказами (видимый браузер). Создаёт папку loaded/<домен>/ и сохраняет туда annotations.yaml.")
    parser.add_argument("url", nargs="?", default="", help="URL страницы для разметки")
    parser.add_argument("--site", "-s", default=None, help="Имя папки сайта (по умолчанию — домен из URL)")
    parser.add_argument("--sites-dir", default=SITES_DIR, help=f"Каталог с папками сайтов (по умолчанию {SITES_DIR})")
    parser.add_argument("--config", "-c", default=None, help="Конфиг YAML (опционально)")
    args = parser.parse_args()

    url = args.url
    if not url:
        print("URL не передан. Введите URL страницы для разметки (или запустите: ./scripts/run_labeler.sh <URL>)")
        try:
            url = input("URL: ").strip()
        except EOFError:
            url = ""
    if not url:
        print("URL не указан. Выход.")
        return
    if not url.startswith("http"):
        url = "https://" + url

    run_labeler(
        url=url,
        site_folder=args.site,
        sites_dir=args.sites_dir,
        config_path=args.config,
    )


if __name__ == "__main__":
    main()
