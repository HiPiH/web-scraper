@echo off
cd /d "%~dp0.."

if not exist ".venv" (
  echo Run scripts\install.bat first.
  exit /b 1
)

call .venv\Scripts\activate.bat
python -m story_scraper.labeler %*
