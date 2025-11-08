import csv, io, re, json, requests, time, os
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction, models
from django.http import JsonResponse, HttpResponseServerError
from .models import Campaign, CampaignRecipient, MessageTemplate, Attachment
from core.settings import WHATSAPP_API_URL
from accounts.models import Contact 

# ========== CONFIG ==========
GEMINI_MODEL = "gemini-2.5-flash-preview-09-2025"
API_KEY = os.environ.get("API_KEY")
MAX_RETRIES = 5
INITIAL_DELAY = 1  # seconds


# ===============================================================
# SECTION 1: WHATSAPP CONNECTION (Node.js Integration)
# ===============================================================

@login_required
def whatsapp_connect_view(request):
    """Main page for WhatsApp connection."""
    return render(request, 'messaging/whatsapp_connect.html')


def make_node_request(method, endpoint, user_id, data=None):
    """Helper to communicate with Node.js service."""
    node_url = f"{WHATSAPP_API_URL}/{endpoint}"
    headers = {'Content-Type': 'application/json'}
    payload = data or {}

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
    """Start WhatsApp session."""
    return make_node_request('post', 'start', request.user.id)


@login_required
def status_api(request):
    """Check WhatsApp session status."""
    return make_node_request('get', 'status', request.user.id)


@login_required
def disconnect_api(request):
    """Disconnect WhatsApp session."""
    return make_node_request('post', 'disconnect', request.user.id)


# ===============================================================
# SECTION 2: CAMPAIGNS & TEMPLATES
# ===============================================================

@login_required
def template_list_view(request):
    """List templates (user + superuser)."""
    templates = MessageTemplate.objects.filter(
        models.Q(created_by=request.user) | models.Q(created_by__is_superuser=True)
    ).distinct().order_by('title')
    return render(request, 'messaging/template_list.html', {'templates': templates})


@login_required
def campaign_list_view(request):
    """List all campaigns by the user."""
    campaigns = Campaign.objects.filter(created_by=request.user).order_by('-created_at')
    return render(request, 'messaging/campaign_list.html', {'campaigns': campaigns})


@login_required
@transaction.atomic
def campaign_create_view(request):
    """Create + schedule campaigns."""
    if request.method == 'POST':
        try:
            name = request.POST.get('campaign_name')
            msg = request.POST.get('message_content')
            attachments = request.FILES.getlist('attachments')

            if not (name and (msg or attachments)):
                raise ValueError("Campaign Name and Message or Attachment required.")

            recipients = _process_recipients(request)
            if not recipients:
                raise ValueError("No valid recipients found. Format must be 92XXXXXXXXXX.")

            # create campaign
            campaign = Campaign.objects.create(
                name=name,
                message_content=msg,
                created_by=request.user
            )

            # add attachments
            for file in attachments:
                Attachment.objects.create(campaign=campaign, file=file)

            # add recipients
            CampaignRecipient.objects.bulk_create([
                CampaignRecipient(campaign=campaign, phone_number=p)
                for p in recipients
            ])

            # load celery task dynamically
            try:
                from .tasks import send_campaign_messages
            except ImportError:
                raise Exception("Celery task import failed. Check messaging.tasks.")

            scheduled_at_str = request.POST.get('scheduled_at')
            if scheduled_at_str:
                scheduled_at = timezone.make_aware(
                    timezone.datetime.strptime(scheduled_at_str, '%Y-%m-%dT%H:%M')
                )
                if scheduled_at <= timezone.now():
                    raise ValueError("Scheduled time must be in the future.")

                campaign.scheduled_at = scheduled_at
                campaign.status = Campaign.Status.PENDING
                send_campaign_messages.apply_async(args=[campaign.id], eta=scheduled_at)
                messages.success(request, f"Campaign '{campaign.name}' scheduled for {scheduled_at.strftime('%Y-%m-%d %H:%M')}.")
            else:
                campaign.status = Campaign.Status.IN_PROGRESS
                campaign.started_at = timezone.now()
                send_campaign_messages.delay(campaign.id)
                messages.success(request, f"Campaign '{campaign.name}' launched.")

            campaign.save()
            return redirect('messaging:campaign_list')

        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Error creating campaign: {e}")

    # GET render form
    templates = MessageTemplate.objects.filter(
        models.Q(created_by=request.user) | models.Q(created_by__is_superuser=True)
    ).distinct()
    contacts = Contact.objects.filter(user=request.user)
    templates_json = json.dumps({t.id: t.content for t in templates})

    return render(request, 'messaging/campaign_form.html', {
        'templates': templates,
        'contacts': contacts,
        'templates_json': templates_json,
    })


# ===============================================================
# SECTION 3: HELPERS
# ===============================================================

def _process_recipients(request):
    """Get recipients from manual, csv or contacts."""
    source = request.POST.get('recipient_source')
    recipients = set()

    if source == 'manual':
        numbers = request.POST.get('manual_numbers', '').strip()
        if not numbers:
            raise ValueError("No numbers provided in manual entry.")
        for n in numbers.splitlines():
            if p := _normalize_phone(n.strip()):
                recipients.add(p)

    elif source == 'csv':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            raise ValueError("CSV file missing.")
        file_content = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(file_content))
        phone_col = next((c for c in reader.fieldnames if 'phone' in c.lower()), None)
        if not phone_col:
            raise ValueError("CSV must contain a 'phone' column.")
        for row in reader:
            phone_data = row.get(phone_col)
            if phone_data and (p := _normalize_phone(phone_data)):
                recipients.add(p)

    elif source == 'contacts':
        ids = request.POST.getlist('contacts')
        if not ids:
            raise ValueError("No contacts selected.")
        for c in Contact.objects.filter(id__in=ids, user=request.user):
            if p := _normalize_phone(c.phone):
                recipients.add(p)

    else:
        raise ValueError("Invalid recipient source.")
    return recipients


def _normalize_phone(number):
    """Normalize Pakistani numbers to +92XXXXXXXXXX."""
    number = re.sub(r'\D', '', str(number))
    if len(number) == 10 and number.startswith('3'):
        number = '92' + number
    elif len(number) == 11 and number.startswith('03'):
        number = '92' + number[1:]
    if len(number) == 12 and number.startswith('92'):
        return f"+{number}"
    return None


# ===============================================================
# SECTION 4: AI DRAFTING (Gemini API)
# ===============================================================

@login_required
def ai_draft_message(request):
    """Generate message draft using Gemini API."""
    if not API_KEY:
        return JsonResponse(
            {'status': 'ERROR', 'message': 'AI API key missing on server.'},
            status=503
        )

    if request.method != 'POST':
        return JsonResponse({'status': 'ERROR', 'message': 'Invalid request method.'}, status=405)

    try:
        data = json.loads(request.body)
        prompt = data.get('prompt')
        if not prompt:
            return JsonResponse({'status': 'ERROR', 'message': 'Prompt is required.'}, status=400)

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {
                "parts": [{"text": "You are a marketing assistant. Draft short, catchy WhatsApp/SMS messages using emojis."}]
            },
        }

        delay = INITIAL_DELAY
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)
                resp.raise_for_status()
                result = resp.json()
                generated = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')
                if not generated:
                    return JsonResponse({'status': 'ERROR', 'message': 'Empty AI response.'}, status=500)
                return JsonResponse({'status': 'SUCCESS', 'draft': generated})

            except requests.exceptions.HTTPError as err:
                if 500 <= err.response.status_code < 600:
                    last_error = f"HTTP {err.response.status_code}, retrying..."
                    time.sleep(delay)
                    delay *= 2
                    continue
                return JsonResponse({'status': 'ERROR', 'message': str(err)}, status=err.response.status_code)

            except requests.exceptions.RequestException as req_err:
                last_error = str(req_err)
                time.sleep(delay)
                delay *= 2
                continue

        return JsonResponse(
            {'status': 'ERROR', 'message': f'AI failed after {MAX_RETRIES} retries. Last error: {last_error}'},
            status=503
        )

    except json.JSONDecodeError:
        return JsonResponse({'status': 'ERROR', 'message': 'Invalid JSON.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'ERROR', 'message': f'Internal Error: {e}'}, status=500)
