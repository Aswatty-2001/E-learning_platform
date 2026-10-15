from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from accounts.models import User, OTPVerification
from accounts.utils import generate_and_send_otp

class AuthFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('register')
        self.verify_otp_url = reverse('verify-otp')
        self.login_url = reverse('login')
        
        # Pre-create a verified user for login tests
        self.existing_user = User.objects.create_user(
            email="existing@test.com",
            password="ExistingP@ss123",
            first_name="Test",
            last_name="User"
        )
        self.existing_user.email_verified = True
        self.existing_user.save()

    def test_student_registration_success(self):
        """Ensure students can register with valid data."""
        payload = {
            "email": "newstudent@test.com",
            "password": "NewP@ss1234",
            "password_confirm": "NewP@ss1234",
            "first_name": "New",
            "last_name": "Student",
            "terms_accepted": True
        }
        res = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 2) # 1 existing + 1 new
        new_user = User.objects.get(email="newstudent@test.com")
        self.assertEqual(new_user.role, 'STUDENT')

    def test_privilege_escalation_prevention(self):
        """Ensure a user cannot register as an ADMIN."""
        payload = {
            "email": "hacker@test.com",
            "password": "HackerP@ss123",
            "password_confirm": "HackerP@ss123",
            "first_name": "Hacker",
            "last_name": "User",
            "terms_accepted": True,
            "role": "ADMIN" # Malicious attempt
        }
        res = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        hacker_user = User.objects.get(email="hacker@test.com")
        # The API should force the role to STUDENT, ignoring the payload
        self.assertEqual(hacker_user.role, 'STUDENT')

    def test_login_success(self):
        """Ensure a verified user can log in and receive JWT tokens."""
        payload = {
            "identifier": "existing@test.com",
            "password": "ExistingP@ss123"
        }
        res = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)

    def test_otp_verification_flow(self):
        """Ensure a user can verify their email with a valid OTP."""
        # Generate an OTP for the existing user
        otp = generate_and_send_otp(self.existing_user, 'EMAIL', 'SIGNUP')
        # Extract the raw code (in a real test we'd mock this, but here we pull from DB logic)
        # Since the code is hashed, we need to simulate the utility's raw code. 
        # Let's create a manual OTP for the test to know the raw code.
        from django.contrib.auth.hashers import make_password
        raw_code = "999999"
        OTPVerification.objects.filter(user=self.existing_user).delete()
        OTPVerification.objects.create(
            user=self.existing_user,
            channel='EMAIL',
            code_hash=make_password(raw_code),
            purpose='SIGNUP',
            expires_at="2026-12-31T12:00:00Z"
        )
        
        payload = {
            "identifier": "existing@test.com",
            "channel": "EMAIL",
            "code": raw_code
        }
        res = self.client.post(self.verify_otp_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        self.existing_user.refresh_from_db()
        self.assertTrue(self.existing_user.email_verified)