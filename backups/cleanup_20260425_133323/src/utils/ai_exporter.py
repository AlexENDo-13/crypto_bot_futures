#!/usr/bin/env python3
import json, os
from datetime import datetime

class AIExporter:
    def __init__(self, export_dir="src/data/ai_exports"):
        self.export_dir = export_dir; os.makedirs(export_dir, exist_ok=True)
    def export_full_state(self, state):
        filename = f"AI_FULL_Export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        path = os.path.join(self.export_dir, filename)
        with open(path, "w", encoding="utf-8") as f: json.dump(state, f, indent=2, ensure_ascii=False)
        return path
