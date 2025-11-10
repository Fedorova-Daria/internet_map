from django.db import models
import ipaddress
import uuid

class Domain(models.Model):
    """Доменное имя"""
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name

class IPAddress(models.Model):
    """IP-адрес"""
    address = models.CharField(max_length=45, unique=True)  # IPv4 или IPv6
    organization = models.CharField(max_length=255, null=True, blank=True)
    cidr = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['address']
    
    def __str__(self):
        return self.address
    
    
class ScanSession(models.Model):
    # Поле для корневого домена, который сканировали
    root_domain = models.CharField(max_length=255, db_index=True)
    # Глубина сканирования
    depth = models.PositiveIntegerField(default=3)
    # Статус сессии
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Ожидание'),
        ('running', 'Выполняется'),
        ('completed', 'Завершено'),
        ('failed', 'Ошибка'),
    ])
    # Дата начала
    created_at = models.DateTimeField(auto_now_add=True)
    # Дата завершения
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Scan for {self.root_domain} at {self.created_at}"
    
    
class Link(models.Model):
    """Связь: домен → IP"""
    
    # ✅ Выносим choices в отдельную константу
    class MethodChoices(models.TextChoices):
        DNS = 'dns', 'DNS A Record'
        TLS = 'tls', 'TLS Certificate'
        REVERSE_DNS = 'reverse_dns', 'Reverse DNS'

    # Привязка к сессии
    scan_session = models.ForeignKey(
        ScanSession,
        on_delete=models.CASCADE,
        related_name='links'
    )
    
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name='ip_links')
    ip = models.ForeignKey(IPAddress, on_delete=models.CASCADE, related_name='domain_links')
    discovered_at = models.DateTimeField(auto_now_add=True)
    
    # ✅ Используем константу в поле
    method = models.CharField(
        max_length=50, 
        default=MethodChoices.DNS, 
        choices=MethodChoices.choices
    )
    
    class Meta:
        unique_together = ('scan_session', 'domain', 'ip')
        ordering = ['-discovered_at']
    
    def __str__(self):
        return f"[{self.scan_session_id}] {self.domain.name} → {self.ip.address}"

    
