import gspread
import requests
import uvicorn
import os
import json
from fastapi import FastAPI, Request
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = FastAPI()

# --- CONFIGURATION (VERIFY THESE NAMES IN AISENSY DASHBOARD) ---
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY5NmM3NTUxZWM2YmRlN2JhNzc4OGJkMCIsIm5hbWUiOiJDYXJlQnJpZGdlIEhlYWx0aCIsImFwcE5hbWUiOiJBaVNlbnN5IiwiY2xpZW50SWQiOiI2OTZjNzU1MWVjNmJkZTdiYTc3ODhiY2IiLCJhY3RpdmVQbGFuIjoiUFJPX01PTlRITFkiLCJpYXQiOjE3Njg4OTY3ODl9.fjEYo4IKjTu8NmVUF9PEx-MsVCuxqGB9v_lFXIJQ4Zo"
AISENSY_URL = "https://backend.aisensy.com/campaign/t1/api/v2"
SHEET_NAME = "Building Lead Assessment Logic Schema"
OWNER_PHONE = "919080553616" 

# --- GOOGLE SHEETS CONNECTION ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)
    sheet = spreadsheet.sheet1
    print("--- SUCCESS: GSHEET CONNECTED ---", flush=True)
except Exception as e:
    print(f"--- [CRITICAL] GSHEET ERROR: {repr(e)} ---", flush=True)

def send_whatsapp(phone, campaign, params=[], media_url=None):
    """Hardened sender with safe name and error logging"""
    payload = {
        "apiKey": API_KEY,
        "campaignName": campaign,
        "destination": phone,
        "userName": "CareBridge Patient",
        "templateParams": params,
        "source": "Cloud_Backend"
    }
    # Add media if it's a VIDEO template
    if media_url:
        payload["media"] = {"url": media_url, "filename": "intro_video.mp4"}
        
    try:
        res = requests.post(AISENSY_URL, json=payload, timeout=10)
        print(f"--- [AISENSY RESPONSE] Status: {res.status_code} | Body: {res.text} ---", flush=True)
        return res
    except Exception as e:
        print(f"--- [AISENSY ERROR] {repr(e)} ---", flush=True)
        return None

@app.api_route("/webhook", methods=["GET", "HEAD"])
async def verify_and_head():
    """Handles health checks from AiSensy and Uptime monitors"""
    return {"status": "Webhook Active"}

@app.post("/webhook")
async def handle_whatsapp(request: Request):
    try:
        raw_data = await request.json()
        
        # 1. Extraction Logic (Matches the AiSensy JSON structure we identified)
        data_layer = raw_data.get("data", {})
        message_layer = data_layer.get("message", {})
        content_layer = message_layer.get("message_content", {})

        phone = message_layer.get("phone_number")
        text = str(content_layer.get("text", "")).strip().lower()
        
        # AiSensy sends media inside message_content
        media_url = content_layer.get("mediaUrl") or content_layer.get("url")

        print(f"DEBUG: Extracted Text: '{text}' | Phone: '{phone}' | Media: {media_url}", flush=True)

        if not phone:
            return {"status": "ignored"}

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 2. Find User in Sheet
        try:
            cell = sheet.find(phone)
            row_idx = cell.row if cell else None
        except gspread.exceptions.CellNotFound:
            row_idx = None

        # --- STATE MACHINE LOGIC ---

        # TRIGGER: Reset or Start
        if "start assessment" in text:
            if not row_idx:
                # Column Order: Phone, Role, Status, City, Notes, LeadStatus, Photo, Timestamp, Workflow
                new_row = [phone, "Patient", "AWAITING_LOCATION", "N/A", "N/A", "New", "No Photo", timestamp, "Pending"]
                sheet.append_row(new_row)
                print(f"DEBUG: Created new lead: {phone}", flush=True)
            else:
                sheet.update_cell(row_idx, 3, "AWAITING_LOCATION")
                sheet.update_cell(row_idx, 8, timestamp)
                print(f"DEBUG: Reset existing lead: {phone}", flush=True)
            
            send_whatsapp(phone, "carebridge_intro")
            return {"status": "flow_initiated"}

        if not row_idx:
            return {"status": "ignored", "reason": "user_not_in_system"}

        # Get Current Status from Column C
        current_status = sheet.cell(row_idx, 3).value

        # STATE 1: Capturing Location (City)
        if current_status == "AWAITING_LOCATION":
            sheet.update_cell(row_idx, 4, text.title())     # Column D
            sheet.update_cell(row_idx, 3, "AWAITING_PHOTO") # Column C
            send_whatsapp(phone, "Carebridge_Photo_Request")
            return {"status": "location_recorded"}

        # STATE 2: Capturing Scalp Photo
        elif current_status == "AWAITING_PHOTO" and media_url:
            sheet.update_cell(row_idx, 7, media_url)        # Column G
            sheet.update_cell(row_idx, 6, "Photo Received") # Column F
            sheet.update_cell(row_idx, 3, "COMPLETED")      # Column C
            
            send_whatsapp(phone, "carebridge_thank_you")
            # Admin Notification
            send_whatsapp(OWNER_PHONE, "carebridge_admin_alert", [phone])
            return {"status": "triage_completed"}

        return {"status": "no_state_match"}

    except Exception as e:
        print(f"--- [CRITICAL ERROR] {repr(e)} ---", flush=True)
        return {"status": "error"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
