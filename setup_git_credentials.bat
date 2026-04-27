@echo off
chcp 65001 >nul
echo ==========================================
echo  CryptoBot v11 — Git Setup Helper
echo ==========================================
echo.

set REPO_PATH=C:\Users\AlexENDo\Desktop\crypto_bot_futures

cd /d "%REPO_PATH%"
if errorlevel 1 (
    echo ERROR: Cannot find repo at %REPO_PATH%
    pause
    exit /b 1
)

echo [1/5] Setting git user name...
git config --global user.name "AlexENDo-13"
echo   Done.

echo [2/5] Setting git user email...
git config --global user.email "your_email@example.com"
echo   Done.

echo [3/5] Setting default branch name...
git config --global init.defaultBranch main
echo   Done.

echo [4/5] Checking remote origin...
git remote -v
echo.

echo [5/5] Testing connection...
git ls-remote --heads origin 2>nul
if errorlevel 1 (
    echo.
    echo WARNING: Cannot connect to remote.
    echo You may need to set up a Personal Access Token.
    echo.
    echo Steps:
    echo   1. Go to https://github.com/settings/tokens
    echo   2. Click "Generate new token (classic)"
    echo   3. Select scopes: repo
    echo   4. Copy the token
    echo   5. Run:
    echo      git remote set-url origin https://AlexENDo-13:YOUR_TOKEN@github.com/AlexENDo-13/crypto_bot_futures.git
    echo.
) else (
    echo   Connection OK!
)

echo.
echo ==========================================
echo  Git setup complete!
echo ==========================================
pause
