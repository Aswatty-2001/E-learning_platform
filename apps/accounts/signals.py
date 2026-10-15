import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from accounts.models import StudentProfile, ContentManagerProfile, SupportProfile, AdminProfile

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == 'STUDENT':
            # Generate simple unique referral code and student ID for now
            # (These will be properly generated via pre_save/save methods in Phase B)
            StudentProfile.objects.create(
                user=instance,
                student_id=f"STU-{instance.id.hex[:6].upper()}",
                referral_code=f"REF{instance.id.hex[:8].upper()}"
            )
        elif instance.role == 'CONTENT_MANAGER':
            ContentManagerProfile.objects.create(
                user=instance,
                employee_id=f"CM-{instance.id.hex[:6].upper()}",
                designation='Instructor',
                qualification='N/A',
                public_display_name=f"{instance.first_name} {instance.last_name}"
            )
        elif instance.role == 'SUPPORT':
            SupportProfile.objects.create(
                user=instance,
                employee_id=f"SP-{instance.id.hex[:6].upper()}",
                designation='Support Agent'
            )
        elif instance.role == 'ADMIN':
            AdminProfile.objects.create(
                user=instance,
                employee_id=f"AD-{instance.id.hex[:6].upper()}",
                designation='Administrator'
            )