from django.core.cache import cache
from django.db.models import Prefetch
from .models import Category

CACHE_KEY = "menu_tree_v1"
CACHE_TIMEOUT = 300  # 5 minutes


def get_menu_tree():
    tree = cache.get(CACHE_KEY)
    if tree is not None:
        return tree
    subs_qs = Category.objects.filter(is_active=True).only("name", "slug", "menu_order")
    mains = (
        Category.objects.filter(parent__isnull=True, is_active=True)
        .prefetch_related(Prefetch("children", queryset=subs_qs, to_attr="active_children"))
        .order_by("menu_order", "name")
    )
    tree = list(mains)
    cache.set(CACHE_KEY, tree, CACHE_TIMEOUT)
    return tree


def invalidate_menu_cache():
    cache.delete(CACHE_KEY)