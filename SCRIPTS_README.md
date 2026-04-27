# 🔧 Скрипты для управления ботом

## Windows (.bat)

### 1. clear_cache.bat — Очистка кэша Python
```
Двойной клик → очистит __pycache__, .pyc, .pyo, старые логи
```
**Запускай перед каждым запуском бота после обновления файлов!**

### 2. push_to_github.bat — Отправка изменений на GitHub
```
Двойной клик → git add → commit → pull → push
```
**Перед первым использованием:**
1. Открой файл в блокноте
2. Измени `REPO_PATH` на свой путь (если отличается)
3. Сохрани

### 3. setup_git_credentials.bat — Настройка Git
```
Двойной клик → настраивает git name/email, проверяет соединение
```
**Запускай один раз после установки Git.**

### 4. full_update.bat — Полное обновление
```
Двойной клик → очистка кэша + git commit + push
```
**Удобно когда обновил много файлов и хочешь всё сразу запушить.**

---

## Linux/Mac (.sh)

```bash
chmod +x clear_cache.sh push_to_github.sh
./clear_cache.sh
./push_to_github.sh
```

---

## 🔐 Настройка токена GitHub (обязательно для push)

GitHub больше не принимает пароль — нужен **Personal Access Token**.

### Шаги:
1. Зайди: https://github.com/settings/tokens
2. Нажми **"Generate new token (classic)"**
3. Дай имя: `CryptoBot`
4. Выбери scope: ✅ **repo** (полный доступ к репозиториям)
5. Нажми **Generate token**
6. **Скопируй токен сразу** (он показывается только один раз!)
7. В командной строке выполни:
```cmd
cd C:\Users\AlexENDo\Desktop\crypto_bot_futures
git remote set-url origin https://AlexENDo-13:ТВОЙ_ТОКЕН@github.com/AlexENDo-13/crypto_bot_futures.git
```

### Проверка:
```cmd
git remote -v
```
Должно показать URL с токеном (токен будет замаскирован).

---

## 🚀 Типичный рабочий процесс

### Обновил файлы бота → хочешь запушить:
```
1. Закрой бота (если запущен)
2. Двойной клик: full_update.bat
3. Готово!
```

### Просто очистить кэш и запустить:
```
1. Двойной клик: clear_cache.bat
2. python main.py
```

### Обновил только 1-2 файла:
```
1. Двойной клик: push_to_github.bat
2. Готово!
```
