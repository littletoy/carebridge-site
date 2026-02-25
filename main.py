import gspread
import requests
import uvicorn
import os
import json
import time
import re
import random
from fastapi import FastAPI, Request
from google.oauth2.service_account import Credentials
from datetime import datetime

app = FastAPI()

# --- CONFIGURATION ---
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY5NmM3NTUxZWM2YmRlN2JhNzc4OGJkMCIsIm5hbWUiOiJDYXJlQnJpZGdlIEhlYWx0aCIsImFwcE5hbWUiOiJBaVNlbnN5IiwiY2xpZW50SWQiOiI2OTZjNzU1MWVjNmJkZTdiYTc3ODhiY2IiLCJhY3RpdmVQbGFuIjoiUFJPX01PTlRITFkiLCJpYXQiOjE3Njg4OTY3ODl9.fjEYo4IKjTu8NmVUF9PEx-MsVCuxqGB9v_lFXIJQ4Zo"
AISENSY_URL = "https://backend.aisensy.com/campaign/t1/api/v2"

# *** UPDATE: NEW SHEET NAME ***
SHEET_NAME = "CareBridge Leads 2026"
OWNER_PHONE = "919080553616"

# --- CAMPAIGN NAMES ---
ASK_NAME_CAMPAIGN = "carebridge_ask_name_new"
LOCATION_PROMPT_CAMPAIGN = "carebridge_location_request_live"
PHOTO_REQUEST_CAMPAIGN = "carebridge_location_nudge"
THANK_YOU_CAMPAIGN = "carebridge_thank_you_live"
ADMIN_ALERT_CAMPAIGN = "admin_alert_live"

# --- GOOGLE SHEET CONNECTION ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
sheet = None 

def get_sheet():
    global sheet
    if sheet: return sheet
    try:
        if os.path.exists("service_account.json"):
            creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
            client = gspread.authorize(creds)
            sheet = client.open(SHEET_NAME).sheet1
            print(f"--- SUCCESS: Connected to '{SHEET_NAME}' ---", flush=True)
            return sheet
        else:
            print("--- [CRITICAL] service_account.json NOT FOUND ---", flush=True)
            return None
    except Exception as e:
        print(f"--- [CONNECTION ERROR] {e} ---", flush=True)
        return None

def clean_phone_for_whatsapp(phone_raw):
    if not phone_raw: return ""
    clean_digits = re.sub(r'\D', '', str(phone_raw))
    if clean_digits: return f"+{clean_digits}"
    return ""

def send_whatsapp(phone, campaign, params=None):
    if params is None: params = []
    final_phone = clean_phone_for_whatsapp(phone)
    payload = {
        "apiKey": API_KEY,
        "campaignName": campaign,
        "destination": final_phone,
        "userName": "CareBridge User",
        "templateParams": params,
        "source": "Cloud_Backend",
    }
    try:
        requests.post(AISENSY_URL, json=payload, timeout=5)
        print(f"AiSensy Sent ({campaign}) to {final_phone}", flush=True)
    except Exception as e:
        print(f"--- [ERROR] Sending Message Failed: {e} ---", flush=True)

@app.post("/webhook")
async def handle_whatsapp(request: Request):
    sheet_instance = get_sheet()
    if not sheet_instance: return {"status": "error_no_db"}

    try:
        raw_data = await request.json()
        data_node = raw_data.get("data", {})
        message_node = data_node.get("message", {})
        msg_content = message_node.get("message_content", {}) or {}
        
        phone = str(message_node.get("phone_number") or "").strip()
        text_body = str(msg_content.get("text") or "").strip().lower()
        media_url = msg_content.get("mediaUrl") or msg_content.get("url")

        if not phone: return {"status": "ignored_no_phone"}

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # --- FIND USER ---
        row_idx = None
        current_status = None
        
        try:
            # Find phone in Column B (Index 2 in gspread)
            cells = sheet_instance.findall(phone)
            if cells:
                last_cell = sorted(cells, key=lambda c: c.row)[-1]
                row_idx = last_cell.row
                # Status is in Column G (Index 7)
                current_status = sheet_instance.cell(row_idx, 7).value 
                print(f"--- FOUND USER {phone} at ROW {row_idx} (Status: {current_status}) ---", flush=True)
        except:
            pass 

        # --- META TRIGGER LOGIC ---
        is_meta_lead = False
        condition_detected = "General"

        if "hair transplant quote" in text_body:
            is_meta_lead = True
            condition_detected = "Hair"
        elif "knee" in text_body or "joint" in text_body:
            is_meta_lead = True
            condition_detected = "Knee"
        elif "cancer" in text_body or "surgery" in text_body:
            is_meta_lead = True
            condition_detected = "Cancer"
        elif "start assessment" in text_body:
            is_meta_lead = True

        # 1. NEW LEAD (Triggered by Button OR First Message)
        if is_meta_lead or (not row_idx and not media_url):
            print(f"--- NEW LEAD DETECTED: {condition_detected} ---", flush=True)
            
            # Create Row: [Timestamp, Phone, Name, Location, Condition, Files, Status]
            sheet_instance.append_row([
                timestamp,          # A
                phone,              # B
                "",                 # C (Name pending)
                "",                 # D (Location pending)
                condition_detected, # E (Auto-detected)
                "",                 # F (Files pending)
                "AWAITING_NAME"     # G (Status)
            ])
            
            send_whatsapp(phone, ASK_NAME_CAMPAIGN)
            return {"status": "lead_created"}

        # 2. SAVE NAME
        elif row_idx and current_status == "AWAITING_NAME" and text_body:
            clean_name = text_body.title()
            if len(clean_name) > 2:
                # Save Name to Column C (3)
                sheet_instance.update_cell(row_idx, 3, clean_name)
                # Update Status to AWAITING_LOCATION in Column G (7)
                sheet_instance.update_cell(row_idx, 7, "AWAITING_LOCATION")
                send_whatsapp(phone, LOCATION_PROMPT_CAMPAIGN)
                return {"status": "name_saved"}

        # 3. SAVE LOCATION
        elif row_idx and current_status == "AWAITING_LOCATION" and text_body:
            # Save Location to Column D (4)
            sheet_instance.update_cell(row_idx, 4, text_body.title())
            # Update Status to AWAITING_PHOTO in Column G (7)
            sheet_instance.update_cell(row_idx, 7, "AWAITING_PHOTO")
            send_whatsapp(phone, PHOTO_REQUEST_CAMPAIGN)
            return {"status": "location_saved"}

        # 4. SAVE PHOTOS
        elif media_url:
            print(f"--- PHOTO RECEIVED FROM {phone} ---", flush=True)
            
            # If new user sent photo immediately
            if not row_idx:
                sheet_instance.append_row([
                    timestamp, phone, "Unknown", "Unknown", "Unknown", media_url, "PHOTO_RECEIVED"
                ])
                send_whatsapp(phone, ASK_NAME_CAMPAIGN)
                return {"status": "new_user_photo_saved"}

            # If user exists, append to Col F (6)
            existing_links = sheet_instance.cell(row_idx, 6).value 
            new_links = f"{existing_links}, {media_url}" if existing_links else media_url
            sheet_instance.update_cell(row_idx, 6, new_links)
            
            # Complete Flow
            if current_status != "COMPLETED":
                sheet_instance.update_cell(row_idx, 7, "COMPLETED")
                user_name = sheet_instance.cell(row_idx, 3).value or "Patient"
                send_whatsapp(phone, THANK_YOU_CAMPAIGN)
                send_whatsapp(OWNER_PHONE, ADMIN_ALERT_CAMPAIGN, params=[user_name, phone])

            return {"status": "photo_appended"}

        return {"status": "ignored"}

    except Exception as e:
        print(f"--- [ERROR] {e} ---", flush=True)
        return {"status": "error"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))