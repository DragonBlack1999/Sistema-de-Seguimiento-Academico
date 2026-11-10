@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title DEMOSTRACION - Sistema de Seguimiento Academico

rem ===========================================================================
rem  Arranca el sistema para mostrarlo y abre el navegador.
rem  Antes de usarlo por primera vez hay que correr instalar_demo.bat.
rem
rem  Para terminar: cierra esta ventana negra.
rem
rem  NO usa el puerto 8000. Es el que toma `manage.py runserver` a secas, asi
rem  que en una computadora donde ya se trabaja en el proyecto suele estar
rem  ocupado por el servidor de desarrollo, que apunta a OTRA base de datos.
rem  Probando esto aparecio en pantalla el colegio de verdad en lugar de la
rem  demostracion, y el ingreso fallaba porque las contrasenas son otras.
rem ===========================================================================

cd /d "%~dp0.."

if not exist "demo\configuracion.bat" (
    echo.
    echo   [X] Falta la configuracion.
    echo.
    echo       Corre primero:  demo\instalar_demo.bat
    echo.
    pause
    exit /b 1
)
call demo\configuracion.bat

if exist "venv\Scripts\python.exe" (
    set "PY=venv\Scripts\python.exe"
) else (
    set "PY=python"
)

rem --------------------------------------------------- un puerto que este libre
set "PUERTO="
for %%P in (8080 8081 8082 8090) do (
    if not defined PUERTO (
        netstat -ano | findstr /r /c:":%%P .*LISTENING" >nul 2>&1
        if errorlevel 1 set "PUERTO=%%P"
    )
)
if not defined PUERTO (
    echo.
    echo   [X] No hay ningun puerto libre ^(8080, 8081, 8082, 8090^).
    echo       Cierra los otros servidores que tengas abiertos y vuelve a intentar.
    echo.
    pause
    exit /b 1
)

rem --------------------------------------------- el dia en que se muestra
rem  Los datos se generaron una vez y se guardaron; la demostracion se abre
rem  otro dia. Sin esto, la primera pantalla dice "han entrado 0 de 402" y el
rem  colegio aparece como si no hubiera abierto. Esto deja el dia a media
rem  manana. No hace nada si el dia ya tiene asistencia.
echo   Poniendo el dia al dia...
"%PY%" manage.py demo_al_dia

echo.
echo   ================================================================
echo    SISTEMA DE SEGUIMIENTO ACADEMICO
echo    U.E. "Eduardo Abaroa Tarde" - Nivel Secundario
echo.
echo    DEMOSTRACION - datos inventados, sin internet
echo   ================================================================
echo.
echo    Direccion:  http://127.0.0.1:!PUERTO!
echo.
echo    DEJA ESTA VENTANA ABIERTA mientras presentas.
echo    Para terminar, cierrala.
echo.
echo   ----------------------------------------------------------------
echo    Si el navegador no abre solo, escribe en el:  127.0.0.1:!PUERTO!
echo   ----------------------------------------------------------------
echo.

rem El navegador se abre con un respiro, para que el servidor ya este
rem escuchando cuando llegue el pedido. Sin esto se ve un "no se puede
rem conectar" justo al empezar, que es lo peor que puede pasar delante de
rem alguien.
start "" /b cmd /c "timeout /t 4 >nul & start http://127.0.0.1:!PUERTO!/"

"%PY%" manage.py runserver 127.0.0.1:!PUERTO! --noreload

echo.
echo   El servidor se detuvo.
pause
endlocal
