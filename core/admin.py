from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Plan

# Register the custom User model
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'plan')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('date_joined', 'last_login', 'stripe_subscription_id', 'stripe_subscription_status', 'subscription_renewal_date', 'stripe_customer_id')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'date_of_birth', 'plan', 'stripe_subscription_id', 'stripe_subscription_status', 'subscription_renewal_date', 'stripe_customer_id')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'stripe_price_id_monthly', 'stripe_price_id_yearly', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'stripe_price_id_monthly', 'stripe_price_id_yearly')
    ordering = ('name',)