
import secrets
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()

class StaffCreationForm(UserCreationForm):
    """
    Custom form for creating staff users (Admin, Content Manager, Support).
    It allows setting the role and generates a temporary password automatically.
    """
    role = forms.ChoiceField(choices=[
        ('ADMIN', 'Admin'),
        ('CONTENT_MANAGER', 'Content Manager'),
        ('SUPPORT', 'Support Team'),
    ], initial='CONTENT_MANAGER')

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # We don't need the password fields in the form, we'll auto-generate it
        self.fields['password1'].required = False
        self.fields['password2'].required = False

    def save(self, commit=True):
        # Generate a secure 16-char temporary password
        temp_password = secrets.token_urlsafe(12)
        
        user = super().save(commit=False)
        user.set_password(temp_password)
        user.is_staff = True
        user.must_change_password = True
        user.role = self.cleaned_data.get('role')
        
        # FIX: Make them superuser if they are an Admin
        if user.role == 'ADMIN':
            user.is_superuser = True
            
        if commit:
            user.save()
            print(f"\n[DEV ALERT] Temporary password for {user.email}: {temp_password}\n")
            
        return user

    