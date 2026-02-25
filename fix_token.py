import requests

# 1. Ask for the Token directly (No spaces will be captured)
print("------------------------------------------------")
ACCESS_TOKEN = input("EAAhECSeoQxkBQgZAc1OdvqiA0Rj8ibMZBbWRPvzCf4wWLV6ODyL5Tu3M61nYZAlCgZAQZARt9k5CWFnl8BmomdQwnOWD3G3flZASPAYHnXwjEaETlZCFPNrb4HRd7vPLR7iG4doSJbZCY42NKqKSWOZAkiZBAowMXIdT6pu0xd8E92BataIcpEo7VetH21YA2ByKedTwZDZD").strip()
print("------------------------------------------------")

# 2. Ask for the Phone ID
PHONE_NUMBER_ID = input("915417844997635").strip()
print("------------------------------------------------")

# 3. The Test Function
def test_connection():
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    # Simple Hello World test
    payload = {
        "messaging_product": "whatsapp",
        "to": "919080553616", # Hardcoded for test
        "type": "template",
        "template": {"name": "hello_world", "language": {"code": "en_US"}}
    }
    
    print(f"\n📡 Testing Connection to ID: {PHONE_NUMBER_ID}...")
    try:
        response = requests.post(url, headers=headers, json=payload)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# Run it
result = test_connection()
print("\n--- RESULT ---")
print(result)