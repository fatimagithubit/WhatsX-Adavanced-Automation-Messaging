# accounts/admin.py
from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Contact

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'user_type', 'is_staff', 'is_superuser')
   

admin.site.register(CustomUser, CustomUserAdmin)


def _safe_register(model, admin_class=None):
    try:
        if admin_class:
            admin.site.register(model, admin_class)
        else:
            admin.site.register(model)
    except AlreadyRegistered:
        
        pass

class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'user')
    search_fields = ('name', 'phone', 'user__username')

class ContactUsAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'user', 'submitted_at')
    readonly_fields = ('submitted_at',)

_safe_register(Contact, ContactAdmin)


