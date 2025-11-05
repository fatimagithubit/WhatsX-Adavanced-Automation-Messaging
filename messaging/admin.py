from django.contrib import admin
from .models import MessageTemplate, Campaign, CampaignRecipient

@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    """
    This is where we control the admin interface for Message Templates.
    """
    list_display = ('title', 'created_by', 'created_at')
    search_fields = ('title', 'content')
    list_filter = ('created_by',)
    
    def save_model(self, request, obj, form, change):
        if not obj.pk: 
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
      
        if request.user.is_superuser:
            return super().get_queryset(request)
     
        return super().get_queryset(request).filter(created_by=request.user)

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """
    Admin view for monitoring campaigns.
    """
    list_display = ('name', 'status', 'created_by', 'created_at', 'scheduled_at', 'completed_at')
    list_filter = ('status', 'created_by')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'completed_at')

@admin.register(CampaignRecipient)
class CampaignRecipientAdmin(admin.ModelAdmin):
    """
    Admin view for viewing campaign logs.
    """
    list_display = ('phone_number', 'campaign', 'status', 'sent_at')
    list_filter = ('status', 'campaign__name')
    search_fields = ('phone_number',)
    readonly_fields = ('sent_at',)