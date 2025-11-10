from django.contrib import admin
from .models import Domain, IPAddress, Link

@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(IPAddress)
class IPAddressAdmin(admin.ModelAdmin):
    list_display = ('address', 'organization', 'created_at')
    search_fields = ('address', 'organization')

@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    list_display = ('domain', 'ip', 'method', 'discovered_at')
    list_filter = ('method', 'discovered_at')
    search_fields = ('domain__name', 'ip__address')