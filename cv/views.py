from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import CVQuestionnaire, AIResponse
from .serializers import CVQuestionnaireSerializer, AIResponseSerializer

class CVQuestionnaireViewSet(viewsets.ModelViewSet):
    queryset = CVQuestionnaire.objects.all()
    serializer_class = CVQuestionnaireSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only return the current user's questionnaires
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class AIResponseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AIResponse.objects.all()
    serializer_class = AIResponseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only return the AI response for the current user's questionnaires
        return self.queryset.filter(questionnaire__user=self.request.user)
