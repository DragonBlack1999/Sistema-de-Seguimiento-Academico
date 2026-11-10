@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Instalar la demostracion - Sistema de Seguimiento Academico

rem ===========================================================================
rem  Deja esta computadora lista para mostrar el sistema. Se corre UNA VEZ.
rem  Despues, para presentar, se usa demo.bat.
rem
rem  No toca el archivo .env que pueda haber: la demostracion se configura por
rem  variables de entorno, que es lo que el proyecto mira primero. Asi una
rem  computadora de desarrollo sigue funcionando igual que antes.
rem ===========================================================================

cd /d "%~dp0.."
echo.
echo   SISTEMA DE SEGUIMIENTO ACADEMICO - instalacion de la demostracion
echo   ================================================================
echo.

rem ------------------------------------------------------------------ PostgreSQL
set "PGBIN="
for %%V in (18 17 16 15 14 13) do (
    if exist "C:\Program Files\PostgreSQL\%%V\bin\psql.exe" (
        if not defined PGBIN set "PGBIN=C:\Program Files\PostgreSQL\%%V\bin"
    )
)
if not defined PGBIN (
    echo   [X] No encuentro PostgreSQL en C:\Program Files\PostgreSQL
    echo.
    echo       Instalalo desde https://www.postgresql.org/download/windows/
    echo       y vuelve a correr este archivo.
    goto :fin
)
echo   [OK] PostgreSQL: %PGBIN%

rem ------------------------------------------------------------------ Python
if exist "venv\Scripts\python.exe" (
    set "PY=venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo   [X] No encuentro Python.
        echo.
        echo       Instalalo desde https://www.python.org/downloads/windows/
        echo       marcando "Add python.exe to PATH", y vuelve a correr esto.
        goto :fin
    )
    echo   [..] Creando el entorno de Python...
    python -m venv venv
    if errorlevel 1 ( echo   [X] No se pudo crear el entorno. & goto :fin )
    set "PY=venv\Scripts\python.exe"
)
echo   [OK] Python: !PY!

echo   [..] Instalando las librerias del proyecto...
"!PY!" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo   [X] Fallo la instalacion. Revisa la conexion a internet.
    goto :fin
)
echo   [OK] Librerias instaladas.

rem ------------------------------------------------------------------ la base
rem  La contrasena se puede pasar como argumento:
rem      instalar_demo.bat miClave
rem  Sirve para volver a correrlo sin teclear nada, y para poder probarlo.
set "CLAVE=%~1"
if not defined CLAVE (
    echo.
    echo   Escribe la contrasena del usuario "postgres" de ESTA computadora.
    set /p CLAVE=Contrasena de postgres:
)
echo.

set "PGPASSWORD=!CLAVE!"
"%PGBIN%\psql" -U postgres -d postgres -tAc "SELECT 1" >nul 2>&1
if errorlevel 1 (
    echo   [X] Esa contrasena no entra, o PostgreSQL no esta encendido.
    goto :fin
)

echo   [..] Creando la base "seguimiento_demo"...
"%PGBIN%\psql" -U postgres -d postgres -c "DROP DATABASE IF EXISTS seguimiento_demo" >nul 2>&1
"%PGBIN%\psql" -U postgres -d postgres -c "CREATE DATABASE seguimiento_demo" >nul 2>&1

echo   [..] Restaurando los datos ^(tarda un par de minutos^)...
if not exist "demo\demo.dump" (
    echo   [X] Falta el archivo demo\demo.dump
    goto :fin
)
"%PGBIN%\pg_restore" -U postgres -d seguimiento_demo --no-owner --no-privileges "demo\demo.dump" >nul 2>&1

rem  El conteo se escribe a un archivo y se lee de ahi: un `for /f` sobre un
rem  comando con comillas anidadas es fragil en batch, y si falla deja la
rem  variable vacia y hace creer que la restauracion no funciono.
"%PGBIN%\psql" -U postgres -d seguimiento_demo -tAc "SELECT count(*) FROM academico_estudiante" -o "%TEMP%\sa_cuenta.txt" >nul 2>&1
set "CUANTOS="
if exist "%TEMP%\sa_cuenta.txt" set /p CUANTOS=<"%TEMP%\sa_cuenta.txt"
del "%TEMP%\sa_cuenta.txt" >nul 2>&1
if not defined CUANTOS (
    echo   [X] La restauracion no dejo datos. Revisa demo\demo.dump
    goto :fin
)
if "!CUANTOS: =!"=="0" (
    echo   [X] La restauracion no dejo datos. Revisa demo\demo.dump
    goto :fin
)
echo   [OK] Base restaurada: !CUANTOS! estudiantes.

rem ------------------------------------------------------------- la configuracion
rem  Se guarda en un .bat que demo.bat invoca. Lleva la contrasena de postgres
rem  de esta computadora, asi que no se sube a ningun lado (esta en .gitignore).
> demo\configuracion.bat echo @echo off
>> demo\configuracion.bat echo rem Generado por instalar_demo.bat. No se sube al repositorio.
>> demo\configuracion.bat echo set "PGBIN=%PGBIN%"
>> demo\configuracion.bat echo set "SECRET_KEY=demo-para-mostrar-no-sirve-en-el-colegio-2026"
>> demo\configuracion.bat echo set "DEBUG=False"
>> demo\configuracion.bat echo set "ALLOWED_HOSTS=localhost,127.0.0.1"
>> demo\configuracion.bat echo set "DB_NAME=seguimiento_demo"
>> demo\configuracion.bat echo set "DB_USER=postgres"
>> demo\configuracion.bat echo set "DB_PASSWORD=!CLAVE!"
>> demo\configuracion.bat echo set "DB_HOST=localhost"
>> demo\configuracion.bat echo set "DB_PORT=5432"
>> demo\configuracion.bat echo set "HORA_ENTRADA=13:50"
>> demo\configuracion.bat echo set "UMBRAL_FALTAS_ALERTA=3"

call demo\configuracion.bat

echo   [..] Poniendo la base al dia y preparando los estilos...
"!PY!" manage.py migrate >nul 2>&1
if errorlevel 1 (
    echo   [X] Fallo "migrate". La base quedo a medias.
    goto :fin
)
"!PY!" manage.py collectstatic --noinput >nul 2>&1

echo.
echo   ================================================================
echo    LISTO.
echo.
echo    Para presentar manana, haz doble clic en:   demo\demo.bat
echo    Las credenciales estan en:                  demo\GUION.md
echo   ================================================================

:fin
set "PGPASSWORD="
set "CLAVE="
echo.
pause
endlocal
