from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView
from django.urls import reverse_lazy
from accounts.forms import StudentRegistrationForm, LoginForm
from accounts.models import User, LoginHistory
from django.contrib.auth.views import PasswordResetView

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import JsonResponse

@login_required
def change_password_api(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password', '')
        new_password1 = request.POST.get('new_password1', '')
        new_password2 = request.POST.get('new_password2', '')
        
        user = request.user
        errors = {}
        
        # 1. Validate old password
        if not old_password:
            errors['old_password'] = ['Please enter your old password.']
        elif not user.check_password(old_password):
            errors['old_password'] = ['Your old password is incorrect.']
        
        # 2. Validate new password is different from old
        if old_password and new_password1 and user.check_password(new_password1):
            errors['new_password1'] = ['New password must be different from your old password.']
        
        # 3. Validate new password strength (Django validators + custom)
        if not new_password1:
            errors['new_password1'] = ['Please enter a new password.']
        else:
            try:
                validate_password(new_password1, user=user)
            except ValidationError as e:
                errors['new_password1'] = list(e.messages)
        
        # 4. Validate passwords match
        if not new_password2:
            errors['new_password2'] = ['Please confirm your new password.']
        elif new_password1 != new_password2:
            errors['new_password2'] = ['Passwords do not match.']
        
        if errors:
            return JsonResponse({'success': False, 'errors': errors})
        
        # Change the password
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


# --- FRONTEND VIEWS ---
class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('password_change_done')

    def form_valid(self, form):
        # Clear the must_change_password flag and update timestamp
        self.request.user.must_change_password = False
        self.request.user.password_changed_at = timezone.now()
        self.request.user.save()
        return super().form_valid(form)

class CustomPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = 'accounts/password_change_done.html'

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

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')

@login_required
def dashboard_redirect(request):
    user = request.user
    if user.role == 'ADMIN':
        return redirect('admin_dashboard')
    elif user.role == 'CONTENT_MANAGER':
        return redirect('content_manager_dashboard')
    elif user.role == 'SUPPORT':
        return redirect('support_dashboard')
    else:
        return redirect('student_dashboard')

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

def home_view(request):
    context = {
        'login_form': LoginForm(),
        'register_form': StudentRegistrationForm(),
    }
    return render(request, 'accounts/home.html', context)