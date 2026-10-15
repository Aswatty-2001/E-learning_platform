from rest_framework import serializers
from django.contrib.auth import get_user_model
from accounts.models import StudentProfile, ContentManagerProfile

User = get_user_model()

class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = (
            'student_id', 'areas_of_interest', 'learning_goals', 'skill_level', 
            'preferred_study_language', 'daily_study_minutes', 'objective_type', 
            'target_exam_or_career', 'education_level', 'institution_name', 
            'field_of_study', 'onboarding_completed'
        )
        read_only_fields = ('student_id',)

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer to return user details. Dynamically includes the profile.
    """
    student_profile = serializers.SerializerMethodField()
    content_manager_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'phone_number', 'first_name', 'last_name', 
            'role', 'status', 'email_verified', 'phone_verified',
            'profile_picture', 'must_change_password', 'student_profile', 'content_manager_profile'
        )
        read_only_fields = fields  # User updates should happen via specific endpoints, not generic PATCH

    def get_student_profile(self, obj):
        if obj.role == 'STUDENT':
            profile = getattr(obj, 'student_profile', None)
            if profile:
                return StudentProfileSerializer(profile).data
        return None

    def get_content_manager_profile(self, obj):
        if obj.role == 'CONTENT_MANAGER':
            profile = getattr(obj, 'content_manager_profile', None)
            if profile:
                # Lightweight inline serializer for CM to expose public data
                return {
                    'employee_id': profile.employee_id,
                    'designation': profile.designation,
                    'approval_status': profile.approval_status,
                    'public_display_name': profile.public_display_name,
                    'can_publish_directly': profile.can_publish_directly
                }
        return None

class OnboardingSerializer(serializers.ModelSerializer):
    """
    Used specifically for the PATCH /api/auth/onboarding/ endpoint.
    """
    class Meta:
        model = StudentProfile
        fields = (
            'areas_of_interest', 'learning_goals', 'skill_level', 
            'preferred_study_language', 'daily_study_minutes', 
            'objective_type', 'target_exam_or_career', 'education_level', 
            'institution_name', 'field_of_study'
        )
        extra_kwargs = {
            'areas_of_interest': {'required': False},
            'learning_goals': {'required': False},
            'skill_level': {'required': False},
        }

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        # Mark onboarding as complete if minimum required fields are filled
        if instance.skill_level and instance.objective_type:
            from django.utils import timezone
            instance.onboarding_completed = True
            instance.onboarding_completed_at = timezone.now()
            instance.save()
        return instance