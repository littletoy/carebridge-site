import requests
import json

# --- HARD DATA ---
API_KEY = "678e38df7ba55026938d87b3"
PROJECT_ID = "678e38de7ba55026938d879c" 
PHONE_NUMBER = "919994581853"

# USE THE T1 DIRECT ENDPOINT
url = "https://backend.aisensy.com/campaign/t1/api/v2"

payload = {
    "apiKey": API_KEY,
    "campaignName": "carebridge_intro", 
    "destination": PHONE_NUMBER,
    "userName": "Karunakaran",
    "source": "Python-Backend",
    "template": {
        "templateName": "carebridge_intro",
        "languageCode": "en",
        "bodyValues": [] 
    }
}

headers = {
    "Content-Type": "application/json"
}

print(f"DEBUG: Attempting Direct T1 Bypass to {PHONE_NUMBER}...")

response = requests.post(url, data=json.dumps(payload), headers=headers)

print(f"Status Code: {response.status_code}")
print(f"Response Body: {response.text}")