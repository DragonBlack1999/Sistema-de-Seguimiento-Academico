@echo off
REM ============================================================
REM  Copia de respaldo diaria del Sistema de Seguimiento Academico
REM  U.E. "Eduardo Abaroa Tarde" - Nivel Secundario
REM
REM  Esto es lo que ejecuta el Programador de tareas de Windows.
REM  Para probarlo a mano, basta con hacerle doble clic.
REM
REM  Lo que imprime queda en respaldos\registro.txt, para poder
REM  mirar despues si alguna noche fallo.
REM
REM  Sin acentos a proposito: cmd.exe no lee este archivo en UTF-8.
REM ============================================================
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

if not exist "%~dp0respaldos" mkdir "%~dp0respaldos"
set REGISTRO=%~dp0respaldos\registro.txt

echo.>> "%REGISTRO%"
echo ===== %DATE% %TIME% =====>> "%REGISTRO%"
venv\Scripts\python.exe manage.py respaldar >> "%REGISTRO%" 2>&1
set CODIGO=%ERRORLEVEL%

if %CODIGO% NEQ 0 (
  echo RESPALDO FALLIDO, codigo %CODIGO%>> "%REGISTRO%"
  echo.
  echo  *** EL RESPALDO FALLO. Revisa respaldos\registro.txt ***
  echo.
) else (
  echo Respaldo terminado.>> "%REGISTRO%"
)

REM Sin pausa: la tarea programada corre sin nadie delante.
exit /b %CODIGO%
