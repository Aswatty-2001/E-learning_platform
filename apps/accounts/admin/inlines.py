from django.contrib import admin
from accounts.models import (
    StudentProfile, ContentManagerProfile, 
    SupportProfile, AdminProfile
)

class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    verbose_name = "Student Profile"
    fk_name = 'user'

class ContentManagerProfileInline(admin.StackedInline):
    model = ContentManagerProfile
    can_delete = False
    verbose_name = "Content Manager Profile"
    fk_name = 'user'

class SupportProfileInline(admin.StackedInline):
    model = SupportProfile
    can_delete = False
    verbose_name = "Support Profile"
    fk_name = 'user'

class AdminProfileInline(admin.StackedInline):
    model = AdminProfile
    can_delete = False
    verbose_name = "Admin Profile"
    fk_name = 'user'