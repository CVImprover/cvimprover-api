# core/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    date_of_birth = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ['date_joined']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username}"

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

    # Add file upload field
    resume = models.FileField(upload_to='resumes/', blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.position}"
