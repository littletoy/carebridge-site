import requests
import json

# --- DO NOT CHANGE THESE ---
API_KEY = "678e38df7ba55026938d87b3"
PROJECT_ID = "678e38de7ba55026938d879c"
PHONE = "919994581853"

# We will try the V2 endpoint with the proper Authorization Header
url = "https://backend.aisensy.com/campaign/t1/api/v2"

payload = {
    "apiKey": API_KEY,
    "campaignName": "carebridge_intro", # MUST MATCH YOUR LIVE API CAMPAIGN NAME
    "destination": PHONE,
    "userName": "Karunakaran",
    "source": "Python-Audit",
    "template": {
        "templateName": "carebridge_intro",
        "languageCode": "en",
        "bodyValues": []
    }
}

headers = {
    "Authorization": f"Bearer {API_KEY}",  # Many BSPs require Bearer tokens
    "x-api-key": API_KEY,                  # Some require this specific header
    "Content-Type": "application/json"
}

print(f"--- STARTING FULL AUDIT FOR PROJECT {PROJECT_ID} ---")
try:
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    print(f"RESULT: Status {response.status_code}")
    print(f"BODY: {response.text}")
except Exception as e:
    print(f"FATAL ERROR: {e}")