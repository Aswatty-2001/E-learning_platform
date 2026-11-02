import re
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import slugify

MAX_CATEGORY_DEPTH = 2  # main + sub; bump to 3 later


class Category(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.PROTECT, related_name="children",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    menu_order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="categories_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="categories_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["menu_order", "name"]
        indexes = [
            models.Index(fields=["parent", "is_active", "menu_order"]),
        ]
        constraints = [
            # Case-insensitive unique name per parent (siblings)
            models.UniqueConstraint(
                models.functions.Lower("name"),
                models.functions.Coalesce("parent", models.Value(-1)),
                name="unique_name_per_parent_ci",
            ),
            # Separate unique for top-level (parent IS NULL) — redundant safety
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="category_name_not_empty",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        # Normalise name: trim + collapse repeated spaces
        if self.name:
            self.name = re.sub(r'\s+', ' ', self.name.strip())
        
        if not self.name:
            raise ValidationError({"name": "Name is required."})
        
        # Length: 3 to 30 characters
        if len(self.name) < 3:
            raise ValidationError({"name": "Name must be at least 3 characters long."})
        if len(self.name) > 30:
            raise ValidationError({"name": "Name must not exceed 30 characters."})
        
        # Only letters, numbers, and spaces allowed
        if not re.match(r'^[A-Za-z0-9 ]+$', self.name):
            raise ValidationError({"name": "Name can only contain letters, numbers, and spaces (no special characters)."})
        
        # No self-parent
        if self.parent_id and self.parent_id == self.pk:
            raise ValidationError({"parent": "A category cannot be its own parent."})
        
        # Depth limit
        depth = 1
        p = self.parent
        seen = set()
        while p is not None:
            if p.pk in seen:
                raise ValidationError({"parent": "Cycle detected."})
            seen.add(p.pk)
            depth += 1
            if depth > MAX_CATEGORY_DEPTH:
                raise ValidationError({"parent": f"Maximum depth is {MAX_CATEGORY_DEPTH} levels."})
            p = p.parent
        
        # Check duplicates (case-insensitive, same parent)
        qs = Category.objects.filter(
            name__iexact=self.name, parent=self.parent
        ).exclude(pk=self.pk)
        if qs.exists():
            scope = "this parent category" if self.parent_id else "parent categories"
            raise ValidationError({"name": f"A category named '{self.name}' already exists under {scope}."})

    def save(self, *args, **kwargs):
        # Slug auto-fill
        if not self.slug:
            base = self.name.replace("&", "and")
            self.slug = slugify(base)
            # Ensure uniqueness
            orig = self.slug
            n = 2
            qs = Category.objects.filter(slug__startswith=orig)
            while qs.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{orig}-{n}"
                n += 1
        # menu_order auto-assign for new main categories
        if self._state.adding and self.parent_id is None and self.menu_order == 0:
            top = Category.objects.filter(parent__isnull=True)
            if top.exists():
                self.menu_order = top.order_by("-menu_order").first().menu_order + 1
            else:
                self.menu_order = 1
        super().save(*args, **kwargs)

    def has_children(self):
        return self.children.exists()

    def has_courses(self):
        """Hook for future Course model. Always False until courses exist."""
        course_model = models.get_model("courses", "Course") if "courses" in settings.INSTALLED_APPS else None
        if course_model is None:
            return False
        return course_model.objects.filter(category=self).exists()

    def can_delete(self):
        return not self.has_children() and not self.has_courses()