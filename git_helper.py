#!/usr/bin/env python3
"""
Git Helper — утилита для быстрого обновления репозитория на GitHub
(c) для торгового бота Crypto Bot Futures
"""
import os
import sys
import subprocess
from datetime import datetime


class GitHelper:
    def __init__(self):
        self.repo_path = self._find_repo_root()
        if not self.repo_path:
            print("❌ Не найден Git репозиторий. Убедитесь, что вы в папке проекта.")
            sys.exit(1)

        os.chdir(self.repo_path)
        self.current_branch = self._get_current_branch()
        self.last_output = ""

    def _find_repo_root(self):
        """Находит корень Git репозитория, начиная с текущей папки"""
        try:
            output = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
            return output
        except:
            return None

    def _get_current_branch(self):
        try:
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                text=True
            ).strip()
            return branch if branch else "main"
        except:
            return "main"

    def _run_git(self, args, capture=True):
        """Запускает git команду и возвращает результат"""
        try:
            if capture:
                result = subprocess.run(
                    ["git"] + args,
                    capture_output=True,
                    text=True,
                    check=False
                )
                self.last_output = result.stdout + result.stderr
                return result.returncode == 0, self.last_output
            else:
                subprocess.run(["git"] + args, check=True)
                return True, ""
        except subprocess.CalledProcessError as e:
            self.last_output = str(e)
            return False, str(e)

    def show_status(self):
        """Показывает статус репозитория"""
        print(f"\n📁 Репозиторий: {self.repo_path}")
        print(f"🌿 Текущая ветка: {self.current_branch}\n")

        success, output = self._run_git(["status", "--short"])
        if output.strip():
            print("📝 Изменённые файлы:")
            print(output)
        else:
            print("✅ Нет изменений для коммита.")

        # Проверяем, есть ли незапушенные коммиты
        success, ahead = self._run_git(["rev-list", "--count", f"origin/{self.current_branch}..{self.current_branch}"])
        if success and ahead.strip().isdigit() and int(ahead.strip()) > 0:
            print(f"⚠️ Локальная ветка опережает origin на {ahead.strip()} коммит(ов).")

    def add_all(self):
        """Добавляет все изменения (git add -A)"""
        print("➕ Добавление всех изменений...")
        success, output = self._run_git(["add", "-A"])
        if success:
            print("✅ Файлы добавлены в индекс.")
        else:
            print("❌ Ошибка при добавлении файлов:")
            print(output)

    def commit(self, message=None):
        """Создаёт коммит"""
        if not message:
            # Предлагаем варианты сообщения
            print("\n📌 Выберите тип коммита:")
            print("1. 🔧 fix: исправление ошибок")
            print("2. ✨ feat: новая функция")
            print("3. 📝 docs: документация")
            print("4. ♻️ refactor: переработка кода")
            print("5. 🚀 perf: оптимизация")
            print("6. 🧪 test: тесты")
            print("7. 🛠️ chore: рутинные задачи")
            print("8. ➕ Ввести своё сообщение")

            choice = input("Ваш выбор (1-8, или Enter для авто-даты): ").strip()

            if choice == "8":
                message = input("Введите сообщение коммита: ").strip()
            elif choice in ("1","2","3","4","5","6","7"):
                prefix_map = {
                    "1": "fix", "2": "feat", "3": "docs", "4": "refactor",
                    "5": "perf", "6": "test", "7": "chore"
                }
                desc = input("Краткое описание: ").strip()
                message = f"{prefix_map[choice]}: {desc}" if desc else f"{prefix_map[choice]}: update"
            else:
                message = f"Auto-update {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        if not message:
            message = f"Update {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        print(f"💬 Коммит: {message}")
        success, output = self._run_git(["commit", "-m", message])
        if success:
            print("✅ Коммит создан.")
        else:
            if "nothing to commit" in output:
                print("ℹ️ Нет изменений для коммита.")
            else:
                print("❌ Ошибка при создании коммита:")
                print(output)

    def push(self):
        """Отправляет изменения на GitHub"""
        print(f"🚀 Отправка ветки '{self.current_branch}' на origin...")
        success, output = self._run_git(["push", "origin", self.current_branch], capture=False)
        # capture=False для интерактивного ввода пароля/токена
        if success:
            print("✅ Изменения отправлены на GitHub.")
        else:
            print("❌ Ошибка при push. Проверьте подключение или авторизацию.")
            if "authentication" in self.last_output.lower():
                print("💡 Возможно, требуется ввести токен доступа GitHub.")

    def show_log(self, count=5):
        """Показывает последние коммиты"""
        print(f"\n📜 Последние {count} коммитов в ветке {self.current_branch}:")
        success, output = self._run_git([
            "log", f"-{count}", "--oneline", "--decorate", "--graph"
        ])
        if success:
            print(output if output.strip() else "Нет коммитов.")
        else:
            print("Ошибка получения истории.")

    def undo_last_commit(self):
        """Отмена последнего коммита (soft reset)"""
        confirm = input("⚠️ Отменить последний коммит (изменения останутся в рабочей папке)? (y/N): ").strip().lower()
        if confirm == 'y':
            success, output = self._run_git(["reset", "--soft", "HEAD~1"])
            if success:
                print("✅ Последний коммит отменён. Файлы возвращены в индекс.")
            else:
                print("❌ Не удалось отменить коммит:")
                print(output)

    def run(self):
        """Главное меню"""
        while True:
            print("\n" + "="*50)
            print(f"🐙 GIT HELPER — {self.repo_path}")
            print(f"🌿 Ветка: {self.current_branch}")
            print("="*50)
            print("1. 📋 Показать статус")
            print("2. ➕ Добавить все изменения (git add -A)")
            print("3. 💾 Закоммитить изменения")
            print("4. 🚀 Отправить на GitHub (git push)")
            print("5. ⚡ Полный цикл: добавить → коммит → пуш")
            print("6. 📜 История последних коммитов")
            print("7. ↩️ Отменить последний коммит (soft)")
            print("8. 🚪 Выход")
            print("-"*50)

            choice = input("Выберите действие (1-8): ").strip()

            if choice == "1":
                self.show_status()
            elif choice == "2":
                self.add_all()
            elif choice == "3":
                self.commit()
            elif choice == "4":
                self.push()
            elif choice == "5":
                self.add_all()
                self.commit()
                self.push()
            elif choice == "6":
                self.show_log()
            elif choice == "7":
                self.undo_last_commit()
            elif choice == "8":
                print("👋 До встречи!")
                break
            else:
                print("❌ Неверный выбор. Попробуйте снова.")

            input("\n⏎ Нажмите Enter для продолжения...")


if __name__ == "__main__":
    helper = GitHelper()
    helper.run()
