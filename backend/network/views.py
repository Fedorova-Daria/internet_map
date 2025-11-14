# backend/network/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Domain, IPAddress, Link, ScanSession
from .serializers import DomainSerializer, IPAddressSerializer, LinkSerializer
from .scanner import InternetMapScanner
from .tasks import run_scanner_task
import logging
from django.utils import timezone
from datetime import timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .serializers import IPAddressSerializer, DomainSerializer, LinkSerializer
logger = logging.getLogger(__name__)

class DomainViewSet(viewsets.ViewSet):
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['domain'],
            properties={
                'domain': openapi.Schema(type=openapi.TYPE_STRING, description='Имя домена для сканирования', example='tyuiu.ru'),
                'depth': openapi.Schema(type=openapi.TYPE_INTEGER, description='Глубина поиска поддоменов', example=2, default=2),
            }
        ),
        responses={
            202: openapi.Response(
                description='Сканирование запущено',
                examples={
                    'application/json': {
                        'status': 'Scan session created and scheduled',
                        'session_id': 123,
                        'domain': 'tyuiu.ru'
                    }
                }
            ),
            400: openapi.Response(description='Ошибка: отсутствует домен'),
            500: openapi.Response(description='Внутренняя ошибка сервера')
        },
        operation_description="""Запускает асинхронное сканирование домена (например, tyuiu.ru) до указанной глубины. Передайте имя домена и глубину — получите ID сессии для последующего запроса."""
    )
    @action(detail=False, methods=['post'])
    def scan(self, request):
        domain_name = request.data.get('domain')
        if not domain_name:
            return Response({'error': 'Domain name is required'}, status=status.HTTP_400_BAD_REQUEST)

        depth = int(request.data.get('depth', 2))

        # Создаем объект сессии сканирования в базе данных
        # Статус 'pending' (ожидание) означает, что задача создана, но еще не взята в работу
        try:
            session = ScanSession.objects.create(
                root_domain=domain_name,
                depth=depth,
                status='pending'
            )
            logger.info(f"Создана новая сессия сканирования ID: {session.id} для домена {domain_name}")

            # ✅ ЗАПУСКАЕМ АСИНХРОННУЮ ЗАДАЧУ
            # Мы передаем только ID сессии. Задача сама извлечет из нее все нужные данные.
            run_scanner_task.delay(session.id)

            # Мгновенно возвращаем ответ пользователю
            return Response({
                'status': 'Scan session created and scheduled',
                'session_id': session.id,
                'domain': domain_name,
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            logger.error(f"Не удалось создать сессию сканирования: {e}")
            return Response({'error': 'Failed to create scan session'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ... ваш метод graph и другие методы остаются без изменений ...
    # Убедитесь, что метод graph все еще здесь
    @action(detail=False, methods=['get'])
    def graph(self, request):
        domain_name = request.query_params.get('domain')
        if not domain_name:
            return Response({'error': 'Domain parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Ищем последнюю ЗАВЕРШЕННУЮ сессию
        latest_session = ScanSession.objects.filter(
            root_domain=domain_name,
            status='completed'
        ).order_by('-created_at').first()

        if not latest_session:
            return Response({'nodes': [], 'edges': []}, status=status.HTTP_200_OK)

        links = Link.objects.filter(scan_session=latest_session).select_related('domain', 'ip')
        
        nodes = {}
        edges = []

        for link in links:
            # Добавляем узел домена
            if link.domain.id not in nodes:
                nodes[link.domain.id] = {
                    'id': f'd-{link.domain.id}',
                    'label': link.domain.name,
                    'type': 'domain',
                }
            # Добавляем узел IP
            if link.ip.id not in nodes:
                nodes[link.ip.id] = {
                    'id': f'ip-{link.ip.id}',
                    'label': link.ip.address,
                    'type': 'ip',
                    'organization': link.ip.organization,
                }
            
            # Добавляем ребро
            edges.append({
                'id': f'e-{link.id}',
                'source': f'd-{link.domain.id}',
                'target': f'ip-{link.ip.id}',
                'type': 'direct' if link.method in ['dns', 'reverse_dns'] else 'via_ip',
                'label': link.method,
            })
            
        # Преобразуем словарь узлов в список
        node_list = list(nodes.values())

        return Response({'nodes': node_list, 'edges': edges})
    
class IPAddressViewSet(viewsets.ModelViewSet):
    """
    API для получения, создания, обновления и удаления IP-адресов.
    Возвращает базовую информацию: адрес, организацию, CIDR (подсеть).
    """
    queryset = IPAddress.objects.all()
    serializer_class = IPAddressSerializer

class LinkViewSet(viewsets.ModelViewSet):
    """
    API для получения, создания, обновления и удаления связей между доменами и IP-адресами.
    Каждая связь содержит тип (dns, tls, reverse_dns), дату, домен и IP.
    """
    queryset = Link.objects.all()
    serializer_class = LinkSerializer
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('domain', openapi.IN_QUERY, description="Имя домена для получения графа", type=openapi.TYPE_STRING, required=True)
        ],
        responses={
            200: openapi.Response(
                description='Граф связей для выбранного домена',
                examples={
                    'application/json': {
                        'domain': 'tyuiu.ru',
                        'nodes': [],
                        'edges': [],
                        'summary': {
                            'total_nodes': 12,
                            'total_edges': 17,
                            'domains': 7,
                            'ips': 5
                        }
                    }
                }
            ),
            404: openapi.Response(description='Нет данных сканирования для указанного домена')
        },
        operation_description="""
        Возвращает полный граф связей по домену (все уникальные домены/IP и все связи с типами и методами).
        Используйте параметр domain для фильтрации (например, ?domain=tyuiu.ru).
        """
    )
    @action(detail=False, methods=['get'])
    def graph(self, request):
        domain_name = request.query_params.get('domain')
        if not domain_name:
            return Response(...)

        # ✅ Находим последнюю УСПЕШНУЮ сессию для этого домена
        latest_session = ScanSession.objects.filter(
        root_domain=domain_name
        ).latest('created_at')

        if not latest_session:
            return Response({'error': f'Нет данных сканирования для домена {domain_name}'}, status=404)

        # ✅ Получаем связи ТОЛЬКО для этой сессии
        links = Link.objects.filter(scan_session=latest_session).select_related('domain', 'ip')
        
        # Собираем уникальные домены и IP из этих связей
        domain_ids = links.values_list('domain_id', flat=True)
        ip_ids = links.values_list('ip_id', flat=True)
        
        domains = Domain.objects.filter(id__in=set(domain_ids))
        ips = IPAddress.objects.filter(id__in=set(ip_ids))
        
        
        nodes = []
        edges = []
        visited_nodes = set()
        
        # Добавить все IP как узлы (синие блоки)
        for ip in ips:
            nodes.append({
                'id': f'ip_{ip.address}',
                'label': ip.address,
                'type': 'ip',
                'organization': ip.organization or 'Unknown',
                'data': ip.address
            })
            visited_nodes.add(f'ip_{ip.address}')
        
        # Добавить все домены как узлы (зелёные блоки)
        for domain in domains:
            nodes.append({
                'id': f'domain_{domain.name}',
                'label': domain.name,
                'type': 'domain',
                'data': domain.name
            })
            visited_nodes.add(f'domain_{domain.name}')
        
        # Добавить рёбра с типами связей
        # Домен → IP (красная линия - прямая связь)
        domain_ip_pairs = set()
        for link in links:
            source = f'domain_{link.domain.name}'
            target = f'ip_{link.ip.address}'
            key = (source, target)
            
            if key not in domain_ip_pairs:
                edges.append({
                    'id': f'edge_{source}_{target}',
                    'source': source,
                    'target': target,
                    'type': 'direct',  # красная линия
                    'method': link.method,
                    'label': link.method
                })
                domain_ip_pairs.add(key)
        
        # IP → Домены (синяя линия - через IP)
        # Каждый IP группирует несколько доменов
        for ip in ips:
            domains_on_ip = set()
            for link in links:
                if link.ip == ip:
                    domains_on_ip.add(link.domain)
            
            # Связать домены через IP (создай "косвенные" рёбра)
            for domain1 in domains_on_ip:
                for domain2 in domains_on_ip:
                    if domain1.name != domain2.name:
                        source = f'domain_{domain1.name}'
                        target = f'domain_{domain2.name}'
                        edge_id = f'edge_{min(source, target)}_{max(source, target)}'
                        
                        # Проверь, нет ли уже такого ребра
                        if not any(e['id'] == edge_id for e in edges):
                            edges.append({
                                'id': edge_id,
                                'source': source,
                                'target': target,
                                'type': 'via_ip',  # синяя линия
                                'label': f'via {ip.address}',
                                'ip': ip.address
                            })
        
        return Response({
            'domain': domain_name,
            'nodes': nodes,
            'edges': edges,
            'summary': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'domains': len([n for n in nodes if n['type'] == 'domain']),
                'ips': len([n for n in nodes if n['type'] == 'ip'])
            }
        })