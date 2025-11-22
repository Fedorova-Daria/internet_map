# backend/network/tasks.py

from celery import shared_task
from .models import ScanSession
from .scanner import InternetMapScanner
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

@shared_task
def run_scanner_task(session_id: int):
    """
    Асинхронная задача для запуска сканера для указанной сессии.
    Эта задача является отказоустойчивой.
    """
    session = None
    
    try:
        session = ScanSession.objects.get(id=session_id)
        session.status = 'running'
        session.save()

        logger.info(f"Начало задачи сканирования для сессии {session.id} ({session.root_domain})")
        
        # Создаем и запускаем сканер
        scanner = InternetMapScanner(session=session, max_depth=session.depth)
        scanner.scan(session.root_domain)

        # Если скан прошел без ошибок, помечаем сессию как завершенную
        session.status = 'completed'
        logger.info(f"Задача сканирования для сессии {session.id} успешно завершена.")

    except ScanSession.DoesNotExist:
        logger.error(f"Сессия с ID {session_id} не найдена. Задача не может быть выполнена.")

    except Exception as e:
        logger.error(f"Ошибка в задаче сканирования для сессии {session_id}: {e}", exc_info=True)
        if session:
            session.status = 'failed'
    
    finally:
        if session:
            session.finished_at = timezone.now()
            session.save()
            logger.info(f"Финальный статус сессии {session.id} сохранен: '{session.status}'")