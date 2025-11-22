# backend/network/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Domain, IPAddress, Link, ScanSession
from .serializers import DomainSerializer, IPAddressSerializer, LinkSerializer
from .scanner import InternetMapScanner
from .tasks import run_scanner_task
import logging
from itertools import combinations
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

        # Получаем запрошенную глубину из POST-запроса.
        requested_depth = int(request.data.get('depth', 2))

        # --- НАЧАЛО НОВОЙ "УМНОЙ" ЛОГИКИ ---

        # 1. Ищем самый глубокий из УЖЕ ЗАВЕРШЕННЫХ сканов для этого домена.
        latest_completed_scan = ScanSession.objects.filter(
            root_domain=domain_name,
            status='completed'
        ).order_by('-depth', '-created_at').first()

        # 2. Проверяем, подходит ли он нам.
        if latest_completed_scan and latest_completed_scan.depth >= requested_depth:
            logger.info(f"Найден подходящий завершенный скан (ID: {latest_completed_scan.id}) с глубиной {latest_completed_scan.depth}. Новый скан не запускаем.")
            # Сразу возвращаем ID этого скана, чтобы фронтенд мог запросить граф.
            return Response({
                'status': 'A suitable completed scan already exists.',
                'session_id': latest_completed_scan.id, # <-- Отдаем ID готового скана
                'domain': domain_name,
            }, status=status.HTTP_200_OK) # <-- Обрати внимание, статус 200 OK, а не 202

        # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

        # Если мы дошли сюда, значит, подходящего скана нет. Запускаем новый.
        try:
            # Добавим проверку, чтобы не создавать дублирующиеся задачи
            existing_pending_scan = ScanSession.objects.filter(
                root_domain=domain_name,
                depth=requested_depth,
                status__in=['pending', 'running']
            ).first()

            if existing_pending_scan:
                logger.info(f"Скан с глубиной {requested_depth} уже в очереди (ID: {existing_pending_scan.id}).")
                return Response({
                    'status': 'Scan session is already pending or running.',
                    'session_id': existing_pending_scan.id,
                    'domain': domain_name,
                }, status=status.HTTP_202_ACCEPTED)

            logger.info(f"Запускаем новый скан для {domain_name} с глубиной {requested_depth}.")
            session = ScanSession.objects.create(
                root_domain=domain_name,
                depth=requested_depth,
                status='pending'
            )
            run_scanner_task.delay(session.id)
            
            return Response({
                'status': 'New scan session created and scheduled.',
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

        # Если сессия не найдена, запускаем новую асинхронную задачу
        if not latest_session:
            try:
                session = ScanSession.objects.create(
                    root_domain=domain_name,
                    depth=2,  # или возьми из параметров
                    status='pending'
                )
                run_scanner_task.delay(session.id)
                return Response({
                    'status': 'Scan started, please check back later',
                    'session_id': session.id,
                    'nodes': [],
                    'edges': []
                }, status=status.HTTP_202_ACCEPTED)
            except Exception as e:
                logger.error(f"Failed to create scan session: {e}")
                return Response({'error': 'Failed to start scan'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        session_id = request.query_params.get('session_id')
        
        if not domain_name:
            return Response({'error': 'Domain parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # ... (код поиска сессии остается без изменений) ...
        latest_session = None
        if session_id:
            try:
                latest_session = ScanSession.objects.get(id=session_id)
            except ScanSession.DoesNotExist:
                return Response({'error': f'Сессия с ID {session_id} не найдена'}, status=404)
        else:
            latest_session = ScanSession.objects.filter(root_domain=domain_name, status='completed').order_by('-created_at').first()

        if not latest_session:
            return Response({'nodes': [], 'edges': [], 'message': 'No completed scan found for this domain.'}, status=status.HTTP_200_OK)

        links_data = Link.objects.filter(scan_session=latest_session).values(
            'id', 'domain__id', 'domain__name', 'ip__id', 'ip__address', 
            'ip__organization', 'ip__cidr', 'method'
        )[:500]

        if not links_data:
            return Response({'nodes': [], 'edges': [], 'message': 'No links found for this session.'}, status=200)

        nodes = {}
        edges = []
        # Этот словарь теперь хранит связи через ЛЮБОЙ узел-посредник
        connector_to_domains = {} 

        for link in links_data:
            domain_id_str = f'd-{link["domain__id"]}'
            # ID посредника (может быть как IP, так и доменом)
            connector_id_str = f'ip-{link["ip__id"]}' 
            
            domain_label = link['domain__name']
            connector_label = link['ip__address']

            # Создаем узел для домена
            if domain_id_str not in nodes:
                node_type = 'domain' if any(char.isalpha() for char in domain_label) else 'ip'
                nodes[domain_id_str] = {'id': domain_id_str, 'label': domain_label, 'type': node_type, 'data': domain_label}
                if node_type == 'ip': nodes[domain_id_str]['organization'] = 'Unknown'

            # Создаем узел для "посредника"
            if connector_id_str not in nodes:
                node_type = 'domain' if any(char.isalpha() for char in connector_label) else 'ip'
                nodes[connector_id_str] = {'id': connector_id_str, 'label': connector_label, 'type': node_type, 'data': connector_label}
                if node_type == 'ip': nodes[connector_id_str]['organization'] = link['ip__organization'] or 'Unknown'

            # Добавляем прямую связь (зеленую)
            edges.append({'id': f'e-{link["id"]}', 'source': domain_id_str, 'target': connector_id_str, 'type': 'direct', 'label': link['method']})
            
            # Готовим данные для создания косвенных связей
            if connector_id_str not in connector_to_domains: connector_to_domains[connector_id_str] = set()
            connector_to_domains[connector_id_str].add(domain_id_str)
            
            # ... (код для подсетей не меняется) ...
            subnet_cidr = link['ip__cidr']
            if subnet_cidr:
                subnet_id_str = f'sub-{subnet_cidr}'
                if subnet_id_str not in nodes: nodes[subnet_id_str] = {'id': subnet_id_str, 'label': subnet_cidr, 'type': 'subnet', 'data': subnet_cidr}
                edges.append({'id': f'member_{connector_id_str}_{subnet_id_str}', 'source': connector_id_str, 'target': subnet_id_str, 'type': 'member_of', 'label': 'belongs to'})

        # --- СОЗДАНИЕ КОСВЕННЫХ СВЯЗЕЙ ---
        
        # 1. Связи через посредников (КРАСНЫЕ или СИНИЕ)
        for connector_id, domain_set in connector_to_domains.items():
            if len(domain_set) > 1 and connector_id in nodes:
                connector_node = nodes[connector_id]
                for domain1_id, domain2_id in combinations(domain_set, 2):
                    # Если посредник - IP, линия КРАСНАЯ
                    if connector_node['type'] == 'ip':
                        edges.append({
                            'id': f'via_{connector_id}_{domain1_id}_{domain2_id}',
                            'source': domain1_id, 'target': domain2_id,
                            'type': 'via_ip', # <-- RED
                            'label': f'via {connector_node["label"]}'
                        })
                    # Если посредник - Домен, линия СИНЯЯ
                    elif connector_node['type'] == 'domain':
                        edges.append({
                            'id': f'via_{connector_id}_{domain1_id}_{domain2_id}',
                            'source': domain1_id, 'target': domain2_id,
                            'type': 'subdomain', # <-- BLUE
                            'label': f'alias via {connector_node["label"]}'
                        })

        # 2. Прямые связи поддоменов (тоже СИНИЕ)
        domain_nodes = {node['label']: node['id'] for node in nodes.values() if node['type'] == 'domain'}
        for name, domain_id in domain_nodes.items():
            parts = name.split('.')
            if len(parts) > 2:
                parent_name = '.'.join(parts[1:])
                if parent_name in domain_nodes:
                    parent_id = domain_nodes[parent_name]
                    edges.append({'id': f'sub_{parent_id}_{domain_id}', 'source': parent_id, 'target': domain_id, 'type': 'subdomain', 'label': 'subdomain of'})

        node_list = list(nodes.values())
        
        return Response({
            'domain': domain_name, 'nodes': node_list, 'edges': edges,
            'summary': {
                'message': 'Showing a partial graph limited to 500 links.', 'total_nodes': len(node_list), 'total_edges': len(edges),
                'domains': len([n for n in node_list if n['type'] == 'domain']), 'ips': len([n for n in node_list if n['type'] == 'ip']),
                'subnets': len([n for n in node_list if n['type'] == 'subnet'])
            }
        })