from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from accounts.admin.forms import StaffCreationForm
from accounts.admin.inlines import (
    StudentProfileInline, ContentManagerProfileInline,
    SupportProfileInline, AdminProfileInline
)

User = get_user_model()

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    # The form to use when adding a new user
    add_form = StaffCreationForm
    

    # Fields to display in the list view
    list_display = ('email', 'first_name', 'last_name', 'role', 'status', 'is_staff', 'email_verified')
    list_filter = ('role', 'status', 'is_staff', 'is_superuser', 'email_verified')
    search_fields = ('email', 'phone_number', 'first_name', 'last_name')
    ordering = ('-date_joined',) if hasattr(User, 'date_joined') else ('-created_at',)

    # Fieldsets for viewing/editing existing users
    fieldsets = (
        (None, {'fields': ('email', 'phone_number', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'profile_picture', 'date_of_birth', 'gender')}),
        ('Role & Status', {'fields': ('role', 'status', 'must_change_password')}),
        ('Verification', {'fields': ('email_verified', 'email_verified_at', 'phone_verified', 'phone_verified_at')}),
        ('Location & Prefs', {'fields': ('country', 'state', 'city', 'timezone', 'preferred_language')}),
        ('Security & Login', {'fields': ('failed_login_attempts', 'locked_until', 'last_login', 'last_login_ip')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Consent', {'fields': ('terms_accepted_at', 'privacy_accepted_at', 'marketing_opt_in')}),
        ('Metadata', {'fields': ('created_by',)}),
    )
    
    # Fieldsets for adding a NEW user (simplified)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role'),
        }),
    )

    # Dynamically show the correct inline profile based on the user's role
    def get_inlines(self, request, obj=None):
        if obj is None:
            # No inlines during initial creation (profile is auto-created via signal)
            return []
        
        if obj.role == 'STUDENT':
            return [StudentProfileInline]
        elif obj.role == 'CONTENT_MANAGER':
            return [ContentManagerProfileInline]
        elif obj.role == 'SUPPORT':
            return [SupportProfileInline]
        elif obj.role == 'ADMIN':
            return [AdminProfileInline]
        return []

    # Ensure admin creating staff gets recorded as created_by
    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)