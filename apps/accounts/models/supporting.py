
import uuid
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.hashers import make_password

class Organisation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class LoginHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    identifier_attempted = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    success = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=40, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

class OTPVerification(models.Model):
    class Channel(models.TextChoices):
        EMAIL = 'EMAIL', 'Email'
        PHONE = 'PHONE', 'Phone'

    class Purpose(models.TextChoices):
        SIGNUP = 'SIGNUP', 'Signup'
        LOGIN = 'LOGIN', 'Login'
        PASSWORD_RESET = 'PASSWORD_RESET', 'Password Reset'
        EMAIL_VERIFY = 'EMAIL_VERIFY', 'Email Verify'
        PHONE_VERIFY = 'PHONE_VERIFY', 'Phone Verify'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    channel = models.CharField(max_length=10, choices=Channel.choices)
    code_hash = models.CharField(max_length=255)
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_code(self, raw_code):
        self.code_hash = make_password(raw_code)

    def check_code(self, raw_code):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_code, self.code_hash)

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=64)
    target_content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    target_object_id = models.UUIDField(null=True, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
