from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Q 
import csv
import io

from .forms import CustomUserCreationForm, UserProfileUpdateForm, ContactForm
from .models import Contact


try:
    from messaging.models import Campaign, CampaignRecipient, MessageTemplate # Updated MessageTemplate import
    CAMPAIGN_MODEL = Campaign
    RECIPIENT_MODEL = CampaignRecipient
    MESSAGING_MODELS_AVAILABLE = True
except ImportError:
    
    class SafeQuerySet:
        def filter(self, *args, **kwargs): return self
        def count(self): return 0
        def values_list(self, *args, **kwargs): return []
        def exists(self): return False
        def annotate(self, *args, **kwargs): return self
        def order_by(self, *args, **kwargs): return self
        def aggregate(self, *args, **kwargs): return {'total_sent': 0}

    class SafeModel:
        objects = SafeQuerySet()
        DoesNotExist = Exception 
        Status = type('Status', (object,), {'SENT': 'SENT', 'PENDING': 'PENDING', 'IN_PROGRESS': 'IN_PROGRESS', 'COMPLETED': 'COMPLETED'})

    CAMPAIGN_MODEL = SafeModel
    RECIPIENT_MODEL = SafeModel
    MESSAGING_MODELS_AVAILABLE = False


User = get_user_model()


# --- Authentication Views ---
def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully. You can now log in.')
            return redirect('accounts:login_view')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """Handles user login."""
    if request.user.is_authenticated:
        return redirect('accounts:user_dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                
                if user.is_staff or user.is_superuser:
                    return redirect(reverse('admin:index'))
                else:
                    return redirect('accounts:user_dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    """Logs out the user and redirects to the login page."""
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect('accounts:login_view')

# --- Dashboard Views (User-Specific or Admin-Global) ---

@login_required
def user_dashboard(request):
    # Determine the time frame for stats (default 7 days)
    try:
        days = int(request.GET.get('days', 7))
    except ValueError:
        days = 7
        
    start_date = timezone.now() - timedelta(days=days)
    
    # ----------------------------------------------------------------------
    # 1. CORE STATS CALCULATION
    # ----------------------------------------------------------------------

    
    total_contacts = Contact.objects.filter(user=request.user).count()

  
    sent_messages = 0
    scheduled_messages = 0
    
    if MESSAGING_MODELS_AVAILABLE:
       
        campaigns_in_period = CAMPAIGN_MODEL.objects.filter(
            created_by=request.user, 
            created_at__gte=start_date
        )
        
        # Count SENT messages from these campaigns
        sent_messages = RECIPIENT_MODEL.objects.filter(
            campaign__in=campaigns_in_period,
            status=RECIPIENT_MODEL.Status.SENT
        ).count()
        
        # Count PENDING recipients (messages scheduled but not yet sent)
        scheduled_messages = RECIPIENT_MODEL.objects.filter(
            campaign__in=campaigns_in_period,
            status=RECIPIENT_MODEL.Status.PENDING,
            campaign__status=CAMPAIGN_MODEL.Status.PENDING 
        ).count()
        
        
        total_sent_ever = RECIPIENT_MODEL.objects.filter(
            campaign__created_by=request.user,
            status=RECIPIENT_MODEL.Status.SENT
        ).count()

        monthly_quota = request.user.message_quota
        remaining_quota = max(0, monthly_quota - total_sent_ever)



    context = {
        # Time frame
        'days': days,
        
        # KPI Cards
        'total_contacts': total_contacts,
        'sent_messages': sent_messages,
        'scheduled_messages': scheduled_messages,
        
        
        # User details for profile card
        'user_avatar_url': request.user.image.url if request.user.image else f"https://ui-avatars.com/api/?name={request.user.username}&background=25D366&color=fff&size=64",
        'edit_profile_url': reverse('accounts:edit_profile'), # Assuming you have this URL name
        
        # Data for chart (Messages by Status)
        'chart_data_messages': [sent_messages, scheduled_messages],
    }

    return render(request, 'accounts/user_dashboard.html', context)

@login_required
def edit_profile_view(request):
    """Handles user profile updates."""
    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:edit_profile') 
    else:
        form = UserProfileUpdateForm(instance=request.user)
    return render(request, 'accounts/edit_profile.html', {'form': form})

edit_profile = edit_profile_view

# --- Contacts Management Views (User-Specific or Admin-Global) ---

@login_required
def contacts_list_view(request):
   
    user = request.user
    
    if user.is_superuser or (hasattr(user, 'user_type') and user.user_type == 'admin'):
        # Admin: 
        contacts = Contact.objects.all().order_by('user__username', 'name')
        is_admin = True
    else:
        # End User: 
        contacts = Contact.objects.filter(user=user).order_by('name')
        is_admin = False
        
    context = {
        'contacts': contacts,
        'is_admin': is_admin
    }
    return render(request, 'accounts/contacts_list.html', context)


@login_required
def contacts_add_view(request):
    
    
    if request.method == 'POST':
        form = ContactForm(request.POST, request.FILES, user=request.user) 
        if form.is_valid():
            contact = form.save(commit=False)
            contact.user = request.user 
            contact.save()
            messages.success(request, f'Contact "{contact.name}" added successfully.')
            return redirect('accounts:contacts_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = ContactForm(user=request.user)

    return render(request, 'accounts/contacts_add.html', {'form': form, 'title': 'Add New Contact'})


@login_required
def contacts_edit_view(request, pk):
    """
    Existing contact ko edit karta hai.
    Admin kisi bhi contact ko edit kar sakta hai. End User sirf apne contacts.
    """
    user = request.user
    
    if user.is_superuser or (hasattr(user, 'user_type') and user.user_type == 'admin'):
        
        contact = get_object_or_404(Contact, pk=pk)
    else:
      
        contact = get_object_or_404(Contact, pk=pk, user=user)

    if request.method == 'POST':
        form = ContactForm(request.POST, request.FILES, instance=contact, user=request.user)
        if form.is_valid():
            form.save() 
            messages.success(request, f'Contact "{contact.name}" updated successfully.')
            return redirect('accounts:contacts_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = ContactForm(instance=contact, user=request.user)

    return render(request, 'accounts/contacts_edit.html', {'form': form, 'title': f'Edit Contact: {contact.name}'})


@login_required
def contacts_delete_view(request, pk):
    
    user = request.user
    
    if user.is_superuser or (hasattr(user, 'user_type') and user.user_type == 'admin'):
       
        contact = get_object_or_404(Contact, pk=pk)
    else:
        
        contact = get_object_or_404(Contact, pk=pk, user=user)

    if request.method == 'POST':
        name = contact.name
        contact.delete()
        messages.success(request, f'Contact "{name}" deleted successfully.')
        return redirect('accounts:contacts_list')

    return render(request, 'accounts/contacts_confirm_delete.html', {'contact': contact})
  
