import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import re
import math

# 1. Initialize Firebase using your exact new key
print("Authenticating with Firebase...")
cred = credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# 2. Define the Base URL for your GCP Bucket
# This matches the folder you just created in Firebase Storage
BASE_IMAGE_URL = "https://storage.googleapis.com/carebridge-prod-2026-17660.firebasestorage.app/doctor_profiles/"

def sanitize_filename(name):
    # This MUST match the exact logic from your scraping script
    return re.sub(r'[^a-zA-Z0-9_\-]', '', str(name).replace(' ', '_'))

def clean_data(val):
    # Firestore throws fatal errors if you try to upload NaN or float-type missing values.
    if pd.isna(val) or (isinstance(val, float) and math.isnan(val)):
        return ""
    return str(val).strip()

def run_pipeline():
    print("Loading Doctor Dump...")
    # Load the doctors data
    df_docs = pd.read_excel('Doctor dump.xlsx', sheet_name='Doctor Dump')
    df_docs.columns = df_docs.columns.str.strip()
    
    # Optional: Load Packages data if you want to merge it. 
    # (Commented out until we map the exact column names linking Doctors to Packages)
    # df_packages = pd.read_csv('Package detials .csv')

    success_count = 0
    
    print("Pushing records to Firestore...")
    for index, row in df_docs.iterrows():
        doc_name = clean_data(row.get('Doctor Name'))
        
        if not doc_name:
            continue
            
        # Generate the exact public URL for this specific doctor
        safe_name = sanitize_filename(doc_name)
        image_url = f"{BASE_IMAGE_URL}{safe_name}.jpg"

        # Build the payload map. Update these row.get() keys to perfectly match your Excel headers.
        doc_payload = {
            "name": doc_name,
            "specialty": clean_data(row.get('Speciality')),
            "hospital": clean_data(row.get('Hospital')),
            "experience_years": clean_data(row.get('Experience')),
            "profile_url": clean_data(row.get('doctor_profile_url')),
            "image_url": image_url, # The dynamically generated GCP URL
            "is_active": True
        }

        try:
            # Push to the 'doctors' collection in Firestore.
            # Using the safe_name as the Document ID so you can easily query it later.
            db.collection('doctors').document(safe_name).set(doc_payload)
            print(f"[{index}] Successfully pushed {doc_name} to Firestore")
            success_count += 1
        except Exception as e:
            print(f"[{index}] Error pushing {doc_name}: {e}")

    print(f"\nPipeline Complete. {success_count} records pushed to production Firestore.")

if __name__ == "__main__":
    run_pipeline()