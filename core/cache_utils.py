from django.core.cache import cache
from django.contrib.auth import get_user_model
import logging
import time

logger = logging.getLogger(__name__)
User = get_user_model()

class CacheManager:
    """Centralized cache management utilities"""
    
    @staticmethod
    def clear_user_cache(user_id):
        """Clear all cache entries for a specific user"""
        cache_keys = [
            f'user_profile_{user_id}',
            f'plans_list_all_{user_id}',
            f'plans_list_monthly_{user_id}',
            f'plans_list_yearly_{user_id}',
        ]
        
        # Clear rate limit cache for current minute
        current_minute = int(time.time() / 60)
        cache_keys.append(f'rate_limit_status_{user_id}_{current_minute}')
        
        # Clear previous minute as well (in case of timing edge cases)
        cache_keys.append(f'rate_limit_status_{user_id}_{current_minute - 1}')
        
        deleted_count = 0
        for key in cache_keys:
            if cache.delete(key):
                deleted_count += 1
        
        logger.info(f"🗑️ Cleared {deleted_count} cache entries for user {user_id}")
        return deleted_count
    
    @staticmethod
    def clear_plan_cache():
        """Clear all plan-related cache entries"""
        # Clear anonymous plan caches
        anonymous_keys = [
            'plans_list_all_anonymous',
            'plans_list_monthly_anonymous',
            'plans_list_yearly_anonymous',
        ]
        
        deleted_count = 0
        for key in anonymous_keys:
            if cache.delete(key):
                deleted_count += 1
        
        # Clear authenticated user plan caches
        try:
            for user in User.objects.all():
                user_keys = [
                    f'plans_list_all_{user.id}',
                    f'plans_list_monthly_{user.id}',
                    f'plans_list_yearly_{user.id}',
                ]
                for key in user_keys:
                    if cache.delete(key):
                        deleted_count += 1
        except Exception as e:
            logger.error(f"Error clearing user plan caches: {e}")
        
        logger.info(f"🗑️ Cleared {deleted_count} plan cache entries")
        return deleted_count
    
    @staticmethod
    def clear_health_cache():
        """Clear health check cache"""
        if cache.delete('health_check_status'):
            logger.info("🗑️ Cleared health check cache")
            return True
        return False
    
    @staticmethod
    def get_cache_stats():
        """Get cache statistics (if supported by backend)"""
        try:
            # This works with django-redis
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            info = redis_conn.info()
            
            return {
                'used_memory': info.get('used_memory_human', 'Unknown'),
                'connected_clients': info.get('connected_clients', 'Unknown'),
                'keyspace_hits': info.get('keyspace_hits', 'Unknown'),
                'keyspace_misses': info.get('keyspace_misses', 'Unknown'),
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

# Convenience functions
def clear_user_cache(user_id):
    """Convenience function to clear user cache"""
    return CacheManager.clear_user_cache(user_id)

def clear_plan_cache():
    """Convenience function to clear plan cache"""
    return CacheManager.clear_plan_cache()

def clear_health_cache():
    """Convenience function to clear health cache"""
    return CacheManager.clear_health_cache()