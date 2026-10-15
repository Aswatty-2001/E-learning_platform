import json
import os
import secrets
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from accounts.models import User, AuditLog, ContentManagerProfile

class Command(BaseCommand):
    help = 'Seeds initial staff users from seed_data.json'

    def handle(self, *args, **kwargs):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        json_path = os.path.join(base_dir, 'management', 'commands', 'seed_data.json')
        
        if not os.path.exists(json_path):
            self.stdout.write(self.style.ERROR(f"seed_data.json not found at {json_path}"))
            return

        with open(json_path, 'r') as f:
            users_data = json.load(f)

        credentials_output = []
        
        for data in users_data:
            role = data['role']
            email = data['email']
            temp_password = secrets.token_urlsafe(12)
            
            # Idempotency: Use update_or_create
            user, created = User.objects.update_or_create(
                email=email,
                defaults={
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                    'phone_number': data['phone'],
                    'role': role,
                    'is_staff': True,
                    'is_superuser': True if role == 'ADMIN' else False,
                    'must_change_password': True,
                    'email_verified': True,
                    'auth_provider': 'EMAIL'
                }
            )
            
            # Only set password if it's a new user, otherwise leave existing password alone
            # (Or if you want to force reset passwords every run, uncomment the next line)
            user.set_password(temp_password)
            user.save()

            # Assign Group
            group_name = 'Admin' if role == 'ADMIN' else role.title().replace('_', ' ')
            try:
                group = Group.objects.get(name=group_name)
                user.groups.add(group)
            except Group.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Group {group_name} does not exist. Run setup_roles first."))
            
            # Handle Profile specific updates (e.g., CM Approval)
            if role == 'CONTENT_MANAGER':
                profile, _ = ContentManagerProfile.objects.get_or_create(user=user)
                profile.approval_status = 'APPROVED'
                profile.approved_by = User.objects.filter(is_superuser=True).first()
                profile.approved_at = timezone.now()
                profile.save()

            # Audit Log
            action = 'CREATE_STAFF_USER' if created else 'UPDATE_STAFF_USER'
            AuditLog.objects.create(
                actor=None, # System action
                action=action,
                target_object_id=user.id,
                changes={'email': user.email, 'role': user.role},
            )
            
            status_msg = "Created" if created else "Updated"
            credentials_output.append(f"{status_msg} {role}: {email} | Temp Password: {temp_password}")

        # Write credentials to a git-ignored file
        cred_file_path = os.path.join(base_dir, '..', '..', 'initial_credentials.txt')
        with open(cred_file_path, 'w') as f:
            f.write("\n".join(credentials_output))
            
        self.stdout.write(self.style.SUCCESS(f"Successfully processed {len(users_data)} users."))
        self.stdout.write(self.style.WARNING(f"Credentials saved to {cred_file_path} (DO NOT COMMIT THIS FILE)"))
        for cred in credentials_output:
            self.stdout.write(cred)