import requests

# Live URL of your Render Service (Aapko yeh Step 3 mein milega)
WHATSAPP_GATEWAY_URL = 'https://whatsapp-service-xyz.onrender.com/send-message' 

# Pehle: Yeh Celery task tha. Ab yeh simple Python function hai.
def send_whatsapp_message(phone_number: str, message_text: str):
    
    try:
        response = requests.post(
            WHATSAPP_GATEWAY_URL,
            json={'phone': phone_number, 'message': message_text},
            timeout=10 # 10 seconds ka timeout
        )
        response.raise_for_status() # Agar 4xx ya 5xx error aaye toh exception utha dega
        
        print(f"Message sent successfully to {phone_number}. Status: {response.status_code}")
        return response.json()
        
    except requests.exceptions.RequestException as e:
        # Agar Node.js service down hai ya koi connection error hai
        print(f"Error connecting to WhatsApp Gateway: {e}")
        # Yahan aap error ko database mein log kar sakte hain
        return {"status": "error", "message": str(e)}

# --- Celery Configuration hata di gayi hai ---
# Is file se 'app' ya 'shared_task' import karne ki ab zaroorat nahin hai.

# NOTE: Is function ko ab aap apne views.py mein direct call karenge:
# from .tasks import send_whatsapp_message
# send_whatsapp_message(phone_number, message_text)
