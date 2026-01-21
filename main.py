import gspread
import requests
import uvicorn
import os
import json
import base64
from fastapi import FastAPI, Request
from google.oauth2.service_account import Credentials
from datetime import datetime

app = FastAPI()

# --- CONFIGURATION ---
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY5NmM3NTUxZWM2YmRlN2JhNzc4OGJkMCIsIm5hbWUiOiJDYXJlQnJpZGdlIEhlYWx0aCIsImFwcE5hbWUiOiJBaVNlbnN5IiwiY2xpZW50SWQiOiI2OTZjNzU1MWVjNmJkZTdiYTc3ODhiY2IiLCJhY3RpdmVQbGFuIjoiUFJPX01PTlRITFkiLCJpYXQiOjE3Njg4OTY3ODl9.fjEYo4IKjTu8NmVUF9PEx-MsVCuxqGB9v_lFXIJQ4Zo"
AISENSY_URL = "https://backend.aisensy.com/campaign/t1/api/v2"
SHEET_NAME = "Building Lead Assessment Logic Schema"
OWNER_PHONE = "919080553616"

# --- CAMPAIGN NAMES ---
# Use the EXACT name from your approved screenshot
INTRO_CAMPAIGN = "carebridge_intro_live"

# ✅ IMPORTANT: Replace this with your APPROVED API campaign that asks for location
LOCATION_PROMPT_CAMPAIGN = "carebridge_location_request_live"

# Your website hosted video
VIDEO_URL = "https://carebridge-health.com/intro.mp4"

PHOTO_REQUEST_CAMPAIGN = "photo_request_live"
THANK_YOU_CAMPAIGN = "thank_you_live"
ADMIN_ALERT_CAMPAIGN = "admin_alert_live"

# --- SECURE GSHEET CONNECTION ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    # Logic to pull from Env Var (Base64 encoded to avoid quoting issues)
    encoded_creds = os.environ.get("GCP_CREDS_B64")
    if encoded_creds:
        creds_json = base64.b64decode(encoded_creds).decode("utf-8")
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        print("--- PROD MODE: CONNECTED VIA ENV VAR ---", flush=True)
    else:
        # Fallback for local testing
        creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
        print("--- DEV MODE: CONNECTED VIA FILE ---", flush=True)

    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
except Exception as e:
    print(f"--- [CRITICAL] GSHEET ERROR: {repr(e)} ---", flush=True)


def send_whatsapp(phone, campaign, params=None, media_url=None):
    """
    Sends a WhatsApp message via AiSensy API Campaign.
    params -> fills templateParams like {{1}}, {{2}}...
    """
    if params is None:
        params = []

    payload = {
        "apiKey": API_KEY,
        "campaignName": campaign,
        "destination": phone,
        "userName": "CareBridge Patient",
        "templateParams": params,
        "source": "Cloud_Backend",
    }

    # Video handling for intro
    if media_url:
        payload["media"] = {"url": media_url, "filename": "intro.mp4"}

    try:
        res = requests.post(AISENSY_URL, json=payload, timeout=10)
        print(f"--- [AISENSY] {campaign} Status: {res.status_code} ---", flush=True)
        return res
    except Exception as e:
        print(f"--- [ERROR] {repr(e)} ---", flush=True)
        return None


@app.api_route("/webhook", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "Webhook Active"}


@app.post("/webhook")
async def handle_whatsapp(request: Request):
    try:
        raw_data = await request.json()
        msg_content = raw_data.get("data", {}).get("message", {}).get("message_content", {})
        phone = raw_data.get("data", {}).get("message", {}).get("phone_number")
        text = str(msg_content.get("text", "")).strip().lower()
        media_url = msg_content.get("mediaUrl") or msg_content.get("url")

        if not phone:
            return {"status": "ignored"}

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Find lead in sheet
        try:
            cell = sheet.find(phone)
            row_idx = cell.row if cell else None
        except:
            row_idx = None

        # --- IMPROVED FLOW LOGIC ---
        if "start assessment" in text:
            # Check if they are ALREADY in the assessment flow
            if row_idx:
                current_status = sheet.cell(row_idx, 3).value
                if current_status != "New":
                    # They are already past the intro, so ask for location instead
                    send_whatsapp(phone, LOCATION_PROMPT_CAMPAIGN)
                    return {"status": "moved_to_location"}

            # If they are new, send the intro
            if not row_idx:
                sheet.append_row([phone, "Patient", "AWAITING_LOCATION", "N/A", "N/A", "New", "No Photo", timestamp])
            else:
                sheet.update_cell(row_idx, 3, "AWAITING_LOCATION")

            send_whatsapp(phone, INTRO_CAMPAIGN, params=["Patient"], media_url=VIDEO_URL)
            return {"status": "intro_sent"}

        if not row_idx:
            return {"status": "ignored"}

        current_status = sheet.cell(row_idx, 3).value

        # State 1: City Capture
        if current_status == "AWAITING_LOCATION":
            sheet.update_cell(row_idx, 4, text.title())
            sheet.update_cell(row_idx, 3, "AWAITING_PHOTO")
            send_whatsapp(phone, PHOTO_REQUEST_CAMPAIGN)
            return {"status": "awaiting_photo"}

        # State 2: Photo Append & Completion
        elif current_status == "AWAITING_PHOTO":
            if media_url:
                existing = sheet.cell(row_idx, 7).value or ""
                sheet.update_cell(row_idx, 7, f"{existing}, {media_url}".strip(", "))

            if "i've uploaded all photos" in text:
                sheet.update_cell(row_idx, 3, "COMPLETED")
                send_whatsapp(phone, THANK_YOU_CAMPAIGN)

                # Notify you
                send_whatsapp(OWNER_PHONE, ADMIN_ALERT_CAMPAIGN, params=[phone, "Assessment Completed"])
                return {"status": "finished"}

        return {"status": "processing"}

    except Exception as e:
        print(f"--- [CRITICAL] {repr(e)} ---", flush=True)
        return {"status": "error"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
