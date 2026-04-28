import os
import base64

output_file = "project_base64.txt"
root_dir = "."
exclude_dirs = {'.git', '__pycache__', 'venv', '.venv', 'env', 'logs', 'data', 'sessions'}

with open(output_file, 'w', encoding='utf-8') as out:
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fname in filenames:
            if fname.endswith('.py'):
                full_path = os.path.join(dirpath, fname)
                relative_path = os.path.relpath(full_path, root_dir)
                try:
                    with open(full_path, 'rb') as f:
                        content = f.read()
                    encoded = base64.b64encode(content).decode('utf-8')
                    out.write(f"FILE: {relative_path}\n")
                    out.write(encoded + "\n")
                    out.write("=" * 60 + "\n")  # разделитель
                except Exception as e:
                    out.write(f"FILE: {relative_path}\n")
                    out.write(f"# ERROR: {e}\n")
                    out.write("=" * 60 + "\n")

print(f"Создан {output_file}. Отправь его содержимое в чат.")
