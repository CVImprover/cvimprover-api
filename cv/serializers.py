from rest_framework import serializers
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
import re
from .models import CVQuestionnaire, AIResponse

def sanitize_text(text):
    """
    sanitize user input by removing html tags and dangerous content
    """
    if not text:
        return text
    
    text = strip_tags(text)
    
    text = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', text, flags=re.IGNORECASE)
    
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    
    text = re.sub(r'\bon\w+\s*=', '', text, flags=re.IGNORECASE)
    
    text = re.sub(r'data:text/html[^"\'>\s]*', '', text, flags=re.IGNORECASE)
    
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


class CVQuestionnaireSerializer(serializers.ModelSerializer):
    job_description = serializers.CharField(
        max_length=5000,
        required=False,
        allow_blank=True,
        help_text="job description (max 5000 characters, html will be stripped)"
    )
    position = serializers.CharField(
        max_length=255,
        help_text="job position (max 255 characters)"
    )
    industry = serializers.CharField(
        max_length=255,
        help_text="industry (max 255 characters)"
    )
    location = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="location (max 255 characters)"
    )

    class Meta:
        model = CVQuestionnaire
        fields = '__all__'
        read_only_fields = ['user', 'submitted_at']

    def validate_job_description(self, value):
        """
        validate and sanitize job_description field
        """
        if value:
            sanitized = sanitize_text(value)
            
            if len(sanitized) > 5000:
                raise serializers.ValidationError("job description must be less than 5000 characters")
            
            return sanitized
        return value

    def validate_position(self, value):
        """
        validate and sanitize position field
        """
        if value:
            sanitized = sanitize_text(value)
            if len(sanitized) > 255:
                raise serializers.ValidationError("position must be less than 255 characters")
            return sanitized
        return value

    def validate_industry(self, value):
        """
        validate and sanitize industry field
        """
        if value:
            sanitized = sanitize_text(value)
            if len(sanitized) > 255:
                raise serializers.ValidationError("industry must be less than 255 characters")
            return sanitized
        return value

    def validate_location(self, value):
        """
        validate and sanitize location field
        """
        if value:
            sanitized = sanitize_text(value)
            if len(sanitized) > 255:
                raise serializers.ValidationError("location must be less than 255 characters")
            return sanitized
        return value

class AIResponseSerializer(serializers.ModelSerializer):
    prompt = serializers.CharField(
        write_only=True, 
        required=True, 
        max_length=5000,
        help_text="prompt to send to the ai model (max 5000 characters, html will be stripped)"
    )

    class Meta:
        model = AIResponse
        fields = ['id', 'questionnaire', 'created_at', 'prompt', 'response_text']

    def validate_prompt(self, value):
        """
        validate and sanitize prompt field
        """
        if value:
            sanitized = sanitize_text(value)
            
            if len(sanitized) > 5000:
                raise serializers.ValidationError("prompt must be less than 5000 characters")
            
            return sanitized
        return value
