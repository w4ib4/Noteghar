from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.admin_views import admin_dashboard

# Import custom admin (if you created it above)
# from .admin import admin_site

urlpatterns = [
    path('admin/dashboard/', admin_dashboard, name='admin_dashboard'),
    path('admin/', admin.site.urls),  # or admin_site.urls if using custom
    path('', include('core.urls')),
    
    # Allauth URLs
    path('accounts/', include('allauth.urls')),
    
    # Custom account URLs
    path('accounts/', include('accounts.urls')),
    
    # App URLs
    path('notes/', include('notes.urls')),
    path('moderation/', include('moderation.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)