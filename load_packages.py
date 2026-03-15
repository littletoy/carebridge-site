import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import math

# 1. Authenticate
if not firebase_admin._apps:
    print("Authenticating with Firebase...")
    cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)

db = firestore.client()

def clean_data(val):
    # Strip NaNs and empty floats so Firestore doesn't choke
    if pd.isna(val) or (isinstance(val, float) and math.isnan(val)):
        return None
    return str(val).strip()

def run_package_pipeline():
    print("Loading Package Pricing directly from Doctor dump.xlsx (Sheet 2)...")
    
    try:
        # sheet_name=1 tells Pandas to completely ignore the doctors and only read the second tab
        df_packages = pd.read_excel('Doctor dump.xlsx', sheet_name=1) 
    except FileNotFoundError:
        print("[!] Critical Error: 'Doctor dump.xlsx' not found in this directory.")
        return
    except Exception as e:
        print(f"[!] Critical Error loading Excel: {e}")
        return

    # Clean header names
    df_packages.columns = df_packages.columns.astype(str).str.strip()
    
    success_count = 0
    print("Pushing packages to Firestore...")
    
    for index, row in df_packages.iterrows():
        payload = {}
        
        # Dynamically build the payload based on whatever columns exist in your sheet
        for col in df_packages.columns:
            val = clean_data(row[col])
            if val is not None and val != "":
                # Convert price strings to numbers if possible, otherwise leave as string
                if 'price' in col.lower() or 'cost' in col.lower() or 'amount' in col.lower():
                    try:
                        cleaned_val = str(val).replace(',', '').replace('Rs.', '').replace('₹', '').replace('INR', '').strip()
                        payload[col] = float(cleaned_val)
                    except ValueError:
                        payload[col] = val
                else:
                    payload[col] = val
                
        # Skip completely empty rows
        if not payload:
            continue
            
        try:
            # Let Firestore auto-generate the Document ID for packages
            db.collection('packages').add(payload)
            success_count += 1
        except Exception as e:
            print(f"[{index}] Error pushing package: {e}")

    print(f"\nPipeline Complete. {success_count} pricing records pushed to production Firestore.")

if __name__ == "__main__":
    run_package_pipeline()