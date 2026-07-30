@echo off
setlocal

set "BACKEND_DIR=%~dp0"

rem El entorno virtual vive en distinto sitio segun quien clono el proyecto:
rem el README lo documenta en backend\.venv, pero tambien es habitual tenerlo
rem en la raiz. Se prueban los dos en vez de exigir uno: el script existe para
rem levantar el servidor, no para imponer una distribucion de carpetas.
set "PYTHON_CCAA=%BACKEND_DIR%.venv\Scripts\python.exe"
if not exist "%PYTHON_CCAA%" set "PYTHON_CCAA=%BACKEND_DIR%..\.venv\Scripts\python.exe"

if not exist "%PYTHON_CCAA%" (
    echo [ERROR] No se encontro el entorno virtual de CCAA. Se busco en:
    echo   %BACKEND_DIR%.venv\Scripts\python.exe
    echo   %BACKEND_DIR%..\.venv\Scripts\python.exe
    echo.
    echo Crea el entorno virtual e instala backend\requirements.txt.
    exit /b 1
)

pushd "%BACKEND_DIR%"
"%PYTHON_CCAA%" manage.py runserver %*
set "EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %EXIT_CODE%
