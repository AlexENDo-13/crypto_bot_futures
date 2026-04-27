@echo off
chcp 65001 >nul
echo ==========================================
echo  CryptoBot v11 — Push to GitHub
echo ==========================================
echo.

REM === CONFIG ===
set REPO_PATH=C:\Users\AlexENDo\Desktop\crypto_bot_futures
set BRANCH=main
set COMMIT_MSG=Update v11.0
REM ================

cd /d "%REPO_PATH%"
if errorlevel 1 (
    echo ERROR: Cannot find repo at %REPO_PATH%
    echo Please edit this file and set correct REPO_PATH
    pause
    exit /b 1
)

echo [1/7] Checking git status...
git status --short
echo.

echo [2/7] Adding all changes...
git add -A
echo   Done.
echo.

echo [3/7] Creating commit...
git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo   WARNING: Nothing to commit or commit failed.
    echo   If no changes, this is OK.
)
echo.

echo [4/7] Pulling latest from remote...
git pull origin %BRANCH% --rebase
echo   Done.
echo.

echo [5/7] Pushing to GitHub...
git push origin %BRANCH%
if errorlevel 1 (
    echo.
    echo ERROR: Push failed!
    echo Possible reasons:
    echo   - No internet connection
    echo   - Wrong credentials
    echo   - Merge conflict
    echo.
    echo To fix credentials, run:
    echo   git config --global user.name "AlexENDo-13"
    echo   git config --global user.email "your@email.com"
    echo   git remote set-url origin https://AlexENDo-13:TOKEN@github.com/AlexENDo-13/crypto_bot_futures.git
    pause
    exit /b 1
)
echo   Done.
echo.

echo [6/7] Verifying remote...
git log --oneline -3
echo.

echo [7/7] Checking GitHub URL...
git remote -v
echo.

echo ==========================================
echo  SUCCESS! Changes pushed to GitHub
echo  Branch: %BRANCH%
echo  Repo: https://github.com/AlexENDo-13/crypto_bot_futures
echo ==========================================
pause
