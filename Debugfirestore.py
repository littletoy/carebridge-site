"""
============================================================
DEBUG SCRIPT — Run this to find why RAG returns 0
============================================================
This prints EXACTLY what's in your Firestore doctors & packages
so we can see what fields exist and what values they have.

Usage:
  Set GOOGLE_CREDENTIALS env var, then:
  python debug_firestore.py
============================================================
"""

import os
import json
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


def check_doctors():
    print("\n" + "=" * 60)
    print("👨‍⚕️ DOCTORS COLLECTION — First 5 documents")
    print("=" * 60)

    docs = list(db.collection("doctors").stream())
    print(f"\nTotal doctor documents: {len(docs)}\n")

    for i, doc in enumerate(docs[:5]):
        data = doc.to_dict()
        print(f"--- Doctor #{i+1} (ID: {doc.id}) ---")
        print(f"  All field names: {list(data.keys())}")
        print()

        # Check key fields
        for field_name in ["Doctor Name ", "Doctor Name", "name", "doctor_name"]:
            if field_name in data:
                print(f"  ✅ '{field_name}' = '{data[field_name]}'")

        for field_name in ["DeptName", "deptname", "dept_name", "department", "Department", "specialty"]:
            if field_name in data:
                print(f"  ✅ '{field_name}' = '{data[field_name]}'")

        # Check hospital_id
        if "hospital_id" in data:
            print(f"  ✅ 'hospital_id' = '{data['hospital_id']}'")
        else:
            print(f"  ❌ 'hospital_id' = MISSING — setup_hospitals.py didn't tag this doc!")

        print()

    # Summary
    has_hospital_id = sum(1 for d in docs if d.to_dict().get("hospital_id"))
    print(f"\n📊 SUMMARY: {has_hospital_id}/{len(docs)} doctors have hospital_id")

    # Check what DeptName values exist
    dept_values = set()
    dept_field_used = None
    for doc in docs:
        data = doc.to_dict()
        for field_name in ["DeptName", "deptname", "dept_name", "department", "Department", "specialty"]:
            if field_name in data and data[field_name]:
                dept_values.add(str(data[field_name]).strip())
                dept_field_used = field_name
                break

    print(f"\n📋 Department field being used: '{dept_field_used}'")
    print(f"📋 ALL unique department values in your data:")
    for dv in sorted(dept_values):
        has_cardio = "CARDIO" in dv.upper()
        marker = " ← CARDIOLOGY MATCH" if has_cardio else ""
        print(f"   • '{dv}'{marker}")

    return docs


def check_packages():
    print("\n" + "=" * 60)
    print("💰 PACKAGES COLLECTION — First 5 documents")
    print("=" * 60)

    docs = list(db.collection("packages").stream())
    print(f"\nTotal package documents: {len(docs)}\n")

    for i, doc in enumerate(docs[:5]):
        data = doc.to_dict()
        print(f"--- Package #{i+1} (ID: {doc.id}) ---")
        print(f"  All field names: {list(data.keys())}")
        print()

        for field_name in ["TYPE ", "TYPE", "type", "Type", "package_type", "category", "specialty"]:
            if field_name in data:
                print(f"  ✅ '{field_name}' = '{data[field_name]}'")

        for field_name in ["Description", "description", "name", "package_name"]:
            if field_name in data:
                print(f"  ✅ '{field_name}' = '{data[field_name]}'")

        for field_name in ["Minimum", "minimum", "min_price"]:
            if field_name in data:
                print(f"  ✅ '{field_name}' = '{data[field_name]}'")

        for field_name in ["Maximum range ", "Maximum range", "maximum", "max_price"]:
            if field_name in data:
                print(f"  ✅ '{field_name}' = '{data[field_name]}'")

        if "hospital_id" in data:
            print(f"  ✅ 'hospital_id' = '{data['hospital_id']}'")
        else:
            print(f"  ❌ 'hospital_id' = MISSING!")

        print()

    has_hospital_id = sum(1 for d in docs if d.to_dict().get("hospital_id"))
    print(f"\n📊 SUMMARY: {has_hospital_id}/{len(docs)} packages have hospital_id")

    # Check TYPE values
    type_values = set()
    for doc in docs:
        data = doc.to_dict()
        for field_name in ["TYPE ", "TYPE", "type", "Type", "package_type", "category"]:
            if field_name in data and data[field_name]:
                type_values.add(str(data[field_name]).strip())
                break

    print(f"\n📋 ALL unique TYPE values:")
    for tv in sorted(type_values):
        print(f"   • '{tv}'")


def check_hospitals():
    print("\n" + "=" * 60)
    print("🏥 HOSPITALS COLLECTION")
    print("=" * 60)

    docs = list(db.collection("hospitals").stream())
    print(f"\nTotal hospital documents: {len(docs)}\n")

    for doc in docs:
        data = doc.to_dict()
        print(f"  • {data.get('name', doc.id)}")
        print(f"    hospital_id: {data.get('hospital_id', 'MISSING')}")
        print(f"    active: {data.get('active', 'MISSING')}")
        print(f"    departments: {data.get('departments', [])}")
        print()


def simulate_rag_query():
    """Simulate exactly what the bot does when it queries RAG."""
    print("\n" + "=" * 60)
    print("🔍 SIMULATING RAG QUERY: CARDIOLOGY + manipal_blr")
    print("=" * 60)

    # This is EXACTLY what query_rag_context does:
    dept_upper = "CARDIOLOGY"
    hospital_id = "manipal_blr"

    print(f"\nSearching doctors where hospital_id='{hospital_id}' AND DeptName contains '{dept_upper}'...\n")

    # Method 1: With hospital_id filter (what the bot does)
    print("--- Method 1: With hospital_id filter ---")
    query = db.collection("doctors").where("hospital_id", "==", hospital_id)
    filtered_docs = list(query.stream())
    print(f"  Docs matching hospital_id='{hospital_id}': {len(filtered_docs)}")

    for doc in filtered_docs[:3]:
        data = doc.to_dict()
        dept = ""
        for field_name in ["DeptName", "deptname", "dept_name", "department", "Department", "specialty"]:
            if field_name in data and data[field_name]:
                dept = str(data[field_name]).strip()
                break
        name = data.get("Doctor Name ") or data.get("Doctor Name") or data.get("name") or doc.id
        match = "✅ MATCH" if dept_upper in dept.upper() else "❌ NO MATCH"
        print(f"    • {name} | DeptName='{dept}' | {match}")

    # Method 2: Without filter (all doctors)
    print(f"\n--- Method 2: ALL doctors (no filter) ---")
    all_docs = list(db.collection("doctors").stream())
    print(f"  Total doctors: {len(all_docs)}")

    cardio_docs = []
    for doc in all_docs:
        data = doc.to_dict()
        dept = ""
        for field_name in ["DeptName", "deptname", "dept_name", "department", "Department", "specialty"]:
            if field_name in data and data[field_name]:
                dept = str(data[field_name]).strip()
                break
        if dept_upper in dept.upper():
            cardio_docs.append((data, dept))

    print(f"  Doctors with CARDIOLOGY in DeptName: {len(cardio_docs)}")
    for data, dept in cardio_docs[:3]:
        name = data.get("Doctor Name ") or data.get("Doctor Name") or data.get("name") or "?"
        h_id = data.get("hospital_id", "NONE")
        print(f"    • {name} | DeptName='{dept}' | hospital_id='{h_id}'")

    if not cardio_docs:
        print("\n  ⚠️ ZERO doctors have 'CARDIOLOGY' in their DeptName!")
        print("  → Your doctors may use a different department name.")
        print("  → Check the 'ALL unique department values' list above.")


if __name__ == "__main__":
    print("=" * 60)
    print("🔍 CareBridge Firestore Debug Tool")
    print("=" * 60)

    check_hospitals()
    check_doctors()
    check_packages()
    simulate_rag_query()

    print("\n" + "=" * 60)
    print("🏁 DEBUG COMPLETE — Share the output above so we can fix the issue")
    print("=" * 60)