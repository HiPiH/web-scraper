"""
Экспорт скачанных рассказов в формат FB2 (FictionBook 2).
Один FB2 на весь сайт (сборник) или один FB2 на каждый рассказ.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from .config import SITES_DIR

# FictionBook 2 namespaces
FB2_NS = "http://www.gribuser.ru/xml/fictionbook/2.0"
XLINK_NS = "http://www.w3.org/1999/xlink"


def _fb2_tag(name: str) -> str:
    return "{%s}%s" % (FB2_NS, name)


def _register_ns():
    ET.register_namespace("", FB2_NS)
    ET.register_namespace("l", XLINK_NS)


def _html_to_blocks(html: str) -> list[dict]:
    """
    Разбить HTML на блоки: {"type": "p", "text": "..."} или {"type": "img", "src": "path"}.
    Путь img — относительный к папке рассказа (например 0007_..._images/unnamed.jpg).
    """
    from lxml import html as lxml_html
    blocks = []
    if not html or not html.strip():
        return blocks
    try:
        doc = lxml_html.fromstring("<div>" + html.strip() + "</div>")
    except Exception:
        text = re.sub(r"<[^>]+>", "\n", html)
        for part in re.split(r"\n\s*\n", text):
            part = part.strip()
            if part:
                blocks.append({"type": "p", "text": part})
        return blocks

    # Порядок: обходим все p и img в порядке появления в документе
    for el in doc.iter():
        tag_name = el.tag.lower() if isinstance(el.tag, str) else (el.tag or "")
        if tag_name == "p":
            text = (el.text_content() or "").strip()
            text = re.sub(r"\s+", " ", text)
            if text:
                blocks.append({"type": "p", "text": text})
            # внутри <p> могут быть <img> — они уже будут в iter, но после этого p
            # лучше собрать img отдельно и вставить по порядку; для простоты сначала все p по порядку, потом img по порядку
        elif tag_name == "img":
            src = el.get("src")
            if src:
                blocks.append({"type": "img", "src": src})
    # Сохраняем порядок: в HTML может быть p, img, p. iter() идёт в document order, но p содержит вложенные — мы сначала получаем p (с текстом), потом при обходе дочерние img. Так что порядок правильный: p, потом дочерние p/img. Но у нас один уровень iter — мы не различаем img внутри p. Оставим как есть: все p подряд, все img подряд. Для FB2 это приемлемо (картинки после абзацев раздела).
    if not blocks:
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            blocks.append({"type": "p", "text": text})
    return blocks


def _image_content_type(path: Path) -> str:
    suf = path.suffix.lower()
    m = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
    return m.get(suf, "application/octet-stream")


def _story_to_fb2_parts(
    story_path: Path,
    story_index: int,
    images_global: dict[str, tuple[str, bytes]],
) -> tuple[list[ET.Element], str]:
    """
    Прочитать один JSON рассказа, вернуть (список элементов body: section с title + p + image, title рассказа).
    Картинки добавляются в images_global: id -> (content-type, data).
    """
    with open(story_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    story_title = ""
    section_el = ET.Element("section")
    if ET.iselement(section_el):
        pass  # ensure we use the right API
    for page in data.get("pages", []):
        if not story_title and page.get("title"):
            story_title = page.get("title", "").strip()
        html = page.get("html", "")
        blocks = _html_to_blocks(html)
        for bl in blocks:
            if bl["type"] == "p":
                p = ET.Element(_fb2_tag("p"))
                p.text = bl.get("text", "").strip()
                if p.text:
                    section_el.append(p)
            elif bl["type"] == "img":
                src = bl.get("src", "")
                # src может быть "0007_..._images/unnamed.jpg" относительно папки сайта
                parts = src.replace("\\", "/").split("/")
                if len(parts) >= 2:
                    # папка _images рядом с JSON
                    img_dir = story_path.parent / parts[-2]
                    img_name = parts[-1]
                else:
                    img_dir = story_path.parent / (story_path.stem.replace(".json", "") + "_images")
                    img_name = parts[-1] if parts else "img"
                img_path = img_dir / img_name
                if img_path.is_file():
                    img_id = "img_%d_%s" % (story_index, len(images_global))
                    content_type = _image_content_type(img_path)
                    images_global[img_id] = (content_type, img_path.read_bytes())
                    im = ET.Element(_fb2_tag("image"))
                    im.set("{%s}href" % XLINK_NS, "#" + img_id)
                    section_el.append(im)

    if story_title:
        title_el = ET.Element(_fb2_tag("title"))
        p = ET.Element(_fb2_tag("p"))
        p.text = story_title
        title_el.append(p)
        section_el.insert(0, title_el)
    return [section_el], story_title or ("Рассказ %d" % (story_index + 1))


def _make_fb2_root(book_title: str, lang: str = "ru") -> ET.Element:
    _register_ns()
    root = ET.Element(
        _fb2_tag("FictionBook"),
        attrib={"xmlns": FB2_NS, "xmlns:l": XLINK_NS},
    )
    desc = ET.SubElement(root, _fb2_tag("description"))
    ti = ET.SubElement(desc, _fb2_tag("title-info"))
    ET.SubElement(ti, _fb2_tag("genre")).text = "sf"
    author = ET.SubElement(ti, _fb2_tag("author"))
    ET.SubElement(author, _fb2_tag("first-name")).text = ""
    ET.SubElement(author, _fb2_tag("last-name")).text = "Сборник"
    ET.SubElement(ti, _fb2_tag("book-title")).text = book_title
    return root


def _write_fb2(root: ET.Element, out_path: Path, binaries: dict[str, tuple[str, bytes]]) -> None:
    for bid, (content_type, data) in binaries.items():
        b = ET.SubElement(root, _fb2_tag("binary"), id=bid, content_type=content_type)
        b.text = base64.b64encode(data).decode("ascii")
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
        tree.write(f, encoding="utf-8", xml_declaration=False, method="xml")


def export_site_to_fb2(
    site_path: Path,
    output: Path | None = None,
    single_file: bool = True,
    book_title: str | None = None,
) -> list[Path]:
    """
    Конвертировать все рассказы из папки сайта в FB2.
    single_file=True — один FB2-файл (сборник), иначе — один FB2 на каждый рассказ.
    Возвращает список созданных файлов.
    """
    site_path = Path(site_path)
    if not site_path.is_dir():
        raise FileNotFoundError("Папка сайта не найдена: %s" % site_path)

    json_files = sorted(site_path.glob("*.json"), key=lambda p: p.name)
    json_files = [p for p in json_files if p.name != "progress.yaml" and p.suffix == ".json"]
    if not json_files:
        return []

    book_title = book_title or ("Сборник — %s" % site_path.name)
    created: list[Path] = []

    if single_file:
        images_global: dict[str, tuple[str, bytes]] = {}
        root = _make_fb2_root(book_title)
        body = ET.SubElement(root, _fb2_tag("body"))
        for i, jpath in enumerate(json_files):
            sections, _ = _story_to_fb2_parts(jpath, i, images_global)
            for sec in sections:
                body.append(sec)
        out_path = output or (site_path / (site_path.name + ".fb2"))
        _write_fb2(root, out_path, images_global)
        created.append(out_path)
    else:
        for i, jpath in enumerate(json_files):
            images_global = {}
            sections, story_title = _story_to_fb2_parts(jpath, i, images_global)
            root = _make_fb2_root(story_title)
            body = ET.SubElement(root, _fb2_tag("body"))
            for sec in sections:
                body.append(sec)
            out_name = jpath.stem + ".fb2"
            out_path = output or site_path
            if out_path.suffix:
                out_path = out_path.parent / out_name
            else:
                out_path = out_path / out_name
            _write_fb2(root, out_path, images_global)
            created.append(out_path)

    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Конвертация скачанных рассказов в FB2 (FictionBook 2)")
    parser.add_argument("--site", "-s", required=True, help="Имя папки сайта (например litclubbs.ru)")
    parser.add_argument("--sites-dir", default=SITES_DIR, help="Каталог с папками сайтов")
    parser.add_argument("--output", "-o", default=None, help="Выходной файл (сборник) или папка (при --per-story)")
    parser.add_argument("--per-story", action="store_true", help="Создать отдельный FB2 на каждый рассказ")
    parser.add_argument("--title", "-t", default=None, help="Название книги (по умолчанию «Сборник — <сайт>»)")
    args = parser.parse_args()

    site_path = Path(args.sites_dir) / args.site
    output = Path(args.output) if args.output else None
    created = export_site_to_fb2(
        site_path,
        output=output,
        single_file=not args.per_story,
        book_title=args.title,
    )
    for p in created:
        print("Создан: %s" % p)
    if not created:
        print("Нет JSON-файлов рассказов в %s" % site_path)


if __name__ == "__main__":
    main()
