import requests
import json

# ==============================================================================
# 🔐 CONFIGURATION (UPDATE THESE WITH YOUR NEW INR ACCOUNT DETAILS)
# ==============================================================================

# 1. Go to WhatsApp Manager -> select your NEW 'CareBridge INR' account.
#    Copy the "915417844997635" (It is different from the old one).
PHONE_NUMBER_ID = "EAAhECSeoQxkBQkSmvEqZA9eOZBPAHnZA0ZBxGcOEXdlrevj1EdA7WAGs9q5KCOpqdZAYZCuCDv0FrLql03ipoutErMnhwdxJslJ1JpZAMdHyruBKI3Ayi1QGz95YVvA2tBZCNrgJAbfDJzjhcFuEChRnbYiRk1FKv1WkE88PEZBhKGxP75NqmctDDZAi1pFWNeZAk9QgQZDZD" 

# 2. Go to Business Settings -> System Users -> Generate Token.
#    Copy the long code starting with "EAA..."
ACCESS_TOKEN = "PASTE_YOUR_NEW_PERMANENT_TOKEN_HERE"

# 3. Enter your Personal WhatsApp Number (91 + 10 digits).
#    Example: "919080553616" (No '+' sign, no spaces).
RECIPIENT_NUMBER = "919080553616" 

# ==============================================================================
# 🚀 THE SENDING ENGINE
# ==============================================================================

def send_reactivation_message(to_mobile, patient_name):
    """
    Sends the 'reactivation_v1' template to a specific number.
    """
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Payload for the 'reactivation_v1' template
    # Make sure this template exists in your WhatsApp Manager!
    payload = {
        "messaging_product": "whatsapp",
        "to": to_mobile,
        "type": "template",
        "template": {
            "name": "reactivation_v1",  # <--- MUST MATCH YOUR TEMPLATE NAME EXACTLY
            "language": {"code": "en_US"}, 
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": patient_name # This fills {{1}} in the message
                        }
                    ]
                }
            ]
        }
    }
    
    print(f"📡 Sending signal to {to_mobile}...")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# ==============================================================================
# 🏁 MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print("------------------------------------------------")
    print("🚀 STARTING BLAST SEQUENCE...")
    print("------------------------------------------------")

    # Send the message
    result = send_reactivation_message(RECIPIENT_NUMBER, "Dr. Dua")

    # Print the result
    print("\n--- SERVER RESPONSE ---")
    print(json.dumps(result, indent=2))
    print("------------------------------------------------")

    # specific check for success
    if "messages" in result:
        print("\n✅ SUCCESS! The message has been sent.")
        print("👉 Check your WhatsApp now!")
    elif "error" in result:
        print("\n❌ FAILED. Please check the error message above.")
        print("👉 Common fixes: Check Token, Check Template Name, Check Payment Method.")