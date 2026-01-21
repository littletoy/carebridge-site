import requests
import json

# --- CONFIGURATION ---
# DOUBLE CHECK: Go to Manage > API Key. Ensure this string is EXACT.
API_KEY = "678e38df7ba55026938d87b3"
PROJECT_ID = "678e38de7ba55026938d879c" 
PHONE_NUMBER = "919994581853"

# Official V2 Campaign URL
url = f"https://backend.aisensy.com/campaign/external/v1/projects/{PROJECT_ID}/template"

payload = {
    "apiKey": API_KEY, # Keep it in the body as well, just in case
    "campaignName": "carebridge_intro", 
    "destination": PHONE_NUMBER,
    "userName": "Karunakaran",
    "template": {
        "templateName": "carebridge_intro",
        "languageCode": "en",
        "bodyValues": [] 
    }
}

headers = {
    "Authorization": f"Bearer {API_KEY}", # Adding standard Bearer token header
    "Content-Type": "application/json",
    "Accept": "application/json"
}

print(f"DEBUG: Triggering Outbound Auth Test...")
response = requests.post(url, data=json.dumps(payload), headers=headers)

print(f"Status Code: {response.status_code}")
print(f"Response Body: {response.text}")