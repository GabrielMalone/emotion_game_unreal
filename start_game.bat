@echo off
cd /d "%~dp0"

:: Add MySQL to PATH (not on system PATH by default)
set "PATH=C:\mysql\bin;%PATH%"

echo ================================================================
echo   emotionGame Startup Script
echo ================================================================
echo.

:: ------------------------------------------------------------------
:: 1. Parse .env for secrets
:: ------------------------------------------------------------------
echo [1/2] Reading .env ...
if not exist ".env" (
    echo   ERROR: .env file not found in %cd%
    pause
    exit /b 1
)

for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
    if "%%a"=="DB_PASSWORD" set "DB_PASS=%%b"
    if "%%a"=="DB_USER"    set "DB_USER=%%b"
    if "%%a"=="DB_NAME"    set "DB_NAME=%%b"
    if "%%a"=="DB_HOST"    set "DB_HOST=%%b"
)

if "%DB_PASS%"=="" echo   WARNING: DB_PASSWORD not found in .env, using empty
if "%DB_USER%"=="" set "DB_USER=root"
if "%DB_NAME%"=="" set "DB_NAME=camodb"
if "%DB_HOST%"=="" set "DB_HOST=localhost"

echo   DB: %DB_USER%@%DB_HOST%/%DB_NAME%

:: ------------------------------------------------------------------
:: 2. Reset database to initial state
:: ------------------------------------------------------------------
echo.
echo [2/2] Resetting camodb to initial state ...

set "SQL_FILE=database\camodb_phase1.sql"
if not exist "%SQL_FILE%" (
    echo   ERROR: Schema file not found: %SQL_FILE%
    pause
    exit /b 1
)

:: Check that mysql is on PATH
where mysql >nul 2>nul
if errorlevel 1 (
    echo   ERROR: 'mysql' command not found on PATH
    echo   Make sure MySQL is installed and on your PATH.
    pause
    exit /b 1
)

:: Run import — capture stderr in case of failure
echo   Importing %SQL_FILE% ...
set "MYSQL_ERR=%TEMP%\mysql_import_err.txt"
mysql -u %DB_USER% -p%DB_PASS% -h %DB_HOST% --default-character-set=utf8mb4 < "%SQL_FILE%" 2>"%MYSQL_ERR%"
if errorlevel 1 (
    echo   ERROR: mysql import failed. Error output:
    type "%MYSQL_ERR%" 2>nul
    del "%MYSQL_ERR%" 2>nul
    echo.
    echo   Retry manually:
    echo     mysql -u %DB_USER% -p -h %DB_HOST% ^< %SQL_FILE%
    pause
    exit /b 1
)
del "%MYSQL_ERR%" 2>nul
echo   Database reset complete.

:: ------------------------------------------------------------------
:: 3. Start camo_server.py using the egvenv Python directly
:: ------------------------------------------------------------------
echo.
echo ================================================================
echo   Starting camo_server.py on http://0.0.0.0:5001
echo ================================================================
echo.

set "VENV_PYTHON=egvenv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" (
    echo   ERROR: venv Python not found at %VENV_PYTHON%
    pause
    exit /b 1
)

"%VENV_PYTHON%" camo_server.py

:: If camo_server exits, keep the window open so errors are visible
echo.
echo camo_server.py exited. Press any key to close.
pause >nul
