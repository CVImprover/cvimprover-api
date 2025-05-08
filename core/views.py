from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from dj_rest_auth.views import UserDetailsView
from .models import CVQuestionnaire
from .serializers import CustomUserDetailsSerializer, CVQuestionnaireSerializer


class CustomUserDetailsView(UserDetailsView):
    serializer_class = CustomUserDetailsSerializer
    permission_classes = [IsAuthenticated]

class CVQuestionnaireViewSet(viewsets.ModelViewSet):
    queryset = CVQuestionnaire.objects.all()
    serializer_class = CVQuestionnaireSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only return the current user's questionnaires
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
