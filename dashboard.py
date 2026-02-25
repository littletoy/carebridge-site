import streamlit as st
import gspread
import pandas as pd
import requests
import json
import base64
import os
import time
from google.oauth2.service_account import Credentials

# --- REAL DOCTOR IDENTITIES ---
DOC_A_FULL_NAME = "Mayank Singh, MBBS, MS, MCh, FISHRS | Hair Surgeon"
DOC_B_FULL_NAME = "Kapil Dua, MBBS, MS, FISHRS | Hair Surgeon"

# --- SECURITY CONFIG ---
# Passwords updated to match the new names
CREDENTIALS = {
    DOC_A_FULL_NAME: "mayank@890", 
    DOC_B_FULL_NAME: "kapil@555"
}

# --- CONFIGURATION ---
SHEET_NAME = "Building Lead Assessment Logic Schema"
AISENSY_URL = "https://backend.aisensy.com/campaign/t1/api/v2"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY5NmM3NTUxZWM2YmRlN2JhNzc4OGJkMCIsIm5hbWUiOiJDYXJlQnJpZGdlIEhlYWx0aCIsImFwcE5hbWUiOiJBaVNlbnN5IiwiY2xpZW50SWQiOiI2OTZjNzU1MWVjNmJkZTdiYTc3ODhiY2IiLCJhY3RpdmVQbGFuIjoiUFJPX01PTlRITFkiLCJpYXQiOjE3Njg4OTY3ODl9.fjEYo4IKjTu8NmVUF9PEx-MsVCuxqGB9v_lFXIJQ4Zo"
RESULT_CAMPAIGN_NAME = "carebridge_doctor_quote" 

# --- GOOGLE CONNECT ---
@st.cache_resource
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if "GCP_CREDS_B64" in os.environ:
        creds_json = base64.b64decode(os.environ["GCP_CREDS_B64"]).decode("utf-8")
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    elif os.path.exists("service_account.json"):
        creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
    else:
        st.error("No Credentials Found.")
        return None
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def send_result_whatsapp(phone, name, grafts, cost, doctor_title):
    payload = {
        "apiKey": API_KEY,
        "campaignName": RESULT_CAMPAIGN_NAME,
        "destination": phone,
        "userName": name,
        # WE PASS THE FULL DOCTOR TITLE HERE SO THE PATIENT SEES IT
        "templateParams": [name, doctor_title, str(grafts), str(cost)],
        "source": "Doctor_Dashboard"
    }
    try:
        res = requests.post(AISENSY_URL, json=payload, timeout=10)
        return res.status_code == 200
    except:
        return False

# --- UI START ---
st.set_page_config(page_title="CareBridge Medical Board", layout="wide")
st.title("🏥 CareBridge Doctor Portal")

# 1. LOGIN SCREEN
with st.sidebar:
    st.header("🔐 Secure Login")
    doctor_role = st.radio("Select Profile:", list(CREDENTIALS.keys()))
    password = st.text_input("Enter Access Code:", type="password")
    
    login_success = False
    if password == CREDENTIALS[doctor_role]:
        # Just show the First Name in the welcome message
        short_name = doctor_role.split(',')[0] 
        st.success(f"Welcome, Dr. {short_name}!")
        login_success = True
    elif password:
        st.error("Incorrect Access Code")

if not login_success:
    st.info("👈 Please select your profile and enter your access code to view patients.")
    st.stop()  # Stop here if not logged in

# 2. MAIN DASHBOARD (Only runs if logged in)
# LOGIC MAP:
# Dr. Mayank Singh -> Uses DocA Columns (12, 13, 14)
# Dr. Kapil Dua    -> Uses DocB Columns (15, 16, 17)

if doctor_role == DOC_A_FULL_NAME:
    my_status_col = "DocA_Status"
    col_indices = (12, 13, 14) 
else:
    my_status_col = "DocB_Status"
    col_indices = (15, 16, 17) 

# The 'public_title' sent to the patient is the full string from the dropdown
public_title = doctor_role 

sheet = get_sheet()

if sheet:
    raw_data = sheet.get_all_records()
    df = pd.DataFrame(raw_data)

    if "Status" in df.columns:
        # FILTER: Completed Assessments where THIS doctor hasn't replied yet
        pending_patients = df[
            (df["Status"] == "COMPLETED") & 
            (df[my_status_col] != "Done")
        ]
        
        # MASKING FOR PRIVACY
        pending_patients["Display_Label"] = pending_patients["Name"] + " (" + pending_patients["Location"] + ")"
        
        st.metric(f"Pending Reviews for Dr. {doctor_role.split(',')[0]}", len(pending_patients))
        
        st.divider()

        if not pending_patients.empty:
            selection = st.selectbox("Select Patient to Review:", pending_patients["Display_Label"].unique())
            
            if selection:
                row_data = pending_patients[pending_patients["Display_Label"] == selection].iloc[0]
                hidden_phone = str(row_data["Phone"]) 
                
                # PHOTO GALLERY
                c1, c2, c3 = st.columns(3)
                def show(col, key, label):
                    val = row_data.get(key)
                    if val and str(val).startswith("http"):
                        col.image(val, caption=label, use_container_width=True)
                    else:
                        col.info(f"No {label}")
                
                show(c1, "Photo1", "Front")
                show(c2, "Photo2", "Top")
                show(c3, "Photo3", "Back")
                
                st.write(f"**Patient:** {row_data['Name']} | **Location:** {row_data['Location']}")
                st.divider()

                # ASSESSMENT FORM
                with st.form("doc_review"):
                    st.subheader(f"✍️ Assessment")
                    st.caption(f"Signing as: **{public_title}**") # Shows who is signing
                    
                    g_in = st.text_input("Graft Recommendation", placeholder="e.g. 2500")
                    c_in = st.text_input("Estimated Cost (INR)", placeholder="e.g. 120000")
                    
                    submitted = st.form_submit_button("✅ Send Secure Estimate")
                    
                    if submitted:
                        if not g_in or not c_in:
                            st.error("Please fill in both fields.")
                        else:
                            with st.spinner(f"Sending Quote to Patient..."):
                                # This sends the WhatsApp with the REAL NAME
                                sent = send_result_whatsapp(hidden_phone, row_data['Name'], g_in, c_in, public_title)
                                
                                if sent:
                                    st.success("Sent Successfully!")
                                    
                                    # UPDATE GOOGLE SHEET
                                    # We find the row and update the specific columns for this doctor
                                    cell = sheet.find(hidden_phone)
                                    r = cell.row
                                    
                                    sheet.update_cell(r, col_indices[0], g_in) # Grafts
                                    sheet.update_cell(r, col_indices[1], c_in) # Cost
                                    sheet.update_cell(r, col_indices[2], "Done") # Status
                                    
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Failed to send WhatsApp. Please try again.")
        else:
            st.success("✅ All Caught Up! No pending patients.")
    else:
        st.error("Sheet Headers Incorrect. Expected 'Status' column.")