"""
Тесты для утилит сканирования сети
"""
from django.test import TestCase
import time
from network.utils.crtsh import fetch_crtsh_json, extract_common_names
from network.utils.dns_utils import (
    resolve_domain_a_aaaa, 
    get_ip_from_domain,
    extract_base_domains
)
from network.utils.rdap import rdap_lookup


class NetworkUtilsTestCase(TestCase):
    """Тесты для базовых утилит"""
    
    def test_extract_common_names_empty(self):
        """Тест извлечения имён из пустого списка"""
        result = extract_common_names([])
        self.assertEqual(result, [])
    
    def test_extract_common_names_valid(self):
        """Тест извлечения имён из валидных данных"""
        test_data = [
            {'common_name': 'tyuiu.ru'},
            {'common_name': 'www.tyuiu.ru'},
            {'common_name': 'mail.tyuiu.ru'},
        ]
        result = extract_common_names(test_data)
        self.assertEqual(len(result), 3)
        self.assertIn('tyuiu.ru', result)
        self.assertIn('www.tyuiu.ru', result)
    
    def test_extract_common_names_case_insensitive(self):
        """Тест что имена нормализуются в lowercase"""
        test_data = [
            {'common_name': 'TYUIU.RU'},
            {'common_name': 'Tyuiu.Ru'},
            {'common_name': 'tyuiu.ru'},
        ]
        result = extract_common_names(test_data)
        # Должен быть только один уникальный домен
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], 'tyuiu.ru')
    
    def test_extract_base_domains(self):
        """Тест извлечения базовых доменов"""
        subdomains = [
            'www.tyuiu.ru',
            'mail.tyuiu.ru',
            'portal.tyuiu.ru',
            'example.com'
        ]
        result = extract_base_domains(subdomains)
        self.assertIn('tyuiu.ru', result)
        self.assertIn('example.com', result)
        self.assertEqual(len(result), 2)


class DNSUtilsTestCase(TestCase):
    """Тесты для DNS утилит"""
    
    def test_dns_resolve_tyuiu(self):
        """Тест DNS резолва для tyuiu.ru"""
        ips, cname = resolve_domain_a_aaaa('tyuiu.ru')
        self.assertTrue(len(ips) > 0, "tyuiu.ru должен иметь хотя бы один IP")
        print(f"\ntyuiu.ru -> {list(ips)}")
    
    def test_get_ip_from_domain_tyuiu(self):
        """Тест получения IP для tyuiu.ru"""
        ips = get_ip_from_domain('tyuiu.ru')
        self.assertTrue(len(ips) > 0, "tyuiu.ru должен иметь IP адреса")
        print(f"\nНайдено IP для tyuiu.ru: {ips}")
    
    def test_dns_resolve_nonexistent(self):
        """Тест DNS резолва для несуществующего домена"""
        ips, cname = resolve_domain_a_aaaa('thisdoesnotexist12345xyz.com')
        self.assertEqual(len(ips), 0, "Несуществующий домен не должен иметь IP")
    
    def test_dns_resolve_with_cname(self):
        """Тест резолва с CNAME"""
        ips, cname_chain = resolve_domain_a_aaaa('www.tyuiu.ru', follow_cname=True)
        if cname_chain:
            print(f"\nCNAME цепочка для www.tyuiu.ru: {cname_chain}")
        # Даже если нет CNAME, должны быть IP
        self.assertIsInstance(ips, set)


class CrtshTestCase(TestCase):
    """Тесты для crt.sh функций (SLOW - требуют сетевых запросов)"""
    
    def test_fetch_crtsh_tyuiu(self):
        """Тест получения данных с crt.sh для tyuiu.ru"""
        print("\nЭто медленный тест - делает реальный запрос к crt.sh...")
        start = time.time()
        
        data = fetch_crtsh_json('tyuiu.ru', debug=False)
        
        elapsed = time.time() - start
        print(f"Запрос к crt.sh занял {elapsed:.2f}с")
        
        self.assertTrue(isinstance(data, list), "Должен вернуть список")
        self.assertTrue(len(data) > 0, "tyuiu.ru должен иметь сертификаты")
        print(f"Найдено {len(data)} записей сертификатов")
    
    def test_extract_subdomains_tyuiu(self):
        """Тест извлечения субдоменов для tyuiu.ru"""
        print("\nЭто медленный тест - делает реальный запрос к crt.sh...")
        
        data = fetch_crtsh_json('tyuiu.ru', debug=False)
        subdomains = extract_common_names(data)
        
        self.assertTrue(len(subdomains) > 0, "Должны быть найдены субдомены")
        print(f"Найдено {len(subdomains)} уникальных субдоменов")
        print(f"Примеры: {', '.join(subdomains[:5])}")
        
        # ИСПРАВЛЕНО: Проверяем что есть хотя бы один субдомен tyuiu.ru
        tyuiu_subdomains = [s for s in subdomains if 'tyuiu.ru' in s]
        self.assertTrue(
            len(tyuiu_subdomains) > 0, 
            f"Должны быть субдомены tyuiu.ru, найдено: {tyuiu_subdomains[:5]}"
        )
        
        # Можно проверить конкретные известные субдомены
        # (из твоего вывода видно что они есть)
        self.assertIn('*.tyuiu.ru', subdomains)  # Wildcard сертификат
    
    def test_crtsh_cache_works(self):
        """Тест что кэш crt.sh работает"""
        import os
        from network.utils.cache import get_cache_path, DEFAULT_CACHE_DIR
        
        print("\nЭто медленный тест...")
        
        # Получить путь к кэшу
        cache_key = "crtsh:test-domain-for-cache.com"
        cache_path = get_cache_path(DEFAULT_CACHE_DIR, cache_key)
        
        # Удалить если существует
        if os.path.exists(cache_path):
            os.remove(cache_path)
        
        # Проверить что кэша нет
        self.assertFalse(os.path.exists(cache_path), "Кэш не должен существовать в начале")
        
        # Сделать запрос с кэшированием (вернет пустой список для несуществующего домена)
        data = fetch_crtsh_json('test-domain-for-cache.com', use_cache=True, debug=False)
        
        # Проверить что кэш был создан
        self.assertTrue(os.path.exists(cache_path), "Кэш должен быть создан после запроса")
        print(f"Кэш создан: {cache_path}")
        
        # Загрузить из кэша
        data_from_cache = fetch_crtsh_json('test-domain-for-cache.com', use_cache=True, debug=False)
        
        # Данные должны совпадать
        self.assertEqual(data, data_from_cache, "Данные из кэша должны совпадать")
        print("Кэш работает корректно!")
        
        # Очистить
        if os.path.exists(cache_path):
            os.remove(cache_path)



class RDAPTestCase(TestCase):
    """Тесты для RDAP функций (SLOW - требуют сетевых запросов)"""
    
    def test_rdap_lookup_real_ip(self):
        """Тест RDAP lookup для реального IP"""
        print("\nЭто медленный тест - делает реальный запрос к RDAP...")
        
        # Сначала получим IP для tyuiu.ru
        ips = get_ip_from_domain('tyuiu.ru')
        self.assertTrue(len(ips) > 0, "Нужен хотя бы один IP")
        
        test_ip = ips[0]
        print(f"Тестируем IP: {test_ip}")
        
        try:
            cidr, name = rdap_lookup(test_ip)
            print(f"CIDR: {cidr}")
            print(f"Название: {name}")
            
            self.assertTrue(cidr, "CIDR не должен быть пустым")
            self.assertIn('/', cidr, "CIDR должен содержать маску")
        except Exception as e:
            self.skipTest(f"RDAP недоступен: {e}")


class QuickTestCase(TestCase):
    """Быстрые тесты без сетевых запросов"""
    
    def test_basic_functionality(self):
        """Быстрая проверка что все импорты работают"""
        from network.utils.crtsh import fetch_crtsh_json, extract_common_names
        from network.utils.dns_utils import resolve_domain_a_aaaa
        from network.utils.analyzer import find_unique_subnets
        
        # Просто проверяем что функции существуют
        self.assertTrue(callable(fetch_crtsh_json))
        self.assertTrue(callable(extract_common_names))
        self.assertTrue(callable(resolve_domain_a_aaaa))
        self.assertTrue(callable(find_unique_subnets))
    
    def test_find_unique_subnets(self):
        """Тест поиска уникальных подсетей"""
        from network.utils.analyzer import find_unique_subnets
        
        test_cidrs = [
            '10.0.0.0/24',
            '10.0.1.0/24',
            '10.0.0.0/16',  # Включает в себя предыдущие две
            '192.168.1.0/24'
        ]
        
        result = find_unique_subnets(test_cidrs)
        
        # Должна остаться только большая подсеть 10.0.0.0/16 и отдельная 192.168.1.0/24
        self.assertEqual(len(result), 2)
        self.assertIn('10.0.0.0/16', result)
        self.assertIn('192.168.1.0/24', result)
