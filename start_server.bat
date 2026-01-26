@echo off
chcp 65001 >nul
cd /d E:\makeup-boot

REM 可选：指定要加载的 env 文件，例如：start_server.bat .env.local
REM 如不传参，默认加载项目根目录 .env
if not "%~1"=="" (
    set ENV_FILE=%~1
)
echo ========================================
echo Starting server on port 8089...
echo ========================================
echo.
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8089
echo.
echo Server stopped. Press any key to exit...
pause >nul

