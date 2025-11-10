# backend/tasks.py

from celery import shared_task
from .scanner import InternetMapScanner
import logging

logger = logging.getLogger(__name__)

@shared_task
def scan_domain_task(root_domain: str, max_depth: int = 3):
    """
    Асинхронная задача сканирования домена.
    Выполняется в фоне через Celery.
    """
    logger.info(f"Запущена задача сканирования: {root_domain}")
    
    try:
        scanner = InternetMapScanner(max_depth=max_depth)
        domains_found, ips_found = scanner.scan(root_domain)
        
        logger.info(f"Сканирование завершено: {domains_found} доменов, {ips_found} IP")
        return {
            'status': 'success',
            'domains_found': domains_found,
            'ips_found': ips_found
        }
    except Exception as e:
        logger.error(f"Ошибка при сканировании: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
