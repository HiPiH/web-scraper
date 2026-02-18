"""
Скрапер контента сайта с рассказами.
Использует разметку (annotations), случайные задержки и настройку headless.
Сначала скачивает рассказы с текущей страницы списка, затем переходит к следующей.
Прогресс сохраняется в YAML для возобновления после сбоя.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

try:
    import yaml
except ImportError:
    yaml = None

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By

from .annotations import SiteAnnotations, find_all_by_selector, find_by_selector
from .browser_utils import (
    create_browser,
    human_like_delay_before_action,
    human_like_delay_between_pages,
)
from .config import load_config, SITES_DIR

PROGRESS_FILENAME = "progress.yaml"


def _format_error(page_url: str, selector: str | None, e: Exception) -> str:
    """Форматированный вывод ошибки: страница, селектор (если есть), описание."""
    lines = [
        "--- Ошибка ---",
        f"Страница: {page_url}",
    ]
    if selector:
        lines.append(f"Селектор: {selector}")
    lines.append(f"Описание: {type(e).__name__}: {e}")
    return "\n".join(lines)


def _normalize_url(base: str, href: str) -> str:
    return urljoin(base, href)


def _same_domain(url: str, base_url: str) -> bool:
    return urlparse(url).netloc == urlparse(base_url).netloc


def _load_progress(output_dir: Path) -> dict:
    """Загрузить прогресс из YAML (что уже скачано)."""
    path = output_dir / PROGRESS_FILENAME
    if not path.is_file() or yaml is None:
        return {"list_url": None, "downloaded": []}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("downloaded", [])
    return data


def _save_progress(output_dir: Path, progress: dict) -> None:
    """Сохранить прогресс в YAML."""
    if yaml is None:
        raise RuntimeError("PyYAML required for progress. pip install pyyaml")
    path = output_dir / PROGRESS_FILENAME
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(progress, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def get_story_links_on_current_page(driver, page_url: str, annotations: SiteAnnotations) -> list[str]:
    """Собрать ссылки на рассказы только с текущей страницы списка."""
    urls = []
    container_sel = annotations.story_list_container_selector
    link_sel = annotations.story_link_selector
    if not container_sel:
        links_el = find_all_by_selector(driver, link_sel) if link_sel else []
    else:
        containers = find_all_by_selector(driver, container_sel)
        links_el = []
        for c in containers:
            links_el.extend(find_all_by_selector(driver, link_sel, root=c))
    for el in links_el:
        try:
            href = el.get_attribute("href")
            if not href:
                continue
            full = _normalize_url(page_url, href)
            if _same_domain(full, annotations.base_url):
                urls.append(full)
        except Exception:
            continue
    return urls


def iter_list_pages(
    driver,
    list_url: str,
    annotations: SiteAnnotations,
    config: dict,
    max_list_pages: int = 100,
):
    """
    Итератор по страницам списка: на каждой странице загружаем её и отдаём (url_страницы_списка, [ссылки на рассказы]).
    Сначала скачали рассказы с этой страницы — потом переходим к следующей.
    """
    page_url = list_url
    list_pages_done = 0

    wait_for_human_done = False
    while page_url and list_pages_done < max_list_pages:
        human_like_delay_between_pages(config)
        try:
            driver.get(page_url)
        except TimeoutException:
            break
        human_like_delay_before_action(config)
        # Дать пользователю пройти проверку Cloudflare / «я не робот» (только раз, в видимом режиме)
        if not wait_for_human_done and config.get("wait_for_human") and not config.get("headless"):
            wait_for_human_done = True
            print("\n>>> Если в браузере видна проверка (Cloudflare, «Подтвердите, что вы не робот» и т.п.) — пройдите её, затем нажмите Enter здесь.\n")
            try:
                input("Нажмите Enter чтобы продолжить... ")
            except EOFError:
                pass

        story_urls = get_story_links_on_current_page(driver, page_url, annotations)
        yield page_url, story_urls

        # После скачивания рассказов драйвер на странице последнего рассказа — возвращаемся на страницу списка
        human_like_delay_between_pages(config)
        try:
            driver.get(page_url)
        except TimeoutException:
            break
        human_like_delay_before_action(config)

        next_sel = annotations.story_list_next_page_selector
        if not next_sel:
            break
        try:
            next_el = find_by_selector(driver, next_sel)
        except NoSuchElementException as e:
            print(_format_error(page_url, next_sel, e))
            print("(Считаем последней страницей списка, продолжаем.)")
            break
        except Exception as e:
            raise RuntimeError(_format_error(page_url, next_sel, e))
        page_url = None
        if next_el:
            try:
                page_url = next_el.get_attribute("href") or None
                if not page_url and next_el.tag_name.lower() == "a":
                    page_url = next_el.get_attribute("href")
            except Exception:
                pass
        list_pages_done += 1


def scrape_story_pages(
    driver,
    story_url: str,
    annotations: SiteAnnotations,
    config: dict,
    max_pages: int = 500,
    images_dir: Path | None = None,
    images_rel: str | None = None,
):
    """Скачивает рассказ постранично. Сохраняет HTML области текста с иллюстрациями на местах; картинки скачиваются, src подменяется на локальный путь."""
    pages_text = []
    page_url = story_url
    pages_done = 0
    user_agent = config.get("user_agent")

    while page_url and pages_done < max_pages:
        human_like_delay_between_pages(config)
        try:
            driver.get(page_url)
        except TimeoutException:
            break
        human_like_delay_before_action(config)

        title_sel = annotations.story_title_selector
        text_sel = annotations.story_text_selector
        title = ""
        if title_sel:
            try:
                el = find_by_selector(driver, title_sel)
                if el:
                    title = (el.text or "").strip()
            except Exception:
                pass
        html = ""
        images = []
        if text_sel:
            try:
                el = find_by_selector(driver, text_sel)
                if el:
                    html, images = _collect_images_and_replace_in_html(
                        el, page_url, images_dir, images_rel, user_agent
                    )
            except Exception:
                pass

        page_data = {"html": html}
        if images:
            page_data["images"] = images
        if title and pages_done == 0:
            page_data["title"] = title
            pages_text.append(page_data)
        else:
            pages_text.append(page_data)

        next_sel = annotations.next_page_selector
        if not next_sel:
            break
        try:
            next_el = find_by_selector(driver, next_sel)
        except Exception as e:
            raise RuntimeError(_format_error(page_url, next_sel, e))
        page_url = None
        if next_el:
            try:
                page_url = next_el.get_attribute("href")
                if not page_url:
                    next_el.click()
                    human_like_delay_between_pages(config)
                    page_url = driver.current_url
            except Exception:
                pass
        pages_done += 1

    return pages_text


def slug_from_url(url: str) -> str:
    """Короткое имя для файла из URL (без слэшей, один уровень)."""
    path = urlparse(url).path.rstrip("/") or "/"
    # убираем слэши и небезопасные символы — один плоский файл
    slug = re.sub(r"[^\w\-.]", "_", path.replace("/", "_")).strip("_")
    return slug[:120] or "page"


def _download_image(
    img_url: str,
    base_url: str,
    folder: Path,
    user_agent: str | None = None,
) -> str | None:
    """Скачать изображение по URL в folder, вернуть имя файла или None."""
    if not img_url or not img_url.strip():
        return None
    full_url = urljoin(base_url, img_url.strip())
    try:
        req = Request(full_url, headers={"User-Agent": user_agent or "Mozilla/5.0"})
        with urlopen(req, timeout=15) as resp:
            data = resp.read()
    except Exception:
        return None
    # имя файла: по расширению из URL или по content-type, иначе .bin
    parsed = urlparse(full_url)
    name = (parsed.path.rstrip("/") or "img").split("/")[-1]
    if not re.search(r"\.(jpe?g|png|gif|webp|bmp|svg)$", name, re.I):
        h = hashlib.sha1(data).hexdigest()[:12]
        name = f"img_{h}.bin"
    else:
        name = re.sub(r"[^\w\-.]", "_", name)[:80] or "img"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(data)
    return name


def _collect_images_and_replace_in_html(
    el,
    page_url: str,
    images_dir: Path | None,
    images_rel: str | None,
    user_agent: str | None,
) -> tuple[str, list[dict]]:
    """
    Взять innerHTML элемента, найти все img, скачать; заменить src на относительный путь к файлу.
    Возвращает (html с подставленными путями к картинкам, список {url, file}).
    """
    try:
        html = el.get_attribute("innerHTML") or ""
    except Exception:
        return "", []
    try:
        imgs = el.find_elements(By.TAG_NAME, "img")
    except Exception:
        return html, []
    # src из атрибута -> локальный путь для подстановки в HTML (один раз качаем на уникальный src)
    src_to_local: dict[str, str] = {}
    result = []
    for img in imgs:
        try:
            src = img.get_attribute("src")
            if not src or src in src_to_local:
                continue
            full_url = urljoin(page_url, src)
            entry = {"url": full_url}
            if images_dir and images_rel:
                fname = _download_image(full_url, page_url, images_dir, user_agent)
                if fname:
                    local_path = f"{images_rel}/{fname}".replace("\\", "/")
                    entry["file"] = fname
                    src_to_local[src] = local_path
                    result.append(entry)
        except Exception:
            continue
    # Подмена src в HTML с сохранением места иллюстрации
    for src_attr, local_path in src_to_local.items():
        escaped = re.escape(src_attr)
        # src="..." или src='...'
        html = re.sub(r'src=(["\'])(' + escaped + r')\1', r'src=\1' + local_path + r'\1', html)
    return html, result


def run_scraper(
    config_path: str | Path | None,
    site: str | None = None,
    annotations_path: str | Path | None = None,
    list_url: str | None = None,
    output_dir: str | Path | None = None,
    sites_dir: str | Path = SITES_DIR,
    headless: bool | None = None,
    max_list_pages: int = 100,
    max_story_pages: int = 500,
    use_undetected: bool = False,
    wait_for_human: bool = False,
) -> None:
    config = load_config(config_path)
    if headless is not None:
        config["headless"] = headless
    if use_undetected:
        config["use_undetected"] = True
    if wait_for_human:
        config["wait_for_human"] = True

    if site:
        sites_dir = Path(sites_dir)
        site_path = sites_dir / site
        annotations_path = site_path / "annotations.yaml"
        output_dir = site_path
        if not annotations_path.is_file():
            raise FileNotFoundError(
                f"Аннотация не найдена: {annotations_path}. Сначала сделайте разметку: ./scripts/run_labeler.sh <URL>"
            )
    else:
        if not annotations_path or not output_dir:
            raise ValueError("Укажите --site <имя_папки_сайта> (например litclubbs.ru) или --annotations и --output.")
        annotations_path = Path(annotations_path)
        output_dir = Path(output_dir)

    annotations = SiteAnnotations.load(Path(annotations_path))
    if not annotations.base_url:
        raise ValueError("Annotations file is empty or missing base_url. Run labeler first.")

    list_url = list_url or annotations.base_url
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    progress = _load_progress(output_dir)
    progress.setdefault("list_url", list_url)
    progress.setdefault("downloaded", [])
    downloaded_set = set(progress["downloaded"])
    next_index = len(progress["downloaded"])

    driver = create_browser(
        headless=config["headless"],
        user_agent=config.get("user_agent"),
        window_width=config.get("window_width", 1920),
        window_height=config.get("window_height", 1080),
        page_load_timeout_sec=config.get("page_load_timeout_sec", 30),
        implicit_wait_sec=config.get("implicit_wait_sec", 5),
        use_undetected=config.get("use_undetected", False),
    )

    try:
        try:
            list_iter = iter_list_pages(
                driver, list_url, annotations, config, max_list_pages
            )
            for list_page_url, story_urls in list_iter:
                print(f"List page: {list_page_url} — рассказов на странице: {len(story_urls)}")
                for url in story_urls:
                    if url in downloaded_set:
                        print(f"  Skip (уже скачан): {url[:60]}...")
                        continue
                    human_like_delay_between_pages(config)
                    slug = slug_from_url(url)
                    images_dir = output_dir / f"{next_index:04d}_{slug}_images"
                    images_rel = f"{next_index:04d}_{slug}_images"
                    try:
                        pages = scrape_story_pages(
                            driver, url, annotations, config, max_story_pages,
                            images_dir=images_dir,
                            images_rel=images_rel,
                        )
                    except Exception as e:
                        if "Страница:" in str(e):
                            print("\n" + str(e))
                        else:
                            print("\n" + _format_error(url, None, e))
                        print("  Пропуск рассказа, продолжаем.\n")
                        continue
                    path = output_dir / f"{next_index:04d}_{slug}.json"
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump({"url": url, "pages": pages}, f, ensure_ascii=False, indent=2)
                    print(f"  Saved: {path}")
                    progress["downloaded"].append(url)
                    downloaded_set.add(url)
                    next_index += 1
                    _save_progress(output_dir, progress)
            print(f"Готово. Скачано всего: {len(progress['downloaded'])}")
        except Exception as e:
            if "Страница:" in str(e):
                print("\n" + str(e))
            else:
                print("\n" + _format_error(getattr(e, "page_url", "(неизвестно)"), getattr(e, "selector", None), e))
            raise
    finally:
        driver.quit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Скачать контент сайта. Укажите имя папки сайта (где лежит annotations.yaml), например: --site litclubbs.ru"
    )
    parser.add_argument("--config", "-c", default="config.yaml", help="Конфиг YAML")
    parser.add_argument("--site", "-s", default=None, help="Имя папки сайта (loaded/<site>/ — там аннотация и сюда сохраняются данные)")
    parser.add_argument("--sites-dir", default=SITES_DIR, help=f"Каталог с папками сайтов (по умолчанию {SITES_DIR})")
    parser.add_argument("--annotations", "-a", default=None, help="Путь к annotations.yaml (если не используете --site)")
    parser.add_argument("--output", "-o", default=None, help="Папка вывода (если не используете --site)")
    parser.add_argument("--list-url", "-l", default=None, help="URL страницы списка (по умолчанию из аннотации)")
    parser.add_argument("--headless", action="store_true", help="Браузер в невидимом режиме")
    parser.add_argument("--no-headless", action="store_true", help="Браузер видимый")
    parser.add_argument("--max-list-pages", type=int, default=100, help="Макс. страниц списка")
    parser.add_argument("--max-story-pages", type=int, default=500, help="Макс. страниц рассказа")
    parser.add_argument("--undetected", action="store_true", help="Использовать undetected-chromedriver (обход Cloudflare)")
    parser.add_argument("--wait-for-human", action="store_true", help="После загрузки первой страницы ждать Enter (успеть нажать галочку в браузере)")
    args = parser.parse_args()

    headless = None
    if args.headless:
        headless = True
    if args.no_headless:
        headless = False

    run_scraper(
        config_path=args.config,
        site=args.site,
        annotations_path=args.annotations,
        list_url=args.list_url,
        output_dir=args.output,
        sites_dir=args.sites_dir,
        headless=headless,
        max_list_pages=args.max_list_pages,
        max_story_pages=args.max_story_pages,
        use_undetected=args.undetected,
        wait_for_human=args.wait_for_human,
    )


if __name__ == "__main__":
    main()
