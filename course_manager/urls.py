from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import CourseViewSet, QuestionViewSet, MaterialViewSet, SubjectViewSet

router = DefaultRouter()
router.register(r'course', CourseViewSet, basename='course')
router.register(r'subject', SubjectViewSet, basename='subject')
router.register(r'question', QuestionViewSet, basename='question')
router.register(r'material', MaterialViewSet, basename='material')

urlpatterns = [
    path('', include(router.urls)),
]
