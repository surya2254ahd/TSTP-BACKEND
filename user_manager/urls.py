from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import UserViewSet, TempUserViewSet

router = DefaultRouter()
router.register(r'user', UserViewSet, basename='user')
router.register(r'student', TempUserViewSet, basename='temp-user')

urlpatterns = [
    path('', include(router.urls)),
]
