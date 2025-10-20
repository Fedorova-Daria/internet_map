from django.db import models
import ipaddress


class Domain(models.Model):
    domain_name = models.CharField(max_length=255, unique=True)
    last_seen = models.DateTimeField(auto_now=True)
    online = models.BooleanField(default=False)
    ips = models.ManyToManyField('IPAddress', related_name='domains')

    def __str__(self):
        return self.domain_name


class IPAddress(models.Model):
    address = models.GenericIPAddressField()
    subnet = models.ManyToManyField('Subnet', related_name='ips')
    online = models.BooleanField()

    def __str__(self):
        return self.address


class Subnet(models.Model):
    """
        Представляет IPv4 подсеть.
        Пример: 217.116.51.0/24
        """
    network = models.CharField(max_length=32, unique=True, help_text="Например, 217.116.51.0/24")
    network_name = models.CharField()

    def __str__(self):
        return self.network

    @property
    def network_obj(self):
        """Возвращает ipaddress.IPv4Network объект."""
        return ipaddress.ip_network(self.network)

    def contains(self, ip: str) -> bool:
        """Проверяет, принадлежит ли IP этой подсети."""
        try:
            return ipaddress.ip_address(ip) in self.network_obj
        except ValueError:
            return False

