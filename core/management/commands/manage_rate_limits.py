# core/management/commands/manage_rate_limits.py

from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from django.contrib.auth import get_user_model
from core.throttling import get_rate_limit_status
from datetime import datetime
import json

User = get_user_model()

class Command(BaseCommand):
    help = 'Manage rate limits: view status, reset limits, block/unblock IPs'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            type=str,
            choices=['status', 'reset', 'block-ip', 'unblock-ip', 'list-blocked', 'clear-all'],
            help='Action to perform'
        )
        
        parser.add_argument(
            '--user',
            type=str,
            help='Username or email for user-specific actions'
        )
        
        parser.add_argument(
            '--ip',
            type=str,
            help='IP address for block/unblock actions'
        )
        
        parser.add_argument(
            '--scope',
            type=str,
            choices=['ai_responses', 'questionnaires', 'api_calls', 'all'],
            default='all',
            help='Scope for rate limit actions'
        )
        
        parser.add_argument(
            '--duration',
            type=int,
            default=15,
            help='Block duration in minutes (default: 15)'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'status':
            self.show_status(options)
        elif action == 'reset':
            self.reset_limits(options)
        elif action == 'block-ip':
            self.block_ip(options)
        elif action == 'unblock-ip':
            self.unblock_ip(options)
        elif action == 'list-blocked':
            self.list_blocked_ips()
        elif action == 'clear-all':
            self.clear_all_limits()

    def show_status(self, options):
        """Show rate limit status for a user."""
        user_identifier = options.get('user')
        
        if not user_identifier:
            self.stdout.write(self.style.ERROR('--user is required for status action'))
            return
        
        try:
            user = User.objects.get(username=user_identifier)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email=user_identifier)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User not found: {user_identifier}'))
                return
        
        self.stdout.write(self.style.SUCCESS(f'\n📊 Rate Limit Status for {user.username}'))
        self.stdout.write(f'Plan: {user.plan.name if user.plan else "No Plan"}')
        self.stdout.write('-' * 60)
        
        scopes = ['ai_responses', 'questionnaires', 'api_calls'] if options['scope'] == 'all' else [options['scope']]
        
        for scope in scopes:
            status = get_rate_limit_status(user, scope)
            if status:
                self.stdout.write(f'\n🔹 {scope.upper().replace("_", " ")}:')
                self.stdout.write(f'  Limit: {status["limit"]}')
                self.stdout.write(f'  Used: {status["used"]}')
                self.stdout.write(f'  Remaining: {status["remaining"]}')
                self.stdout.write(f'  Resets at: {status["reset_at"].strftime("%Y-%m-%d %H:%M:%S")}')
        
        self.stdout.write('')

    def reset_limits(self, options):
        """Reset rate limits for a user."""
        user_identifier = options.get('user')
        
        if not user_identifier:
            self.stdout.write(self.style.ERROR('--user is required for reset action'))
            return
        
        try:
            user = User.objects.get(username=user_identifier)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email=user_identifier)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User not found: {user_identifier}'))
                return
        
        scopes = ['ai_responses', 'questionnaires', 'api_calls'] if options['scope'] == 'all' else [options['scope']]
        
        for scope in scopes:
            cache_key = f'throttle_{scope}_{user.pk}'
            cache.delete(cache_key)
        
        self.stdout.write(self.style.SUCCESS(f'✅ Rate limits reset for {user.username} (scopes: {", ".join(scopes)})'))

    def block_ip(self, options):
        """Block an IP address."""
        ip_address = options.get('ip')
        duration = options.get('duration', 15)
        
        if not ip_address:
            self.stdout.write(self.style.ERROR('--ip is required for block-ip action'))
            return
        
        block_key = f'blocked:ip:{ip_address}'
        cache.set(block_key, True, duration * 60)
        
        self.stdout.write(self.style.SUCCESS(f'🚫 IP {ip_address} blocked for {duration} minutes'))

    def unblock_ip(self, options):
        """Unblock an IP address."""
        ip_address = options.get('ip')
        
        if not ip_address:
            self.stdout.write(self.style.ERROR('--ip is required for unblock-ip action'))
            return
        
        block_key = f'blocked:ip:{ip_address}'
        cache.delete(block_key)
        
        self.stdout.write(self.style.SUCCESS(f'✅ IP {ip_address} unblocked'))

    def list_blocked_ips(self):
        """List all blocked IPs (this is tricky with Redis, showing concept)."""
        self.stdout.write(self.style.WARNING('⚠️  Listing blocked IPs requires Redis SCAN operation'))
        self.stdout.write('Note: This is a placeholder. Full implementation requires direct Redis access.')
        
        # This would require direct Redis connection to scan keys
        # For now, just show the concept
        self.stdout.write('\nTo list blocked IPs manually, use:')
        self.stdout.write('  redis-cli KEYS "blocked:ip:*"')

    def clear_all_limits(self):
        """Clear all rate limit counters (use with caution)."""
        confirm = input('⚠️  This will clear ALL rate limit counters. Are you sure? (yes/no): ')
        
        if confirm.lower() != 'yes':
            self.stdout.write('Cancelled.')
            return
        
        # Clear throttle keys (pattern-based deletion)
        self.stdout.write('Clearing all rate limit counters...')
        
        # Note: This is a simplified version
        # Full implementation would scan and delete all throttle keys
        cache.clear()
        
        self.stdout.write(self.style.SUCCESS('✅ All rate limit counters cleared'))