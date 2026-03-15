"""
============================================================
STEP 1: RUN THIS ONCE to set up multi-hospital Firestore
============================================================
This script:
  1. Creates 'hospitals' collection with Manipal locations
  2. Updates existing doctor docs with hospital_id
  3. Updates existing package docs with hospital_id

Usage:
  python setup_hospitals.py
============================================================
"""

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# --- Init Firebase ---
print("Authenticating with Firebase using serviceAccountKey.json...")
cred = credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(cred)

db = firestore.client()

# ============================================================
# HOSPITAL DATA — Add your partner hospitals here
# ============================================================
HOSPITALS = [
    # --- MANIPAL HOSPITALS ---
    {
        "hospital_id": "manipal_blr",
        "name": "Manipal Hospital, Bangalore",
        "short_name": "Manipal Bangalore",
        "city": "bangalore",
        "state": "karnataka",
        "lat": 12.9716,
        "lng": 77.5946,
        "rating": 4.8,
        "departments": [
            "CARDIOLOGY", "CARDIOTHORACIC", "ORTHOPAEDICS", "SPINE",
            "ONCOLOGY", "NEUROLOGY", "NEUROSURGERY",
            "GASTROENTEROLOGY", "SURGICAL GASTROENTEROLOGY",
            "UROLOGY", "NEPHROLOGY", "TRANSPLANT",
            "LIVER TRANSPLANT", "VASCULAR",
        ],
        "active": True,
        "network": "Manipal Hospitals",
    },
    {
        "hospital_id": "manipal_chn",
        "name": "Manipal Hospital, Chennai",
        "short_name": "Manipal Chennai",
        "city": "chennai",
        "state": "tamil nadu",
        "lat": 13.0827,
        "lng": 80.2707,
        "rating": 4.7,
        "departments": [
            "CARDIOLOGY", "CARDIOTHORACIC", "ORTHOPAEDICS", "SPINE",
            "ONCOLOGY", "NEUROLOGY", "GASTROENTEROLOGY", "UROLOGY",
            "NEPHROLOGY",
        ],
        "active": True,
        "network": "Manipal Hospitals",
    },
    {
        "hospital_id": "manipal_del",
        "name": "Manipal Hospital, Delhi",
        "short_name": "Manipal Delhi",
        "city": "delhi",
        "state": "delhi",
        "lat": 28.6139,
        "lng": 77.2090,
        "rating": 4.6,
        "departments": [
            "CARDIOLOGY", "ORTHOPAEDICS", "ONCOLOGY", "NEUROLOGY",
            "GASTROENTEROLOGY", "UROLOGY", "NEPHROLOGY", "TRANSPLANT",
        ],
        "active": True,
        "network": "Manipal Hospitals",
    },
]

def setup_hospitals():
    """Create/update hospitals collection."""
    print("\n📦 Setting up hospitals collection...\n")
    for h in HOSPITALS:
        doc_ref = db.collection("hospitals").document(h["hospital_id"])
        doc_ref.set(h)
        print(f"  ✅ {h['name']} ({h['hospital_id']})")
    print(f"\n✅ {len(HOSPITALS)} hospitals created/updated.\n")


def tag_existing_doctors(default_hospital_id="manipal_blr"):
    """
    Add hospital_id to all existing doctor docs that don't have one.
    """
    print(f"\n👨‍⚕️ Tagging existing doctors with hospital_id='{default_hospital_id}'...\n")
    count = 0
    for doc in db.collection("doctors").stream():
        data = doc.to_dict()
        if not data.get("hospital_id"):
            # Try to detect city from DeptName
            dept_name = data.get("DeptName", "") or ""
            if "MHC" in dept_name.upper():
                h_id = "manipal_chn"
            elif "MHD" in dept_name.upper():
                h_id = "manipal_del"
            else:
                h_id = default_hospital_id  # Default to Bangalore

            db.collection("doctors").document(doc.id).update({
                "hospital_id": h_id
            })
            name = data.get("Doctor Name ") or data.get("Doctor Name") or doc.id
            count += 1

    print(f"\n✅ {count} doctors newly tagged.\n")


def tag_existing_packages(default_hospital_id="manipal_blr"):
    """Add hospital_id to all existing package docs."""
    print(f"\n💰 Tagging existing packages with hospital_id='{default_hospital_id}'...\n")
    count = 0
    for doc in db.collection("packages").stream():
        data = doc.to_dict()
        if not data.get("hospital_id"):
            db.collection("packages").document(doc.id).update({
                "hospital_id": default_hospital_id
            })
            desc = data.get("Description") or data.get("description") or doc.id
            count += 1

    print(f"\n✅ {count} packages newly tagged.\n")


def verify_setup():
    """Print summary of what's in Firestore."""
    print("\n" + "=" * 50)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 50)

    # Hospitals
    hospitals = list(db.collection("hospitals").where("active", "==", True).stream())
    print(f"\n🏥 Hospitals: {len(hospitals)}")
    for h in hospitals:
        d = h.to_dict()
        print(f"   • {d['name']} — {len(d.get('departments', []))} departments")

    # Doctors with hospital_id
    all_docs = list(db.collection("doctors").stream())
    tagged = [d for d in all_docs if d.to_dict().get("hospital_id")]
    print(f"\n👨‍⚕️ Doctors: {len(all_docs)} total, {len(tagged)} tagged with hospital_id")

    # Packages with hospital_id
    all_pkgs = list(db.collection("packages").stream())
    tagged_pkgs = [p for p in all_pkgs if p.to_dict().get("hospital_id")]
    print(f"💰 Packages: {len(all_pkgs)} total, {len(tagged_pkgs)} tagged with hospital_id")

    if len(tagged) < len(all_docs):
        print(f"\n⚠️  {len(all_docs) - len(tagged)} doctors still need hospital_id!")
    if len(tagged_pkgs) < len(all_pkgs):
        print(f"⚠️  {len(all_pkgs) - len(tagged_pkgs)} packages still need hospital_id!")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    print("=" * 50)
    print("🏥 CareBridge — Multi-Hospital Setup")
    print("=" * 50)

    setup_hospitals()
    tag_existing_doctors()
    tag_existing_packages()
    verify_setup()

    print("\n🎉 Setup complete! You can now deploy the updated main.py\n")