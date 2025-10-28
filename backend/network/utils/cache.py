"""
Кэширование для сканера
"""
import os
import hashlib
import json

DEFAULT_CACHE_DIR = "cache/crtsh"

def get_cache_path(cache_dir: str, key: str) -> str:
    """Генерирует путь к файлу кэша"""
    h = hashlib.sha1(key.encode()).hexdigest()
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{h}.json")

def load_from_cache(cache_path: str):
    """Загрузить данные из кэша"""
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def save_to_cache(cache_path: str, data):
    """Сохранить данные в кэш"""
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass
