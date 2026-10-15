from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from accounts.models import User, StudentProfile, ContentManagerProfile, SupportProfile

class Command(BaseCommand):
    help = 'Creates default roles (Groups) and assigns base permissions.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Setting up roles and permissions...")
        
        # 1. Admin Group (Full access is handled by is_superuser flag, but group is useful for grouping)
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        
        # 2. Content Manager Group
        cm_group, _ = Group.objects.get_or_create(name='Content Manager')
        # Give CMs view/change permissions for their own profile, but we'll handle course perms later
        cm_ct = ContentType.objects.get_for_model(ContentManagerProfile)
        cm_permissions = Permission.objects.filter(content_type=cm_ct)
        cm_group.permissions.set(cm_permissions)
        
        # 3. Support Group
        support_group, _ = Group.objects.get_or_create(name='Support')
        support_ct = ContentType.objects.get_for_model(SupportProfile)
        support_permissions = Permission.objects.filter(content_type=support_ct)
        support_group.permissions.set(support_permissions)
        
        # 4. Student Group
        student_group, _ = Group.objects.get_or_create(name='Student')
        student_ct = ContentType.objects.get_for_model(StudentProfile)
        student_permissions = Permission.objects.filter(content_type=student_ct)
        student_group.permissions.set(student_permissions)

        self.stdout.write(self.style.SUCCESS('Roles and permissions setup completed successfully.'))