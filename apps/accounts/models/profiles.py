import uuid
from django.db import models
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField

class StudentProfile(models.Model):
    class SkillLevel(models.TextChoices):
        BEGINNER = 'BEGINNER', 'Beginner'
        INTERMEDIATE = 'INTERMEDIATE', 'Intermediate'
        ADVANCED = 'ADVANCED', 'Advanced'

    class ObjectiveType(models.TextChoices):
        EXAM = 'EXAM', 'Exam'
        ACADEMIC = 'ACADEMIC', 'Academic'
        CAREER = 'CAREER', 'Career'
        HOBBY = 'HOBBY', 'Hobby'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=20, unique=True) # e.g. STU-2026-000123
    
    areas_of_interest = models.JSONField(default=list, blank=True)
    learning_goals = models.JSONField(default=list, blank=True)
    skill_level = models.CharField(max_length=20, choices=SkillLevel.choices, blank=True)
    preferred_study_language = models.CharField(max_length=10, default='en')
    daily_study_minutes = models.PositiveIntegerField(null=True, blank=True)
    objective_type = models.CharField(max_length=20, choices=ObjectiveType.choices, blank=True)
    target_exam_or_career = models.CharField(max_length=120, blank=True)
    
    education_level = models.CharField(max_length=80, blank=True)
    institution_name = models.CharField(max_length=160, blank=True)
    field_of_study = models.CharField(max_length=120, blank=True)
    
    guardian_name = models.CharField(max_length=120, blank=True)
    guardian_phone = PhoneNumberField(null=True, blank=True)
    
    organisation = models.ForeignKey('accounts.Organisation', null=True, blank=True, on_delete=models.SET_NULL)
    referral_code = models.CharField(max_length=16, unique=True)
    referred_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='referrals')
    
    notify_email = models.BooleanField(default=True)
    notify_sms = models.BooleanField(default=False)
    notify_push = models.BooleanField(default=True)
    notify_in_app = models.BooleanField(default=True)
    
    onboarding_completed = models.BooleanField(default=False)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    
    study_streak_days = models.PositiveIntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.first_name}'s Student Profile"

class ContentManagerProfile(models.Model):
    class ApprovalStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='content_manager_profile')
    
    employee_id = models.CharField(max_length=40, unique=True)
    designation = models.CharField(max_length=80)
    department = models.CharField(max_length=80, blank=True)
    bio = models.TextField(blank=True)
    qualification = models.CharField(max_length=255)
    areas_of_expertise = models.JSONField(default=list, blank=True)
    years_of_experience = models.PositiveIntegerField(default=0)
    
    public_display_name = models.CharField(max_length=120, unique=True)
    linkedin_url = models.URLField(blank=True)
    website_url = models.URLField(blank=True)
    
    approval_status = models.CharField(max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_cms')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    can_publish_directly = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.first_name} - CM Profile"

class SupportProfile(models.Model):
    class Department(models.TextChoices):
        PAYMENTS = 'PAYMENTS', 'Payments'
        TECHNICAL = 'TECHNICAL', 'Technical'
        ACCOUNTS = 'ACCOUNTS', 'Accounts'
        GENERAL = 'GENERAL', 'General'

    class SupportLevel(models.TextChoices):
        L1 = 'L1', 'Level 1'
        L2 = 'L2', 'Level 2'
        L3 = 'L3', 'Level 3'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_profile')
    
    employee_id = models.CharField(max_length=40, unique=True)
    designation = models.CharField(max_length=80)
    department = models.CharField(max_length=20, choices=Department.choices, default=Department.GENERAL)
    support_level = models.CharField(max_length=5, choices=SupportLevel.choices, default=SupportLevel.L1)
    languages_spoken = models.JSONField(default=list, blank=True)
    
    shift_start = models.TimeField(null=True, blank=True)
    shift_end = models.TimeField(null=True, blank=True)
    can_handle_refunds = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.first_name} - Support Profile"

class AdminProfile(models.Model):
    class AdminLevel(models.TextChoices):
        SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
        ADMIN = 'ADMIN', 'Admin'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='admin_profile')
    
    employee_id = models.CharField(max_length=40, unique=True)
    designation = models.CharField(max_length=80)
    department = models.CharField(max_length=80, blank=True)
    admin_level = models.CharField(max_length=20, choices=AdminLevel.choices, default=AdminLevel.ADMIN)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.first_name} - Admin Profile"