import csv, io, re, json, requests, time, os
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction, models
from django.http import JsonResponse, HttpResponseServerError
from .models import Campaign, CampaignRecipient, MessageTemplate, Attachment

from accounts.models import Contact 

# --- CONFIGURATION ---

GEMINI_MODEL = "gemini-2.5-flash-preview-09-2025" 
# The API key provided by the user is now configured here.
API_KEY = os.environ.get("API_KEY")
MAX_RETRIES = 5
INITIAL_DELAY = 1  # seconds

# =========================================================================
# SECTION 1: WHATSAPP CONNECTION (Integration with Node.js Service)
# =========================================================================

@login_required
def whatsapp_connect_view(request):
    """Renders the main page for connecting to WhatsApp."""
    return render(request, 'messaging/whatsapp_connect.html')

def make_node_request(method, endpoint, user_id, data=None):
    """
    Helper function to call the Node.js service endpoint, passing user_id 
    for multi-session support. Handles connection errors and timeouts.
    """
    node_url = f"http://127.0.0.1:3001/{endpoint}"
    
    headers = {'Content-Type': 'application/json'}
    payload = data if data is not None else {}
    
    try:
        if method.lower() == 'post':
            
            payload['userId'] = user_id
            response = requests.post(node_url, json=payload, headers=headers, timeout=30)
        else:
           
            node_url_with_id = f"{node_url}?userId={user_id}"
            response = requests.get(node_url_with_id, timeout=10)
            
        response.raise_for_status() 
        return JsonResponse(response.json())
        
    except requests.exceptions.RequestException as e:
      
        return JsonResponse(
            {'status': 'ERROR', 'message': f'WhatsApp service failed or timed out: {e}'}, 
            status=503
        )

@login_required
def start_session_api(request):
    """Starts the WhatsApp session for the current user."""
    return make_node_request('post', 'start', request.user.id)

@login_required
def status_api(request):
    """Checks the status of the WhatsApp session for the current user."""
    return make_node_request('get', 'status', request.user.id)

@login_required
def disconnect_api(request):
    """Disconnects the WhatsApp session for the current user."""
    return make_node_request('post', 'disconnect', request.user.id)

# =========================================================================
# SECTION 2: TEMPLATES AND CAMPAIGNS
# =========================================================================

@login_required
def template_list_view(request):
    """Displays a list of templates available to the user (created by user or superuser)."""
    templates = MessageTemplate.objects.filter(
        models.Q(created_by=request.user) | models.Q(created_by__is_superuser=True)
    ).distinct().order_by('title')
    return render(request, 'messaging/template_list.html', {'templates': templates})

@login_required
def campaign_list_view(request):
    """Displays a list of all campaigns created by the user."""
    campaigns = Campaign.objects.filter(created_by=request.user).order_by('-created_at')
    return render(request, 'messaging/campaign_list.html', {'campaigns': campaigns})

@login_required
@transaction.atomic
def campaign_create_view(request):
    """Handles creating a new campaign, processing recipients, and scheduling the send task."""
    if request.method == 'POST':
        try:
            campaign_name = request.POST.get('campaign_name')
            message_content = request.POST.get('message_content')
            attachments = request.FILES.getlist('attachments')
            
            if not all([campaign_name, message_content]) and not attachments:
                raise ValueError("Campaign Name and either a Message or an Attachment are required.")
            
            
            recipients = _process_recipients(request)
            if not recipients: 
                raise ValueError("No valid recipients found. Check number format (e.g., 92XXXXXXXXXX).")
            
            # 1. Create the Campaign object
            campaign = Campaign.objects.create(
                name=campaign_name,
                message_content=message_content,
                created_by=request.user
            )

            # 2. Handle multiple attachments
            attachments = request.FILES.getlist('attachments')
            for attachment_file in attachments:
                Attachment.objects.create(campaign=campaign, file=attachment_file)
            
            # 3. Bulk create recipients associated with the campaign
            recipient_objects = [CampaignRecipient(campaign=campaign, phone_number=p) for p in recipients]
            CampaignRecipient.objects.bulk_create(recipient_objects)

            # 3. Safely import the Celery task here to prevent circular dependencies
            try:
                from .tasks import send_campaign_messages
            except ImportError:
                raise Exception("Failed to load Celery task 'send_campaign_messages'. Check messaging.tasks.")
            
            # 4. Handle Scheduling vs. Immediate Send
            scheduled_at_str = request.POST.get('scheduled_at')
            
            if scheduled_at_str:
                # Scheduled Send
                scheduled_at = timezone.make_aware(timezone.datetime.strptime(scheduled_at_str, '%Y-%m-%dT%H:%M'))
                if scheduled_at <= timezone.now(): 
                    raise ValueError("Scheduled time must be in the future.")
                
                campaign.scheduled_at = scheduled_at
                campaign.status = Campaign.Status.PENDING
                
                # Schedule Celery task to run at the specified time
                send_campaign_messages.apply_async(args=[campaign.id], eta=scheduled_at)
                messages.success(request, f"Campaign '{campaign.name}' scheduled successfully for {scheduled_at.strftime('%Y-%m-%d %H:%M')}.")
            else:
                # Immediate Send
                campaign.status = Campaign.Status.IN_PROGRESS
                campaign.started_at = timezone.now()
                
                # Launch Celery task immediately
                send_campaign_messages.delay(campaign.id)
                messages.success(request, f"Campaign '{campaign.name}' has been launched and is now running.")
            
            campaign.save()
            return redirect('messaging:campaign_list')
            
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"An unexpected error occurred during campaign creation: {e}")
            
    # GET or failed POST request: Render the form
    user_templates = MessageTemplate.objects.filter(
        models.Q(created_by=request.user) | models.Q(created_by__is_superuser=True)
    ).distinct()
    user_contacts = Contact.objects.filter(user=request.user)
    
    # Prepare template content for use in frontend JavaScript
    templates_json = json.dumps({t.id: t.content for t in user_templates})
    
    context = {
        'templates': user_templates, 
        'contacts': user_contacts, 
        'templates_json': templates_json
    }
    return render(request, 'messaging/campaign_form.html', context)

def _process_recipients(request):
    """Helper function to process recipients based on the 'one source' rule."""
    source = request.POST.get('recipient_source')
    recipients = set()
    
    if source == 'manual':
        numbers = request.POST.get('manual_numbers', '').strip()
        if not numbers: 
            raise ValueError("Manual Entry selected, but no numbers were provided.")
        for n in numbers.splitlines():
            if p := _normalize_phone(n.strip()): recipients.add(p)
            
    elif source == 'csv':
        csv_file = request.FILES.get('csv_file')
        if not csv_file: 
            raise ValueError("CSV Upload selected, but no file was uploaded.")
        
        # Read file content into StringIO
        file_content = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(file_content))
        
        # Find the phone number column (case-insensitive search for 'phone')
        phone_col = next((c for c in reader.fieldnames if 'phone' in c.lower()), None)
        if not phone_col: 
            raise ValueError("CSV must have a column with 'phone' in the header (e.g., phone, Phone Number).")
        
        for row in reader:
            phone_data = row.get(phone_col)
            if phone_data and (p := _normalize_phone(phone_data)): 
                recipients.add(p)
            
    elif source == 'contacts':
        contact_ids = request.POST.getlist('contacts')
        if not contact_ids: 
            raise ValueError("From Contacts selected, but no contacts were checked.")
        
        # Fetch contacts belonging to the current user
        for contact in Contact.objects.filter(id__in=contact_ids, user=request.user):
            if p := _normalize_phone(contact.phone): recipients.add(p)
            
    else:
        raise ValueError("A valid recipient source was not selected.")
        
    return recipients

def _normalize_phone(number):
    """
    Normalizes the phone number to E.164 format (+92XXXXXXXXXX).
    Assumes Pakistan country code (92) based on the original logic.
    Returns the normalized number string or None if invalid.
    """
    # 1. Remove all non-digit characters
    number = re.sub(r'\D', '', str(number))

    # 2. Check for Pakistani number lengths/prefixes
    if len(number) == 10 and number.startswith('3'):
        # e.g., 3001234567 (10 digits starting with 3) -> 923001234567
        number = '92' + number
    elif len(number) == 11 and number.startswith('03'):
        # e.g., 03001234567 (11 digits starting with 03) -> 923001234567
        number = '92' + number[1:]
    
    # 3. Final check for E.164 format (12 digits starting with 92)
    if len(number) == 12 and number.startswith('92'):
        return f"+{number}" # Returns +923001234567
    
    return None

# =========================================================================
# SECTION 3: AI DRAFTING (Gemini API Integration with Exponential Backoff)
# =========================================================================

@login_required
def ai_draft_message(request):
    """
    Generates a message draft using the Gemini API based on a user prompt,
    implementing exponential backoff for reliable API calls.
    This view is called via AJAX/fetch from the frontend.
    """
    # --- API Key Check ---
    if not API_KEY:
        return JsonResponse(
            {'status': 'ERROR', 'message': 'AI Service is not configured. The API key is missing on the server.'},
            status=503 # Service Unavailable
        )

    if request.method != 'POST':
        return JsonResponse({'status': 'ERROR', 'message': 'Invalid request method.'}, status=405)
    
    try:
        data = json.loads(request.body)
        user_prompt = data.get('prompt')

        if not user_prompt:
            return JsonResponse({'status': 'ERROR', 'message': 'Prompt is required.'}, status=400)

        # API endpoint setup
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={API_KEY}"

        # API Payload
        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "systemInstruction": {
                "parts": [{"text": "You are a marketing message drafting assistant. Draft a short, concise, and engaging message suitable for SMS or WhatsApp based on the user's request. Keep the formatting simple and use emojis where appropriate."}]
            },
        }
        
        delay = INITIAL_DELAY
        last_error = None

        # --- Exponential Backoff Logic ---
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    api_url, 
                    json=payload, 
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                response.raise_for_status() # Success, break out of loop
                
                # Process successful response
                result = response.json()
                generated_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')

                if not generated_text:
                    # Treat empty response as a hard error, no retry
                    return JsonResponse(
                        {'status': 'ERROR', 'message': 'AI returned an empty or malformed response.'}, 
                        status=500
                    )

                return JsonResponse({'status': 'SUCCESS', 'draft': generated_text})

            except requests.exceptions.HTTPError as http_err:
                # Retry on 5xx errors (server-side issues)
                if 500 <= http_err.response.status_code < 600:
                    last_error = f"HTTP {http_err.response.status_code} error. Retrying in {delay:.2f}s..."
                    time.sleep(delay)
                    delay *= 2
                    continue
                else:
                    # Treat client errors (4xx) as non-retryable
                    return JsonResponse(
                        {'status': 'ERROR', 'message': f'AI API Client Error: {http_err}'}, 
                        status=http_err.response.status_code
                    )

            except requests.exceptions.RequestException as req_err:
                # Retry on connection errors, timeouts, etc.
                last_error = f"Network or Timeout Error: {req_err}. Retrying in {delay:.2f}s..."
                time.sleep(delay)
                delay *= 2
                continue

        # If the loop completes without success
        return JsonResponse(
            {'status': 'ERROR', 'message': f'AI Service failed after {MAX_RETRIES} attempts. Last error: {last_error}'}, 
            status=503
        )

    except json.JSONDecodeError:
        return JsonResponse({'status': 'ERROR', 'message': 'Invalid JSON request body.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'ERROR', 'message': f'An unexpected internal error occurred: {e}'}, status=500)
