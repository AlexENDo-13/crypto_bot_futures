import os
import json

class Settings:
    def __init__(self, config_path="config/bot_config.json"):
        self.config_path = config_path
        self._data = {
            "demo_mode": True,
            "virtual_balance": 100.0,
            "api_key": os.getenv("BINGX_API_KEY", ""),
            "api_secret": os.getenv("BINGX_API_SECRET", ""),
            "max_positions": 3,
            "pair_blacklist":[],
            "risk_per_trade": 1.0,
            "leverage": 10,
            "strategy_params": {}
        }
        self.load()

    # ВАЖНО: Это свойство исправляет ошибку UI (AttributeError: 'Settings' object has no attribute 'data')
    @property
    def data(self):
        return self._data

    def load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                try:
                    file_data = json.load(f)
                    self._data.update(file_data)
                except json.JSONDecodeError:
                    pass # Если файл сломан, используем дефолтные

    def save(self):
        # Гарантируем, что папка config существует
        os.makedirs(os.path.dirname(self.config_path) or '.', exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4, ensure_ascii=False)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def update(self, new_data: dict):
        self._data.update(new_data)
        self.save()

    def to_dict(self):
        return dict(self._data)
