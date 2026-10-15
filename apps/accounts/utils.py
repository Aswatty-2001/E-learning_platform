import random
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from accounts.models import OTPVerification, LoginHistory

def generate_and_send_otp(user, channel, purpose):
    """
    Generates a 6-digit OTP, hashes it, saves it to DB, and "sends" it.
    """
    raw_code = f"{random.randint(100000, 999999)}"
    expires_at = timezone.now() + timezone.timedelta(minutes=10)
    
    otp = OTPVerification.objects.create(
        user=user,
        channel=channel,
        code_hash=make_password(raw_code),
        purpose=purpose,
        expires_at=expires_at
    )
    
    # DEV ONLY: Print to console. In prod, trigger Celery email/SMS task.
    print(f"\n[DEV OTP ALERT] To: {user.email or user.phone_number} | Code: {raw_code}\n")
    return otp

def log_login_attempt(request, user, success, reason=""):
    """
    Creates a LoginHistory record.
    """
    ip_address = request.META.get('REMOTE_ADDR')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    identifier_attempted = request.data.get('identifier', '') if hasattr(request, 'data') else ''
    
    LoginHistory.objects.create(
        user=user if success else None,
        identifier_attempted=identifier_attempted,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        failure_reason=reason
    )