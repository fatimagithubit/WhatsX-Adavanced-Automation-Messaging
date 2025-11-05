from django import forms
from django.db.models import Q
# Aapke naye finalized models ko import karna
from .models import MessageCampaign, MessageTemplate, WhatsAppCredentials 
# Yeh assume kiya gaya hai ki accounts.models mein Contact hai
from accounts.models import Contact 


# =========================================================================
# 1. WhatsApp Credentials Form (CONNECTION)
# =========================================================================

class WhatsAppCredentialsForm(forms.ModelForm):
    """
    Form for configuring the user's WhatsApp API credentials (session and number).
    """
    class Meta:
        model = WhatsAppCredentials
        # Hum session_id aur phone_number ko user se lete hain
        fields = ['session_id', 'whatsapp_phone_number'] 
        
        widgets = {
            'session_id': forms.TextInput(attrs={'placeholder': 'External API Session ID'}),
            'whatsapp_phone_number': forms.TextInput(attrs={'placeholder': 'e.g., +923001234567 (WhatsApp Number)'}),
        }
        
# =========================================================================
# 2. Message Campaign Form (BULK SENDING)
# =========================================================================

class CampaignForm(forms.ModelForm): 
    """
    Form to create/edit a MessageCampaign, including recipient selection options.
    """
    
    
    # 1. Contacts jo database mein hain
    selected_contacts = forms.ModelMultipleChoiceField(
        queryset=Contact.objects.none(), # Initial queryset empty rakha hai
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Select Contacts from List"
    )

    # 2. Manual numbers text area
    manual_numbers = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Enter phone numbers, one per line (e.g., +923001234567)'}),
        required=False,
        label="Manual Phone Numbers (One per Line)"
    )
    
    # 3. CSV upload
    csv_file = forms.FileField(
        required=False,
        label="Upload Contact CSV File (Name, Phone_Number columns expected)"
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        if self.user:
           
            admin_users = self.user.__class__.objects.filter(Q(is_superuser=True))
            
            self.fields['message_template'].queryset = MessageTemplate.objects.filter(
                Q(created_by=self.user) | Q(created_by__in=admin_users)
            ).distinct().order_by('title')

           
            self.fields['selected_contacts'].queryset = Contact.objects.filter(user=self.user).order_by('name')

        # scheduled_time 
        self.fields['scheduled_time'].widget = forms.DateTimeInput(
            attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
        )
        self.fields['message_template'].empty_label = "--- Select a Template (Optional) ---"


    def clean(self):
        cleaned_data = super().clean()
        
        selected_contacts = self.data.getlist('selected_contacts')
        manual_numbers = cleaned_data.get('manual_numbers')
        csv_file = self.files.get('csv_file')
        message_template = cleaned_data.get('message_template')
        message_content = cleaned_data.get('message_content')
        
       
        if not message_template and not message_content:
            self.add_error('message_content', "Please provide a message template or write the message content manually.")

      
        if not selected_contacts and not manual_numbers and not csv_file:
            
            raise forms.ValidationError(
                "You must select contacts, enter manual numbers, or upload a CSV file to send the campaign."
            )
        
        return cleaned_data


    class Meta:
        model = MessageCampaign 
        
        fields = ['name', 'message_template', 'message_content', 'scheduled_time', 'attachment']
        
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter Campaign Name (e.g., Eid Offers 2025)'}),
            'message_content': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Write your message here. (Overrides template content if both are provided.)'}),
        }
