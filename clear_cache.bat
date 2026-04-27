@echo off
chcp 65001 >nul
echo ==========================================
echo  CryptoBot v11 — Cache Cleaner
echo ==========================================
echo.

echo [1/4] Deleting __pycache__ folders...
for /d /r . %%d in (__pycache__) do @if exist "%%d" (
    echo   - Removing: %%d
    rd /s /q "%%d"
)
echo   Done.
echo.

echo [2/4] Deleting .pyc files...
for /r . %%f in (*.pyc) do @if exist "%%f" (
    echo   - Removing: %%f
    del /q "%%f"
)
echo   Done.
echo.

echo [3/4] Deleting .pyo files...
for /r . %%f in (*.pyo) do @if exist "%%f" (
    echo   - Removing: %%f
    del /q "%%f"
)
echo   Done.
echo.

echo [4/4] Deleting logs older than 7 days...
forfiles /p logs /s /m *.log /d -7 /c "cmd /c del @path" 2>nul
echo   Done.
echo.

echo ==========================================
echo  Cache cleaned successfully!
echo  You can now run: python main.py
echo ==========================================
pause
