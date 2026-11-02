from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Category
from .services import invalidate_menu_cache


@receiver(post_save, sender=Category)
def _cat_saved(sender, **kwargs):
    invalidate_menu_cache()


@receiver(post_delete, sender=Category)
def _cat_deleted(sender, **kwargs):
    invalidate_menu_cache()