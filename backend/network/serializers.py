from rest_framework import serializers
from .models import Domain, IPAddress, Subnet

class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ['id', 'domain_name', 'last_seen', 'online']


class IPAddressSerializer(serializers.ModelSerializer):
    domains = DomainSerializer(many=True, read_only=True)

    class Meta:
        model = IPAddress
        fields = ['id', 'address', 'online', 'domains']


class SubnetSerializer(serializers.ModelSerializer):
    ips = IPAddressSerializer(many=True, read_only=True)

    class Meta:
        model = Subnet
        fields = ['id', 'network', 'network_name', 'ips']
