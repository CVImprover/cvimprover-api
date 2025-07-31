from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

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

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='questionnaires')
    position = models.CharField(max_length=255)
    industry = models.CharField(max_length=255)
    experience_level = models.CharField(max_length=10, choices=EXPERIENCE_LEVEL_CHOICES)
    company_size = models.CharField(max_length=10, choices=COMPANY_SIZE_CHOICES)
    location = models.CharField(max_length=255, blank=True, null=True)
    application_timeline = models.CharField(max_length=20, choices=APPLICATION_TIMELINE_CHOICES)
    job_description = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    resume = models.FileField(upload_to='resumes/', blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.position}"


class AIResponse(models.Model):
    # model was OneToOneField
    questionnaire = models.ForeignKey(
        CVQuestionnaire, 
        related_name='ai_response', 
        on_delete=models.CASCADE
    )
    response_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        created = self.created_at
        if timezone.is_aware(created):
            created = timezone.localtime(created)
        created = created.replace(microsecond=0)
        return f"Response for {self.questionnaire.position} - {created.strftime('%Y-%m-%d %H:%M:%S')}"
