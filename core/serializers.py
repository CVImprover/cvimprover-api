from rest_framework import serializers
from .models import CVQuestionnaire, User
from dj_rest_auth.serializers import UserDetailsSerializer
from core.models import AIResponse

class CVQuestionnaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = CVQuestionnaire
        fields = '__all__'
        read_only_fields = ['user', 'submitted_at']

class CustomUserDetailsSerializer(UserDetailsSerializer):
    email = serializers.EmailField(required=False)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    class Meta(UserDetailsSerializer.Meta):
        model = User
        fields = UserDetailsSerializer.Meta.fields + ('date_of_birth',)



class AIResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIResponse
        fields = ['id', 'questionnaire', 'response_text', 'created_at']
