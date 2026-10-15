from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)
    terms_accepted = serializers.BooleanField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('email', 'phone_number', 'password', 'password_confirm', 
                  'first_name', 'last_name', 'terms_accepted')
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
        }

    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError("You must accept the terms and conditions.")
        return value

    def validate(self, attrs):
        if not attrs.get('email') and not attrs.get('phone_number'):
            raise serializers.ValidationError("Either an email or a phone number must be provided.")
        
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        validated_data.pop('terms_accepted')
        
        validated_data['role'] = 'STUDENT'
        validated_data['auth_provider'] = 'EMAIL' if validated_data.get('email') else 'PHONE'
        
        from django.utils import timezone
        validated_data['terms_accepted_at'] = timezone.now()

        user = User.objects.create_user(**validated_data)
        return user

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)

class OTPVerifySerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True)
    channel = serializers.ChoiceField(choices=['EMAIL', 'PHONE'], required=True)
    code = serializers.CharField(max_length=6, required=True)