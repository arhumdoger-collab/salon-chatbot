from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

test_data = {
    "customer_name": "Test User",
    "customer_phone": "9999999999",
    "barber_id": None,  # pehle None se try, agar chalta hai to ID issue nahi
    "booking_date": "2026-01-30",
    "booking_time": "4:00 PM"
}

try:
    response = supabase.table("bookings").insert(test_data).execute()
    print("SUCCESS! Row inserted. ID:", response.data[0]["id"] if response.data else "no data")
except Exception as e:
    print("ERROR:", str(e))