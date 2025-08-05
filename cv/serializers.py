from rest_framework import serializers
from .models import CVQuestionnaire, AIResponse

class CVQuestionnaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = CVQuestionnaire
        fields = '__all__'
        read_only_fields = ['user', 'submitted_at']



class AIResponseSerializer(serializers.ModelSerializer):
    prompt = serializers.CharField(write_only=True, required=True, help_text="Prompt to send to the AI model.")

    class Meta:
        model = AIResponse
        fields = ['id', 'questionnaire', 'created_at', 'prompt', 'response_text']
