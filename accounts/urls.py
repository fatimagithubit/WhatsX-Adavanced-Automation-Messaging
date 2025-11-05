from django.urls import path
from . import views_ui

app_name = 'accounts'

urlpatterns = [
    # Auth URLs
    path('login/', views_ui.login_view, name='login_view'),
    path('register/', views_ui.register_view, name='register_view'),
    path('logout/', views_ui.logout_view, name='logout_view'),
    

    path('dashboard/', views_ui.user_dashboard, name='user_dashboard'),
    
    path('profile/edit/', views_ui.edit_profile, name='edit_profile'),
    path('contacts/', views_ui.contacts_list_view, name='contacts_list'),
    path('contacts/add/', views_ui.contacts_add_view, name='contacts_add'),
    path('contacts/edit/<int:pk>/', views_ui.contacts_edit_view, name='contacts_edit'),
    path('contacts/delete/<int:pk>/', views_ui.contacts_delete_view, name='contacts_delete'),
  
] 