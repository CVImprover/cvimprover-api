# core/middleware/rate_limit.py
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class RateLimitMiddleware:
    """
    Middleware for IP-based rate limiting and DDoS protection.
    This works at the middleware level before view processing.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Configurable limits
        self.limits = {
            'requests_per_minute': 60,
            'requests_per_hour': 1000,
            'suspicious_threshold': 100,  # requests/min triggers alert
        }
    
    def __call__(self, request):
        # Skip rate limiting for certain paths
        exempt_paths = ['/admin/', '/static/', '/media/', '/health/']
        if any(request.path.startswith(path) for path in exempt_paths):
            return self.get_response(request)
        
        # Get client IP
        ip_address = self.get_client_ip(request)
        
        # Check if IP is blocked
        if self.is_ip_blocked(ip_address):
            logger.warning(f"Blocked IP attempted access: {ip_address}")
            return JsonResponse({
                'error': 'access_denied',
                'message': 'Your IP has been temporarily blocked due to suspicious activity.',
                'contact': 'Please contact support if you believe this is an error.'
            }, status=403)
        
        # Check rate limits
        if not self.check_rate_limit(ip_address, request):
            logger.warning(f"Rate limit exceeded for IP: {ip_address}")
            return JsonResponse({
                'error': 'rate_limit_exceeded',
                'message': 'Too many requests from your IP address.',
                'retry_after': '60 seconds'
            }, status=429)
        
        # Process request
        response = self.get_response(request)
        
        # Add rate limit headers
        self.add_rate_limit_headers(response, ip_address)
        
        return response
    
    def get_client_ip(self, request):
        """
        Extract client IP from request, considering proxies.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def check_rate_limit(self, ip_address, request):
        """
        Check if IP has exceeded rate limits.
        """
        now = timezone.now()
        
        # Minute-based limiting
        minute_key = f'ratelimit:ip:{ip_address}:minute'
        minute_requests = cache.get(minute_key, [])
        
        # Clean old requests (older than 1 minute)
        minute_requests = [
            req_time for req_time in minute_requests 
            if now - req_time < timedelta(minutes=1)
        ]
        
        # Check minute limit
        if len(minute_requests) >= self.limits['requests_per_minute']:
            # Check if this is suspicious activity
            if len(minute_requests) >= self.limits['suspicious_threshold']:
                self.block_ip(ip_address, duration_minutes=15)
                logger.error(f"Suspicious activity detected from IP: {ip_address}")
            return False
        
        # Hour-based limiting
        hour_key = f'ratelimit:ip:{ip_address}:hour'
        hour_requests = cache.get(hour_key, [])
        
        # Clean old requests (older than 1 hour)
        hour_requests = [
            req_time for req_time in hour_requests 
            if now - req_time < timedelta(hours=1)
        ]
        
        # Check hour limit
        if len(hour_requests) >= self.limits['requests_per_hour']:
            return False
        
        # Update counters
        minute_requests.append(now)
        hour_requests.append(now)
        
        cache.set(minute_key, minute_requests, 60)  # 1 minute TTL
        cache.set(hour_key, hour_requests, 3600)   # 1 hour TTL
        
        return True
    
    def is_ip_blocked(self, ip_address):
        """
        Check if IP is in the blocked list.
        """
        block_key = f'blocked:ip:{ip_address}'
        return cache.get(block_key, False)
    
    def block_ip(self, ip_address, duration_minutes=15):
        """
        Block an IP address for a specified duration.
        """
        block_key = f'blocked:ip:{ip_address}'
        cache.set(block_key, True, duration_minutes * 60)
        
        logger.warning(
            f"IP blocked for {duration_minutes} minutes: {ip_address}",
            extra={'ip_address': ip_address, 'duration_minutes': duration_minutes}
        )
    
    def add_rate_limit_headers(self, response, ip_address):
        """
        Add rate limit information to response headers.
        """
        minute_key = f'ratelimit:ip:{ip_address}:minute'
        minute_requests = cache.get(minute_key, [])
        
        now = timezone.now()
        minute_requests = [
            req_time for req_time in minute_requests 
            if now - req_time < timedelta(minutes=1)
        ]
        
        remaining = max(0, self.limits['requests_per_minute'] - len(minute_requests))
        
        response['X-RateLimit-Limit'] = str(self.limits['requests_per_minute'])
        response['X-RateLimit-Remaining'] = str(remaining)
        response['X-RateLimit-Reset'] = str(int((now + timedelta(minutes=1)).timestamp()))
        
        return response


class RequestLoggingMiddleware:
    """
    Log all API requests for monitoring and debugging.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip logging for certain paths
        skip_paths = ['/static/', '/media/', '/admin/jsi18n/']
        if any(request.path.startswith(path) for path in skip_paths):
            return self.get_response(request)
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Log request
        user_id = request.user.id if request.user.is_authenticated else 'anonymous'
        
        logger.info(
            f"API Request: {request.method} {request.path}",
            extra={
                'method': request.method,
                'path': request.path,
                'user_id': user_id,
                'ip_address': ip,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            }
        )
        
        response = self.get_response(request)
        
        # Log response
        logger.info(
            f"API Response: {request.method} {request.path} - {response.status_code}",
            extra={
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'user_id': user_id,
            }
        )
        
        return response