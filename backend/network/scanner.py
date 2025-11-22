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
    scan_subnet_with_nmap,
    get_subdomains_with_theharvester
)
import logging
import dns.resolver
import dns.exception
import ipaddress 
# Настройка логгера
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

            # ШАГ 1: DNS запрос (с правильной обработкой CNAME)
            ips = self._get_ips_for_domain(domain)
            if not ips:
                logger.warning(f"Не найдено IP адресов для {domain}, пропускаем.")
                # Если IP нет, нужно обработать crt.sh и выйти
                self._process_crtsh_subdomains(domain, depth)
                continue

            logger.info(f"Найдено {len(ips)} IP адресов для {domain}: {ips}")

            for ip in ips:
                # Сохраняем основную связь Домен -> IP
                self._save_link(self.session, domain, ip, method='dns')
                
                if ip in self.visited_ips:
                    continue
                
                self.visited_ips.add(ip)

                # ШАГ 2: Reverse DNS
                reverse_domains = get_domains_from_ip_reverse_dns(ip)
                logger.info(f"Найдено {len(reverse_domains)} обратных доменов для IP {ip}")
                for rev_domain in reverse_domains:
                    if rev_domain not in self.visited_domains:
                        self.queue.append((rev_domain, depth + 1))
                        logger.info(f"Добавлен в очередь (Reverse DNS): {rev_domain}")

                # ШАГ 2.5: SSL-сертификат на самом IP
                tls_domains = get_domains_from_tls(ip)
                logger.info(f"Найдено {len(tls_domains)} доменов из SSL для IP {ip}")
                for tls_domain in tls_domains:
                    if tls_domain not in self.visited_domains:
                        self._save_link(self.session, tls_domain, ip, method='tls-cert')
                        self.queue.append((tls_domain, depth + 1))
                        logger.info(f"Добавлен в очередь (SSL): {tls_domain}")
                
                # ШАГ 2.6: Сканирование подсети
                self._scan_ip_subnet(ip, depth)

            # ШАГ 3: Поиск поддоменов через theHarvester
            logger.info(f"Запускаем theHarvester для поиска поддоменов {domain}...")
            
            
            subdomains_info = get_subdomains_with_theharvester(domain)

            for sub_domain, sub_ip in subdomains_info:
                # Добавляем найденный поддомен в очередь, если еще не были на нем
                if sub_domain not in self.visited_domains:
                    self.queue.append((sub_domain, depth + 1))
                    logger.info(f"Добавлен в очередь (theHarvester): {sub_domain}")
                
                # Если theHarvester сразу нашел IP, создаем связь
                if sub_ip:
                    self._save_link(self.session, sub_domain, sub_ip, method='harvester')

        logger.info(f"Сканирование завершено. Найдено доменов: {len(self.visited_domains)}, IP: {len(self.visited_ips)}")
        return len(self.visited_domains), len(self.visited_ips)

    def _get_ips_for_domain(self, domain_name: str, max_cname_hops=5) -> list:
        """Рекурсивно получает IP-адреса для домена, следуя по цепочке CNAME."""
        if max_cname_hops <= 0:
            logger.warning(f"Достигнут лимит CNAME-переходов для {domain_name}")
            return []
        
        try:
            # Сначала пытаемся получить A-запись (IP-адрес)
            answers = dns.resolver.resolve(domain_name, 'A')
            return [rdata.to_text() for rdata in answers]
        
        except dns.resolver.NoAnswer:
            # A-записи нет. Проверяем, есть ли CNAME.
            try:
                cname_answers = dns.resolver.resolve(domain_name, 'CNAME')
                cname_target = cname_answers[0].to_text().strip('.')
                logger.info(f"Найден CNAME для {domain_name}: {cname_target}. Следуем по цепочке...")
                # Рекурсивно ищем IP уже для нового домена
                return self._get_ips_for_domain(cname_target, max_cname_hops - 1)
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
                logger.warning(f"Не удалось найти ни A, ни CNAME запись для {domain_name}")
                return []
                
        except (dns.resolver.NXDOMAIN, dns.exception.Timeout):
            logger.error(f"Не удалось разрешить домен: {domain_name}")
            return []
        except Exception as e:
            logger.error(f"Непредвиденная ошибка DNS для {domain_name}: {e}")
            return []

    def _process_crtsh_subdomains(self, domain: str, depth: int):
        """Получает поддомены из crt.sh и добавляет их в очередь."""
        subdomains = self._get_subdomains_from_crtsh(domain)
        logger.info(f"Найдено {len(subdomains)} прямых поддоменов из crt.sh для {domain}")
        for subdomain in subdomains:
            if subdomain not in self.visited_domains:
                self.queue.append((subdomain, depth + 1))
                logger.info(f"Добавлен в очередь (crt.sh): {subdomain}")

    def _scan_ip_subnet(self, ip: str, parent_domain: str, current_depth: int):
        """Определяет подсеть для IP и запускает ее сканирование."""
        try:
            cidr, org = rdap_lookup(ip)
            ip_obj, _ = IPAddress.objects.get_or_create(address=ip)
            ip_obj.organization = org
            ip_obj.cidr = cidr
            ip_obj.save()
            
            if cidr and cidr not in self.scanned_subnets:
                network = ipaddress.ip_network(cidr, strict=False)
                if network.prefixlen < 24: # Ограничиваем размер подсети
                    logger.warning(f"Подсеть {cidr} слишком большая, пропускаем.")
                    return
                
                logger.info(f"Начинаем Nmap-сканирование новой подсети: {cidr} (найдена от {parent_domain})")
                self.scanned_subnets.add(cidr)

                subnet_results = scan_subnet_with_nmap(cidr)
                for found_ip, found_domains in subnet_results:
                    for found_domain in found_domains:
                        # Создаем связь между НАЙДЕННЫМ доменом и РОДИТЕЛЬСКИМ доменом,
                        # используя IP родительского домена как точку связи.
                        self._save_link(self.session, found_domain, ip, method='nmap-subnet')
                        
                        if found_domain not in self.visited_domains:
                            self.queue.append((found_domain, current_depth + 1)) # Увеличиваем глубину
                            logger.info(f"Добавлен в очередь (Subnet Scan): {found_domain}")
            
            elif cidr:
                logger.debug(f"Подсеть {cidr} уже сканировалась, пропускаем.")
        
        except Exception as e:
            logger.warning(f"Не удалось обработать подсеть для IP {ip}: {e}")
    
    def _get_subdomains_from_crtsh(self, domain: str) -> set:
        """Получить ТОЛЬКО ПРЯМЫЕ поддомены из crt.sh."""
        subdomains = set()
        try:
            crtsh_data = fetch_crtsh_json(domain, use_cache=True, debug=False)
            common_names = extract_common_names(crtsh_data)
            base_parts = domain.split('.')
            
            for name in common_names:
                if name == domain or name.startswith('*.'):
                    continue
                if not name.endswith('.' + domain):
                    continue
                
                name_parts = name.split('.')
                if len(name_parts) == len(base_parts) + 1:
                    subdomains.add(name)
            
            logger.debug(f"crt.sh {domain}: {len(common_names)} записей, {len(subdomains)} прямых")
        except Exception as e:
            logger.warning(f"crt.sh ошибка для {domain}: {e}")
        return subdomains
    
    def _save_link(self, session, domain_name_arg: str, ip_address_arg: str, method: str = 'dns'):
        """
        Сохраняет связь.
        """
        try:
            domain_obj, _ = Domain.objects.get_or_create(name=domain_name_arg)
            ip_obj, _ = IPAddress.objects.get_or_create(address=ip_address_arg)
            
            link, created = Link.objects.get_or_create(
                scan_session=session,
                domain=domain_obj,
                ip=ip_obj,
                defaults={'method': method}
            )
            if created:
                logger.info(f" Создана связь: {domain_name_arg} → {ip_address_arg}")

        except Exception as e:
            logger.error(f"Критическая ошибка при сохранении связи '{domain_name_arg}' -> '{ip_address_arg}': {e}")

