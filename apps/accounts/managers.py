from django.contrib.auth.models import BaseUserManager
from phonenumber_field.phonenumber import PhoneNumber

class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifier
    for authentication instead of usernames. Supports login via email or phone.
    """
    def create_user(self, email=None, phone_number=None, password=None, **extra_fields):
        if not email and not phone_number:
            raise ValueError("Either an email or a phone number must be provided.")
        
        if email:
            email = self.normalize_email(email)
        
        user = self.model(email=email, phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'ADMIN')
        extra_fields.setdefault('email_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email=email, password=password, **extra_fields)