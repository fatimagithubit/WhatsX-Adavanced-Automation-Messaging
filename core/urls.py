
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

def fix_admin(request):
    user = CustomUser.objects.filter(username='fatima').first()
    if not user:
        return HttpResponse("❌ User not found.")
    user.is_staff = True
    user.is_superuser = True
    user.save()
    return HttpResponse("✅ Fatima promoted to admin & superuser successfully!")
    
urlpatterns += [
    path('fix-admin/', fix_admin),
]

# This is for serving static/media files correctly in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
