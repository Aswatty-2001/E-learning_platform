from django.contrib import admin
from django.urls import path, include
from accounts.views import home_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    
    # This is the line that connects your API!
    path('api/v1/auth/', include('accounts.urls')), 
    path('', include('accounts.urls')),
]