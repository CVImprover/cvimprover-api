from rest_framework import serializers
from .models import CVQuestionnaire, AIResponse

class CVQuestionnaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = CVQuestionnaire
        fields = '__all__'
        read_only_fields = ['user', 'submitted_at']



class AIResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIResponse
        fields = ['id', 'questionnaire', 'response_text', 'created_at']
