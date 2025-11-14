# backend/network/scanner.py


from collections import deque
from .models import Domain, IPAddress, Link
from .tools import (
    get_domains_from_ip_reverse_dns,
    rdap_lookup,
    fetch_crtsh_json,
    extract_common_names,
    get_domains_from_tls, 
    scan_subnet_for_tls,
    resolve_domain_ipv4, 
)
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S'
)


logger = logging.getLogger(__name__)


class InternetMapScanner:
    def __init__(self, session, max_depth=3, max_rate_limit=1.0):
        self.session = session
        self.max_depth = max_depth
        self.max_rate_limit = max_rate_limit
        self.visited_domains = set()
        self.visited_ips = set()
        # ✅ Заводим "память" для просканированных подсетей
        self.scanned_subnets = set()
        self.queue = deque()

    def scan(self, root_domain: str):
        logger.info(f"Начинаем сканирование: {root_domain}")
        self.queue.clear()
        self.queue.append((root_domain, 0))

        while self.queue:
            domain, depth = self.queue.popleft()
            
            if domain in self.visited_domains:
                continue
            
            logger.info(f"[Глубина {depth}] Сканируем: {domain}")
            self.visited_domains.add(domain)

            if depth >= self.max_depth:
                logger.info(f"Достигнут лимит глубины {self.max_depth} для ветки {domain}")
                continue

            # ШАГ 1: DNS запрос (только IPv4)
            ips = self._get_ips_for_domain(domain)
            logger.info(f"Найдено {len(ips)} IP адресов для {domain}: {ips}")

            for ip in ips:
                if ip in self.visited_ips:
                    continue
                
                self.visited_ips.add(ip)
                self._save_link(self.session, domain, ip, method='dns')

                # ШАГ 2: Reverse DNS
                reverse_domains = get_domains_from_ip_reverse_dns(ip)
                logger.info(f"Найдено {len(reverse_domains)} обратных доменов для IP {ip}")
                for rev_domain in reverse_domains:
                    if rev_domain not in self.visited_domains:
                        queue.append((rev_domain, depth + 1))
                        logger.info(f"Добавлен в очередь (Reverse DNS): {rev_domain}")

                # ШАГ 2.5: SSL-сертификат на самом IP
                tls_domains = get_domains_from_tls(ip)
                logger.info(f"Найдено {len(tls_domains)} доменов из SSL для IP {ip}")
                for tls_domain in tls_domains:
                    if tls_domain not in self.visited_domains:
                        self._save_link(self.session, tls_domain, ip, method='tls-cert')
                        queue.append((tls_domain, depth + 1))
                        logger.info(f"Добавлен в очередь (SSL): {tls_domain}")
                
                # ✅ ШАГ 2.6: Сканирование подсети (перенесено сюда и улучшено)
                self._scan_ip_subnet(ip, depth)

            # ШАГ 3: crt.sh поддомены
            subdomains = self._get_subdomains_from_crtsh(domain)
            logger.info(f"Найдено {len(subdomains)} прямых поддоменов из crt.sh для {domain}")
            for subdomain in subdomains:
                if subdomain not in self.visited_domains:
                    self.queue.append((subdomain, depth + 1))
                    self._save_link(self.session, root_domain, subdomain, method='crtsh')  # Прямая связь по домену
                    logger.info(f"Добавлен в очередь (crt.sh): {subdomain}")

        logger.info(f"Сканирование завершено. Найдено доменов: {len(self.visited_domains)}, IP: {len(self.visited_ips)}")
        return len(self.visited_domains), len(self.visited_ips)

    # ✅ Метод для DNS-запроса теперь использует правильную функцию
    def _get_ips_for_domain(self, domain: str) -> list:
        """Получить IP адреса для домена через DNS (только IPv4)."""
        ips, _ = resolve_domain_ipv4(domain, follow_cname=True)
        return list(ips)

    # ✅ Создаем отдельный, чистый метод для сканирования подсети
    def _scan_ip_subnet(self, ip: str, current_depth: int):
        """Определяет подсеть для IP и запускает ее 'умное' сканирование."""
        try:
            cidr, org = rdap_lookup(ip)

            # Обновляем информацию об IP в БД
            ip_obj, _ = IPAddress.objects.get_or_create(address=ip)
            ip_obj.organization = org
            ip_obj.cidr = cidr
            ip_obj.save()

            # ✅ Проверяем, сканировали ли мы эту подсеть ранее
            if cidr and cidr not in self.scanned_subnets:
                logger.info(f"Начинаем сканирование новой подсети: {cidr}")
                self.scanned_subnets.add(cidr)
                
                subnet_results = scan_subnet_for_tls(cidr)
                for found_ip, found_domains in subnet_results:
                    # Добавляем все найденные домены в очередь
                    for found_domain in found_domains:
                        if found_domain not in self.visited_domains:
                            self._save_link(self.session, found_domain, found_ip, method='tls-subnet')
                            self.queue.append((found_domain, current_depth))
                            logger.info(f"Добавлен в очередь (Subnet Scan): {found_domain}")
            else:
                logger.debug(f"Подсеть {cidr} уже сканировалась, пропускаем.")
        except Exception as e:
            logger.warning(f"Не удалось обработать подсеть для IP {ip}: {e}")
    
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
