# backend/network/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Domain, IPAddress, Link, ScanSession
from .serializers import DomainSerializer, IPAddressSerializer, LinkSerializer
from .scanner import InternetMapScanner
from .tasks import scan_domain_task
import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

class DomainViewSet(viewsets.ModelViewSet):
    """API для управления доменами"""
    queryset = Domain.objects.all()
    serializer_class = DomainSerializer
    
    @action(detail=False, methods=['post'])
    def scan(self, request):
        domain = request.data.get('domain')
        depth = int(request.data.get('depth', 3))
        
        if not domain:
            return Response({'error': 'domain is required'}, status=status.HTTP_400_BAD_REQUEST)

        cache_ttl = timedelta(days=1)
        # Теперь этот запрос будет работать, так как поля существуют
        recent_session = ScanSession.objects.filter(
            root_domain=domain,
            depth=depth,
            status='completed',
            completed_at__gte=timezone.now() - cache_ttl
        ).order_by('-completed_at').first()

        if recent_session:
            logger.info(f"Найдена сессия для {domain}. Возвращаем из кэша.")
            return Response({'status': 'completed_from_cache', 'domain': domain}, status=status.HTTP_200_OK)
        
        session = ScanSession.objects.create(root_domain=domain, depth=depth, status='running')
        
        try:
            scanner = InternetMapScanner(session=session, max_depth=depth)
            domains_found, ips_found = scanner.scan(domain)
            
            session.status = 'completed'
            session.completed_at = timezone.now()
            session.save()
            
            return Response({
                'status': 'completed',
                'domain': domain,
                'domains_found': domains_found,
                'ips_found': ips_found
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            session.status = 'failed'
            session.completed_at = timezone.now()
            session.save()
            logger.error(f"Ошибка сканирования {domain}: {e}", exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPAddressViewSet(viewsets.ModelViewSet):
    """API для управления IP адресами"""
    queryset = IPAddress.objects.all()
    serializer_class = IPAddressSerializer

class LinkViewSet(viewsets.ModelViewSet):
    """API для управления связями между доменами и IP"""
    queryset = Link.objects.all()
    serializer_class = LinkSerializer
    
    @action(detail=False, methods=['get'])
    def graph(self, request):
        domain_name = request.query_params.get('domain')
        if not domain_name:
            return Response(...)

        # ✅ Находим последнюю УСПЕШНУЮ сессию для этого домена
        latest_session = ScanSession.objects.filter(
            root_domain=domain_name,
            status='completed'
        ).order_by('-created_at').first()

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