import os
import base64

OUTPUT_FILE = "project_base64.txt"
ROOT_DIR = "."

# Папки, которые не нужно сканировать
EXCLUDE_DIRS = {'.git', '__pycache__', 'venv', '.venv', 'env', 'logs', 'data', 'sessions', 'backups'}

# Файлы, которые уже удалены из репозитория (содержали ключи)
FORBIDDEN_FILES = {
    "test_keys.py",
    "test_bingx_api.py",
    "bingx_api_test.py",
    "test_signature.py",
    # добавьте любые другие файлы, которые нельзя включать в дамп
}

# Также исключаем сам выходной файл, чтобы не "зациклиться"
FORBIDDEN_FILES.add(OUTPUT_FILE)

def file_contains_secrets(filepath):
    """
    Простая эвристика: если в тексте файла встречается подозрительно длинная строка,
    похожая на ключ (например, 'api_secret = "..." длиной > 30 символов).
    Возвращает True, если файл подозрителен.
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Ищем строки вида: SECRET = "длинная_последовательность"
            if 'api_secret' in content.lower() and len(content) > 200:
                # Грубая проверка, можно доработать
                return True
    except:
        pass
    return False

def should_include(full_path, relative_path):
    # Исключаем запрещённые файлы по имени
    if relative_path in FORBIDDEN_FILES:
        return False, "explicitly excluded"
    # Исключаем если в имени есть подозрительные слова (дополнительная защита)
    name = os.path.basename(full_path).lower()
    if any(kw in name for kw in ['secret', 'credential', 'api_key', 'private_key']):
        return False, "sensitive name"
    # Проверка содержимого (лёгкая) - если файл содержит похожий на секрет паттерн
    if file_contains_secrets(full_path):
        return False, "possible secrets inside"
    return True, ""

with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
    for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
        # Фильтруем директории
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

        for fname in filenames:
            if fname.endswith('.py'):
                full_path = os.path.join(dirpath, fname)
                relative_path = os.path.relpath(full_path, ROOT_DIR)

                include, reason = should_include(full_path, relative_path)
                if not include:
                    print(f"SKIPPED: {relative_path} ({reason})")
                    continue

                try:
                    with open(full_path, 'rb') as f:
                        content = f.read()
                    encoded = base64.b64encode(content).decode('utf-8')
                    out.write(f"FILE: {relative_path}\n")
                    out.write(encoded + "\n")
                    out.write("=" * 60 + "\n")
                except Exception as e:
                    out.write(f"FILE: {relative_path}\n")
                    out.write(f"# ERROR: {e}\n")
                    out.write("=" * 60 + "\n")

print(f"Дамп создан: {OUTPUT_FILE}")
print("Внимание: новый дамп не содержит файлов с ключами. Проверьте его перед отправкой.")
