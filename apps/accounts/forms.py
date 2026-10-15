from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from phonenumber_field.formfields import PhoneNumberField

User = get_user_model()

class StudentRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=80, required=True)
    last_name = forms.CharField(max_length=80, required=True)
    phone_number = forms.CharField(max_length=17, required=False, help_text="Optional: Include country code (e.g., +91...)")
    terms_accepted = forms.BooleanField(required=True, label="I accept the Terms and Privacy Policy")

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'password1', 'password2')

class LoginForm(forms.Form):
    identifier = forms.CharField(label="Email or Phone", max_length=150, required=True, 
                                 widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter email or phone'}))
    password = forms.CharField(label="Password", strip=False, 
                               widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))