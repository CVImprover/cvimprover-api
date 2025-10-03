from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from .models import User, Plan
from rest_framework.authtoken.admin import TokenAdmin
from rest_framework.authtoken.models import TokenProxy

admin.site.unregister(Group)
admin.site.unregister(TokenProxy)

@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'plan', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'plan', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('date_joined', 'last_login', 'stripe_subscription_id', 'stripe_subscription_status', 'stripe_customer_id')
    ordering = ('-date_joined',)
    date_hierarchy = 'date_joined'

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {
            'fields': ('first_name', 'last_name', 'email', 'date_of_birth'),
            'classes': ('tab',)
        }),
        (_('Subscription'), {
            'fields': ('plan', 'stripe_subscription_id', 'stripe_subscription_status', 'stripe_customer_id'),
            'classes': ('tab',)
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('tab',)
        }),
        (_('Important dates'), {
            'fields': ('last_login', 'date_joined'),
            'classes': ('tab',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
        (_('Personal info'), {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'date_of_birth'),
        }),
        (_('Subscription'), {
            'classes': ('wide',),
            'fields': ('plan',),
        }),
    )

@admin.register(Plan)
class PlanAdmin(ModelAdmin):
    list_display = ('name', 'stripe_price_id_monthly', 'stripe_price_id_yearly', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'stripe_price_id_monthly', 'stripe_price_id_yearly')
    ordering = ('name',)
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (_('Plan Information'), {
            'fields': ('name', 'description')
        }),
        (_('Stripe Configuration'), {
            'fields': ('stripe_price_id_monthly', 'stripe_price_id_yearly'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass

@admin.register(TokenProxy)
class TokenAdmin(TokenAdmin,ModelAdmin):
    pass