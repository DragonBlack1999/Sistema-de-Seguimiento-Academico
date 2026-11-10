@echo off
chcp 65001 >nul
title Revisar la demostracion
cd /d "%~dp0.."
if not exist "demo\configuracion.bat" (
    echo   [X] Corre primero: demo\instalar_demo.bat
    pause
    exit /b 1
)
call demo\configuracion.bat
if exist "venv\Scripts\python.exe" ( set "PY=venv\Scripts\python.exe" ) else ( set "PY=python" )
echo.
echo   Recorriendo el guion entero. Tarda medio minuto.
echo.
"%PY%" demo\revisar_demo.py
echo.
pause
