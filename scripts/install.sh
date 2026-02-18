#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
SCRIPT_DIR="$(pwd)"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

echo "Activating virtual environment and installing dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "Done. To activate venv manually: source .venv/bin/activate"
echo "Run labeler: ./scripts/run_labeler.sh <URL>"
echo "Run scraper: ./scripts/run_scraper.sh --site <имя_папки_сайта>"
