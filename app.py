import streamlit as st
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from openai import OpenAI
from datetime import datetime, timedelta
import re

try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
except:
    load_dotenv()
    groq_api_key = os.getenv("GROQ_API_KEY")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

if not all([groq_api_key, supabase_url, supabase_key]):
    st.error(".env file mein keys daal de bhai!")
    st.stop()

client = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
supabase: Client = create_client(supabase_url, supabase_key)

@st.cache_data(ttl=60)
def load_barbers():
    try:
        res = supabase.table("barbers").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Barbers load nahi hue: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_services():
    try:
        res = supabase.table("barber_services").select("*, barbers(name)").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

barbers_df = load_barbers()
services_df = load_services()

now = datetime.now()
today_name = now.strftime("%A")
today_date = now.strftime("%d %B %Y")

if not barbers_df.empty:
    info = []
    available_today = []
    off_today = []

    for _, row in barbers_df.iterrows():
        n = row['name']
        t = row.get('timing', 'N/A')
        o = row.get('off_day', 'N/A')
        p = row.get('phone_number', 'N/A')
        info.append(f"{n}: Timing {t}, Off day {o}, Phone {p}")
        off_days = [d.strip() for d in str(o).split(",")] if o else []
        if today_name in off_days:
            off_today.append(n)
        else:
            available_today.append(n)

    barber_details_str = "\n".join(info)
    barber_names_str = ", ".join(barbers_df['name'].tolist())
    available_today_str = ", ".join(available_today) if available_today else "Koi nahi"
    off_today_str = ", ".join(off_today) if off_today else "Koi nahi"
else:
    barber_details_str = "Koi barber nahi hai abhi."
    barber_names_str = ""
    available_today_str = "Koi nahi"
    off_today_str = "Koi nahi"

if not services_df.empty:
    svc_lines = []
    for _, row in services_df.iterrows():
        barber_name = row.get('barbers', {}).get('name', f"Barber ID {row.get('barber_id', '?')}") if isinstance(row.get('barbers'), dict) else f"Barber ID {row.get('barber_id', '?')}"
        dur = row.get('duration_minutes', 30)
        svc_lines.append(f"{barber_name}: {row.get('service_name','?')} - Rs.{row.get('charge','?')} ({dur} min)")
    services_str = "\n".join(svc_lines)
else:
    services_str = "Koi services data nahi."

system_prompt = f"""
Tu Salon Dost hai – bohot polite aur helpful salon assistant.

Aaj ki date: {today_date} ({today_name})

Available barbers aur unki details:
{barber_details_str}

Barber services aur charges (Rs. mein):
{services_str}

Aaj ({today_name}) available barbers: {available_today_str}
Aaj ({today_name}) off par hain: {off_today_str}

Rules:
- Barber ke baare mein poocha to uski real details bata dena.
- Service ya charge ke baare mein poocha to barber_services data se sahi jawab dena.
- "Kaun sab se acha hai X service ke liye" poocha to us service ke saare barbers aur unke charges bata dena.
- "Aaj kaun available hai" ya "aaj kaun aa raha hai" poocha to SIRF aaj ke available barbers batao: {available_today_str}
- "Aaj kaun off hai" poocha to: {off_today_str}
- Agar user booking karna chahta hai to SIRF yeh puchna: "Booking karwni hai? (Haan/Nahi)"
- Haan bolne par system khud handle karega, tu dobara mat puchna.
- Random ya off-topic baat pe: "Main sirf salon info ke liye hoon."
- Hinglish mein reply dena (Hindi + English mix).
- BILKUL ek hi reply dena, double message nahi.
- Chhota aur clear reply dena.
"""

# ============================================================
# FLEXIBLE DATE PARSER
# ============================================================
def parse_flexible_date(text):
    text = text.strip().lower()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    relative_list = [
        ("aaj ki", 0), ("aaj", 0), ("aj ki", 0), ("aj", 0), ("today", 0), ("abhi", 0),
        ("kal ki", 1), ("kal", 1), ("kl ki", 1), ("kl", 1),
        ("aglay din", 1), ("agle din", 1), ("agli bar", 1),
        ("aglay", 1), ("agle", 1), ("agli", 1),
        ("ag ki", 1), ("ag", 1),
        ("agla", 1),
        ("tomorrow", 1), ("tmrw", 1), ("tmr", 1),
        ("parson ki", 2), ("parson", 2), ("prson ki", 2), ("prson", 2),
        ("parso", 2), ("prso", 2), ("day after tomorrow", 2),
        ("nrson", 3),
    ]
    for word, delta in relative_list:
        if word in text:
            return today + timedelta(days=delta)

    month_map = {
        "jan": 1, "january": 1, "janwari": 1,
        "feb": 2, "february": 2, "febwari": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5, "mai": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    for month_str, month_num in month_map.items():
        m = re.search(rf'(\d{{1,2}})\s*{month_str}(?:\s+(\d{{4}}))?', text)
        if m:
            day = int(m.group(1))
            year = int(m.group(2)) if m.group(2) else today.year
            try:
                result = datetime(year, month_num, day)
                if result.date() < today.date() and not m.group(2):
                    result = datetime(year + 1, month_num, day)
                return result
            except:
                pass
        m = re.search(rf'{month_str}\s+(\d{{1,2}})(?:\s+(\d{{4}}))?', text)
        if m:
            day = int(m.group(1))
            year = int(m.group(2)) if m.group(2) else today.year
            try:
                result = datetime(year, month_num, day)
                if result.date() < today.date() and not m.group(2):
                    result = datetime(year + 1, month_num, day)
                return result
            except:
                pass

    m = re.search(r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})', text)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day)
        except:
            pass

    m = re.match(r'^(\d{1,2})$', text.strip())
    if m:
        day = int(m.group(1))
        try:
            candidate = today.replace(day=day)
            if candidate.date() < today.date():
                if today.month == 12:
                    candidate = candidate.replace(year=today.year + 1, month=1)
                else:
                    candidate = candidate.replace(month=today.month + 1)
            return candidate
        except:
            pass

    try:
        from dateutil import parser as date_parser
        return date_parser.parse(text, dayfirst=True, fuzzy=True)
    except:
        pass

    return None


# ============================================================
# FLEXIBLE TIME PARSER — FIXED VERSION
# ============================================================
def parse_flexible_time(text):
    text_lower = text.strip().lower()

    # Normalize common typos
    text_lower = re.sub(r'\bbja\b',   'baje', text_lower)
    text_lower = re.sub(r'\bbaj\b',   'baje', text_lower)
    text_lower = re.sub(r'\bbjay\b',  'baje', text_lower)
    text_lower = re.sub(r'\bbjae\b',  'baje', text_lower)
    text_lower = re.sub(r'\bbajay\b', 'baje', text_lower)

    # === PERIOD DETECTION (AM/PM hint) ===
    period_hint = None

    # Explicit AM/PM markers — check first (highest priority)
    if re.search(r'\bam\b', text_lower):
        period_hint = "am"
    elif re.search(r'\bpm\b', text_lower):
        period_hint = "pm"

    # Urdu/Hinglish AM words
    urdu_am_words = ["subah", "suba", "fajar", "fajr", "morning", "صبح"]

    # Urdu/Hinglish PM words — ALL common spellings included
    urdu_pm_words = [
        # Noon/afternoon
        "dhupar", "dhuphar", "dopahar", "dopeher", "zuhr", "dohar",
        "noon", "midday", "dupaher", "dupar",
        # Evening — complete spelling variations
        "shaam", "sham", "shm", "shhm", "شام", "evening", "eve",
        # Night
        "raat", "rart", "night", "رات",
    ]

    if not period_hint:
        for w in urdu_am_words:
            if w in text_lower:
                period_hint = "am"
                break

    if not period_hint:
        for w in urdu_pm_words:
            if w in text_lower:
                period_hint = "pm"
                break

    # === URDU NUMBER WORDS — sorted longest first to avoid partial match ===
    urdu_numbers = [
        ("barah baje", 12), ("gyarah baje", 11), ("das baje", 10), ("nau baje", 9),
        ("naw baje", 9),    ("aath baje", 8),   ("ath baje", 8),   ("saat baje", 7),
        ("sat baje", 7),    ("chhe baje", 6),   ("che baje", 6),   ("panch baje", 5),
        ("char baje", 4),   ("teen baje", 3),   ("do baje", 2),    ("ek baje", 1),
        ("12 baje", 12),    ("11 baje", 11),    ("10 baje", 10),   ("9 baje", 9),
        ("8 baje", 8),      ("7 baje", 7),      ("6 baje", 6),     ("5 baje", 5),
        ("4 baje", 4),      ("3 baje", 3),      ("2 baje", 2),     ("1 baje", 1),
        ("barah", 12), ("gyarah", 11), ("das", 10), ("nau", 9), ("naw", 9),
        ("aath", 8),   ("ath", 8),    ("saat", 7), ("sat", 7),
        ("chhe", 6),   ("che", 6),   ("panch", 5), ("char", 4), ("teen", 3),
    ]

    hour   = None
    minute = 0

    # Try Urdu word numbers first (longest match wins)
    for phrase, val in urdu_numbers:
        if phrase in text_lower:
            hour = val
            # Check for minutes after phrase e.g. "3 baje 30 minute"
            mm = re.search(rf'{re.escape(phrase)}\s+(?:aur\s+)?(\d{{1,2}})', text_lower)
            if mm:
                minute = int(mm.group(1))
            break

    # Numeric format "4:30" or "16:30"
    if hour is None:
        mm = re.search(r'\b(\d{1,2}):(\d{2})\b', text_lower)
        if mm:
            hour   = int(mm.group(1))
            minute = int(mm.group(2))

    # Two numbers separated by space — hour + minute e.g. "5 30"
    if hour is None:
        mm = re.search(r'\b([1-9]|1[0-2])\s+([0-5][0-9])\b', text_lower)
        if mm:
            hour   = int(mm.group(1))
            minute = int(mm.group(2))

    # Single number 1-12
    if hour is None:
        mm = re.search(r'\b(1[0-2]|[1-9])\b', text_lower)
        if mm:
            hour = int(mm.group(1))

    if hour is None:
        return None

    # Half / quarter past
    if any(w in text_lower for w in ["half", "adha", "aadha"]):
        minute = 30
    if any(w in text_lower for w in ["quarter", "pauna"]):
        minute = 15

    # === APPLY AM/PM CONVERSION ===
    if period_hint == "am":
        # Morning — if 12 AM it means midnight (0)
        if hour == 12:
            hour = 0
        # All other morning hours stay as-is (1-11 AM)

    elif period_hint == "pm":
        # Afternoon/Evening/Night — convert to 24h
        # 12 PM stays 12 (noon), 1-11 PM → add 12
        if hour != 12:
            hour += 12

    else:
        # No time-of-day hint given at all
        # Smart salon default:
        # Hours 1-9  → likely PM (salon appointments mostly afternoon/evening)
        # Hours 10-12 → likely AM/noon (morning opening times)
        if 1 <= hour <= 9:
            hour += 12
        # 10, 11, 12 stay as-is

    # Final validation
    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        return None

    try:
        return datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    except:
        return None


# ============================================================
# BARBER TIMING PARSER
# ============================================================
def parse_barber_timing(timing_str):
    try:
        parts = re.split(r'[-–]', timing_str)
        if len(parts) != 2:
            return None, None

        def to_minutes(t):
            t = t.strip().upper()
            m = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM)', t)
            if not m:
                return None
            h    = int(m.group(1))
            mins = int(m.group(2)) if m.group(2) else 0
            period = m.group(3)
            if period == 'PM' and h != 12:
                h += 12
            elif period == 'AM' and h == 12:
                h = 0
            return h * 60 + mins

        start_min = to_minutes(parts[0])
        end_min   = to_minutes(parts[1])
        if start_min is not None and end_min is not None:
            return start_min, end_min
    except:
        pass
    return None, None


# ============================================================
# UI
# ============================================================
st.title("✂️ Salon Dost - Booking App")
st.caption("Assalam o Alaikum! Poocho kuch bhi 😊")

with st.sidebar:
    st.header("💈 Available Barbers")
    if not barbers_df.empty:
        st.dataframe(barbers_df[['name', 'timing', 'off_day', 'phone_number']], hide_index=True)
    else:
        st.info("Koi barber nahi database mein")

    if not services_df.empty:
        st.divider()
        st.subheader("🛎️ Services & Charges")
        display_svc = services_df.copy()
        if 'barbers' in display_svc.columns:
            display_svc['barber_name'] = display_svc['barbers'].apply(
                lambda x: x.get('name', '') if isinstance(x, dict) else ''
            )
            st.dataframe(display_svc[['barber_name', 'service_name', 'charge']], hide_index=True)

    st.divider()
    st.markdown(f"📅 **Aaj:** {today_date} ({today_name})")
    st.markdown(f"✅ **Available aaj:** {available_today_str}")
    st.markdown(f"❌ **Off aaj:** {off_today_str}")


# Session state init
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": system_prompt}]
if "booking_step" not in st.session_state:
    st.session_state.booking_step = 0
if "booking_data" not in st.session_state:
    st.session_state.booking_data = {}

# Chat history display
for msg in st.session_state.messages[1:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


def get_ai_reply(messages):
    try:
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full = ""
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.5,
                max_tokens=200,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    full += delta
                    placeholder.markdown(full + "▌")
            placeholder.markdown(full)
        return full.strip()
    except Exception as e:
        err = f"AI error: {e}"
        with st.chat_message("assistant"):
            st.markdown(err)
        return err


def show_direct_reply(text):
    with st.chat_message("assistant"):
        st.markdown(text)
    return text


# Service Selection UI (step 2)
if st.session_state.get("booking_step") == 2:
    services_list = []
    if not services_df.empty:
        services_list = sorted(services_df["service_name"].dropna().unique().tolist())

    if "svc_selections" not in st.session_state:
        st.session_state.svc_selections = {s: False for s in services_list}

    with st.container(border=True):
        st.markdown("💇 **Kaunsi service(s) chahiye?**")
        st.caption("Ek ya zyada select karein, phir Confirm dabayein")
        cols = st.columns(2)
        for idx, svc in enumerate(services_list):
            st.session_state.svc_selections[svc] = cols[idx % 2].checkbox(
                svc,
                value=st.session_state.svc_selections.get(svc, False),
                key=f"chk_{svc}"
            )
        selected_svcs = [s for s, v in st.session_state.svc_selections.items() if v]
        if selected_svcs:
            st.success("✅ Selected: " + ", ".join(selected_svcs))
        col1, col2 = st.columns([1, 3])
        if col1.button("✅ Confirm", key="confirm_svc_btn", type="primary"):
            if selected_svcs:
                st.session_state.booking_data["service"] = ", ".join(selected_svcs)
                if "svc_selections" in st.session_state:
                    del st.session_state.svc_selections
                st.session_state.booking_step = 3
                svc_msg = "✅ Services: **" + ", ".join(selected_svcs) + "**\n\n📞 Ab apna **phone number** bataiye:"
                st.session_state.messages.append({"role": "assistant", "content": svc_msg})
                st.rerun()
            else:
                st.warning("⚠️ Kam se kam ek service select karein!")


def fetch_barber_bookings(barber_name, date_str=None):
    try:
        res = supabase.table("barbers").select("id, name, timing").ilike("name", f"%{barber_name}%").limit(1).execute()
        if not res.data:
            return None, None, None
        barber_id = res.data[0]["id"]
        bname     = res.data[0]["name"]
        timing    = res.data[0].get("timing", "N/A")
        if not date_str:
            date_str = datetime.now().strftime("%d %B %Y")
        bookings_res = supabase.table("bookings").select(
            "booking_time, customer_name, service_name"
        ).eq("barber_id", barber_id).eq("booking_date", date_str).execute()
        return bname, timing, bookings_res.data if bookings_res.data else []
    except Exception as e:
        print("Bookings fetch error:", e)
        return None, None, None


# ============================================================
# MAIN CHAT INPUT
# ============================================================
if prompt := st.chat_input("Kya poochna hai?", disabled=(st.session_state.get("booking_step") == 2)):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    reply        = ""
    lower_prompt = prompt.lower().strip()

    # ============ BOOKING FLOW ============
    if st.session_state.booking_step > 0:
        step = st.session_state.booking_step
        data = st.session_state.booking_data

        if step == 1:
            data["name"] = prompt
            st.session_state.booking_step = 2
            with st.chat_message("assistant"):
                st.markdown(f"👋 Shukriya **{prompt}**! Ab service select karein:")
            reply = f"Shukriya {prompt}! Service select karein"

        elif step == 2:
            reply = ""

        elif step == 3:
            data["phone"] = prompt
            chosen_services = [s.strip() for s in data.get("service", "").split(",") if s.strip()]
            if not services_df.empty and chosen_services:
                sets = []
                for cs in chosen_services:
                    ids = set(services_df[services_df["service_name"].str.lower() == cs.lower()]["barber_id"].tolist())
                    sets.append(ids)
                valid_barber_ids   = set.union(*sets) if sets else set()
                valid_barber_names = []
                if not barbers_df.empty:
                    valid_barber_names = barbers_df[barbers_df["id"].isin(valid_barber_ids)]["name"].tolist()
                data["valid_barbers"] = valid_barber_names
            else:
                valid_barber_names    = barbers_df["name"].tolist() if not barbers_df.empty else []
                data["valid_barbers"] = valid_barber_names

            services_display = data.get("service", "")

            if len(valid_barber_names) == 1:
                only_barber    = valid_barber_names[0]
                data["barber"] = only_barber
                reply = show_direct_reply(
                    f"💈 **{services_display}** ke liye sirf **{only_barber}** available hai.\n\n"
                    f"📅 Date bataiye (jaise: kal, parson, 15 march):"
                )
                st.session_state.booking_step = 6
            elif len(valid_barber_names) == 0:
                reply = show_direct_reply(
                    f"❌ **{services_display}** ke liye koi barber nahi mila. Admin se rabta karein."
                )
                st.session_state.booking_step = 0
                st.session_state.booking_data = {}
            else:
                names_str = ", ".join(valid_barber_names)
                reply = show_direct_reply(
                    f"💈 **{services_display}** ke liye yeh barbers available hain:\n\n**({names_str})**\n\nKaunsa barber chahiye?"
                )
                st.session_state.booking_step = 4

        elif step == 4:
            chosen = prompt.strip()
            valid  = data.get("valid_barbers", [])
            match  = [b for b in valid if chosen.lower() in b.lower()]
            if not match:
                valid_str = ", ".join(valid) if valid else barber_names_str
                reply = show_direct_reply(
                    f"❌ **{chosen}** yeh service nahi karta.\n\n"
                    f"**{data.get('service','')}** ke liye yeh barbers hain: **{valid_str}**\n\nInmein se choose karein:"
                )
            else:
                data["barber"] = match[0]
                reply = show_direct_reply("📅 Date bataiye (jaise: kal, parson, 15 march, 20 march 2026):")
                st.session_state.booking_step = 6

        elif step == 6:
            parsed_date = parse_flexible_date(lower_prompt)

            if parsed_date is None:
                reply = show_direct_reply(
                    "❌ Date samajh nahi aaya. Yeh formats try karein:\n"
                    "• **kal**, **parson**\n"
                    "• **15 march**, **20 april 2026**\n"
                    "• **15/3/2026**"
                )
            elif parsed_date.date() < datetime.now().date():
                reply = show_direct_reply(
                    f"❌ Yeh date ({parsed_date.strftime('%d %B %Y')}) guzar chuki hai! "
                    f"Aaj ya aage ki date dein (aaj: {datetime.now().strftime('%d %B %Y')}):"
                )
            else:
                chosen_day  = parsed_date.strftime("%A")
                barber_off  = ""
                if not barbers_df.empty:
                    brow = barbers_df[barbers_df["name"].str.lower() == data.get("barber", "").lower()]
                    if not brow.empty:
                        barber_off = brow.iloc[0].get("off_day", "")
                off_days_list = [d.strip().lower() for d in str(barber_off).split(",") if d.strip()]
                if chosen_day.lower() in off_days_list:
                    reply = show_direct_reply(
                        f"❌ **{data.get('barber','')}** ka {chosen_day} off hota hai! "
                        f"(Off days: {barber_off})\n\nKoi aur date dein:"
                    )
                else:
                    data["date"] = parsed_date.strftime("%d %B %Y")
                    barber_timing_hint = ""
                    if not barbers_df.empty:
                        brow = barbers_df[barbers_df["name"].str.lower() == data.get("barber", "").lower()]
                        if not brow.empty:
                            barber_timing_hint = brow.iloc[0].get("timing", "")
                    reply = show_direct_reply(
                        f"✅ Date set: **{data['date']}**\n\n"
                        f"⏰ Time bataiye"
                        + (f" ({barber_timing_hint} ke beech)" if barber_timing_hint else "")
                        + f"\n💡 Jaise: sham 4 baje, dhupar 2 baje, 3:30 PM, subah 10 baje"
                    )
                    st.session_state.booking_step = 7

        elif step == 7:
            user_time = parse_flexible_time(lower_prompt)

            if user_time is None:
                reply = show_direct_reply(
                    "❌ Time samajh nahi aaya. Yeh formats try karein:\n"
                    "• **sham 4 baje**, **sham 6 baje**, **shaam 5 baje**\n"
                    "• **dhupar 2 baje**, **subah 10 baje**\n"
                    "• **3:30 PM**, **15:00**"
                )
            else:
                barber_id     = None
                barber_name   = data["barber"]
                barber_timing = None
                try:
                    res = supabase.table("barbers").select("id, name, timing").ilike(
                        "name", f"%{data['barber']}%"
                    ).limit(1).execute()
                    if res.data:
                        barber_id     = res.data[0]["id"]
                        barber_name   = res.data[0]["name"]
                        barber_timing = res.data[0].get("timing", "")
                except Exception as e:
                    print("Barber fetch error:", e)

                t_start, t_end = parse_barber_timing(barber_timing) if barber_timing else (None, None)
                in_range       = True
                if t_start is not None and t_end is not None:
                    user_total_min = user_time.hour * 60 + user_time.minute
                    in_range       = t_start <= user_total_min < t_end

                if not in_range:
                    reply = show_direct_reply(
                        f"❌ {barber_name} sirf **{barber_timing}** tak available hai.\n\n"
                        f"💡 Jaise: sham 2 baje, sham 4 baje, 6:30 PM"
                    )
                else:
                    chosen_services = [s.strip() for s in data.get("service", "").split(",") if s.strip()]
                    user_duration   = 30
                    if not services_df.empty and chosen_services and barber_id:
                        matched = services_df[
                            (services_df["service_name"].isin(chosen_services)) &
                            (services_df["barber_id"] == barber_id)
                        ]
                        if not matched.empty and "duration_minutes" in matched.columns:
                            user_duration = int(matched["duration_minutes"].sum())

                    user_start = user_time.hour * 60 + user_time.minute
                    user_end   = user_start + user_duration

                    already_booked = False
                    booked_slots   = []
                    try:
                        existing = supabase.table("bookings").select(
                            "booking_time, service_name"
                        ).eq("barber_id", barber_id).eq("booking_date", data["date"]).execute()
                        if existing.data:
                            for b in existing.data:
                                bt = parse_flexible_time(b["booking_time"])
                                if bt:
                                    b_start    = bt.hour * 60 + bt.minute
                                    b_duration = 30
                                    b_svcs     = [s.strip() for s in (b.get("service_name") or "").split(",") if s.strip()]
                                    if not services_df.empty and b_svcs:
                                        bm = services_df[
                                            (services_df["service_name"].isin(b_svcs)) &
                                            (services_df["barber_id"] == barber_id)
                                        ]
                                        if bm.empty:
                                            bm = services_df[services_df["service_name"].isin(b_svcs)]
                                        if not bm.empty and "duration_minutes" in bm.columns:
                                            b_duration = int(bm["duration_minutes"].sum())
                                    elif not b_svcs:
                                        b_duration = 60
                                    b_end = b_start + b_duration
                                    booked_slots.append((b_start, b_end))
                                    if user_start < b_end and user_end > b_start:
                                        already_booked = True
                    except Exception as e:
                        print("Booking check error:", e)

                    if already_booked:
                        next_slot_min = user_start
                        max_iter      = 48
                        iterations    = 0
                        while iterations < max_iter:
                            slot_end = next_slot_min + user_duration
                            conflict = any(next_slot_min < be and slot_end > bs for bs, be in booked_slots)
                            if not conflict:
                                break
                            next_slot_min = min(be for bs, be in booked_slots if next_slot_min < be and slot_end > bs)
                            iterations   += 1
                        next_h        = next_slot_min // 60
                        next_m        = next_slot_min % 60
                        next_time_str = f"{next_h % 12 or 12}:{next_m:02d} {'AM' if next_h < 12 else 'PM'}"
                        reply = show_direct_reply(
                            f"❌ Yeh slot ({user_time.strftime('%I:%M %p')}) already book hai!\n\n"
                            f"💡 Agla available slot: **{next_time_str}** ({user_duration} min ke liye).\n\nKoi aur time likhiye:"
                        )
                    else:
                        data["time"] = user_time.strftime("%I:%M %p")

                        save_data = {
                            "customer_name":  data["name"],
                            "customer_phone": data["phone"],
                            "barber_id":      barber_id,
                            "booking_date":   data["date"],
                            "booking_time":   data["time"],
                            "service_name":   data.get("service", "")
                        }

                        try:
                            response = supabase.table("bookings").insert(save_data).execute()
                            if response.data:
                                row_id = response.data[0]["id"]
                                reply  = show_direct_reply(f"""✅ **Booking Confirm Ho Gayi!**

👤 Naam: {data['name']}
📞 Phone: {data['phone']}
✂️ Service: {data.get('service', 'N/A')}
💈 Barber: {barber_name}
📅 Date: {data['date']}
⏰ Time: {data['time']}
🆔 Booking ID: `{row_id}`

Database mein save ho chuki hai! Shukriya 🙏""")
                                st.success(f"✅ Booking saved! ID: {row_id}")
                            else:
                                reply = show_direct_reply("❌ Booking save nahi hui. Dobara try karo.")
                        except Exception as e:
                            reply = show_direct_reply(f"❌ Booking save nahi hui.\nError: `{str(e)}`")
                            print("SAVE ERROR:", e)

                        st.session_state.booking_step = 0
                        st.session_state.booking_data = {}

    # ============ NORMAL FLOW ============
    else:
        yes_words    = ["haan", "han", "yes", "hna", "ok", "okay", "bilkul"]
        prompt_words = lower_prompt.split()
        is_yes       = any(word in prompt_words for word in yes_words)

        last_assistant_msg = ""
        for msg in reversed(st.session_state.messages[:-1]):
            if msg["role"] == "assistant":
                last_assistant_msg = msg["content"].lower()
                break

        booking_was_asked = any(
            word in last_assistant_msg for word in ["booking karwni hai", "booking karna", "book"]
        )

        if is_yes and booking_was_asked:
            st.session_state.booking_step = 1
            st.session_state.booking_data = {}
            reply = show_direct_reply("👍 Theek hai! Pehle apna **naam** bataiye:")

        elif any(word in lower_prompt for word in ["book", "booking", "appointment", "reserve"]):
            booking_hint  = {"role": "system", "content": "User booking karna chahta hai. Sirf poocho: 'Booking karwni hai? (Haan/Nahi)'"}
            temp_messages = st.session_state.messages[:-1] + [booking_hint, st.session_state.messages[-1]]
            reply         = get_ai_reply(temp_messages)

        else:
            found_barber = None
            if not barbers_df.empty:
                for _, row in barbers_df.iterrows():
                    if row['name'].lower() in lower_prompt:
                        found_barber = row['name']
                        break

            info_patterns = [
                "off", "timing", "phone", "number", "charge", "kitna", "din", "day",
                "kab se", "kab tak", "bara", "baray", "batao", "batana", "kya hai", "kia ha",
                "kab ha", "kab hai", "service", "karta", "krta"
            ]
            is_info_only = any(w in lower_prompt for w in info_patterns)

            schedule_words = [
                "free ha", "free hai", "available ha", "available hai",
                "koi booking", "koi apoitment", "koi appointment", "koi slot",
                "schedule ha", "schedule hai", "aaj koi", "abhi koi"
            ]
            is_schedule_query = (
                found_barber and not is_info_only and
                any(w in lower_prompt for w in schedule_words)
            )

            if is_schedule_query:
                today_str = datetime.now().strftime("%d %B %Y")
                bname, timing, bookings = fetch_barber_bookings(found_barber, today_str)
                if bname is None:
                    reply = get_ai_reply(st.session_state.messages)
                elif not bookings:
                    reply = show_direct_reply(
                        f"✅ **{bname}** aaj ({today_str}) bilkul free hai!\n\n"
                        f"⏰ Timing: {timing}\n"
                        f"Abhi koi appointment book nahi hai."
                    )
                else:
                    booked_slots = ""
                    for b in bookings:
                        svc = b.get('service_name') or 'N/A'
                        booked_slots += f"• {b['booking_time']} — {svc}\n"
                    reply = show_direct_reply(
                        f"📋 **{bname}** ki aaj ({today_str}) ki appointments:\n\n"
                        f"{booked_slots}\n"
                        f"⏰ Timing: {timing}\n\n"
                        f"💡 Booking karwni hai? Upar wale booked slots chhod ke koi aur time choose karein."
                    )
            else:
                reply = get_ai_reply(st.session_state.messages)

    if reply:
        st.session_state.messages.append({"role": "assistant", "content": reply})