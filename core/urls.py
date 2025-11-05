
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),

   
    path('', RedirectView.as_view(pattern_name='accounts:login_view', permanent=False), name='home'),

    # All account-related pages will be under '/accounts/'
    path('accounts/', include('accounts.urls', namespace='accounts')),
    
    # All messaging app pages will be under '/app/'
    path('app/', include('messaging.urls', namespace='messaging')), 
    
]



# This is for serving static/media files correctly in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)