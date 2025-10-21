from django.shortcuts import render

from rest_framework import viewsets, filters
from .models import Domain, IPAddress, Subnet
from .serializers import DomainSerializer, IPAddressSerializer, SubnetSerializer

class DomainViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Domain.objects.all().order_by('domain_name')
    serializer_class = DomainSerializer


class IPAddressViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = IPAddress.objects.all().order_by('address')
    serializer_class = IPAddressSerializer


class SubnetViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Subnet.objects.prefetch_related('ips__domains').all()
    serializer_class = SubnetSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['network', 'network_name', 'ips__address']
