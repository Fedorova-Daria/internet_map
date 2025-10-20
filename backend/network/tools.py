import requests
import time
import json
import os
import hashlib
import whois
from ipwhois import IPWhois
import dns.resolver, dns.reversename
from typing import List, Set, Tuple, Dict, Optional
import socket
import ssl
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import datetime


DEFAULT_CACHE_DIR = "cache/crtsh"
DEFAULT_SLEEP = 1.0


def get_domains_from_ip_reverse_dns(ip: str) -> List[str]:
    """
    Делает обратный DNS-запрос (PTR) по IP и возвращает список доменов.
    Если PTR не найден или ошибка — возвращает пустой список.
    """
    name = dns.reversename.from_address(ip)
    try:
        ans = dns.resolver.resolve(name, 'PTR')
        return [r.to_text().rstrip('.') for r in ans]
    except Exception:
        return []


# Кэш с crt который предложил чат гпт
def _cache_path(cache_dir: str, key: str) -> str:
    h = hashlib.sha1(key.encode()).hexdigest()
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{h}.json")


def rdap_lookup(ip: str):
    obj = IPWhois(ip)
    res = obj.lookup_rdap()

    cidr = res['network']['cidr']
    name = res["network"]["name"]
    return cidr, name


# Получает json с crt.sh со связанными с доменом субдоменами
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
    cache_path = _cache_path(cache_dir, key)

    # try cache first
    if use_cache and os.path.exists(cache_path):
        try:
            if debug: print(f"[crtsh] loading from cache {cache_path}")
            return json.load(open(cache_path, "r", encoding="utf-8"))
        except Exception as e:
            if debug: print(f"[crtsh] cache load failed: {e}")

    url = f"https://crt.sh/json?q={domain}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; poc-crtsh/1.0; +https://example.invalid)",
        "Accept": "application/json, text/*;q=0.8, */*;q=0.1",
    }

    last_text_sample = None
    for attempt in range(1, max_retries + 1):
        try:
            if debug: print(f"[crtsh] GET {url} (attempt {attempt})")
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
                        # cache
                        if use_cache:
                            try:
                                json.dump(data, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)
                            except Exception:
                                pass
                        time.sleep(sleep_sec)
                        return data
                    except ValueError:
                        # sometimes it's almost-json or corrupted; we'll try to salvage below
                        if debug: print("[crtsh] JSON decode failed, will try to salvage")
                # fallback: attempt to extract JSON array substring from body
                try:
                    # find first '[' and last ']' — crude but often works when server wraps JSON into HTML
                    start = body.find('[')
                    end = body.rfind(']')
                    if start != -1 and end != -1 and end > start:
                        possible = body[start:end+1]
                        data = json.loads(possible)
                        if use_cache:
                            try:
                                json.dump(data, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)
                            except Exception:
                                pass
                        time.sleep(sleep_sec)
                        return data
                except Exception as ex:
                    if debug: print(f"[crtsh] salvage JSON failed: {ex}")
                # final fallback: no JSON available
                if debug:
                    print(f"[crtsh] status=200 but no JSON parsed. sample:\n{last_text_sample[:400]}")
                return []
            elif status in (429, 503):
                # rate limited or service unavailable — backoff
                if debug: print(f"[crtsh] status {status} — backoff and retry")
                time.sleep(sleep_sec * attempt)
                continue
            else:
                if debug: print(f"[crtsh] unexpected status {status}. sample:\n{last_text_sample[:400]}")
                time.sleep(sleep_sec * attempt)
                continue
        except requests.RequestException as e:
            if debug: print(f"[crtsh] request exception: {e}")
            time.sleep(sleep_sec * attempt)
            continue

    # exhausted retries — log sample if debug
    if debug:
        print("[crtsh] exhausted retries. last sample (first 1000 chars):")
        print(last_text_sample or "<no response>")
    return []


def extract_common_names(crtsh_json):
    """
    При наличии crt.sh JSON (списка словарей) возвращает отсортированный уникальный список значений common_name.
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


def get_nameservers(domain: str):
    w = whois.whois(domain)
    result = []
    for line in w.text.splitlines():
        line = line.strip()
        if line.lower().startswith("nserver:"):
            # берём всё после 'nserver:'
            result.append(line.split(":", 1)[1].strip())
    return result


def extract_base_domains(subdomains: List[str]) -> List[str]:
    """
    Из списка субдоменов возвращает уникальные базовые домены.
    Например, ['mail.tyuiu.ru', 'www.tyuiu.ru'] -> ['tyuiu.ru']
    """
    base_domains: Set[str] = set()
    for sub in subdomains:
        parts = sub.strip().split('.')
        if len(parts) >= 2:
            base_domains.add('.'.join(parts[-2:]))  # берём последние два элемента
    return list(base_domains)


def get_ip_from_domain(domain: str):
    """
    Возвращает список IP для домена (A-записи)
    """
    try:
        answers = dns.resolver.resolve(domain, 'A')
        return [r.to_text() for r in answers]
    except Exception:
        return []


def grab_tls_names(ip: str,
                   port: int = 443,
                   server_name: Optional[str] = None,
                   timeout: float = 5.0,
                   try_sni_first: bool = True,
                   follow_cn: bool = True) -> Tuple[Set[str], Dict]:
    """
    Активно подключиться к ip:port, выполнить TLS-рукопожатие и извлечь имена сертификатов.

        Возвращает:
        (names_set, meta_dict)

        names_set: набор доменных имён (в нижнем регистре, без конечной точки)
        meta_dict: {
        'ip': ip,
        'port': port,
        'server_name_used': server_name_or_ip,
        'connected': True/False,
        'error': необязательная строка ошибки,
        'cert_not_before': ..., 'cert_not_after': ...,
        'raw_cn': необязательный CN или None,
        'raw_sans': [..] или [],
        'fetched_at': временная метка iso
        }

        Примечания:
        - server_name: необязательный домен для SNI. Если None, SNI будет IP (может работать со сбоями на многих хостах).
        - try_sni_first: если True и указано имя_сервера, при рукопожатии сначала используется этот SNI.
        - follow_cn: включить CN в результаты, если SAN отсутствует или является дополнительным (CN может дублироваться).
    """

    meta = {
        'ip': ip,
        'port': port,
        'server_name_used': None,
        'connected': False,
        'error': None,
        'raw_cn': None,
        'raw_sans': [],
        'cert_not_before': None,
        'cert_not_after': None,
        'fetched_at': datetime.datetime.utcnow().isoformat() + 'Z',
    }
    names = set()

    # Decide SNI: use provided server_name, otherwise use ip (string)
    sni_name = server_name if server_name else ip
    meta['server_name_used'] = sni_name

    # Create SSL context that does NOT verify certificates (we only want cert)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # create socket and wrap with TLS
    sock = None
    ssock = None
    try:
        sock = socket.create_connection((ip, port), timeout=timeout)
        sock.settimeout(timeout)
        # Wrap socket with TLS; SNI set by server_hostname parameter
        ssock = ctx.wrap_socket(sock, server_hostname=sni_name)
        # If handshake succeeded, get peer cert in DER form
        der = ssock.getpeercert(binary_form=True)
        meta['connected'] = True

        # parse certificate
        cert = x509.load_der_x509_certificate(der, default_backend())

        # validity
        try:
            not_before = cert.not_valid_before_utc
            not_after = cert.not_valid_after_utc
            # convert to iso
            meta['cert_not_before'] = not_before.isoformat()
            meta['cert_not_after'] = not_after.isoformat()
        except Exception:
            pass

        # Subject CN (may be absent or deprecated)
        try:
            cn_attributes = cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
            if cn_attributes:
                cn = cn_attributes[0].value
                meta['raw_cn'] = cn
                if follow_cn:
                    names.add(cn.lower().rstrip('.'))
        except Exception:
            pass

        # SANs
        try:
            ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            dnsnames = ext.value.get_values_for_type(x509.DNSName)
            for d in dnsnames:
                if d:
                    names.add(d.lower().rstrip('.'))
            meta['raw_sans'] = list(dnsnames)
        except Exception:
            # no SAN ext
            meta['raw_sans'] = []

    except Exception as e:
        meta['error'] = str(e)
    finally:
        try:
            if ssock:
                ssock.close()
        except Exception:
            pass
        try:
            if sock:
                sock.close()
        except Exception:
            pass

    return names, meta


# -------------------------
# Простое DNS resolve + CNAME follow
# -------------------------
def resolve_domain_a_aaaa(domain: str, follow_cname: bool = True, max_cname: int = 5, timeout: float = 3.0):
    """
    Возвращает (set of ips, list of cname_chain)
    """
    domain = domain.strip().rstrip('.')
    ips = set()
    cname_chain = []
    try:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = timeout
        resolver.timeout = timeout

        cur = domain
        for depth in range(max_cname):
            # сначала A
            try:
                ans = resolver.resolve(cur, 'A', raise_on_no_answer=False)
                if ans:
                    for r in ans:
                        ips.add(r.to_text())
                # AAAA
                ans6 = resolver.resolve(cur, 'AAAA', raise_on_no_answer=False)
                if ans6:
                    for r in ans6:
                        ips.add(r.to_text())
            except dns.exception.DNSException:
                pass

            if not follow_cname:
                break

            # check CNAME
            try:
                cname_ans = resolver.resolve(cur, 'CNAME', raise_on_no_answer=False)
                if cname_ans:
                    # берем первую цель
                    target = cname_ans[0].to_text().rstrip('.')
                    cname_chain.append((cur, target))
                    cur = target
                    continue
            except dns.exception.DNSException:
                pass
            break  # нет CNAME, выходим
    except Exception:
        pass
    return ips, cname_chain


# --------------------------
# Примеры использования:
# --------------------------
if __name__ == "__main__":
    input()

