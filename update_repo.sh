#!/bin/bash
set -e
echo "🔄 Обновление репозитория..."
if ! command -v git &> /dev/null; then
    echo "❌ Git не установлен"
    exit 1
fi
if [ ! -d ".git" ]; then
    git init
    read -p "URL репозитория: " REPO_URL
    git remote add origin "$REPO_URL"
fi
git add -A
read -p "Сообщение коммита: " MSG
if [ -z "$MSG" ]; then
    MSG="Обновление бота"
fi
git commit -m "$MSG" || echo "Нет изменений"
git push -u origin main || git push -u origin master
echo "✅ Готово!"
