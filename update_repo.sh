#!/bin/bash
# update_repo.sh — скрипт обновления репозитория на GitHub

set -e

echo "🔄 Обновление репозитория..."

# Проверка наличия git
if ! command -v git &> /dev/null; then
    echo "❌ Git не установлен. Установите: sudo apt install git"
    exit 1
fi

# Проверка инициализации репозитория
if [ ! -d ".git" ]; then
    echo "⚠️ Git не инициализирован. Инициализирую..."
    git init
    echo "Введите URL репозитория (например: https://github.com/username/repo.git):"
    read REPO_URL
    git remote add origin "$REPO_URL"
fi

# Проверка remote
if ! git remote get-url origin &> /dev/null; then
    echo "⚠️ Remote origin не настроен."
    echo "Введите URL репозитория:"
    read REPO_URL
    git remote add origin "$REPO_URL"
fi

# Добавление файлов
echo "📦 Добавление файлов..."
git add -A

# Коммит
echo "📝 Создание коммита..."
read -p "Введите сообщение коммита (или Enter для дефолтного): " MSG
if [ -z "$MSG" ]; then
    MSG="Обновление бота: исправлены API, риск-менеджмент, адаптация под малый депозит"
fi
git commit -m "$MSG" || echo "⚠️ Нет изменений для коммита"

# Push
echo "🚀 Push на GitHub..."
git push -u origin main || git push -u origin master || {
    echo "❌ Push не удался. Проверьте credentials:"
    echo "   git config --global user.name 'Your Name'"
    echo "   git config --global user.email 'your@email.com'"
    echo "   git remote set-url origin https://USERNAME:TOKEN@github.com/USERNAME/REPO.git"
    exit 1
}

echo "✅ Репозиторий успешно обновлён!"
