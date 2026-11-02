from django.urls import path
from django.contrib.auth import views as auth_views
from accounts.views import ( home_view,
    register_view, login_view, logout_view, 
    student_dashboard, admin_dashboard, cm_dashboard, support_dashboard, dashboard_redirect, 
    CustomPasswordChangeView, CustomPasswordChangeDoneView, change_password_api, content_creator_add_view,  creator_register_view, creator_dashboard,student_list_view, content_creator_list_view ,
    content_creator_detail_view, assign_subcategories_view,
    approve_creator_view, reject_creator_view ,  
)


urlpatterns = [
    # Frontend Auth
    path('', home_view, name='home'),
      path('staff/students/', student_list_view, name='student_list'),  # NEW
    path('staff/content-creators/', content_creator_list_view, name='content_creator_list'),
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard_redirect, name='dashboard_redirect'),
    path('register/creator/', creator_register_view, name='creator_register'),  # NEW
    path('staff/content-creator/add/', content_creator_add_view, name='content_creator_add'),
    path('dashboard/creator/', creator_dashboard, name='content_creator_dashboard'),  # Use this name # NEW
    path('dashboard/student/', student_dashboard, name='student_dashboard'),
    path('dashboard/admin/', admin_dashboard, name='admin_dashboard'),
    path('dashboard/cm/', cm_dashboard, name='content_manager_dashboard'),
    path('dashboard/support/', support_dashboard, name='support_dashboard'),
    path('password/change/', CustomPasswordChangeView.as_view(), name='password_change'),
    path('password/change/done/', CustomPasswordChangeDoneView.as_view(), name='password_change_done'),
    path('password/reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html',
        subject_template_name='accounts/password_reset_subject.txt',
        email_template_name='accounts/password_reset_email.html'
    ), name='password_reset'),

    path('password/reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'
    ), name='password_reset_done'),

    path('password/reset/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html'
    ), name='password_reset_confirm'),

     path('password/reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'
    ), name='password_reset_complete'),

    path('password/change/api/', change_password_api, name='password_change_api'),
    path('staff/content-creators/<uuid:pk>/', content_creator_detail_view, name='content_creator_detail'),
    path('staff/content-creators/<uuid:pk>/assign/', assign_subcategories_view, name='assign_subcategories'),
    path('staff/content-creators/<uuid:pk>/approve/', approve_creator_view, name='approve_creator'),
    path('staff/content-creators/<uuid:pk>/reject/', reject_creator_view, name='reject_creator'),
]