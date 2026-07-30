@echo off
setlocal

set "BACKEND_DIR=%~dp0"
set "PYTHON_CCAA=%BACKEND_DIR%..\.venv\Scripts\python.exe"

if not exist "%PYTHON_CCAA%" (
    echo [ERROR] No se encontro el entorno virtual de CCAA:
    echo %PYTHON_CCAA%
    echo.
    echo Crea el entorno virtual en la raiz del proyecto e instala requirements.txt.
    exit /b 1
)

pushd "%BACKEND_DIR%"
"%PYTHON_CCAA%" manage.py runserver %*
set "EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %EXIT_CODE%
