"""
RDAP и WHOIS утилиты
"""
from ipwhois import IPWhois
import whois
from typing import Tuple, List

def rdap_lookup(ip: str) -> Tuple[str, str]:
    """
    RDAP lookup для IP
    Возвращает: (cidr, name)
    """
    # Твой существующий код
    obj = IPWhois(ip)
    res = obj.lookup_rdap()
    
    cidr = res['network']['cidr']
    name = res["network"]["name"]
    return cidr, name

def get_nameservers(domain: str) -> List[str]:
    """Получить NS-серверы"""
    # Твой существующий код
    w = whois.whois(domain)
    result = []
    for line in w.text.splitlines():
        line = line.strip()
        if line.lower().startswith("nserver:"):
            result.append(line.split(":", 1)[1].strip())
    return result