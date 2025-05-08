from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import CVQuestionnaireViewSet

router = DefaultRouter()
router.register(r'questionnaire', CVQuestionnaireViewSet, basename='questionnaire')

urlpatterns = [
    path('', include(router.urls)),
]
