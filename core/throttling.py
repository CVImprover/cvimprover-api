# core/throttling.py
from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import hashlib

class PlanBasedThrottle(UserRateThrottle):
    """
    Base throttle class that adjusts rate based on user's subscription plan.
    """
    # Override in subclasses
    scope = 'plan_based'
    
    # Define limits for each plan and scope
    PLAN_RATES = {
        'Free': {
            'ai_responses': '3/day',
            'questionnaires': '5/day',
            'api_calls': '100/hour',
        },
        'Basic': {
            'ai_responses': '20/day',
            'questionnaires': '50/day',
            'api_calls': '300/hour',
        },
        'Pro': {
            'ai_responses': '100/day',
            'questionnaires': '200/day',
            'api_calls': '600/hour',
        },
        'Premium': {
            'ai_responses': '1000/day',
            'questionnaires': '1000/day',
            'api_calls': '1200/hour',
        },
    }
    
    def __init__(self):
        super().__init__()
        self.plan_name = None
        self.current_limit = None
        
    def get_cache_key(self, request, view):
        """
        Create a unique cache key for this user/plan/scope combination.
        """
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
    
    def get_rate(self):
        """
        Determine the rate limit based on user's plan.
        """
        if not hasattr(self, 'request') or not self.request:
            return '3/day'  # Default fallback
            
        user = getattr(self.request, 'user', None)
        
        # Anonymous or no plan - use Free tier limits
        if not user or not user.is_authenticated or not user.plan:
            self.plan_name = 'Free'
            return self.PLAN_RATES['Free'].get(self.scope, '3/day')
        
        # Get plan-specific rate
        plan_name = user.plan.name
        self.plan_name = plan_name
        rate = self.PLAN_RATES.get(plan_name, {}).get(self.scope, '3/day')
        self.current_limit = rate
        
        return rate
    
    def throttle_success(self):
        """
        Called when request is allowed. Update the cache.
        """
        return super().throttle_success()
    
    def throttle_failure(self):
        """
        Called when request is throttled. Store info for error response.
        """
        # Calculate when the limit resets
        cache_key = self.get_cache_key(self.request, None)
        history = cache.get(cache_key, [])
        
        if history:
            remaining_duration = self.duration - (self.now - history[-1])
            reset_time = timezone.now() + timedelta(seconds=remaining_duration)
        else:
            reset_time = timezone.now()
        
        # Store throttle info on request for custom error handling
        self.request.throttle_info = {
            'detail': f'{self.scope.replace("_", " ").title()} limit exceeded',
            'current_plan': self.plan_name or 'Free',
            'limit': self.current_limit or self.get_rate(),
            'reset_at': reset_time.isoformat(),
            'upgrade_url': '/core/plans/'
        }
        
        return False


class AIResponseThrottle(PlanBasedThrottle):
    """
    Throttle for AI response generation endpoints.
    Most restrictive since it costs money (OpenAI API calls).
    """
    scope = 'ai_responses'


class QuestionnaireThrottle(PlanBasedThrottle):
    """
    Throttle for questionnaire creation.
    """
    scope = 'questionnaires'


class GeneralAPIThrottle(PlanBasedThrottle):
    """
    General API throttle for all authenticated endpoints.
    """
    scope = 'api_calls'


class AnonRateThrottle(SimpleRateThrottle):
    """
    Strict rate limiting for anonymous/unauthenticated users.
    """
    scope = 'anon'
    
    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None  # Only throttle anonymous users
            
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request)
        }
    
    def get_rate(self):
        """
        Anonymous users get very limited access.
        """
        return '20/hour'


class BurstRateThrottle(SimpleRateThrottle):
    """
    Allow short bursts of requests but prevent sustained high rates.
    """
    scope = 'burst'
    
    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
            
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
    
    def get_rate(self):
        """
        Allow bursts but limit sustained usage.
        """
        if hasattr(self, 'request') and self.request.user.is_authenticated:
            user = self.request.user
            if user.plan and user.plan.name == 'Premium':
                return '100/minute'
            elif user.plan and user.plan.name == 'Pro':
                return '50/minute'
            elif user.plan and user.plan.name == 'Basic':
                return '30/minute'
        
        return '10/minute'  # Free/Anonymous


class IPBasedThrottle(SimpleRateThrottle):
    """
    IP-based throttle for DDoS protection.
    Works even for authenticated users as a safety net.
    """
    scope = 'ip_based'
    
    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
    
    def get_rate(self):
        """
        Per-IP rate limit regardless of authentication.
        """
        return '1000/hour'


class UploadThrottle(PlanBasedThrottle):
    """
    Special throttle for file uploads (resume PDFs).
    """
    scope = 'uploads'
    
    PLAN_RATES = {
        'Free': {'uploads': '3/day'},
        'Basic': {'uploads': '20/day'},
        'Pro': {'uploads': '100/day'},
        'Premium': {'uploads': '500/day'},
    }


# Helper function to get rate limit status for a user
def get_rate_limit_status(user, scope='ai_responses'):
    """
    Get current rate limit status for a user.
    Returns: dict with usage info
    """
    if not user or not user.is_authenticated:
        return None
    
    throttle_class = {
        'ai_responses': AIResponseThrottle,
        'questionnaires': QuestionnaireThrottle,
        'api_calls': GeneralAPIThrottle,
    }.get(scope, AIResponseThrottle)
    
    throttle = throttle_class()
    
    # Create a mock request
    class MockRequest:
        def __init__(self, user):
            self.user = user
            self.META = {}
    
    mock_request = MockRequest(user)
    throttle.request = mock_request
    
    rate = throttle.get_rate()
    num_requests, duration = throttle.parse_rate(rate)
    
    # Get current usage from cache
    cache_key = throttle.get_cache_key(mock_request, None)
    history = cache.get(cache_key, [])
    
    # Filter to requests within the current window
    now = throttle.timer()
    while history and history[-1] <= now - duration:
        history.pop()
    
    used = len(history)
    remaining = max(0, num_requests - used)
    
    # Calculate reset time
    if history:
        reset_seconds = duration - (now - history[-1])
        reset_time = timezone.now() + timedelta(seconds=reset_seconds)
    else:
        reset_time = timezone.now() + timedelta(seconds=duration)
    
    return {
        'scope': scope,
        'limit': num_requests,
        'used': used,
        'remaining': remaining,
        'reset_at': reset_time,
        'plan': user.plan.name if user.plan else 'Free'
    }