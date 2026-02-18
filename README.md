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

Опции: `--headless` / `--no-headless`, `--sites-dir каталог`, `--list-url URL`, `--config config.yaml`, `--undetected`, `--wait-for-human` (см. ниже).

Логика: сначала скачиваются рассказы с текущей страницы списка, затем переход на следующую страницу списка. **progress.yaml** в папке сайта хранит список уже скачанных URL — при повторном запуске с тем же `--site` скачивание продолжается с места остановки.

### 3. Экспорт в FB2 (книга)

Скачанные рассказы можно собрать в одну книгу FictionBook 2 (один .fb2 файл) или в отдельный .fb2 на каждый рассказ.

```bash
# Один FB2-сборник по умолчанию в папке сайта
./scripts/run_fb2_export.sh --site litclubbs.ru

# Указать выходной файл
./scripts/run_fb2_export.sh --site litclubbs.ru --output loaded/litclubbs.ru/книга.fb2

# Отдельный FB2 на каждый рассказ (в ту же папку или в --output как папку)
./scripts/run_fb2_export.sh --site litclubbs.ru --per-story

# Своё название книги
./scripts/run_fb2_export.sh --site litclubbs.ru --title "Фантастика с litclubbs"
```

**Windows:** `scripts\run_fb2_export.bat --site litclubbs.ru`

В FB2 попадают текст (из HTML) и иллюстрации (встроены в файл). Жанр по умолчанию — «sf», автор в описании — «Сборник».

## Структура

- **loaded/<имя_сайта>/annotations.yaml** — разметка (селекторы).
- **loaded/<имя_сайта>/progress.yaml** — прогресс скачивания.
- **loaded/<имя_сайта>/*.json** — рассказы; **loaded/<имя_сайта>/*_images/** — иллюстрации.

## Обход Cloudflare и проверок «я не робот»

Если сайт показывает проверку (Cloudflare, hCaptcha, «Подтвердите, что вы не робот» и т.п.), можно использовать один или оба способа.

### 1. Ручное прохождение (галочка в браузере)

Запустите скрапер или разметку **в видимом режиме** и включите ожидание после загрузки страницы: скрипт откроет страницу и будет ждать, пока вы нажмёте Enter в терминале. За это время пройдите проверку в браузере (нажмите галочку и т.д.).

- **Скрапер:** `--no-headless --wait-for-human` или в **config.yaml**: `headless: false`, `wait_for_human: true`.
- **Разметка:** `--wait-for-human` (браузер и так видимый).

Пример:
```bash
./scripts/run_scraper.sh --site example.com --no-headless --wait-for-human
```

### 2. undetected-chromedriver

Библиотека [undetected-chromedriver](https://pypi.org/project/undetected-chromedriver/) подменяет драйвер так, чтобы его сложнее было определить как бота. Часто проверка тогда не показывается или проходится автоматически.

Установка (опционально):
```bash
pip install undetected-chromedriver
```

Использование:
- **Скрапер:** `--undetected` или в **config.yaml**: `use_undetected: true`.
- **Разметка:** `--undetected`.

Пример:
```bash
./scripts/run_scraper.sh --site example.com --undetected --no-headless
```

Рекомендуется при защите от ботов запускать в **видимом режиме** (`--no-headless`): headless чаще детектируется. При необходимости комбинируйте: `--undetected --no-headless --wait-for-human`.

## Конфигурация

- **config.yaml** — общие настройки (headless, таймауты, задержки, `use_undetected`, `wait_for_human`).
