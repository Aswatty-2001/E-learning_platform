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

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone:
            # Convert to string for comparison
            phone_str = str(phone)
            if User.objects.filter(phone_number=phone_str).exists():
                raise forms.ValidationError("A user with this phone number already exists.")
        return phone

    def clean_terms_accepted(self, value):
        if not value:
            raise forms.ValidationError("You must accept the terms and conditions.")
        return value

    def validate(self, attrs):
        if not attrs.get('email') and not attrs.get('phone_number'):
            raise forms.ValidationError("Either an email or a phone number must be provided.")
        
        if attrs.get('password1') != attrs.get('password2'):
            raise forms.ValidationError({"password": "Password fields didn't match."})
        
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        validated_data.pop('terms_accepted')
        
        validated_data['role'] = 'STUDENT'
        validated_data['auth_provider'] = 'EMAIL' if validated_data.get('email') else 'PHONE'
        
        from django.utils import timezone
        validated_data['terms_accepted_at'] = timezone.now()

        user = User.objects.create_user(**validated_data)
        return user

class LoginForm(forms.Form):
    identifier = forms.CharField(label="Email or Phone", max_length=150, required=True, 
                                 widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter email or phone'}))
    password = forms.CharField(label="Password", strip=False, 
                               widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))