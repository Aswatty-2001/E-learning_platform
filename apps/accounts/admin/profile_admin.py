from django.contrib import admin
from django.utils import timezone
from accounts.models import ContentManagerProfile, AuditLog

@admin.register(ContentManagerProfile)
class ContentManagerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee_id', 'approval_status', 'designation', 'can_publish_directly')
    list_filter = ('approval_status', 'can_publish_directly')
    search_fields = ('user__email', 'employee_id', 'public_display_name')
    actions = ['approve_profiles', 'reject_profiles']

    def approve_profiles(self, request, queryset):
        updated = queryset.update(
            approval_status='APPROVED', 
            approved_by=request.user, 
            approved_at=timezone.now(),
            rejection_reason=''
        )
        # Audit log entry
        for profile in queryset:
            AuditLog.objects.create(
                actor=request.user,
                action='APPROVE_CM',
                target_content_type=None, # Can set ContentType if needed
                target_object_id=profile.user_id,
                changes={'status': 'APPROVED', 'profile_id': str(profile.id)},
                ip_address=request.META.get('REMOTE_ADDR')
            )
        self.message_user(request, f"{updated} Content Manager profile(s) successfully approved.")
    approve_profiles.short_description = "Approve selected Content Managers"

    def reject_profiles(self, request, queryset):
        updated = queryset.update(
            approval_status='REJECTED', 
            approved_by=request.user, 
            approved_at=timezone.now()
        )
        for profile in queryset:
            AuditLog.objects.create(
                actor=request.user,
                action='REJECT_CM',
                target_object_id=profile.user_id,
                changes={'status': 'REJECTED', 'profile_id': str(profile.id)},
                ip_address=request.META.get('REMOTE_ADDR')
            )
        self.message_user(request, f"{updated} Content Manager profile(s) rejected.")
    reject_profiles.short_description = "Reject selected Content Managers"