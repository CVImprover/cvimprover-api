from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import CVQuestionnaire

class CVQuestionnaireAdmin(admin.ModelAdmin):
    list_display = ['user', 'position', 'industry', 'experience_level', 'company_size', 'application_timeline', 'submitted_at']
    search_fields = ['user__username', 'position', 'industry']

admin.site.register(CVQuestionnaire, CVQuestionnaireAdmin)
