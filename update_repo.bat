@echo off
echo 🔄 Обновление репозитория...
where git >nul 2>&1 || (echo ❌ Git не установлен & pause & exit /b 1)
if not exist ".git" (git init & set /p REPO_URL="URL: " & git remote add origin %REPO_URL%)
git add -A
set /p MSG="Сообщение: "
if "%MSG%"=="" set MSG="Обновление бота"
git commit -m "%MSG%" || echo Нет изменений
git push -u origin main || git push -u origin master
echo ✅ Готово!
pause
