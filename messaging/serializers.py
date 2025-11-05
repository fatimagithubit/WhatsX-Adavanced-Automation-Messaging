from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from messaging.models import MessageCampaign, CampaignRecipient
from .models import Contact

User = get_user_model()

# --- Utility Serializers for Reading/Viewing ---

class CampaignRecipientSerializer(serializers.ModelSerializer):
    """Serializer for viewing individual recipient status within a campaign."""
    contact_name = serializers.ReadOnlyField(source='contact.name')

    class Meta:
        model = CampaignRecipient
        fields = ['id', 'contact_name', 'phone_number', 'send_status', 'sent_at', 'error_message']
        read_only_fields = ['id', 'contact_name', 'phone_number', 'send_status', 'sent_at', 'error_message']

class MessageCampaignSerializer(serializers.ModelSerializer):
    """
    Serializer for listing and viewing overall campaign details.
    Includes count of recipients and a nested view of individual recipients.
    """
    recipients = CampaignRecipientSerializer(many=True, read_only=True)
    
    class Meta:
        model = MessageCampaign
        fields = [
            'id', 'name', 'message_content', 'message_template', 
            'status', 'created_at', 'scheduled_time', 'attachment',
            'total_recipients', 'messages_sent', 'messages_failed',
            'recipients' # Nested serializer for detailed view
        ]
        read_only_fields = [
            'id', 'status', 'created_at', 
            'total_recipients', 'messages_sent', 'messages_failed', 'recipients'
        ]

# --- Main Serializer for Campaign Creation (Write Operations) ---

class CampaignCreationSerializer(serializers.ModelSerializer):
    """
    Serializer used specifically for creating a new campaign.
    It takes a list of contact IDs and generates CampaignRecipient entries.
    """
    # This field receives a list of primary keys (IDs) of Contact objects
    contact_ids = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=Contact.objects.all()),
        write_only=True,
        required=True,
        help_text="A list of Contact IDs (integers) to send the message to."
    )
    
    # Optional field for manually inputting extra phone numbers
    manual_numbers = serializers.ListField(
        child=serializers.CharField(max_length=20),
        write_only=True,
        required=False,
        default=[],
        help_text="A list of phone numbers (strings) not saved in Contacts."
    )

    class Meta:
        model = MessageCampaign
        fields = [
            'id', 'name', 'message_content', 'message_template', 
            'scheduled_time', 'attachment', 
            'contact_ids', 'manual_numbers'
        ]

    def validate(self, data):
        """Ensure at least one recipient is specified."""
        contact_ids = data.get('contact_ids', [])
        manual_numbers = data.get('manual_numbers', [])
        
        if not (contact_ids or manual_numbers):
            raise serializers.ValidationError("The campaign must target at least one contact ID or manual phone number.")
            
        return data

    def create(self, validated_data):
        """
        Creates the MessageCampaign and all associated CampaignRecipient records
        in a single database transaction.
        """
        contact_pks = validated_data.pop('contact_ids') # list of Contact objects
        manual_numbers = validated_data.pop('manual_numbers')
        
        # Determine initial status
        if validated_data.get('scheduled_time'):
            validated_data['status'] = 'PENDING'
        else:
            # If no schedule, it's a DRAFT ready for the worker to pick up immediately
            validated_data['status'] = 'DRAFT' 
        
        user = self.context['request'].user
        validated_data['user'] = user
        
        # Use a transaction to ensure either everything saves, or nothing does
        with transaction.atomic():
            campaign = MessageCampaign.objects.create(**validated_data)
            recipients_to_create = []

            # 1. Add recipients from saved Contacts (contact_pks is a list of Contact objects)
            for contact in contact_pks:
                recipients_to_create.append(
                    CampaignRecipient(
                        campaign=campaign,
                        contact=contact,
                        phone_number=contact.phone, # Use the phone number from the Contact object
                        send_status='PENDING'
                    )
                )

            # 2. Add recipients from manual numbers (Ensure numbers are unique)
            for number in set(manual_numbers):
                # Check if this number was already included via a saved contact to avoid duplicates
                is_duplicate = any(r.phone_number == number for r in recipients_to_create)
                
                if not is_duplicate:
                    recipients_to_create.append(
                        CampaignRecipient(
                            campaign=campaign,
                            phone_number=number,
                            contact=None, # No linked Contact object
                            send_status='PENDING'
                        )
                    )

            # Bulk create all recipient records
            CampaignRecipient.objects.bulk_create(recipients_to_create)
            
            # Update the campaign's total_recipients count
            campaign.total_recipients = len(recipients_to_create)
            campaign.save()

            return campaign