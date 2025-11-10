# backend/network/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DomainViewSet, IPAddressViewSet, LinkViewSet

router = DefaultRouter()
router.register(r'domains', DomainViewSet, basename='domain')
router.register(r'ips', IPAddressViewSet, basename='ip')
router.register(r'links', LinkViewSet, basename='link')

urlpatterns = [
    path('', include(router.urls)),
]
