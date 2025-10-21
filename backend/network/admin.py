from django.contrib import admin
from .models import IPAddress, Domain, Subnet  # обязательно импорт модели!


admin.site.register(IPAddress)
admin.site.register(Domain)
admin.site.register(Subnet)

