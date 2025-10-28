"""
Модуль для работы с crt.sh API
"""
import requests
import time
import json
import os   
from typing import List
from .cache import get_cache_path, load_from_cache, save_to_cache, DEFAULT_CACHE_DIR

DEFAULT_SLEEP = 1.0

def fetch_crtsh_json(domain: str,
                     cache_dir: str = DEFAULT_CACHE_DIR,
                     use_cache: bool = True,
                     max_retries: int = 3,
                     timeout: int = 20,
                     sleep_sec: float = DEFAULT_SLEEP,
                     debug: bool = False):
    """
    Fetch crt.sh JSON for a domain and return parsed Python object (list of dicts).
    - domain: e.g. "tyuiu.ru" or "example.com"
    - use_cache: if True, read/write cache files in cache_dir
    - max_retries: retry attempts on transient errors
    - timeout: HTTP timeout in seconds
    - sleep_sec: politeness pause after successful fetch
    - debug: print diagnostics
    Returns: list (parsed JSON) or [] on failure.
    """
    key = f"crtsh:{domain}"
    cache_path = get_cache_path(cache_dir, key)

    # try cache first
    if use_cache and os.path.exists(cache_path):
        try:
            if debug: 
                print(f"[crtsh] loading from cache {cache_path}")
            # ИСПРАВЛЕНО: использован контекстный менеджер with
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            if debug: 
                print(f"[crtsh] cache load failed: {e}")

    url = f"https://crt.sh/json?q={domain}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; network-scanner/1.0)",
        "Accept": "application/json, text/*;q=0.8, */*;q=0.1",
    }

    last_text_sample = None
    for attempt in range(1, max_retries + 1):
        try:
            if debug: 
                print(f"[crtsh] GET {url} (attempt {attempt})")
            r = requests.get(url, headers=headers, timeout=timeout)
            last_text_sample = (r.text or "")[:2000]
            status = r.status_code

            if status == 200:
                # If likely JSON, parse it
                ctype = r.headers.get("Content-Type", "").lower()
                body = r.text.strip()
                if "application/json" in ctype or body.startswith("["):
                    try:
                        data = r.json()
                        # cache - ИСПРАВЛЕНО: использован контекстный менеджер
                        if use_cache:
                            try:
                                with open(cache_path, "w", encoding="utf-8") as f:
                                    json.dump(data, f, ensure_ascii=False)
                            except Exception:
                                pass
                        time.sleep(sleep_sec)
                        return data
                    except ValueError:
                        if debug: 
                            print("[crtsh] JSON decode failed, will try to salvage")
                
                # fallback: attempt to extract JSON array substring from body
                try:
                    start = body.find('[')
                    end = body.rfind(']')
                    if start != -1 and end != -1 and end > start:
                        possible = body[start:end+1]
                        data = json.loads(possible)
                        # ИСПРАВЛЕНО: использован контекстный менеджер
                        if use_cache:
                            try:
                                with open(cache_path, "w", encoding="utf-8") as f:
                                    json.dump(data, f, ensure_ascii=False)
                            except Exception:
                                pass
                        time.sleep(sleep_sec)
                        return data
                except Exception as ex:
                    if debug: 
                        print(f"[crtsh] salvage JSON failed: {ex}")
                
                # final fallback: no JSON available
                if debug:
                    print(f"[crtsh] status=200 but no JSON parsed. sample:\n{last_text_sample[:400]}")
                return []
            
            elif status in (429, 503):
                # rate limited or service unavailable — backoff
                if debug: 
                    print(f"[crtsh] status {status} — backoff and retry")
                time.sleep(sleep_sec * attempt)
                continue
            else:
                if debug: 
                    print(f"[crtsh] unexpected status {status}. sample:\n{last_text_sample[:400]}")
                time.sleep(sleep_sec * attempt)
                continue
        except requests.RequestException as e:
            if debug: 
                print(f"[crtsh] request exception: {e}")
            time.sleep(sleep_sec * attempt)
            continue

    # exhausted retries — log sample if debug
    if debug:
        print("[crtsh] exhausted retries. last sample (first 1000 chars):")
        print(last_text_sample or "<no response>")
    return []


def extract_common_names(crtsh_json) -> List[str]:
    """
    При наличии crt.sh JSON (списка словарей) возвращает отсортированный 
    уникальный список значений common_name.
    - Игнорирует записи без 'common_name'.
    - Нормализует до нижнего регистра и удаляет пробелы и точки в конце.
    """
    if not crtsh_json:
        return []
    names = set()
    for entry in crtsh_json:
        if not isinstance(entry, dict):
            continue
        cn = entry.get("common_name")
        if not cn:
            continue
        cn = cn.strip().lower().rstrip('.')
        if cn:
            names.add(cn)
    return sorted(names)
