@echo off
setlocal

rem Detect whether this is the main project layout (PolyLibs/.venv) or the
rem open-source backup layout (.venv directly next to polylibs/).
set "SCRIPT_DIR=%~dp0"
set "VENV_DIR="

if exist "%SCRIPT_DIR%PolyLibs\.venv\Scripts\python.exe" (
    set "VENV_DIR=%SCRIPT_DIR%PolyLibs\.venv"
) else if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "VENV_DIR=%SCRIPT_DIR%.venv"
)

rem Find a Python interpreter to create the venv if needed.
python --version >nul 2>nul
if errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    set "PYTHON_CMD=python"
)

rem Decide where the venv should live, but create it outside the block so
rem variable expansion works reliably without delayed expansion.
if not defined VENV_DIR (
    echo Project venv not found. Creating...
    if exist "%SCRIPT_DIR%PolyLibs\" (
        set "VENV_DIR=%SCRIPT_DIR%PolyLibs\.venv"
    ) else (
        set "VENV_DIR=%SCRIPT_DIR%.venv"
    )
)

set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

rem Create the venv only if the expected python.exe is actually missing.
if not exist "%VENV_PYTHON%" (
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Failed to create virtual environment. Please install Python and try again.
        pause >nul
        exit /b 1
    )
    echo Venv created: %VENV_DIR%
)

echo Using project venv: %VENV_PYTHON%

rem start.py will check for missing dependencies and install them into the venv.
"%VENV_PYTHON%" "%SCRIPT_DIR%start.py" %*

if errorlevel 1 (
    echo.
    echo Press any key to close...
    pause >nul
)
