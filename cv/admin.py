from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from .models import CVQuestionnaire, AIResponse

@admin.register(CVQuestionnaire)
class CVQuestionnaireAdmin(ModelAdmin):
    list_display = ['user', 'position', 'industry', 'experience_level', 'company_size', 'application_timeline', 'submitted_at']
    list_filter = ['industry', 'experience_level', 'company_size', 'application_timeline', 'submitted_at']
    search_fields = ['user__username', 'user__email', 'position', 'industry']
    readonly_fields = ['submitted_at']
    date_hierarchy = 'submitted_at'
    
    fieldsets = (
        (_('User Information'), {
            'fields': ('user',)
        }),
        (_('Job Details'), {
            'fields': ('position', 'industry', 'experience_level', 'company_size', 'location', 'application_timeline')
        }),
        (_('Job Description'), {
            'fields': ('job_description',)
        }),
        (_('Resume'), {
            'fields': ('resume',)
        }),
        (_('Timestamps'), {
            'fields': ('submitted_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(AIResponse)
class AIResponseAdmin(ModelAdmin):
    list_display = ['questionnaire', 'created_at']
    list_filter = ['created_at']
    search_fields = ['questionnaire__user__username', 'questionnaire__position']
    readonly_fields = ['created_at', 'response_text']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Response Information'), {
            'fields': ('questionnaire', 'response_text')
        }),
        (_('Timestamps'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
