from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # This is the line that connects your API!
    path('api/v1/auth/', include('accounts.urls')), 
    path('', include('accounts.urls')),
]