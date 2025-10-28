"""
Анализ доменов второго уровня
"""
import time
import json
from ipaddress import ip_network
from collections import defaultdict
from typing import Dict, List, Set

from .crtsh import fetch_crtsh_json, extract_common_names
from .dns_utils import resolve_domain_a_aaaa
from .rdap import rdap_lookup

def analyze_second_level_domain(target_domain: str, debug: bool = True) -> Dict:
    """
    Полный анализ домена второго уровня:
    1. Находит все субдомены через crt.sh
    2. Резолвит их в IP
    3. Получает CIDR подсети через RDAP
    4. Находит уникальные подсети
    """
    if debug:
        print(f"\n{'='*60}")
        print(f"Анализ домена: {target_domain}")
        print(f"{'='*60}\n")
    
    # ШАГ 1: Субдомены
    if debug:
        print("[Шаг 1] Получение субдоменов через crt.sh...")
    
    crtsh_data = fetch_crtsh_json(target_domain, debug=debug)
    subdomains = extract_common_names(crtsh_data)
    
    if debug:
        print(f"✓ Найдено субдоменов: {len(subdomains)}")
    
    # ШАГ 2: Резолв в IP
    if debug:
        print(f"\n[Шаг 2] Резолв субдоменов в IP...")
    
    domain_to_ips = {}
    all_ips = set()
    
    for i, subdomain in enumerate(subdomains, 1):
        if debug and i % 10 == 0:
            print(f"  Обработано: {i}/{len(subdomains)}")
        
        ips, cname_chain = resolve_domain_a_aaaa(subdomain)
        
        if ips:
            domain_to_ips[subdomain] = list(ips)
            all_ips.update(ips)
    
    if debug:
        print(f"✓ Уникальных IP: {len(all_ips)}")
    
    # ШАГ 3: RDAP lookup
    if debug:
        print(f"\n[Шаг 3] RDAP lookup для IP...")
    
    ip_to_subnet = {}
    failed_ips = []
    
    for i, ip in enumerate(all_ips, 1):
        if debug and i % 5 == 0:
            print(f"  Обработано: {i}/{len(all_ips)}")
        
        try:
            cidr, name = rdap_lookup(ip)
            ip_to_subnet[ip] = {
                'cidr': cidr,
                'name': name,
                'domains': []
            }
            time.sleep(0.5)  # Вежливость
        except Exception as e:
            if debug:
                print(f"  ⚠ Ошибка для {ip}: {e}")
            failed_ips.append(ip)
    
    # Связать домены с IP
    for domain, ips in domain_to_ips.items():
        for ip in ips:
            if ip in ip_to_subnet:
                ip_to_subnet[ip]['domains'].append(domain)
    
    # ШАГ 4: Группировка по подсетям
    if debug:
        print(f"\n[Шаг 4] Группировка по подсетям...")
    
    subnet_to_ips = defaultdict(lambda: {
        'ips': [],
        'name': '',
        'domains': set()
    })
    
    for ip, info in ip_to_subnet.items():
        cidr = info['cidr']
        subnet_to_ips[cidr]['ips'].append(ip)
        subnet_to_ips[cidr]['name'] = info['name']
        subnet_to_ips[cidr]['domains'].update(info['domains'])
    
    for subnet_info in subnet_to_ips.values():
        subnet_info['domains'] = list(subnet_info['domains'])
    
    # ШАГ 5: Уникальные подсети
    if debug:
        print(f"\n[Шаг 5] Поиск уникальных подсетей...")
    
    unique_subnets = find_unique_subnets(list(subnet_to_ips.keys()))
    
    if debug:
        print(f"✓ Уникальных подсетей: {len(unique_subnets)}")
        print(f"\n{'='*60}")
        print("РЕЗУЛЬТАТ:")
        print(f"Субдоменов: {len(subdomains)}")
        print(f"Уникальных IP: {len(all_ips)}")
        print(f"Уникальных подсетей: {len(unique_subnets)}")
        print(f"{'='*60}")
    
    return {
        'target_domain': target_domain,
        'total_subdomains': len(subdomains),
        'subdomains_with_ips': len(domain_to_ips),
        'total_unique_ips': len(all_ips),
        'total_subnets': len(subnet_to_ips),
        'unique_subnets': len(unique_subnets),
        'subdomains': subdomains,
        'domain_to_ips': domain_to_ips,
        'ip_to_subnet': ip_to_subnet,
        'subnet_to_ips': dict(subnet_to_ips),
        'unique_subnet_list': list(unique_subnets),
        'failed_ips': failed_ips
    }

def find_unique_subnets(cidr_list: List[str]) -> Set[str]:
    """
    Найти непересекающиеся подсети.
    Если одна подсеть является частью другой, оставить только большую.
    """
    if not cidr_list:
        return set()
    
    from ipaddress import ip_network
    
    # Конвертировать в объекты ip_network
    networks = []
    for cidr in cidr_list:
        try:
            networks.append(ip_network(cidr, strict=False))
        except ValueError as e:
            print(f"⚠ Некорректный CIDR {cidr}: {e}")
            continue
    
    if not networks:
        return set()
    
    # Сортировать по размеру (от больших к меньшим)
    networks.sort(key=lambda n: n.num_addresses, reverse=True)
    
    unique = []
    
    for net in networks:
        # Проверить, входит ли текущая сеть в уже добавленные
        is_subset = False
        
        for existing in unique:
            # Если текущая сеть - подсеть существующей, пропустить
            if net.subnet_of(existing) or net == existing:
                is_subset = True
                break
        
        if not is_subset:
            unique.append(net)
    
    return {str(net) for net in unique}
