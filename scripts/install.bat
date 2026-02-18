@echo off
cd /d "%~dp0.."

if not exist ".venv" (
  echo Creating virtual environment...
  python -m venv .venv
)

echo Activating virtual environment and installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Done. To activate venv manually: .venv\Scripts\activate.bat
echo Run labeler: scripts\run_labeler.bat ^<URL^>
echo Run scraper: scripts\run_scraper.bat --site ^<имя_папки_сайта^>
pause
