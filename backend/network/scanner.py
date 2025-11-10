# backend/network/scanner.py

from collections import deque
from .models import Domain, IPAddress, Link
from .tools import (
    get_domains_from_ip_reverse_dns,
    rdap_lookup,
    fetch_crtsh_json,
    extract_common_names,
    grab_tls_names,
    resolve_domain_a_aaaa,
)
import logging

logger = logging.getLogger(__name__)

class InternetMapScanner:
    # ✅ Принимаем экземпляр сессии сканирования
    def __init__(self, session, max_depth=3, max_rate_limit=1.0):
        self.session = session # Сохраняем сессию
        self.max_depth = max_depth
        self.max_rate_limit = max_rate_limit
        self.visited_domains = set()
        self.visited_ips = set()
    
    def scan(self, root_domain: str):
        """Основной BFS алгоритм сканирования."""
        logger.info(f"Начинаем сканирование: {root_domain}")
        
        queue = deque([(root_domain, 0)])
        
        while queue:
            domain, depth = queue.popleft()
            
            logger.info(f"[Уровень {depth}] Сканируем: {domain}")
            
            if domain in self.visited_domains:
                logger.debug(f"Домен {domain} уже обработан, пропускаем")
                continue
            
            self.visited_domains.add(domain)
            
            if depth > self.max_depth:
                logger.info(f"Достигнут лимит глубины {self.max_depth}")
                break
            
            # ШАГ 1: DNS запрос
            ips = self._get_ips_for_domain(domain)
            logger.info(f"Найдено {len(ips)} IP адресов для {domain}: {ips}")
            
            for ip in ips:
                if ip not in self.visited_ips:
                    self.visited_ips.add(ip)
                    self._save_link(self.session, domain, ip, method='dns')
                    
                    # ШАГ 2: Reverse DNS
                    reverse_domains = self._get_reverse_domains(ip)
                    logger.info(f"Найдено {len(reverse_domains)} обратных доменов для IP {ip}")
                    
                    for rev_domain in reverse_domains:
                        if rev_domain not in self.visited_domains and depth + 1 <= self.max_depth:
                            queue.append((rev_domain, depth + 1))
                            logger.info(f"Добавлен в очередь (reverse): {rev_domain}")
            
            # ШАГ 3: crt.sh поддомены (ТОЛЬКО ПРЯМЫЕ!)
            subdomains = self._get_subdomains_from_crtsh(domain)
            logger.info(f"Найдено {len(subdomains)} прямых поддоменов из crt.sh для {domain}")
            
            for subdomain in subdomains:
                if subdomain not in self.visited_domains and depth + 1 <= self.max_depth:
                    queue.append((subdomain, depth + 1))
                    logger.info(f"Добавлен в очередь (crt.sh): {subdomain}")
        
        logger.info(f"Сканирование завершено. Найдено доменов: {len(self.visited_domains)}, IP: {len(self.visited_ips)}")
        return len(self.visited_domains), len(self.visited_ips)
    
    def _get_ips_for_domain(self, domain: str) -> list:
        """Получить IP адреса для домена через DNS."""
        ips = set()
        
        try:
            dns_ips, _ = resolve_domain_a_aaaa(domain, follow_cname=True)
            ips.update(dns_ips)
            logger.debug(f"DNS запрос для {domain}: {dns_ips}")
        except Exception as e:
            logger.warning(f"DNS ошибка для {domain}: {e}")
        
        return list(ips)
    
    def _get_reverse_domains(self, ip: str) -> set:
        """Найти домены на этом IP."""
        domains = set()
        
        try:
            reverse_domains = get_domains_from_ip_reverse_dns(ip)
            domains.update(reverse_domains)
            logger.debug(f"Reverse DNS для {ip}: {reverse_domains}")
        except Exception as e:
            logger.warning(f"Reverse DNS ошибка для {ip}: {e}")
        
        try:
            cidr, org = rdap_lookup(ip)
            ip_obj, _ = IPAddress.objects.get_or_create(address=ip)
            ip_obj.organization = org
            ip_obj.cidr = cidr
            ip_obj.save()
            logger.debug(f"RDAP для {ip}: org={org}, cidr={cidr}")
        except Exception as e:
            logger.warning(f"RDAP ошибка для {ip}: {e}")
        
        return domains
    
    def _get_subdomains_from_crtsh(self, domain: str) -> set:
        """
        Получить ТОЛЬКО ПРЯМЫЕ поддомены из crt.sh (на 1 уровень ниже).
        Например, для tyuiu.ru вернёт www.tyuiu.ru, api.tyuiu.ru,
        но НЕ sub.api.tyuiu.ru (это будет обработано позже).
        """
        subdomains = set()
        
        try:
            crtsh_data = fetch_crtsh_json(domain, use_cache=True, debug=False)
            common_names = extract_common_names(crtsh_data)
            
            base_parts = domain.split('.')  # ['tyuiu', 'ru']
            
            for name in common_names:
                # Пропускаем сам домен и wildcard
                if name == domain or name.startswith('*.'):
                    continue
                
                # Проверяем, что это поддомен
                if not name.endswith('.' + domain):
                    continue
                
                name_parts = name.split('.')
                
                # ← КЛЮЧЕВОЕ: только прямые поддомены (1 уровень ниже)
                if len(name_parts) == len(base_parts) + 1:
                    subdomains.add(name)
            
            logger.debug(f"crt.sh {domain}: {len(common_names)} записей, {len(subdomains)} прямых")
            
        except Exception as e:
            logger.warning(f"crt.sh ошибка для {domain}: {e}")
        
        return subdomains
    
    def _save_link(self, session, domain_name: str, ip_address: str, method: str = 'dns'):
        """Сохранить связь в БД."""
        try:
            domain_obj, _ = Domain.objects.get_or_create(name=domain_name)
            ip_obj, _ = IPAddress.objects.get_or_create(address=ip_address)
            link, created = Link.objects.get_or_create(
                scan_session=session,
                domain=domain_obj,
                ip=ip_obj,
                defaults={'method': method}
            )
            logger.debug(f"Сохранена связь: {domain_name} → {ip_address}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении связи: {e}")
