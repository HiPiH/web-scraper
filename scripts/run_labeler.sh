#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
if [ ! -d ".venv" ]; then
  echo "Run ./scripts/install.sh first."
  exit 1
fi
source .venv/bin/activate
exec python -m story_scraper.labeler "$@"
