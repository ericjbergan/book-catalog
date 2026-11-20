@echo off
title Book Catalog Server
cd /d "%~dp0"

rem If the server is already running, just open the browser
netstat -ano | findstr /r /c:":5000 .*LISTENING" >nul
if %errorlevel%==0 (
    start "" http://localhost:5000
    exit /b
)

rem Open the browser once the server has had a moment to start
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start "" http://localhost:5000"

echo Starting Book Catalog at http://localhost:5000
echo Close this window to stop the server.
echo.
"C:\Python310\python.exe" app.py
pause
