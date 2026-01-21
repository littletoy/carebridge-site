import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from datetime import datetime, timedelta

# --- CONFIG ---
API_KEY = "678e38df7ba55026938d87b3"
CAMPAIGN_NAME = "Carebridge_Followup_V1" # Create this template in AiSensy
SHEET_NAME = "Building Lead Assessment Logic Schema"

def run_nurture():
    # 1. Access Sheet
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    
    records = sheet.get_all_records()
    now = datetime.now()

    for i, row in enumerate(records):
        status = row.get("Status")
        timestamp_str = row.get("Timestamp") # Format: 2026-01-19 22:00:00
        phone = row.get("Phone")

        if status == "New" or status == "AWAITING_LOCATION":
            lead_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            
            # Logic: If lead is > 4 hours old but < 24 hours old
            if now - lead_time > timedelta(hours=4) and now - lead_time < timedelta(hours=24):
                print(f"NUDGING: {phone} is stuck. Sending follow-up...")
                
                # Trigger AiSensy Template
                payload = {
                    "apiKey": API_KEY,
                    "campaignName": CAMPAIGN_NAME,
                    "destination": str(phone),
                    "userName": "Patient",
                    "templateParams": []
                }
                requests.post("https://backend.aisensy.com/campaign/t1/api/v2", json=payload)
                
                # Update status so we don't nudge them twice
                sheet.update_cell(i + 2, 6, "Nudged") 

if __name__ == "__main__":
    run_nurture()