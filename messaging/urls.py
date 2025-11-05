

from django.urls import path
from . import views_ui

app_name = 'messaging'

urlpatterns = [
    path('connect/', views_ui.whatsapp_connect_view, name='whatsapp_connect'),
    path('templates/', views_ui.template_list_view, name='template_list'),
    path('campaigns/', views_ui.campaign_list_view, name='campaign_list'),
    path('campaigns/create/', views_ui.campaign_create_view, name='campaign_create'),
    path('api/whatsapp/start/', views_ui.start_session_api, name='whatsapp_start_api'),
    path('api/whatsapp/status/', views_ui.status_api, name='whatsapp_status_api'),
    path('api/whatsapp/disconnect/', views_ui.disconnect_api, name='whatsapp_disconnect_api'),
    path('api/ai-draft/', views_ui.ai_draft_message, name='ai_draft_message'),]