from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import DomainViewSet, IPAddressViewSet, SubnetViewSet

router = DefaultRouter()
router.register(r'domain', DomainViewSet)
router.register(r'ipaddress', IPAddressViewSet)
router.register(r'subnet', SubnetViewSet)

urlpatterns = [
    path('', include(router.urls)),
]