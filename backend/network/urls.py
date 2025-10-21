from rest_framework.routers import DefaultRouter
from .views import DomainViewSet, IPAddressViewSet, SubnetViewSet

router = DefaultRouter()
router.register(r'domain', DomainViewSet)
router.register(r'ipaddress', IPAddressViewSet)
router.register(r'subnet', SubnetViewSet)

urlpatterns = router.urls
