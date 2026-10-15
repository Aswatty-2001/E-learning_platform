from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()

class EmailOrPhoneModelBackend(ModelBackend):
    """
    Authenticates user via email or phone number.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None
        
        try:
            # If it starts with '+', treat as phone number, else email
            if username.startswith('+'):
                user = User.objects.get(phone_number=username)
            else:
                user = User.objects.get(email__iexact=username)
        except User.DoesNotExist:
            # Run the default password hasher to reduce timing attacks
            User().set_password(password)
            return None

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None