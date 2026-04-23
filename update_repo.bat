@echo off
chcp 65001 >nul
REM update_repo.bat — скрипт обновления репозитория на GitHub (Windows)

echo 🔄 Обновление репозитория...

REM Проверка git
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Git не установлен. Скачайте с https://git-scm.com/
    pause
    exit /b 1
)

REM Проверка инициализации
if not exist ".git" (
    echo ⚠️ Git не инициализирован. Инициализирую...
    git init
    set /p REPO_URL="Введите URL репозитория (например: https://github.com/username/repo.git): "
    git remote add origin %REPO_URL%
)

REM Проверка remote
git remote get-url origin >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️ Remote origin не настроен.
    set /p REPO_URL="Введите URL репозитория: "
    git remote add origin %REPO_URL%
)

REM Добавление файлов
echo 📦 Добавление файлов...
git add -A

REM Коммит
echo 📝 Создание коммита...
set /p MSG="Введите сообщение коммита (или Enter для дефолтного): "
if "%MSG%"=="" set MSG="Обновление бота: исправлены API, риск-менеджмент, адаптация под малый депозит"
git commit -m "%MSG%" || echo ⚠️ Нет изменений для коммита

REM Push
echo 🚀 Push на GitHub...
git push -u origin main || git push -u origin master || (
    echo ❌ Push не удался. Проверьте credentials:
    echo    git config --global user.name "Your Name"
    echo    git config --global user.email "your@email.com"
    echo    git remote set-url origin https://USERNAME:TOKEN@github.com/USERNAME/REPO.git
    pause
    exit /b 1
)

echo ✅ Репозиторий успешно обновлён!
pause
