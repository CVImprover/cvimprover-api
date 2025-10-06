from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.contrib.auth import get_user_model
from .models import Plan
from .cache_utils import CacheManager
import logging
import time

logger = logging.getLogger(__name__)
User = get_user_model()

@receiver(post_save, sender=Plan)
@receiver(post_delete, sender=Plan)
def invalidate_plan_cache(sender, **kwargs):
    """Invalidate plan-related cache when Plan objects change"""
    
    # Clear all plan list caches using cache manager
    deleted_count = CacheManager.clear_plan_cache()
    logger.info(f"🗑️ Invalidated {deleted_count} plan cache entries due to Plan model changes")

@receiver(post_save, sender=User)
def invalidate_user_cache(sender, instance, **kwargs):
    """Invalidate user-specific caches when User objects change"""
    
    # Clear user-specific caches
    deleted_count = CacheManager.clear_user_cache(instance.id)
    logger.info(f"🗑️ Invalidated {deleted_count} cache entries for user {instance.id}")