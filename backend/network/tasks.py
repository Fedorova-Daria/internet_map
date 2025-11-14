# backend/network/tasks.py

from celery import shared_task
from .scanner import InternetMapScanner
from .models import ScanSession
import logging

logger = logging.getLogger(__name__)

@shared_task
def run_scanner_task(session_id):
    try:
        session = ScanSession.objects.get(id=session_id)
        session.status = 'running'
        session.save()
        logger.info(f"Запуск сканирования для сессии {session_id}, домен: {session.root_domain}")

        scanner = InternetMapScanner(session=session, max_depth=session.depth)
        scanner.scan(session.root_domain)

        # Обновляем статус при завершении
        session.status = 'completed'
        session.save()
        logger.info(f"Сканирование для сессии {session_id} завершено.")
    except Exception as e:
        logger.error(f"Ошибка сканирования сессии {session_id}: {e}")
        if session:
            session.status = 'failed'
            session.save()
