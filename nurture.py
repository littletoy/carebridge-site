import gspread
import requests
import os
import json
import base64
import re
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY5NmM3NTUxZWM2YmRlN2JhNzc4OGJkMCIsIm5hbWUiOiJDYXJlQnJpZGdlIEhlYWx0aCIsImFwcE5hbWUiOiJBaVNlbnN5IiwiY2xpZW50SWQiOiI2OTZjNzU1MWVjNmJkZTdiYTc3ODhiY2IiLCJhY3RpdmVQbGFuIjoiUFJPX01PTlRITFkiLCJpYXQiOjE3Njg4OTY3ODl9.fjEYo4IKjTu8NmVUF9PEx-MsVCuxqGB9v_lFXIJQ4Zo"
AISENSY_URL = "https://backend.aisensy.com/campaign/t1/api/v2"
SHEET_NAME = "Building Lead Assessment Logic Schema"

# --- CAMPAIGNS ---
# These must match the exact Campaign Names in your AiSensy Dashboard
CAMPAIGN_START = "carebridge_ask_name_new"
CAMPAIGN_LOCATION = "carebridge_location_request_live"
CAMPAIGN_PHOTO = "carebridge_location_nudge"

def get_sheet_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        # Try Prod Env Var first, then Local File
        encoded_creds = os.environ.get("GCP_CREDS_B64")
        if encoded_creds:
            creds_json = base64.b64decode(encoded_creds).decode("utf-8")
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        else:
            creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"Auth Failed: {e}")
        return None

def clean_phone_number(phone_raw):
    """Ensures phone number has a + prefix."""
    if not phone_raw: return ""
    
    # 1. Remove non-numeric characters (spaces, dashes, parens)
    clean_digits = re.sub(r'\D', '', str(phone_raw))
    
    # 2. Add the + prefix if we have digits
    if clean_digits:
        return f"+{clean_digits}"
    return ""

def send_template(phone, campaign_name):
    # This now produces +919080553616
    clean_phone = clean_phone_number(phone)
    
    if not clean_phone:
        print(f" -> SKIP: Invalid/Empty Phone '{phone}'")
        return False

    payload = {
        "apiKey": API_KEY,
        "campaignName": campaign_name,
        "destination": clean_phone,     # Corrected format with +
        "userName": "CareBridge User",  # Required by AiSensy
        "source": "Nurture_Script"
    }

    try:
        r = requests.post(AISENSY_URL, json=payload, timeout=10)
        
        if r.status_code == 200:
            print(f" -> SUCCESS: Sent {campaign_name} to {clean_phone}", flush=True)
            return True
        else:
            # Print the detailed error from AiSensy if it fails
            print(f" -> FAILED: {campaign_name} to {clean_phone} | Status: {r.status_code} | Msg: {r.text}", flush=True)
            return False
            
    except Exception as e:
        print(f" -> NETWORK ERROR to {clean_phone}: {e}", flush=True)
        return False

def run_smart_nurture():
    print("--- STARTING SMART NURTURE ---", flush=True)
    gc = get_sheet_client()
    if not gc: return

    try:
        sheet = gc.open(SHEET_NAME).sheet1
        rows = sheet.get_all_values()
        
        # Skip header row
        data_rows = rows[1:]
        now = datetime.now()
        updates_made = False

        for i, row in enumerate(data_rows):
            sheet_row_index = i + 2
            
            # Safeguard against empty rows
            if len(row) < 11: continue

            phone = row[0]
            status = row[2]  # Col C (Status)
            nudge_status = row[5] # Col F (Nudge Status)
            timestamp_str = row[10] # Col K (Timestamp)

            # Filter: Only process users who haven't been nudged yet
            if nudge_status != "New": continue

            try:
                lead_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                hours_passed = (now - lead_time).total_seconds() / 3600
                
                # Logic: Nudge if user is stuck for more than 1 hour but less than 48 hours
                if 1 < hours_passed < 48:
                    
                    campaign_to_send = None
                    new_status = None 
                    
                    # Case 1: Stuck at Name -> Send Start Template & Reset Status
                    if status == "Pending Name" or status == "AWAITING_NAME":
                        print(f"Stuck at Name: {phone}")
                        campaign_to_send = CAMPAIGN_START
                        new_status = "AWAITING_NAME"

                    # Case 2: Stuck at Location -> Send Location Template
                    elif status == "AWAITING_LOCATION":
                        print(f"Stuck at Location: {phone}")
                        campaign_to_send = CAMPAIGN_LOCATION

                    # Case 3: Stuck at Photo -> Send Photo Template
                    elif status == "AWAITING_PHOTO":
                        print(f"Stuck at Photo: {phone}")
                        campaign_to_send = CAMPAIGN_PHOTO

                    # EXECUTE SEND
                    if campaign_to_send:
                        success = send_template(phone, campaign_to_send)
                        
                        if success:
                            # 1. Update Status (Only if needed, e.g. Resetting Name)
                            if new_status:
                                sheet.update_cell(sheet_row_index, 3, new_status)
                            
                            # 2. Mark as Nudged so we don't spam them
                            sheet.update_cell(sheet_row_index, 6, "Nudged")
                            updates_made = True

            except ValueError:
                # Skip rows with bad timestamp formats
                continue

        if not updates_made:
            print("No leads needed nurturing.", flush=True)

    except Exception as e:
        print(f"Critical Error: {e}", flush=True)

if __name__ == "__main__":
    run_smart_nurture()