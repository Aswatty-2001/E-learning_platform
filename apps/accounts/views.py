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
            
            # TODO: Send OTP email here
            
            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('login')
    else:
        form = StudentRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})

@csrf_protect
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data['identifier']
            password = form.cleaned_data['password']
            
            # Log attempt
            ip_address = request.META.get('REMOTE_ADDR')
            
            try:
                if identifier.startswith('+'):
                    user = User.objects.get(phone_number=identifier)
                else:
                    user = User.objects.get(email__iexact=identifier)
            except User.DoesNotExist:
                user = None

            if user:
                authenticated_user = authenticate(request, username=identifier, password=password)
                if authenticated_user:
                    # Check if account is locked
                    if user.locked_until and user.locked_until > timezone.now():
                        messages.error(request, 'Account temporarily locked. Try again later.')
                        LoginHistory.objects.create(user=user, identifier_attempted=identifier, ip_address=ip_address, success=False, failure_reason='LOCKED')
                        return render(request, 'accounts/login.html', {'form': form})
                    
                    # Success logic
                    user.failed_login_attempts = 0
                    user.locked_until = None
                    user.last_login = timezone.now()
                    user.last_login_ip = ip_address
                    user.save()
                    
                    LoginHistory.objects.create(user=user, identifier_attempted=identifier, ip_address=ip_address, success=True)
                    
                    login(request, authenticated_user)
                    
                    # Redirect to forced password change if staff first login
                    if user.must_change_password:
                        return redirect('password_change')
                    
                    return redirect('dashboard_redirect')
                else:
                    # Bad password
                    user.failed_login_attempts += 1
                    if user.failed_login_attempts >= 5:
                        user.locked_until = timezone.now() + timezone.timedelta(minutes=15)
                    user.save()
                    LoginHistory.objects.create(user=user, identifier_attempted=identifier, ip_address=ip_address, success=False, failure_reason='BAD_PASSWORD')
                    messages.error(request, 'Invalid credentials.')
            else:
                LoginHistory.objects.create(user=None, identifier_attempted=identifier, ip_address=ip_address, success=False, failure_reason='NOT_FOUND')
                messages.error(request, 'Invalid credentials.')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})

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