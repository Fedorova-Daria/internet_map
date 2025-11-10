# backend/network/serializers.py

from rest_framework import serializers
from .models import Domain, IPAddress, Link

class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['created_at']

class IPAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = IPAddress
        fields = ['id', 'address', 'organization', 'cidr', 'created_at']
        read_only_fields = ['created_at']

class LinkSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.name', read_only=True)
    ip_address = serializers.CharField(source='ip.address', read_only=True)
    
    class Meta:
        model = Link
        fields = ['id', 'domain', 'domain_name', 'ip', 'ip_address', 'method', 'discovered_at']
        read_only_fields = ['discovered_at']
