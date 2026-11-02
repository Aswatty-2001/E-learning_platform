from django.contrib import admin
from django.urls import path, include
from accounts.views import home_view
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    
    # This is the line that connects your API!
    path('api/v1/auth/', include('accounts.urls')), 
    path('', include('accounts.urls')),
        path('courses/', include('courses.urls')),
    path('courses/', include('categories.urls')),
        
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)