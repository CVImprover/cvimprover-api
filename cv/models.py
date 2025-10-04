from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError

User = get_user_model()

class CVQuestionnaire(models.Model):
    EXPERIENCE_LEVEL_CHOICES = [
        ('0-2', '0-2 years'),
        ('3-5', '3-5 years'),
        ('6+', '6+ years'),
    ]

    COMPANY_SIZE_CHOICES = [
        ('startup', 'Startup'),
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('enterprise', 'Enterprise'),
    ]

    APPLICATION_TIMELINE_CHOICES = [
        ('immediate', 'Immediate'),
        ('1-3 months', '1-3 months'),
        ('3-6 months', '3-6 months'),
        ('6+ months', '6+ months'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='questionnaires', db_index=True)
    position = models.CharField(max_length=255, help_text="job position (max 255 characters)", db_index=True)
    industry = models.CharField(max_length=255, help_text="industry (max 255 characters)", db_index=True)
    experience_level = models.CharField(max_length=10, choices=EXPERIENCE_LEVEL_CHOICES, db_index=True)
    company_size = models.CharField(max_length=10, choices=COMPANY_SIZE_CHOICES, db_index=True)
    location = models.CharField(max_length=255, blank=True, null=True, help_text="location (max 255 characters)")
    application_timeline = models.CharField(max_length=20, choices=APPLICATION_TIMELINE_CHOICES, db_index=True)
    job_description = models.TextField(blank=True, null=True, help_text="job description (max 5000 characters)")
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resume = models.FileField(upload_to='resumes/', blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'submitted_at'], name='cv_user_submitted_idx'),
            models.Index(fields=['position', 'industry'], name='cv_position_industry_idx'),
            models.Index(fields=['experience_level', 'company_size'], name='cv_exp_company_idx'),
            models.Index(fields=['submitted_at'], name='cv_submitted_at_idx'),
        ]

    def clean(self):
        """
        validate model data at the model level
        """
        super().clean()
        
        if self.job_description and len(self.job_description) > 5000:
            raise ValidationError({
                'job_description': 'job description must be less than 5000 characters'
            })
        
        if self.position and len(self.position) > 255:
            raise ValidationError({
                'position': 'position must be less than 255 characters'
            })
        
        if self.industry and len(self.industry) > 255:
            raise ValidationError({
                'industry': 'industry must be less than 255 characters'
            })
        
        if self.location and len(self.location) > 255:
            raise ValidationError({
                'location': 'location must be less than 255 characters'
            })

    def __str__(self):
        return f"{self.user.username} - {self.position}"


class AIResponse(models.Model):
    questionnaire = models.ForeignKey(CVQuestionnaire, related_name='ai_response', on_delete=models.CASCADE, db_index=True)
    response_text = models.TextField(help_text="ai generated response text")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['questionnaire', 'created_at'], name='ai_quest_created_idx'),
            models.Index(fields=['created_at'], name='ai_created_at_idx'),
        ]

    def clean(self):
        """
        validate model data at the model level
        """
        super().clean()
        
        if self.response_text and len(self.response_text) > 10000:
            raise ValidationError({
                'response_text': 'response text must be less than 10000 characters'
            })

    def __str__(self):
        created = self.created_at
        created = timezone.localtime(created).replace(microsecond=0)
        
        return f"Response for {self.questionnaire.position} - {created.strftime('%Y-%m-%d %H:%M:%S')}"