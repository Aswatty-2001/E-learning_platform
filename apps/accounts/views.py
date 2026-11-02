from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView, PasswordResetView
from django.urls import reverse_lazy
from accounts.forms import StudentRegistrationForm, LoginForm
from accounts.models import User, LoginHistory
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import JsonResponse
from accounts.models import ContentCreatorProfile
from django.contrib.auth import login as django_login
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from accounts.models import CreatorCategoryAssignment
from categories.models import Category


@login_required
def content_creator_detail_view(request, pk):
    """View full details of a content creator, including assigned subcategories."""
    if request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied
    
    creator = get_object_or_404(User, pk=pk, role='CONTENT_CREATOR')
    profile = creator.content_creator_profile
    assignments = CreatorCategoryAssignment.objects.filter(
        creator_profile=profile
    ).select_related('category', 'category__parent', 'assigned_by')
    
    # Get all subcategories grouped by parent (for the assignment dropdown)
    all_subcategories = Category.objects.filter(
        parent__isnull=False, is_active=True
    ).select_related('parent').order_by('parent__menu_order', 'menu_order')
    
    # Group by parent
    subcat_groups = {}
    for sub in all_subcategories:
        parent_name = sub.parent.name if sub.parent else 'Other'
        if parent_name not in subcat_groups:
            subcat_groups[parent_name] = []
        subcat_groups[parent_name].append(sub)
    
    # Already-assigned category IDs (to disable them in the form)
    assigned_ids = list(assignments.values_list('category_id', flat=True))
    
    return render(request, 'accounts/content_creator_detail.html', {
        'creator': creator,
        'profile': profile,
        'assignments': assignments,
        'subcat_groups': subcat_groups,
        'assigned_ids': assigned_ids,
    })


@login_required
def assign_subcategories_view(request, pk):
    """Assign subcategories to a content creator (Admin/CM only)."""
    if request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied
    
    creator = get_object_or_404(User, pk=pk, role='CONTENT_CREATOR')
    profile = creator.content_creator_profile
    
    if request.method == 'POST':
        selected_ids = request.POST.getlist('subcategories')
        
        # Remove existing assignments not in the new selection
        CreatorCategoryAssignment.objects.filter(
            creator_profile=profile
        ).exclude(category_id__in=selected_ids).delete()
        
        # Add new assignments
        added_count = 0
        for cat_id in selected_ids:
            _, created = CreatorCategoryAssignment.objects.get_or_create(
                creator_profile=profile,
                category_id=cat_id,
                defaults={'assigned_by': request.user}
            )
            if created:
                added_count += 1
        
        # Log
        from accounts.models import AuditLog
        AuditLog.objects.create(
            actor=request.user,
            action='ASSIGN_CATEGORIES_TO_CREATOR',
            target_object_id=creator.id,
            changes={'assigned_count': len(selected_ids), 'added': added_count},
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        
        messages.success(request, f'Assigned {len(selected_ids)} subcategorie(s) to {creator.first_name}.')
        return redirect('content_creator_detail', pk=pk)
    
    return redirect('content_creator_detail', pk=pk)


@login_required
def approve_creator_view(request, pk):
    """Approve a content creator (Admin/CM only)."""
    if request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied
    
    creator = get_object_or_404(User, pk=pk, role='CONTENT_CREATOR')
    profile = creator.content_creator_profile
    profile.approval_status = 'APPROVED'
    profile.approved_by = request.user
    profile.approved_at = timezone.now()
    profile.rejection_reason = ''
    profile.save()
    
    from accounts.models import AuditLog
    AuditLog.objects.create(
        actor=request.user,
        action='APPROVE_CONTENT_CREATOR',
        target_object_id=creator.id,
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    
    messages.success(request, f'{creator.first_name} has been approved! They can now publish courses.')
    return redirect('content_creator_detail', pk=pk)


@login_required
def reject_creator_view(request, pk):
    """Reject a content creator (Admin/CM only)."""
    if request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied
    
    creator = get_object_or_404(User, pk=pk, role='CONTENT_CREATOR')
    profile = creator.content_creator_profile
    profile.approval_status = 'REJECTED'
    profile.approved_by = request.user
    profile.approved_at = timezone.now()
    profile.rejection_reason = request.POST.get('rejection_reason', '').strip()
    profile.save()
    
    from accounts.models import AuditLog
    AuditLog.objects.create(
        actor=request.user,
        action='REJECT_CONTENT_CREATOR',
        target_object_id=creator.id,
        changes={'reason': profile.rejection_reason},
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    
    messages.success(request, f'{creator.first_name} has been rejected.')
    return redirect('content_creator_detail', pk=pk)




# ===================== CONTENT CREATOR: PUBLIC REGISTRATION =====================

def creator_register_view(request):
    """Public registration for content creators. Forces role=CONTENT_CREATOR."""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone_number = request.POST.get('phone_number', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        profile_photo = request.FILES.get('profile_photo')
        resume = request.FILES.get('resume')
        terms_accepted = request.POST.get('terms_accepted') == 'on'
        
        errors = []
        
        if not first_name or len(first_name) < 2:
            errors.append('First name is required (min 2 characters).')
        if not email:
            errors.append('Email address is required.')
        elif User.objects.filter(email__iexact=email).exists():
            errors.append('A user with this email already exists.')
        if not terms_accepted:
            errors.append('You must accept the Terms and Privacy Policy.')
        if not password1 or len(password1) < 10:
            errors.append('Password must be at least 10 characters.')
        elif password1 != password2:
            errors.append('Passwords do not match.')
        
        # Validate resume if uploaded
        if resume:
            if resume.size > 5 * 1024 * 1024:
                errors.append('Resume file too large. Maximum 5MB allowed.')
            allowed_types = ['application/pdf', 'application/msword', 
                            'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
            if resume.content_type not in allowed_types and not resume.name.lower().endswith(('.pdf', '.doc', '.docx')):
                errors.append('Resume must be a PDF, DOC, or DOCX file.')
        
        # Validate phone if provided
                # Validate phone if provided
        if phone_number:
            # Check phone uniqueness
            if User.objects.filter(phone_number=phone_number).exists():
                errors.append('A user with this phone number already exists.')
            else:
                try:
                    from phonenumber_field.phonenumber import PhoneNumber
                    phone = PhoneNumber.from_string(phone_number)
                    if not phone.is_valid():
                        errors.append('Please enter a valid phone number with country code (e.g., +91 9876543210).')
                except Exception:
                    errors.append('Please enter a valid phone number with country code (e.g., +91 9876543210).')
        
        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'accounts/creator_register.html', {'form_data': request.POST})
        
        # Create the user - FORCED role=CONTENT_CREATOR (no privilege escalation)
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number if phone_number else None,
            role='CONTENT_CREATOR',
            is_staff=True,
            is_active=True,
            must_change_password=False,
            auth_provider='EMAIL',
            terms_accepted_at=timezone.now(),
        )
        user.set_password(password1)
        user.save()
        
        # Save profile photo and resume
        profile = user.content_creator_profile
        if profile_photo:
            profile.profile_photo = profile_photo
        if resume:
            profile.resume = resume
        profile.save()
        
        # Log them in
        django_login(request, user, backend='accounts.backends.EmailOrPhoneModelBackend')
        
        messages.success(request, 'Welcome! Your content creator account is pending approval. You can create draft courses but cannot publish until an admin reviews your resume and approves your profile.')
        return redirect('content_creator_dashboard')  # FIXED URL name
    
    return render(request, 'accounts/creator_register.html', {'form_data': {}})


# ===================== CONTENT CREATOR: STAFF BACKEND REGISTRATION =====================

@login_required
def content_creator_add_view(request):
    """Admin/Content Manager registers a new Content Creator through a backend form."""
    if request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone_number = request.POST.get('phone_number', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        profile_photo = request.FILES.get('profile_photo')
        resume = request.FILES.get('resume')
        
        errors = []
        
        if not first_name or len(first_name) < 2:
            errors.append('First name is required (min 2 characters).')
        if not email:
            errors.append('Email address is required.')
        elif User.objects.filter(email__iexact=email).exists():
            errors.append('A user with this email already exists.')
        if not password1:
            errors.append('Password is required.')
        elif len(password1) < 10:
            errors.append('Password must be at least 10 characters.')
        elif password1 != password2:
            errors.append('Passwords do not match.')
        
        if resume and resume.size > 5 * 1024 * 1024:
            errors.append('Resume file too large. Maximum 5MB allowed.')
        
        if phone_number:
            # Check phone uniqueness
            if User.objects.filter(phone_number=phone_number).exists():
                errors.append('A user with this phone number already exists.')
            else:
                try:
                    from phonenumber_field.phonenumber import PhoneNumber
                    phone = PhoneNumber.from_string(phone_number)
                    if not phone.is_valid():
                        errors.append('Please enter a valid phone number with country code.')
                except Exception:
                    errors.append('Please enter a valid phone number with country code.')
        
        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'accounts/content_creator_add.html', {'form_data': request.POST})
        
        user = User(
            email=email, first_name=first_name, last_name=last_name,
            role='CONTENT_CREATOR', is_staff=True, is_active=True,
            must_change_password=False, created_by=request.user, auth_provider='EMAIL',
        )
        if phone_number:
            user.phone_number = phone_number
        user.set_password(password1)
        user.save()
        
        profile = user.content_creator_profile
        if profile_photo:
            profile.profile_photo = profile_photo
        if resume:
            profile.resume = resume
        profile.save()
        
        from accounts.models import AuditLog
        AuditLog.objects.create(
            actor=request.user, action='CREATE_CONTENT_CREATOR',
            target_object_id=user.id,
            changes={'email': user.email, 'first_name': first_name, 'last_name': last_name},
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        
        messages.success(request, f'Content Creator "{first_name}" has been registered successfully!')
        return redirect('content_creator_add')
    
    return render(request, 'accounts/content_creator_add.html', {'form_data': {}})


# ===================== CONTENT CREATOR: DASHBOARD =====================

@login_required
def creator_dashboard(request):
    return render(request, 'accounts/dashboards/creator.html')


# ===================== PASSWORD CHANGE (AJAX) =====================

@login_required
def change_password_api(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password', '')
        new_password1 = request.POST.get('new_password1', '')
        new_password2 = request.POST.get('new_password2', '')
        
        user = request.user
        errors = {}
        
        if not old_password:
            errors['old_password'] = ['Please enter your old password.']
        elif not user.check_password(old_password):
            errors['old_password'] = ['Your old password is incorrect.']
        
        if old_password and new_password1 and user.check_password(new_password1):
            errors['new_password1'] = ['New password must be different from your old password.']
        
        if not new_password1:
            errors['new_password1'] = ['Please enter a new password.']
        else:
            try:
                validate_password(new_password1, user=user)
            except ValidationError as e:
                errors['new_password1'] = list(e.messages)
        
        if not new_password2:
            errors['new_password2'] = ['Please confirm your new password.']
        elif new_password1 != new_password2:
            errors['new_password2'] = ['Passwords do not match.']
        
        if errors:
            return JsonResponse({'success': False, 'errors': errors})
        
        user.set_password(new_password1)
        user.must_change_password = False
        user.password_changed_at = timezone.now()
        user.save()
        update_session_auth_hash(request, user)
        
        return JsonResponse({
            'success': True, 
            'message': 'Your password has been changed successfully.'
        })
    
    return JsonResponse({'success': False, 'errors': {'general': ['Invalid request.']}})


# ===================== PASSWORD CHANGE (FORM-BASED) =====================

class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('password_change_done')

    def form_valid(self, form):
        self.request.user.must_change_password = False
        self.request.user.password_changed_at = timezone.now()
        self.request.user.save()
        return super().form_valid(form)

class CustomPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = 'accounts/password_change_done.html'


# ===================== STUDENT REGISTRATION (PUBLIC) =====================

@csrf_protect
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'STUDENT'
            user.auth_provider = 'EMAIL'
            user.terms_accepted_at = timezone.now()
            user.save()
            messages.success(request, 'Your account has been created successfully!')
            return redirect('home')
        else:
            return render(request, 'accounts/home.html', {
                'login_form': LoginForm(),
                'register_form': form,
                'active_modal': 'registerModal'
            })
    else:
        form = StudentRegistrationForm()
    
    return render(request, 'accounts/home.html', {
        'login_form': LoginForm(),
        'register_form': form
    })


# ===================== LOGIN =====================

@csrf_protect
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data['identifier']
            password = form.cleaned_data['password']
            
            ip_address = request.META.get('REMOTE_ADDR')
            
            try:
                if identifier.startswith('+'):
                    user = User.objects.get(phone_number=identifier)
                else:
                    user = User.objects.get(email__iexact=identifier)
            except User.DoesNotExist:
                user = None

            if user:
                if user.locked_until and user.locked_until > timezone.now():
                    messages.error(request, 'Account temporarily locked. Try again later.')
                    LoginHistory.objects.create(user=user, identifier_attempted=identifier, ip_address=ip_address, success=False, failure_reason='LOCKED')
                    return render(request, 'accounts/home.html', {
                        'login_form': form,
                        'register_form': StudentRegistrationForm(),
                        'active_modal': 'loginModal'
                    })
                
                from accounts.backends import EmailOrPhoneModelBackend
                backend = EmailOrPhoneModelBackend()
                authenticated_user = backend.authenticate(request, username=identifier, password=password)

                if authenticated_user:
                    user.failed_login_attempts = 0
                    user.locked_until = None
                    user.last_login = timezone.now()
                    user.last_login_ip = ip_address
                    user.save()
                    
                    LoginHistory.objects.create(user=user, identifier_attempted=identifier, ip_address=ip_address, success=True)
                    login(request, authenticated_user, backend='accounts.backends.EmailOrPhoneModelBackend')
                    
                    if user.must_change_password:
                        return redirect('password_change')
                    return redirect('dashboard_redirect')
                else:
                    user.failed_login_attempts += 1
                    if user.failed_login_attempts >= 5:
                        user.locked_until = timezone.now() + timezone.timedelta(minutes=15)
                    user.save()
                    LoginHistory.objects.create(user=user, identifier_attempted=identifier, ip_address=ip_address, success=False, failure_reason='BAD_PASSWORD')
                    messages.error(request, 'Invalid credentials.')
            else:
                LoginHistory.objects.create(user=None, identifier_attempted=identifier, ip_address=ip_address, success=False, failure_reason='NOT_FOUND')
                messages.error(request, 'Invalid credentials.')
            
            return render(request, 'accounts/home.html', {
                'login_form': form,
                'register_form': StudentRegistrationForm(),
                'active_modal': 'loginModal'
            })
    else:
        form = LoginForm()
    
    return render(request, 'accounts/home.html', {
        'login_form': form,
        'register_form': StudentRegistrationForm()
    })


# ===================== LOGOUT =====================

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')


# ===================== DASHBOARD REDIRECT =====================

@login_required
def dashboard_redirect(request):
    user = request.user
    if user.role == 'ADMIN':
        return redirect('admin_dashboard')
    elif user.role == 'CONTENT_MANAGER':
        return redirect('content_manager_dashboard')
    elif user.role == 'CONTENT_CREATOR':
        return redirect('content_creator_dashboard')  # FIXED URL name
    elif user.role == 'SUPPORT':
        return redirect('support_dashboard')
    else:
        return redirect('student_dashboard')


# ===================== DASHBOARDS =====================

@login_required
def student_dashboard(request):
    return render(request, 'accounts/dashboards/student.html')

@login_required
def admin_dashboard(request):
    return render(request, 'accounts/dashboards/admin.html')

@login_required
def cm_dashboard(request):
    return render(request, 'accounts/dashboards/cm.html')

@login_required
def support_dashboard(request):
    return render(request, 'accounts/dashboards/support.html')

@login_required
def creator_dashboard(request):
    return render(request, 'accounts/dashboards/creator.html')


# ===================== HOME PAGE =====================

def home_view(request):
    from categories.services import get_menu_tree
    context = {
        'login_form': LoginForm(),
        'register_form': StudentRegistrationForm(),
        'menu_tree': get_menu_tree(),
    }
    return render(request, 'accounts/home.html', context)


# ===================== LIST VIEWS (ADMIN/CM ONLY) =====================

@login_required
def student_list_view(request):
    """Admin and Content Manager can view the list of registered students."""
    if request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied
    
    search = request.GET.get('search', '').strip()
    students = User.objects.filter(role='STUDENT').order_by('-created_at')
    
    if search:
        students = students.filter(
            Q(first_name__icontains=search) | 
            Q(last_name__icontains=search) | 
            Q(email__icontains=search)
        )
    
    return render(request, 'accounts/student_list.html', {
        'students': students,
        'search': search,
        'total_count': User.objects.filter(role='STUDENT').count(),
    })


@login_required
def content_creator_list_view(request):
    """Admin and Content Manager can view the list of registered content creators."""
    if request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied
    
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    
    creators = User.objects.filter(role='CONTENT_CREATOR').order_by('-created_at')
    
    if search:
        creators = creators.filter(
            Q(first_name__icontains=search) | 
            Q(last_name__icontains=search) | 
            Q(email__icontains=search)
        )
    
    if status_filter:
        creators = creators.filter(content_creator_profile__approval_status=status_filter)
    
    return render(request, 'accounts/content_creator_list.html', {
        'creators': creators,
        'search': search,
        'status_filter': status_filter,
        'total_count': User.objects.filter(role='CONTENT_CREATOR').count(),
        'pending_count': User.objects.filter(
            role='CONTENT_CREATOR', 
            content_creator_profile__approval_status='PENDING'
        ).count(),
        'approved_count': User.objects.filter(
            role='CONTENT_CREATOR', 
            content_creator_profile__approval_status='APPROVED'
        ).count(),
    })