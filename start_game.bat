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
    if "%%a"=="DB_PORT"    set "DB_PORT=%%b"
    if "%%a"=="DB_SSL_CA"  set "DB_SSL_CA=%%b"
    if "%%a"=="DB_DEBUG_PASSWORD" set "DB_DEBUG_PASS=%%b"
    if "%%a"=="DEBUG_SHORT_RESPONSES" set "DEBUG_SHORT=%%b"
)

if "%DB_PASS%"=="" echo   WARNING: DB_PASSWORD not found in .env, using empty
if "%DB_USER%"=="" set "DB_USER=root"
if "%DB_NAME%"=="" set "DB_NAME=camodb"
if "%DB_HOST%"=="" set "DB_HOST=localhost"
if "%DB_PORT%"=="" set "DB_PORT=3306"
if "%DB_SSL_CA%"=="" set "DB_SSL_CA=isrg-root-x1.pem"

:: --- debug mode: skip remote DB, use local ---
if not "%DEBUG_SHORT%"=="" (
    echo.
    echo   *** DEBUG MODE: overriding DB to localhost ***
    echo   DEBUG_SHORT_RESPONSES = %DEBUG_SHORT%
    set "DB_HOST=localhost"
    set "DB_PORT=3306"
    set "DB_USER=root"
    if not "%DB_DEBUG_PASS%"=="" set "DB_PASS=%DB_DEBUG_PASS%"
    set "DB_SSL_CA="
)

echo   DB: %DB_USER%@%DB_HOST%:%DB_PORT%/%DB_NAME%
if not "%DB_SSL_CA%"=="" (
    if exist "%DB_SSL_CA%" (
        echo   SSL CA: %DB_SSL_CA%
    ) else (
        echo   WARNING: SSL CA file not found: %DB_SSL_CA% - proceeding without SSL
        set "DB_SSL_CA="
    )
)

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

:: Build SSL args for mysql CLI
set "MYSQL_SSL_ARGS="
if not "%DB_SSL_CA%"=="" (
    if exist "%DB_SSL_CA%" (
        set "MYSQL_SSL_ARGS=--ssl-ca=%DB_SSL_CA% --ssl-mode=VERIFY_IDENTITY"
    )
)

:: Run import — capture stderr in case of failure
echo   Importing %SQL_FILE% ...
set "MYSQL_ERR=%TEMP%\mysql_import_err.txt"
mysql -u %DB_USER% -p%DB_PASS% -h %DB_HOST% -P %DB_PORT% %MYSQL_SSL_ARGS% --default-character-set=utf8mb4 < "%SQL_FILE%" 2>"%MYSQL_ERR%"
if errorlevel 1 (
    echo   ERROR: mysql import failed. Error output:
    type "%MYSQL_ERR%" 2>nul
    del "%MYSQL_ERR%" 2>nul
    echo.
    echo   Retry manually:
    echo     mysql -u %DB_USER% -p -h %DB_HOST% -P %DB_PORT% %MYSQL_SSL_ARGS% ^< %SQL_FILE%
    pause
    exit /b 1
)
del "%MYSQL_ERR%" 2>nul
echo   Database reset complete.

:: ------------------------------------------------------------------
:: 3. Prompt for player name (Enter = default "gabriel")
:: ------------------------------------------------------------------
echo.
echo =================================================================
echo   Player name (press Enter for default 'gabriel'):
echo =================================================================
set /p PLAYER_NAME_INPUT="  > "
if "%PLAYER_NAME_INPUT%"=="" (
    set "PLAYER_NAME=gabriel"
) else (
    set "PLAYER_NAME=%PLAYER_NAME_INPUT%"
)
echo   Player: %PLAYER_NAME%

:: ------------------------------------------------------------------
:: 4. Start camo_server.py using the egvenv Python directly
:: ------------------------------------------------------------------
echo.
echo ================================================================
echo   Starting camo_server.py on http://0.0.0.0:5001 (Player: %PLAYER_NAME%)
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
