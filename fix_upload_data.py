"""
============================================================
FIX SCRIPT: Re-upload Doctors + Upload Packages to Firestore
============================================================
This script:
  1. Reads Doctor_dump.xlsx (both sheets)
  2. Updates every doctor doc with the CORRECT fields:
     - DeptName (from Excel, e.g. "CARDIOLOGY MHB")
     - specialty (cleaned department name, e.g. "CARDIOLOGY")
     - designation, field_expertise (from Excel)
     - hospital_id (mapped from DeptName suffix: MHB → manipal_blr)
  3. Creates 'packages' collection with all 270 packages
     - Each package gets a hospital_id = "manipal_blr" (default)

Usage:
  1. Put Doctor_dump.xlsx in the same folder
  2. Set GOOGLE_CREDENTIALS env var
  3. Run: python fix_upload_data.py
============================================================
"""

import os
import re
import json
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore

# --- Init Firebase ---
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS")
if GOOGLE_CREDENTIALS_JSON:
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    cred = credentials.Certificate(creds_dict)
    firebase_admin.initialize_app(cred)
else:
    firebase_admin.initialize_app()

db = firestore.client()

# ============================================================
# HOSPITAL CODE MAPPING
# ============================================================
# DeptName suffix → hospital_id
# Based on Manipal Hospital location codes found in your data:
#   MHB = Manipal Hospital Bangalore (Old Airport Road)  — 322 doctors
#   MHW = Manipal Hospital Whitefield (Bangalore)        —  23 doctors
#   MCI = Manipal Comprehensive (Bangalore)              —  44 doctors
#   MKB = Manipal Kasturba (Bangalore)                   —   8 doctors
#   MSB = Manipal Sarjapur (Bangalore)                   —   9 doctors
#   MVB = Manipal Varthur (Bangalore)                    —   5 doctors
#   MMH = Manipal Millers Road (Bangalore)               —   5 doctors
#   MHM = Manipal Hospital Mysore                        —   4 doctors
#   MCB = Manipal (Bangalore variant)                    —   2 doctors
#   MHE / MHY / MHH = Other Manipal branches             —   few
#   MYB = Manipal Yeshwanthpur (Bangalore)

HOSPITAL_CODE_MAP = {
    # Bangalore locations (all map to manipal_blr for now)
    "MHB": "manipal_blr",
    "MHW": "manipal_blr",   # Whitefield — same city
    "MCI": "manipal_blr",   # Comprehensive — same city
    "MKB": "manipal_blr",   # Kasturba — same city
    "MSB": "manipal_blr",   # Sarjapur — same city
    "MVB": "manipal_blr",   # Varthur — same city
    "MMH": "manipal_blr",   # Millers Road — same city
    "MCB": "manipal_blr",   # Another Bangalore branch
    "MYB": "manipal_blr",   # Yeshwanthpur — same city
    "MBB": "manipal_blr",   # Bangalore variant

    # Other cities (update these when you add those hospitals)
    "MHM": "manipal_blr",   # Mysore — map to BLR for now
    "MHH": "manipal_blr",   # Another branch
    "MHE": "manipal_blr",   # Another branch
    "MHY": "manipal_blr",   # Hyderabad? — map to BLR for now
    "MHN": "manipal_blr",   # Another branch
    "MMY": "manipal_blr",   # Mysore variant
    "MCID": "manipal_blr",  # MCI variant with D
    "MIC": "manipal_blr",   # variant
}


def extract_hospital_code(dept_name):
    """
    Extract hospital code from DeptName.
    Examples:
        "CARDIOLOGY MHB"           → "MHB"
        "CARDIOLOGYMHB"            → "MHB"
        "ONCOLOGYMEDICALMHB"       → "MHB"
        "GASTROENTEROLOGY MEDICAL MHB" → "MHB"
        "Cardiology (Electro Physiologist) MHB" → "MHB"
    """
    if not dept_name:
        return "MHB"  # default

    dept = str(dept_name).strip()

    # Try: last word/token is the code
    parts = dept.split()
    if parts:
        last = parts[-1].strip("()")
        if last.upper() in HOSPITAL_CODE_MAP:
            return last.upper()

    # Try: last 3 characters (for concatenated names like "CARDIOLOGYMHB")
    for length in [4, 3]:
        if len(dept) >= length:
            suffix = dept[-length:].upper()
            if suffix in HOSPITAL_CODE_MAP:
                return suffix

    # Try: scan for any known code
    dept_upper = dept.upper()
    for code in sorted(HOSPITAL_CODE_MAP.keys(), key=len, reverse=True):
        if code in dept_upper:
            return code

    return "MHB"  # default to Bangalore


def clean_department_name(dept_name):
    """
    Extract the clean department name (without hospital code).
    "CARDIOLOGY MHB"           → "CARDIOLOGY"
    "CARDIOLOGYMHB"            → "CARDIOLOGY"
    "ONCOLOGYMEDICALMHB"       → "ONCOLOGY MEDICAL"
    "GASTROENTEROLOGY SURGICAL MCB" → "GASTROENTEROLOGY SURGICAL"
    "Cardiology (Electro Physiologist) MHB" → "CARDIOLOGY"
    """
    if not dept_name:
        return ""

    dept = str(dept_name).strip().upper()

    # Remove hospital codes from end
    for code in sorted(HOSPITAL_CODE_MAP.keys(), key=len, reverse=True):
        if dept.endswith(code):
            dept = dept[:-len(code)].strip()
            break
        # Also try with space
        if dept.endswith(" " + code):
            dept = dept[:-(len(code) + 1)].strip()
            break

    # Remove parenthetical content
    dept = re.sub(r'\(.*?\)', '', dept).strip()

    # Clean up extra spaces
    dept = re.sub(r'\s+', ' ', dept).strip()

    # Remove "PACKAGE" if somehow present
    dept = dept.replace(" PACKAGE", "").strip()

    return dept


def sanitize_doc_id(name):
    """Create a Firestore-safe document ID from doctor name."""
    safe = str(name).strip()
    safe = safe.replace(" ", "_").replace(".", "")
    safe = re.sub(r'[^a-zA-Z0-9_\-]', '', safe)
    return safe if safe else f"doc_{hash(name)}"


# ============================================================
# STEP 1: RE-UPLOAD DOCTORS
# ============================================================
def upload_doctors():
    print("\n" + "=" * 60)
    print("👨‍⚕️ STEP 1: Uploading/Updating 454 Doctors")
    print("=" * 60)

    df = pd.read_excel('Doctor_dump.xlsx', sheet_name='Doctor Dump')
    df.columns = df.columns.str.strip()

    success = 0
    errors  = 0

    for index, row in df.iterrows():
        try:
            name = str(row.get("Doctor Name", "")).strip()
            if not name or name == "nan":
                continue

            dept_raw    = str(row.get("DeptName", "")).strip()
            hosp_code   = extract_hospital_code(dept_raw)
            hospital_id = HOSPITAL_CODE_MAP.get(hosp_code, "manipal_blr")
            clean_dept  = clean_department_name(dept_raw)

            designation = str(row.get("designation", "")).strip()
            if designation == "nan":
                designation = ""

            expertise = str(row.get("field_expertise", "")).strip()
            if expertise == "nan":
                expertise = ""

            fellowship = str(row.get("fellowship_membership", "")).strip()
            if fellowship == "nan":
                fellowship = ""

            profile_url = str(row.get("doctor_profile_url", "")).strip()
            if profile_url == "nan":
                profile_url = ""

            # Document ID: use the same format as existing docs
            doc_id = "Dr_" + sanitize_doc_id(name.replace("Dr. ", "").replace("Dr.", ""))

            # Build the update data
            update_data = {
                # Original Excel field names (so RAG code can find them)
                "Doctor Name ": name,      # with trailing space (matches Excel)
                "Doctor Name": name,        # without trailing space (backup)
                "DeptName": dept_raw,        # original raw value
                "designation": designation,
                "field_expertise": expertise,
                "fellowship_membership": fellowship,
                "doctor_profile_url": profile_url,

                # Cleaned/computed fields
                "name": name,               # simple name field
                "specialty": clean_dept,     # e.g. "CARDIOLOGY" (was EMPTY before!)
                "hospital_id": hospital_id,  # e.g. "manipal_blr"
                "hospital_code": hosp_code,  # e.g. "MHB"
                "is_active": True,
            }

            # Merge — keeps existing fields like image_url, photo_url
            db.collection("doctors").document(doc_id).set(update_data, merge=True)

            if index < 5 or index % 50 == 0:
                print(f"  [{index}] ✅ {name} → {clean_dept} | {hospital_id}", flush=True)

            success += 1

        except Exception as e:
            print(f"  [{index}] ❌ Error: {e}", flush=True)
            errors += 1

    print(f"\n✅ Doctors uploaded: {success} success, {errors} errors")
    return success


# ============================================================
# STEP 2: UPLOAD PACKAGES
# ============================================================
def upload_packages():
    print("\n" + "=" * 60)
    print("💰 STEP 2: Uploading 270 Packages")
    print("=" * 60)

    df = pd.read_excel('Doctor_dump.xlsx', sheet_name='Package detials ')
    df.columns = df.columns.str.strip()

    success = 0
    errors  = 0

    for index, row in df.iterrows():
        try:
            pkg_type = str(row.get("TYPE", "")).strip()
            if not pkg_type or pkg_type == "nan":
                continue

            description = str(row.get("Description", "")).strip()
            if description == "nan":
                description = ""

            minimum = row.get("Minimum")
            maximum = row.get("Maximum range")

            # Convert to numbers
            try:
                minimum = int(float(str(minimum).replace(",", ""))) if pd.notna(minimum) else 0
            except:
                minimum = 0
            try:
                maximum = int(float(str(maximum).replace(",", ""))) if pd.notna(maximum) else 0
            except:
                maximum = 0

            # Clean department from package type
            # "CARDIOLOGY ANGIO PACKAGE" → "CARDIOLOGY"
            # "CARDIOTHORACIC SURGERY PACKAGE" → "CARDIOTHORACIC"
            clean_type = pkg_type.upper().replace(" PACKAGE", "").replace(" PROCEDURE", "").strip()

            # Create document ID
            safe_desc = sanitize_doc_id(description)[:50]
            doc_id = f"pkg_{index}_{safe_desc}"

            package_data = {
                # Original Excel fields (with trailing space to match Excel exactly)
                "TYPE ": pkg_type,           # with space (matches Excel header)
                "TYPE": pkg_type,            # without space (backup)
                "Description": description,
                "Minimum": minimum,
                "Maximum range ": maximum,   # with trailing space (matches Excel)
                "Maximum range": maximum,    # without space (backup)

                # Computed fields
                "clean_type": clean_type,     # "CARDIOLOGY ANGIO" etc
                "hospital_id": "manipal_blr", # All current packages are Manipal BLR
                "is_active": True,
            }

            db.collection("packages").document(doc_id).set(package_data)

            if index < 5 or index % 30 == 0:
                print(f"  [{index}] ✅ {description} | {pkg_type} | ₹{minimum:,}-₹{maximum:,}", flush=True)

            success += 1

        except Exception as e:
            print(f"  [{index}] ❌ Error: {e}", flush=True)
            errors += 1

    print(f"\n✅ Packages uploaded: {success} success, {errors} errors")
    return success


# ============================================================
# STEP 3: VERIFY
# ============================================================
def verify():
    print("\n" + "=" * 60)
    print("🔍 VERIFICATION")
    print("=" * 60)

    # Count doctors with specialty filled
    docs = list(db.collection("doctors").limit(10).stream())
    filled = 0
    for doc in docs:
        d = doc.to_dict()
        if d.get("specialty") or d.get("DeptName"):
            filled += 1

    print(f"\n  Doctors checked (sample of 10): {filled}/10 have specialty field")

    # Show a sample cardiology doctor
    print("\n  Sample CARDIOLOGY doctor:")
    for doc in db.collection("doctors").limit(100).stream():
        d = doc.to_dict()
        dept = d.get("DeptName", "")
        if "CARDIOLOGY" in str(dept).upper():
            print(f"    ID: {doc.id}")
            print(f"    name: {d.get('name', '')}")
            print(f"    DeptName: {d.get('DeptName', '')}")
            print(f"    specialty: {d.get('specialty', '')}")
            print(f"    hospital_id: {d.get('hospital_id', '')}")
            print(f"    designation: {d.get('designation', '')[:60]}")
            break

    # Count packages
    pkgs = list(db.collection("packages").limit(5).stream())
    print(f"\n  Packages collection: {len(pkgs)}+ documents")
    if pkgs:
        p = pkgs[0].to_dict()
        print(f"    Sample: {p.get('Description', '')} | {p.get('TYPE', '')} | ₹{p.get('Minimum', 0):,}")

    # Simulate RAG query
    print("\n  Simulating RAG: CARDIOLOGY + manipal_blr")
    query = db.collection("doctors").where("hospital_id", "==", "manipal_blr")
    cardio_count = 0
    for doc in query.stream():
        d = doc.to_dict()
        dept = ""
        for field in ["DeptName", "specialty"]:
            if d.get(field):
                dept = str(d[field]).upper()
                break
        if "CARDIOLOGY" in dept:
            cardio_count += 1
    print(f"    → Found {cardio_count} CARDIOLOGY doctors at manipal_blr")

    pkg_query = db.collection("packages").where("hospital_id", "==", "manipal_blr")
    cardio_pkgs = 0
    for doc in pkg_query.stream():
        p = doc.to_dict()
        ptype = str(p.get("TYPE ", "") or p.get("TYPE", "")).upper()
        if "CARDIOLOGY" in ptype:
            cardio_pkgs += 1
    print(f"    → Found {cardio_pkgs} CARDIOLOGY packages at manipal_blr")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("=" * 60)
    print("🔧 CareBridge — Fix Doctor Data + Upload Packages")
    print("=" * 60)

    doc_count = upload_doctors()
    pkg_count = upload_packages()
    verify()

    print(f"\n🎉 Done! {doc_count} doctors updated, {pkg_count} packages created.")
    print("   Now redeploy or test your bot — RAG should return results!")
    print("=" * 60)