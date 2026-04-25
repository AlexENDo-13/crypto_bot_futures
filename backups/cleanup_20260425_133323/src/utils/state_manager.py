#!/usr/bin/env python3
import json, os

class StateManager:
    def __init__(self, state_path="data/state.json"):
        self.state_path = state_path; os.makedirs(os.path.dirname(state_path), exist_ok=True)
    def save(self, state):
        try:
            with open(self.state_path, "w", encoding="utf-8") as f: json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e: print(f"Ошибка сохранения состояния: {e}")
    def load(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f: return json.load(f)
            except Exception: pass
        return {}
