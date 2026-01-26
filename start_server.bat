@echo off
chcp 65001 >nul
cd /d E:\makeup-boot

REM 可选：指定要加载的 env 文件，例如：start_server.bat .env.local
REM 如不传参，默认加载项目根目录 .env
if not "%~1"=="" (
    set ENV_FILE=%~1
)
echo.
.venv\Scripts\python.exe run_server.py
echo.
echo Server stopped. Press any key to exit...
pause >nul

