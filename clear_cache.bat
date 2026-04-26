@echo off
chcp 65001 >nul
echo ==========================================
echo  CryptoBot Cache Cleaner v1.0
echo ==========================================
echo.

echo [1/8] Cleaning src\exchange\__pycache__ ...
if exist "src\exchange\__pycache__" (
    rd /s /q "src\exchange\__pycache__"
    echo     OK
) else (
    echo     Already clean
)

echo [2/8] Cleaning src\core\__pycache__ ...
if exist "src\core\__pycache__" (
    rd /s /q "src\core\__pycache__"
    echo     OK
) else (
    echo     Already clean
)

echo [3/8] Cleaning src\coreisk\__pycache__ ...
if exist "src\coreisk\__pycache__" (
    rd /s /q "src\coreisk\__pycache__"
    echo     OK
) else (
    echo     Already clean
)

echo [4/8] Cleaning src\core\market\__pycache__ ...
if exist "src\core\market\__pycache__" (
    rd /s /q "src\core\market\__pycache__"
    echo     OK
) else (
    echo     Already clean
)

echo [5/8] Cleaning src\core\scanner\__pycache__ ...
if exist "src\core\scanner\__pycache__" (
    rd /s /q "src\core\scanner\__pycache__"
    echo     OK
) else (
    echo     Already clean
)

echo [6/8] Cleaning src\core\executor\__pycache__ ...
if exist "src\core\executor\__pycache__" (
    rd /s /q "src\core\executor\__pycache__"
    echo     OK
) else (
    echo     Already clean
)

echo [7/8] Cleaning src\core\exit\__pycache__ ...
if exist "src\core\exit\__pycache__" (
    rd /s /q "src\core\exit\__pycache__"
    echo     OK
) else (
    echo     Already clean
)

echo [8/8] Cleaning src\core	rading\__pycache__ ...
if exist "src\core	rading\__pycache__" (
    rd /s /q "src\core	rading\__pycache__"
    echo     OK
) else (
    echo     Already clean
)

echo.
echo [9/8] Cleaning src\core\engine\__pycache__ ...
if exist "src\core\engine\__pycache__" (
    rd /s /q "src\core\engine\__pycache__"
    echo     OK
) else (
    echo     Already clean
)

echo.
echo [10/8] Cleaning .pyc files ...
for /r %%i in (*.pyc) do del /q "%%i" 2>nul
echo     OK

echo.
echo [11/8] Cleaning __pycache__ recursively ...
for /d /r %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d" 2>nul
)
echo     OK

echo.
echo ==========================================
echo  Cache cleared successfully!
echo ==========================================
echo.
pause
