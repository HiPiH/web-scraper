# Веб-скрапер сайтов с рассказами

Проект состоит из двух частей:
1. **Скрапер** — скачивание контента сайта (поддержка headless и видимого режима).
2. **Инструмент разметки** — разметка областей текста, заголовков, перехода на следующую страницу и списка ссылок на рассказы (в т.ч. многостраничного).

Все зависимости и запуск — через виртуальное окружение и скрипты CLI.

## Установка

**macOS / Linux:**
```bash
./scripts/install.sh
# вручную: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

**Windows (cmd):**
```bat
scripts\install.bat
```
Либо вручную: `python -m venv .venv`, затем `.venv\Scripts\activate.bat`, затем `pip install -r requirements.txt`.

## Использование

### 1. Разметка (браузер в видимом режиме)

Создаётся папка по имени сайта (домен из URL): **loaded/<домен>/**. Туда сохраняется **annotations.yaml**.

```bash
# macOS / Linux
./scripts/run_labeler.sh https://litclubbs.ru/articles/proza/sci-fi

# Windows
scripts\run_labeler.bat https://litclubbs.ru/articles/proza/sci-fi
```
Или: `python -m story_scraper.labeler <URL>`.

В результате: **loaded/litclubbs.ru/annotations.yaml**. В разметке задаются: область текста, заголовок, «следующая страница», список ссылок на рассказы и пагинация списка.

Опционально: `--site имя_папки` — задать имя папки вручную; `--sites-dir каталог` — каталог вместо `loaded/`.

### 2. Скачивание контента

Указываете **только имя папки сайта** — аннотация и все скачанные данные лежат в ней.

```bash
# macOS / Linux
./scripts/run_scraper.sh --site litclubbs.ru

# Windows
scripts\run_scraper.bat --site litclubbs.ru
```
Или: `python -m story_scraper.scraper --site litclubbs.ru`.

Скрапер берёт аннотацию из **loaded/litclubbs.ru/annotations.yaml** и сохраняет рассказы, картинки и **progress.yaml** в **loaded/litclubbs.ru/**.

Опции: `--headless` / `--no-headless`, `--sites-dir каталог`, `--list-url URL`, `--config config.yaml`.

Логика: сначала скачиваются рассказы с текущей страницы списка, затем переход на следующую страницу списка. **progress.yaml** в папке сайта хранит список уже скачанных URL — при повторном запуске с тем же `--site` скачивание продолжается с места остановки.

## Структура

- **loaded/<имя_сайта>/annotations.yaml** — разметка (селекторы).
- **loaded/<имя_сайта>/progress.yaml** — прогресс скачивания.
- **loaded/<имя_сайта>/*.json** — рассказы; **loaded/<имя_сайта>/*_images/** — иллюстрации.

## Конфигурация

- **config.yaml** — общие настройки (headless, таймауты, задержки).
