from django.core.exceptions import PermissionDenied


def can_manage_categories(user):
    """Only ADMIN and CONTENT_MANAGER can manage categories."""
    if not user.is_authenticated:
        raise PermissionDenied
    if user.role not in ("ADMIN", "CONTENT_MANAGER"):
        raise PermissionDenied
    return True


def can_delete_category(user):
    """Only ADMIN can delete categories."""
    return user.is_authenticated and user.role == "ADMIN"