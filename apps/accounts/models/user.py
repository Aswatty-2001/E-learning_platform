import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField
from accounts.managers import CustomUserManager

class User(AbstractBaseUser, PermissionsMixin):
    class Roles(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        CONTENT_MANAGER = 'CONTENT_MANAGER', 'Content Manager'
        CONTENT_CREATOR = 'CONTENT_CREATOR', 'Content Creator'
        SUPPORT = 'SUPPORT', 'Support Team'
        STUDENT = 'STUDENT', 'Student'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        PENDING_APPROVAL = 'PENDING_APPROVAL', 'Pending Approval'
        SUSPENDED = 'SUSPENDED', 'Suspended'
        BLOCKED = 'BLOCKED', 'Blocked'

    class AuthProviders(models.TextChoices):
        EMAIL = 'EMAIL', 'Email'
        PHONE = 'PHONE', 'Phone'
        GOOGLE = 'GOOGLE', 'Google'
        FACEBOOK = 'FACEBOOK', 'Facebook'
        APPLE = 'APPLE', 'Apple'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone_number = PhoneNumberField(unique=True, null=True, blank=True)
    
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.STUDENT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified = models.BooleanField(default=False)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    
    country = CountryField(null=True, blank=True)
    state = models.CharField(max_length=80, blank=True)
    city = models.CharField(max_length=80, blank=True)
    timezone = models.CharField(max_length=50, default='Asia/Kolkata')
    preferred_language = models.CharField(max_length=10, default='en')
    
    auth_provider = models.CharField(max_length=20, choices=AuthProviders.choices, default=AuthProviders.EMAIL)
    social_uid = models.CharField(max_length=255, blank=True)
    
    must_change_password = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    last_login = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    privacy_accepted_at = models.DateTimeField(null=True, blank=True)
    marketing_opt_in = models.BooleanField(default=False)
    
    created_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='created_users')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return self.email or str(self.phone_number)