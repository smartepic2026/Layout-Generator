@echo off
cd /d "%~dp0\.."
echo ============================================================
echo  BioForge CD Studio - Backend
echo  Working folder: %CD%
echo ============================================================
echo.
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY (where py >nul 2>&1 && set "PY=py")
if not defined PY echo [ERROR] Python not found. Install from python.org and check "Add Python to PATH". && goto end
echo Using Python: %PY%
%PY% --version
echo.
echo [1/2] Installing dependencies (first run only, may take minutes)...
%PY% -m pip install -r requirements.txt
%PY% -m pip install -r backend\requirements.txt
echo.
echo [2/2] Starting server.
echo When you see:  Uvicorn running on http://127.0.0.1:8000
echo open  http://localhost:8000  in your browser.
echo KEEP THIS WINDOW OPEN. Closing it stops the server.
echo ============================================================
%PY% -m uvicorn backend.app:app --port 8000
:end
echo.
echo (Server stopped or an error occurred. Read the message above.)
pause
