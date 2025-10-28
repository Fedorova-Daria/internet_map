"""
DNS утилиты
"""
import dns.resolver
import dns.reversename
import dns.exception
from typing import List, Set, Tuple

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

def get_ip_from_domain(domain: str) -> List[str]:
    """Получить A-записи для домена"""
    try:
        answers = dns.resolver.resolve(domain, 'A')
        return [r.to_text() for r in answers]
    except Exception:
        return []

def get_domains_from_ip_reverse_dns(ip: str) -> List[str]:
    """Обратный DNS (PTR)"""
    # Твой существующий код
    name = dns.reversename.from_address(ip)
    try:
        ans = dns.resolver.resolve(name, 'PTR')
        return [r.to_text().rstrip('.') for r in ans]
    except Exception:
        return []

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