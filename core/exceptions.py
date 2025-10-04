# core/exceptions.py
from rest_framework.views import exception_handler
from rest_framework import status
from rest_framework.response import Response

def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides detailed rate limit information.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # Check if this is a throttle exception
    if response is not None and response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        request = context.get('request')
        
        # Check if we have custom throttle info
        if hasattr(request, 'throttle_info'):
            throttle_info = request.throttle_info
            
            custom_response_data = {
                'error': 'rate_limit_exceeded',
                'message': throttle_info.get('detail', 'Rate limit exceeded'),
                'current_plan': throttle_info.get('current_plan', 'Free'),
                'limit': throttle_info.get('limit', 'Unknown'),
                'reset_at': throttle_info.get('reset_at'),
                'suggestion': {
                    'message': 'Upgrade your plan for higher limits',
                    'upgrade_url': throttle_info.get('upgrade_url', '/core/plans/')
                }
            }
            
            # Add plan-specific upgrade suggestions
            current_plan = throttle_info.get('current_plan', 'Free')
            if current_plan == 'Free':
                custom_response_data['suggestion']['recommended_plan'] = 'Basic'
                custom_response_data['suggestion']['new_limit'] = '20 AI responses/day'
            elif current_plan == 'Basic':
                custom_response_data['suggestion']['recommended_plan'] = 'Pro'
                custom_response_data['suggestion']['new_limit'] = '100 AI responses/day'
            elif current_plan == 'Pro':
                custom_response_data['suggestion']['recommended_plan'] = 'Premium'
                custom_response_data['suggestion']['new_limit'] = 'Unlimited AI responses'
            
            response.data = custom_response_data
        else:
            # Fallback for standard throttle errors
            response.data = {
                'error': 'rate_limit_exceeded',
                'message': 'Too many requests. Please try again later.',
                'detail': str(exc)
            }
    
    return response