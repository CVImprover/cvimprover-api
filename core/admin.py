from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from .models import User, Plan

# User Admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'plan')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('date_joined', 'last_login', 'stripe_subscription_id', 'stripe_subscription_status',)
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'date_of_birth', 'plan', 'stripe_subscription_id', 'stripe_subscription_status', 'stripe_customer_id')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )

# Plan Admin with validation
class PlanAdminForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        try:
            self.instance.clean()  # call model validation
        except ValidationError as e:
            raise ValidationError(e.message_dict)
        return cleaned_data

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    form = PlanAdminForm
    list_display = ('name', 'stripe_price_id_monthly', 'stripe_price_id_yearly', 'order', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'stripe_price_id_monthly', 'stripe_price_id_yearly')
    ordering = ('order',)
