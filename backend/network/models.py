from django.db import models
import ipaddress
import uuid
from scanner.models import ScanSession


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
    online = models.BooleanField(default=False)

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


class SSLCertificate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scan_session = models.ForeignKey(
        "ScanSession",
        on_delete=models.CASCADE,
        related_name="certificates"
    )

    domain = models.CharField(max_length=255, db_index=True)
    fingerprint_sha256 = models.CharField(max_length=64, unique=True)
    subject = models.JSONField(default=dict, blank=True)
    issuer = models.JSONField(default=dict, blank=True)

    not_before = models.DateTimeField()
    not_after = models.DateTimeField()

    san = models.JSONField(default=list, blank=True)  # Subject Alternative Names
    raw_data = models.TextField(blank=True, null=True)  # PEM, если хочешь сохранить оригинал
    is_expired = models.BooleanField(default=False)

    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "network_ssl_certificate"
        ordering = ("-not_after",)
        indexes = [
            models.Index(fields=["fingerprint_sha256"]),
            models.Index(fields=["domain"]),
        ]

    def __str__(self):
        return f"{self.domain} ({self.fingerprint_sha256[:8]}...)"

    def mark_expired(self):
        """Отметить серт как истекший."""
        self.is_expired = True
        self.save(update_fields=["is_expired"])

