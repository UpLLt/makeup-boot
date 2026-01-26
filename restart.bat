@echo off
chcp 65001 >nul
echo [Restart] Finding process on port 8089...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8089 ^| findstr LISTENING') do (
    echo [Restart] Found process PID: %%a
    echo [Restart] Killing process...
    taskkill /PID %%a /F
    if errorlevel 1 (
        echo [Restart] Failed to kill process or process already terminated
    ) else (
        echo [Restart] Process killed successfully
    )
    timeout /t 1 /nobreak >nul
    goto :start
)
echo [Restart] No process found on port 8089

:start
echo [Restart] Starting uvicorn service on port 8089...
cd /d E:\makeup-boot

REM 可选：指定要加载的 env 文件，例如：restart.bat .env.local
REM 如不传参，默认加载项目根目录 .env
if not "%~1"=="" (
    set ENV_FILE=%~1
)
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8089

