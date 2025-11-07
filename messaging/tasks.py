import requests
from django.conf import settings
from django.utils import timezone
from .models import Campaign, CampaignRecipient

def send_campaign_messages(campaign_id):
    """Sends all messages in a campaign directly via Node.js WhatsApp API."""
    campaign = Campaign.objects.get(id=campaign_id)
    recipients = CampaignRecipient.objects.filter(campaign=campaign)
    
    success_count = 0
    fail_count = 0

    for recipient in recipients:
        payload = {
            "userId": campaign.created_by.id,
            "phone": recipient.phone_number,
            "message": campaign.message_content
        }
        try:
            response = requests.post(
                f"{settings.WHATSAPP_GATEWAY_URL}",
                json=payload,
                timeout=15
            )
            response.raise_for_status()
            success_count += 1
        except requests.RequestException as e:
            print(f"❌ Failed to send message to {recipient.phone_number}: {e}")
            fail_count += 1

    campaign.status = Campaign.Status.COMPLETED
    campaign.completed_at = timezone.now()
    campaign.save()

    print(f"✅ Campaign '{campaign.name}' completed — Sent: {success_count}, Failed: {fail_count}")
    return {"sent": success_count, "failed": fail_count}
