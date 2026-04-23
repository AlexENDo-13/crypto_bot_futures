import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


class StateManager:
    """Управление состоянием бота (паттерны, кэш, настройки)."""

    def __init__(self, state_file: str = "data/bot_state.json"):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state: Dict[str, Any] = {"last_update": 0, "patterns": {}}
        self._load()

    def _load(self) -> None:
        if not self.state_file.exists():
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                self._state = json.load(f)
        except Exception:
            pass

    def _save(self) -> None:
        self._state["last_update"] = time.time()
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._state[key] = value
        self._save()

    def update_pattern(self, name: str, data: Dict[str, Any]) -> None:
        if "patterns" not in self._state:
            self._state["patterns"] = {}
        self._state["patterns"][name] = data
        self._save()

    def get_pattern(self, name: str) -> Optional[Dict[str, Any]]:
        return self._state.get("patterns", {}).get(name)
