from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CVQuestionnaireViewSet, AIResponseViewSet

router = DefaultRouter()
router.register(r'questionnaire', CVQuestionnaireViewSet, basename='questionnaire')
router.register(r'ai-responses', AIResponseViewSet, basename='ai-response')


urlpatterns = [
    path('', include(router.urls)),
]
