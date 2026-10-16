@echo off
cd /d "%~dp0"
taskkill /F /IM python.exe >nul 2>&1
timeout /t 1 >nul
del /q coach.db coach.db-journal >nul 2>&1
start "Pravesh backend" cmd /k py -m uvicorn app.main:app --port 8001
start "Pravesh frontend" cmd /k py -m http.server 5500
timeout /t 3 >nul
start http://localhost:5500
