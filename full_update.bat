@echo off
chcp 65001 >nul
echo ==========================================
echo  CryptoBot v11 — FULL UPDATE (Cache + Push)
echo ==========================================
echo.

set REPO_PATH=C:\Users\AlexENDo\Desktop\crypto_bot_futures
set BRANCH=main
set COMMIT_MSG=Update v11.0

cd /d "%REPO_PATH%"
if errorlevel 1 (
    echo ERROR: Cannot find repo at %REPO_PATH%
    pause
    exit /b 1
)

echo [STEP 1/8] Clearing Python cache...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
for /r . %%f in (*.pyc) do @if exist "%%f" del /q "%%f"
for /r . %%f in (*.pyo) do @if exist "%%f" del /q "%%f"
echo   Cache cleared.
echo.

echo [STEP 2/8] Checking git status...
git status --short
echo.

echo [STEP 3/8] Adding all changes...
git add -A
echo   Done.
echo.

echo [STEP 4/8] Creating commit...
git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo   WARNING: Nothing to commit.
)
echo.

echo [STEP 5/8] Pulling latest from remote...
git pull origin %BRANCH% --rebase
echo   Done.
echo.

echo [STEP 6/8] Pushing to GitHub...
git push origin %BRANCH%
if errorlevel 1 (
    echo.
    echo ERROR: Push failed! Check credentials.
    pause
    exit /b 1
)
echo   Done.
echo.

echo [STEP 7/8] Verifying...
git log --oneline -3
echo.

echo [STEP 8/8] You can now run the bot:
echo   python main.py
echo.

echo ==========================================
echo  FULL UPDATE COMPLETE!
echo  Repo: https://github.com/AlexENDo-13/crypto_bot_futures
echo ==========================================
pause
