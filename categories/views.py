from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST

from accounts.models import AuditLog
from .models import Category
from .services import get_menu_tree
from .permissions import can_manage_categories


def _log(request, action, obj, changes=None):
    AuditLog.objects.create(
        actor=request.user,
        action=action,
        target_object_id=obj.pk,
        changes=changes or {},
        ip_address=request.META.get('REMOTE_ADDR'),
        metadata={"model": "Category", "name": obj.name},
    )


# ===================== Staff: menu management =====================

def menu_management(request):
    can_manage_categories(request.user)
    search = request.GET.get("search", "").strip()
    
    if search:
        # Search by parent category name — fetch that parent + its subcategories
        mains = Category.objects.filter(
            parent__isnull=True, name__icontains=search
        ).order_by("menu_order", "name")
    else:
        mains = Category.objects.filter(parent__isnull=True).order_by("menu_order", "name")
    
    rows = []
    for m in mains:
        rows.append((m, 0))
        for s in m.children.order_by("menu_order", "name"):
            rows.append((s, 1))
    
    # Get all parent categories for the dropdown filter
    all_parents = Category.objects.filter(parent__isnull=True).order_by("menu_order", "name")
    
    return render(request, "categories/menu_management.html", {
        "rows": rows, 
        "search": search,
        "all_parents": all_parents,
    })


def _save_category(request, cat, is_sub=False):
    """Helper to handle save logic for both parent and sub forms."""
    name = request.POST.get("name", "").strip()
    slug = request.POST.get("slug", "").strip()
    menu_order_raw = request.POST.get("menu_order", "").strip()
    description = request.POST.get("description", "").strip()
    is_active = request.POST.get("is_active") == "on"

    # Word count check for description (max 200 words)
    if description:
        word_count = len(description.split())
        if word_count > 200:
            return False, f"Description must not exceed 200 words (currently {word_count} words)."

    cat.name = name
    cat.slug = slug
    
    # Auto-calculate menu order if empty or 0 (new categories get next free position)
    if not menu_order_raw or menu_order_raw == "0":
        siblings = Category.objects.filter(parent=cat.parent)
        if siblings.exists():
            max_order = siblings.order_by("-menu_order").first().menu_order
            cat.menu_order = max_order + 1
        else:
            cat.menu_order = 1
    else:
        try:
            cat.menu_order = int(menu_order_raw)
        except ValueError:
            cat.menu_order = 0
    
    cat.description = description
    cat.is_active = is_active
    cat.updated_by = request.user
    if cat._state.adding:
        cat.created_by = request.user

    try:
        cat.full_clean()
    except Exception as e:
        # Extract first error message for cleaner display
        err_str = str(e)
        if "unique_name_per_parent_ci" in err_str:
            scope = "this parent category" if cat.parent_id else "parent categories"
            return False, f"A category with this name already exists under {scope}."
        return False, err_str

    try:
        cat.save()
        _log(request, "CATEGORY_CREATE", cat,
             {"name": cat.name, "slug": cat.slug, "parent": cat.parent_id})
        messages.success(request, "Category saved successfully.")
        return True, None
    except Exception as e:
        err_msg = str(e)
        if "unique_name_per_parent_ci" in err_msg:
            scope = "this parent category" if cat.parent_id else "parent categories"
            return False, f"A category with this name already exists under {scope}."
        if "unique" in err_msg.lower() and "slug" in err_msg.lower():
            return False, "This slug is already taken. Please use a different slug."
        return False, err_msg




def parent_add_view(request):
    """Add a new parent (main) category."""
    can_manage_categories(request.user)
    cat = Category()
    # Calculate suggested menu order (next free position)
    existing = Category.objects.filter(parent__isnull=True)
    suggested_order = existing.order_by("-menu_order").first().menu_order + 1 if existing.exists() else 1
    
    if request.method == "POST":
        ok, err = _save_category(request, cat)
        if ok:
            return redirect("categories:menu_management")
        messages.error(request, err)
    return render(request, "categories/parent_add.html", {"cat": cat, "suggested_order": suggested_order})


def sub_add_view(request):
    """Add a new subcategory (must choose a parent)."""
    can_manage_categories(request.user)
    cat = Category()
    parents = Category.objects.filter(parent__isnull=True, is_active=True).order_by("menu_order", "name")
    
    # Calculate suggested menu order for subcategories
    selected_parent_id = request.POST.get("parent") if request.method == "POST" else (parents.first().pk if parents.exists() else None)
    suggested_order = 1
    if selected_parent_id:
        subs = Category.objects.filter(parent_id=selected_parent_id)
        suggested_order = subs.order_by("-menu_order").first().menu_order + 1 if subs.exists() else 1
    
    if request.method == "POST":
        parent_id = request.POST.get("parent", "").strip()
        if not parent_id:
            messages.error(request, "Please select a parent category.")
        else:
            try:
                cat.parent_id = int(parent_id)
            except ValueError:
                messages.error(request, "Invalid parent category.")
        ok, err = _save_category(request, cat)
        if ok:
            return redirect("categories:menu_management")
        if err:
            messages.error(request, err)
    return render(request, "categories/sub_add.html", {"cat": cat, "parents": parents, "suggested_order": suggested_order})

def category_edit_view(request, pk):
    """Edit an existing category."""
    can_manage_categories(request.user)
    cat = get_object_or_404(Category, pk=pk)
    parents = Category.objects.filter(parent__isnull=True).exclude(pk=pk).order_by("menu_order", "name")
    if request.method == "POST":
        parent_id = request.POST.get("parent", "").strip()
        cat.parent_id = int(parent_id) if parent_id else None
        ok, err = _save_category(request, cat)
        if ok:
            return redirect("categories:menu_management")
        messages.error(request, err)
    return render(request, "categories/category_edit.html", {"cat": cat, "parents": parents})


@require_POST
def category_toggle(request, pk):
    """AJAX endpoint to hide/show a category (no page reload)."""
    can_manage_categories(request.user)
    cat = get_object_or_404(Category, pk=pk)
    cat.is_active = not cat.is_active
    cat.updated_by = request.user
    cat.save(update_fields=["is_active", "updated_by", "updated_at"])
    _log(request, "CATEGORY_HIDE" if not cat.is_active else "CATEGORY_SHOW", cat)
    
    # If it's an AJAX request, return JSON
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        from django.http import JsonResponse
        return JsonResponse({
            "success": True,
            "is_active": cat.is_active,
            "status_badge": "● Active" if cat.is_active else "○ Hidden",
            "badge_class": "badge-active" if cat.is_active else "badge-hidden",
            "button_text": "Hide" if cat.is_active else "Show",
        })
    
    messages.success(request, f"Category {'hidden' if not cat.is_active else 'shown'}.")
    return redirect("categories:menu_management")


def category_move(request, pk, direction):
    """Move a category up or down among its siblings."""
    can_manage_categories(request.user)
    cat = get_object_or_404(Category, pk=pk)
    siblings = list(Category.objects.filter(parent=cat.parent).order_by("menu_order", "name"))
    idx = next((i for i, s in enumerate(siblings) if s.pk == cat.pk), None)
    if idx is None:
        return redirect("categories:menu_management")
    if direction == "up" and idx > 0:
        swap = siblings[idx - 1]
    elif direction == "down" and idx < len(siblings) - 1:
        swap = siblings[idx + 1]
    else:
        return redirect("categories:menu_management")
    cat.menu_order, swap.menu_order = swap.menu_order, cat.menu_order
    cat.updated_by = request.user
    swap.updated_by = request.user
    cat.save(update_fields=["menu_order", "updated_by", "updated_at"])
    swap.save(update_fields=["menu_order", "updated_by", "updated_at"])
    _log(request, "CATEGORY_REORDER", cat, {"direction": direction})
    return redirect("categories:menu_management")


# ===================== Public: category page =====================

def category_page(request, slug, sub_slug=None):
    main = get_object_or_404(Category, slug=slug, parent__isnull=True, is_active=True)
    sub = None
    if sub_slug:
        sub = get_object_or_404(Category, slug=sub_slug, parent=main, is_active=True)
    subs = main.children.filter(is_active=True).order_by("menu_order", "name")
    return render(request, "categories/category_page.html", {
        "main": main, "sub": sub, "subs": subs, "menu_tree": get_menu_tree(),
    })



