from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv
import os, re, json, uuid
from openai import OpenAI
from datetime import datetime, timedelta, timezone

load_dotenv()


groq_api_key = os.getenv("GROQ_API_KEY")
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

client   = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
supabase: Client = create_client(supabase_url, supabase_key)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# MODELS
# ============================================================
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    session_id: str = ""
    booking_step: Any = 0
    booking_data: Optional[Any] = None

# ============================================================
# SESSION HELPERS
# ============================================================
def session_load(session_id: str) -> dict:
    if not session_id:
        return {"booking_step": 0, "booking_data": {}}
    try:
        res = supabase.table("sessions").select("data").eq("id", session_id).execute()
        if res.data:
            return res.data[0]["data"]
    except:
        pass
    return {"booking_step": 0, "booking_data": {}}

def session_save(session_id: str, data: dict):
    try:
        supabase.table("sessions").upsert({
            "id": session_id,
            "data": data,
            "updated_at": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print("Session save error:", e)

def session_clear(session_id: str):
    try:
        supabase.table("sessions").delete().eq("id", session_id).execute()
    except:
        pass

# ============================================================
# BARBER NAME MATCHER
# ============================================================
def find_barber_in_text(text, valid_names):
    text_lower = text.lower()
    for name in valid_names:
        if name.lower() in text_lower:
            return name
    words = [w for w in re.split(r'\W+', text_lower) if len(w) > 2]
    for name in valid_names:
        for word in words:
            if word in name.lower() or name.lower() in word:
                return name
    return None

# ============================================================
# SERVICE NAMES HELPER
# ============================================================
def get_service_names(booking_data, barbers_list, services_list):
    if booking_data.get("barber"):
        barber_row = next((b for b in barbers_list if b["name"].lower() == booking_data["barber"].lower()), None)
        if barber_row:
            return sorted(set(
                s["service_name"] for s in services_list
                if s.get("barber_id") == barber_row["id"] and s.get("service_name")
            ))
    return sorted(set(s["service_name"] for s in services_list if s.get("service_name")))

# ============================================================
# DATE PARSER
# ============================================================
def parse_flexible_date(text):
    text  = text.strip().lower()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    relative_list = [
        ("aaj ki", 0), ("aaj", 0), ("aj ki", 0), ("aj", 0),
        ("today", 0), ("abhi", 0), ("is waqt", 0), ("ag ki", 0), ("ag", 0),
        ("kal ki", 1), ("kal", 1), ("kl ki", 1), ("kl", 1),
        ("aglay din", 1), ("agle din", 1), ("agli bar", 1),
        ("aglay", 1), ("agle", 1), ("agli", 1), ("agla", 1),
        ("tomorrow", 1), ("tmrw", 1), ("tmr", 1), ("next day", 1),
        ("parson ki", 2), ("parson", 2), ("prson ki", 2), ("prson", 2),
        ("parso", 2), ("prso", 2), ("day after tomorrow", 2), ("nrson", 3),
    ]
    for word, delta in relative_list:
        if word in text:
            return today + timedelta(days=delta)
    month_map = {
        "jan":1,"january":1,"janwari":1,"feb":2,"february":2,"mar":3,"march":3,
        "apr":4,"april":4,"may":5,"mai":5,"jun":6,"june":6,"jul":7,"july":7,
        "aug":8,"august":8,"sep":9,"sept":9,"september":9,"oct":10,"october":10,
        "nov":11,"november":11,"dec":12,"december":12,
    }
    for month_str, month_num in month_map.items():
        m = re.search(rf'(\d{{1,2}})\s*{month_str}(?:\s+(\d{{4}}))?', text)
        if m:
            day=int(m.group(1)); year=int(m.group(2)) if m.group(2) else today.year
            try: return datetime(year, month_num, day)
            except: pass
        m = re.search(rf'{month_str}\s+(\d{{1,2}})(?:\s+(\d{{4}}))?', text)
        if m:
            day=int(m.group(1)); year=int(m.group(2)) if m.group(2) else today.year
            try: return datetime(year, month_num, day)
            except: pass
    m = re.search(r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})', text)
    if m:
        day,month,year=int(m.group(1)),int(m.group(2)),int(m.group(3))
        if year<100: year+=2000
        try: return datetime(year,month,day)
        except: pass
    m = re.match(r'^(\d{1,2})$', text.strip())
    if m:
        day=int(m.group(1))
        try:
            candidate=today.replace(day=day)
            if candidate.date()<today.date():
                candidate=candidate.replace(month=today.month+1) if today.month<12 else candidate.replace(year=today.year+1,month=1)
            return candidate
        except: pass
    try:
        from dateutil import parser as dp
        return dp.parse(text, dayfirst=True, fuzzy=True)
    except: pass
    return None

# ============================================================
# TIME PARSER
# ============================================================
def parse_flexible_time(text):
    text_lower = text.strip().lower()
    for old, new in [('bja','baje'),('baj','baje'),('bjay','baje'),('bjae','baje'),('bajay','baje')]:
        text_lower = re.sub(rf'\b{old}\b', new, text_lower)
    period_hint = None
    if re.search(r'\bam\b', text_lower):   period_hint = "am"
    elif re.search(r'\bpm\b', text_lower): period_hint = "pm"
    urdu_am = ["subah","suba","fajar","fajr","morning"]
    urdu_pm = ["dhupar","dhuphar","dopahar","dopeher","zuhr","dohar","noon","midday","shaam","sham","shm","evening","eve","raat","rart","night"]
    if not period_hint:
        for w in urdu_am:
            if w in text_lower: period_hint="am"; break
    if not period_hint:
        for w in urdu_pm:
            if w in text_lower: period_hint="pm"; break
    urdu_numbers = [
        ("barah baje",12),("gyarah baje",11),("das baje",10),("nau baje",9),("naw baje",9),
        ("aath baje",8),("ath baje",8),("saat baje",7),("sat baje",7),("chhe baje",6),
        ("che baje",6),("panch baje",5),("char baje",4),("teen baje",3),("do baje",2),("ek baje",1),
        ("12 baje",12),("11 baje",11),("10 baje",10),("9 baje",9),("8 baje",8),("7 baje",7),
        ("6 baje",6),("5 baje",5),("4 baje",4),("3 baje",3),("2 baje",2),("1 baje",1),
        ("barah",12),("gyarah",11),("das",10),("nau",9),("naw",9),("aath",8),("ath",8),
        ("saat",7),("sat",7),("chhe",6),("che",6),("panch",5),("char",4),("teen",3),
    ]
    hour=None; minute=0
    for phrase,val in urdu_numbers:
        if phrase in text_lower:
            hour=val
            mm=re.search(rf'{re.escape(phrase)}\s+(?:aur\s+)?(\d{{1,2}})',text_lower)
            if mm: minute=int(mm.group(1))
            break
    if hour is None:
        mm=re.search(r'\b(\d{1,2}):(\d{2})\b',text_lower)
        if mm: hour=int(mm.group(1)); minute=int(mm.group(2))
    if hour is None:
        mm=re.search(r'\b([1-9]|1[0-2])\s+([0-5][0-9])\b',text_lower)
        if mm: hour=int(mm.group(1)); minute=int(mm.group(2))
    if hour is None:
        mm=re.search(r'\b(1[0-2]|[1-9])\b',text_lower)
        if mm: hour=int(mm.group(1))
    if hour is None: return None
    if any(w in text_lower for w in ["half","adha","aadha"]): minute=30
    if any(w in text_lower for w in ["quarter","pauna"]): minute=15
    if period_hint=="am":
        if hour==12: hour=0
    elif period_hint=="pm":
        if hour!=12: hour+=12
    else:
        if 1<=hour<=9: hour+=12
    if not (0<=hour<=23) or not (0<=minute<=59): return None
    try: return datetime.now().replace(hour=hour,minute=minute,second=0,microsecond=0)
    except: return None

# ============================================================
# BARBER TIMING PARSER
# ============================================================
def parse_barber_timing(timing_str):
    try:
        parts=re.split(r'[-–]',timing_str)
        if len(parts)!=2: return None,None
        def to_min(t):
            t=t.strip().upper()
            m=re.match(r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM)',t)
            if not m: return None
            h=int(m.group(1)); mins=int(m.group(2)) if m.group(2) else 0
            if m.group(3)=='PM' and h!=12: h+=12
            elif m.group(3)=='AM' and h==12: h=0
            return h*60+mins
        return to_min(parts[0]),to_min(parts[1])
    except: return None,None

# ============================================================
# FRESH DATA
# ============================================================
def get_fresh_data():
    now=datetime.now(timezone.utc) + timedelta(hours=5); today_name=now.strftime("%A"); today_date=now.strftime("%d %B %Y")
    barbers_data=supabase.table("barbers").select("*").execute().data or []
    services_data=supabase.table("barber_services").select("*, barbers(name)").execute().data or []
    available_today=[]; off_today=[]; barber_details=[]
    for b in barbers_data:
        n=b['name']; t=b.get('timing','N/A'); o=b.get('off_day','N/A'); p=b.get('phone_number','N/A')
        barber_details.append(f"{n}: Timing {t}, Off day {o}, Phone {p}")
        off_days=[d.strip() for d in str(o).split(",")] if o else []
        if today_name in off_days: off_today.append(n)
        else: available_today.append(n)
    svc_lines=[]
    for s in services_data:
        bname=s.get('barbers',{}).get('name',f"ID {s.get('barber_id','?')}") if isinstance(s.get('barbers'),dict) else f"ID {s.get('barber_id','?')}"
        svc_lines.append(f"{bname}: {s.get('service_name','?')} - Rs.{s.get('charge','?')} ({s.get('duration_minutes',30)} min)")
    return {
        "today_name":today_name,"today_date":today_date,
        "barbers":barbers_data,"services":services_data,
        "barber_details":"\n".join(barber_details),"services_str":"\n".join(svc_lines),
        "available_today":", ".join(available_today) if available_today else "Koi nahi",
        "off_today":", ".join(off_today) if off_today else "Koi nahi",
    }

# ============================================================
# SYSTEM PROMPT
# ============================================================
def build_system_prompt(data):
    return f"""Tu Salon Dost ka AI assistant hai. Hinglish mein baat karo.

Aaj: {data['today_date']} ({data['today_name']})
Barbers: {data['barber_details']}
Services: {data['services_str']}
Available aaj: {data['available_today']}
Off aaj: {data['off_today']}

STRICT RULES:
1. Har sawal ka seedha jawab do — chahe kaise bhi likha ho.
2. "info", "batao", "kya hai", "kaun", "kaise", "kia" = info sawal hai, jawab do.
3. Barber ki services poochi = us barber ki exact services batao.
4. "sabse acha/sasta/best" = data se compare karke jawab do.
5. Agar user booking karna chahe to poocho: "Booking karwni hai? (Haan/Nahi)"
6. Agar user ek saath service + barber mention kare to confirm karo: "Haan [Barber] [Service] karta hai! Booking karwni hai?"
7. Off-topic sawal = "Main sirf salon info ke liye hoon."
8. Reply chhota rakho — sirf jawab, koi extra explanation nahi.
9. Confident raho — "lekin", "shayad", "however" mat likho."""

# ============================================================
# AI INTENT + EXTRACT
# ============================================================
def detect_intent_and_extract(user_msg, barbers_list, services_list, today_date, today_name):
    barber_names=[b["name"] for b in barbers_list]
    service_names=list(set(s["service_name"] for s in services_list if s.get("service_name")))
    prompt=f"""Analyze salon chatbot message. Return ONLY valid JSON.
Today: {today_date} ({today_name})
Known barbers: {barber_names}
Known services: {service_names}
Message: "{user_msg}"
Return:
{{
  "intent": "booking" or "info" or "other",
  "name": null, "phone": null,
  "service": "EXACT from list or null",
  "barber": "EXACT from list or null",
  "date": "DD Month YYYY or null",
  "time": "HH:MM AM/PM or null"
}}
STRICT:
- intent=booking ONLY if user CLEARLY says "booking karni hai", "appointment chahiye", "book karo", "karwani hai"
- If user asks "kya X karega?" or "X bhi karega?" = intent is "info"
- Mixed message = intent is "info"
- service from: {service_names} only ("haircut","cut","cutting"→"Hair Cutting","beard","dari"→"Beard","massage","malish"→"Massage","color","rang"→"Color")
- barber from: {barber_names} only
- "kal"=tomorrow, "aaj"/"ag"=today, "parson"=day after tomorrow
- 1-9 no hint=PM
- null if not mentioned"""
    try:
        resp=client.chat.completions.create(model="llama-3.3-70b-versatile",messages=[{"role":"user","content":prompt}],temperature=0.1,max_tokens=300)
        raw=re.sub(r'```json|```','',resp.choices[0].message.content.strip()).strip()
        return json.loads(raw)
    except: return {"intent":"other"}

# ============================================================
# SAVE BOOKING
# ============================================================
def save_booking_to_db(booking_data, barbers_list):
    barber_row=next((b for b in barbers_list if b["name"].lower()==booking_data.get("barber","").lower()),None)
    barber_id=barber_row["id"] if barber_row else None
    barber_name=barber_row["name"] if barber_row else booking_data.get("barber","")
    save_d={
        "customer_name":booking_data.get("name",""),"customer_phone":booking_data.get("phone",""),
        "barber_id":barber_id,"booking_date":booking_data.get("date",""),
        "booking_time":booking_data.get("time",""),"service_name":booking_data.get("service","")
    }
    resp=supabase.table("bookings").insert(save_d).execute()
    if resp.data:
        row_id=resp.data[0]["id"]
        return True,f"""✅ **Booking Confirm Ho Gayi!**

👤 Naam: {booking_data.get('name','')}
📞 Phone: {booking_data.get('phone','')}
✂️ Service: {booking_data.get('service','N/A')}
💈 Barber: {barber_name}
📅 Date: {booking_data.get('date','')}
⏰ Time: {booking_data.get('time','')}
🆔 Booking ID: `{row_id}`

Shukriya! 🙏"""
    return False,"❌ Booking save nahi hui. Dobara try karo."

# ============================================================
# RESOLVE AFTER SERVICE
# ============================================================
def _resolve_after_service(booking_data, barbers_list, services_list):
    chosen_svcs=[s.strip() for s in booking_data.get("service","").split(",") if s.strip()]
    if not chosen_svcs: return 2,"💇 Service select karein:"
    valid_ids=set()
    for cs in chosen_svcs:
        ids=set(s["barber_id"] for s in services_list if s.get("service_name","").lower()==cs.lower())
        valid_ids.update(ids)
    valid_names=[b["name"] for b in barbers_list if b["id"] in valid_ids] or [b["name"] for b in barbers_list]
    booking_data["valid_barbers"]=valid_names
    svc_display=booking_data.get("service","")
    if booking_data.get("barber"):
        match=[b for b in valid_names if booking_data["barber"].lower() in b.lower()]
        if match: booking_data["barber"]=match[0]
        else:
            requested=booking_data.pop("barber")
            return 4,(f"❌ **{requested}** ke paas **{svc_display}** service nahi hai.\n\n✅ Available: **{', '.join(valid_names)}**\n\nKaunsa barber chahiye?")
    if not booking_data.get("barber"):
        if len(valid_names)==0: return 0,f"❌ **{svc_display}** ke liye koi barber nahi."
        elif len(valid_names)==1: booking_data["barber"]=valid_names[0]
        else: return 4,f"💈 **{svc_display}** ke liye barber chunein:\n**{', '.join(valid_names)}**\n\nKaunsa barber chahiye?"
    barber_name=booking_data["barber"]
    br=next((b for b in barbers_list if b["name"].lower()==barber_name.lower()),None)
    th=br.get("timing","") if br else ""
    if booking_data.get("date") and booking_data.get("time"):
        return 7,(f"✅ Confirm karein:\n💈 Barber: **{barber_name}**\n✂️ Service: **{svc_display}**\n📅 Date: **{booking_data['date']}**\n⏰ Time: **{booking_data['time']}**\n\nSahi hai? (Haan/Nahi)")
    if not booking_data.get("date"):
        return 6,f"💈 Barber: **{barber_name}**\n\n📅 Date bataiye (kal, parson, 15 march)"+(f" — {th}" if th else "")+":"
    if not booking_data.get("time"):
        return 7,f"✅ Date: **{booking_data['date']}**\n\n⏰ Time bataiye"+(f" ({th} ke beech)" if th else "")+":"
    return 7,"⏰ Time confirm karein:"

# ============================================================
# MAIN ENDPOINT
# ============================================================
@app.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())

    session      = session_load(session_id)
    booking_step = session.get("booking_step", 0)
    booking_data = session.get("booking_data", {})

    # ✅ KEY FIX: Frontend se aayi booking_data ko session data ke upar merge karo
    # Sirf non-empty values se override karo
    if req.booking_data and isinstance(req.booking_data, dict):
        for k, v in req.booking_data.items():
            if v is not None and v != "" and v != {} and v != []:
                booking_data[k] = v

    # Step bhi frontend se lo agar session mein nahi hai
    if req.booking_step and not booking_step:
        booking_step = req.booking_step

    # ✅ Step 3 ke liye — session step use karo (frontend se aata hai 3)
    if req.booking_step == 3:
        booking_step = 3

    data          = get_fresh_data()
    system_prompt = build_system_prompt(data)
    lower_prompt  = req.messages[-1].content.lower().strip() if req.messages else ""
    prompt        = req.messages[-1].content.strip() if req.messages else ""
    barbers_list  = data["barbers"]
    services_list = data["services"]

    def ret(rep, step, bdata, extra=None):
        session_save(session_id, {"booking_step": step, "booking_data": bdata})
        res={"reply":rep,"booking_step":step,"booking_data":bdata,"session_id":session_id}
        if extra: res.update(extra)
        return res

    # ============================================================
    # BOOKING FLOW
    # ============================================================
    if booking_step and booking_step != 0:

        if booking_step == 1:
            booking_data["name"] = prompt
            return ret(f"👋 Shukriya **{prompt}**! Apna **phone number** bataiye:", "need_phone", booking_data)

        elif booking_step == "need_phone":
            booking_data["phone"] = prompt
            if booking_data.get("service"):
                step,rep=_resolve_after_service(booking_data,barbers_list,services_list)
                svc_names=get_service_names(booking_data,barbers_list,services_list)
                if step==2: return ret(rep,step,booking_data,{"show_services":svc_names})
                return ret(rep,step,booking_data)
            svc_names=get_service_names(booking_data,barbers_list,services_list)
            barber_name=booking_data.get("barber","")
            msg=f"💇 **{barber_name}** ki services select karein:" if barber_name else "💇 Kaunsi service chahiye? Select karein:"
            return ret(msg,2,booking_data,{"show_services":svc_names})

        elif booking_step == 2:
            svc_names=get_service_names(booking_data,barbers_list,services_list)
            barber_name=booking_data.get("barber","")
            msg=f"💇 **{barber_name}** ki services select karein:" if barber_name else "💇 Upar se service select karein:"
            return ret(msg,2,booking_data,{"show_services":svc_names})

        elif booking_step == 3:
            # ✅ Service ab booking_data mein already hai (frontend ne merge kiya)
            if not booking_data.get("service"):
                svc_names=get_service_names(booking_data,barbers_list,services_list)
                barber_name=booking_data.get("barber","")
                msg=f"💇 **{barber_name}** ki services select karein:" if barber_name else "💇 Service select karein:"
                return ret(msg,2,booking_data,{"show_services":svc_names})
            # ✅ Session mein bhi save karo service ke saath
            session_save(session_id,{"booking_step":3,"booking_data":booking_data})
            step,rep=_resolve_after_service(booking_data,barbers_list,services_list)
            svc_names=get_service_names(booking_data,barbers_list,services_list)
            if step==2: return ret(rep,step,booking_data,{"show_services":svc_names})
            return ret(rep,step,booking_data)

        elif booking_step == 4:
            valid=booking_data.get("valid_barbers",[])
            found=find_barber_in_text(prompt,valid)
            if not found: return ret(f"😊 In mein se barber ka naam likhein:\n**{', '.join(valid)}**",4,booking_data)
            booking_data["barber"]=found
            br=next((b for b in barbers_list if b["name"].lower()==found.lower()),None)
            th=br.get("timing","") if br else ""
            if booking_data.get("date") and booking_data.get("time"):
                step,rep=_resolve_after_service(booking_data,barbers_list,services_list)
                return ret(rep,step,booking_data)
            return ret("📅 Date bataiye (kal, parson, 15 march)"+(f" — {th}" if th else "")+":"  ,6,booking_data)

        elif booking_step == 6:
            parsed_date=parse_flexible_date(lower_prompt)
            if parsed_date is None: return ret("❌ Date samajh nahi aaya.\n• **kal**, **parson**\n• **15 march**, **20 april 2026**",6,booking_data)
            if parsed_date.date()<datetime.now().date(): return ret(f"❌ Yeh date ({parsed_date.strftime('%d %B %Y')}) guzar chuki hai! Aaj ya aage ki date dein:",6,booking_data)
            if parsed_date.date()>(datetime.now()+timedelta(days=7)).date():
                max_d=(datetime.now()+timedelta(days=7)).strftime('%d %B %Y')
                return ret(f"❌ Sirf 7 din ke andar booking karein.\n✅ Maximum: **{max_d}**\n\nKoi aur date dein:",6,booking_data)
            chosen_day=parsed_date.strftime("%A")
            barber_row=next((b for b in barbers_list if b["name"].lower()==booking_data.get("barber","").lower()),None)
            barber_off=barber_row.get("off_day","") if barber_row else ""
            off_list=[d.strip().lower() for d in str(barber_off).split(",") if d.strip()]
            if chosen_day.lower() in off_list:
                return ret(f"❌ **{booking_data.get('barber','')}** ka {chosen_day} off hai! (Off: {barber_off})\n\nKoi aur date dein:",6,booking_data)
            booking_data["date"]=parsed_date.strftime("%d %B %Y")
            timing_hint=barber_row.get("timing","") if barber_row else ""
            reply=(f"✅ Date: **{booking_data['date']}**\n\n⏰ Time bataiye"+(f" ({timing_hint} ke beech)" if timing_hint else "")+"\n💡 Jaise: sham 4 baje, 3:30 PM")
            return ret(reply,7,booking_data)

        elif booking_step == 7:
            yes_words=["haan","han","yes","hna","ok","okay","bilkul","sahi","theek","confirm"]
            is_confirm=any(w in lower_prompt.split() for w in yes_words)
            if is_confirm and booking_data.get("time"):
                user_time=parse_flexible_time(booking_data["time"])
            else:
                user_time=parse_flexible_time(lower_prompt)
            if user_time is None: return ret("❌ Time samajh nahi aaya.\n• **sham 4 baje**, **subah 10 baje**\n• **3:30 PM**",7,booking_data)
            barber_row=next((b for b in barbers_list if b["name"].lower()==booking_data.get("barber","").lower()),None)
            barber_id=barber_row["id"] if barber_row else None
            barber_name=barber_row["name"] if barber_row else booking_data.get("barber","")
            barber_timing=barber_row.get("timing","") if barber_row else ""
            t_start,t_end=parse_barber_timing(barber_timing) if barber_timing else (None,None)
            if t_start and t_end:
                u_min=user_time.hour*60+user_time.minute
                if not (t_start<=u_min<t_end): return ret(f"❌ {barber_name} sirf **{barber_timing}** tak available hai.\n\nKoi aur time dein:",7,booking_data)
            if booking_data.get("date"):
                try:
                    booked_date=datetime.strptime(booking_data["date"],"%d %B %Y")
                    chosen_day=booked_date.strftime("%A")
                    barber_off=barber_row.get("off_day","") if barber_row else ""
                    off_list=[d.strip().lower() for d in str(barber_off).split(",") if d.strip()]
                    if chosen_day.lower() in off_list:
                        booking_data.pop("date",None)
                        return ret(f"❌ **{barber_name}** ka {chosen_day} off hai!\n\n📅 Koi aur date dein:",6,booking_data)
                except: pass
            chosen_svcs=[s.strip() for s in booking_data.get("service","").split(",") if s.strip()]
            user_dur=30
            if chosen_svcs and barber_id:
                matched=[s for s in services_list if s.get("service_name") in chosen_svcs and s.get("barber_id")==barber_id]
                if matched: user_dur=sum(s.get("duration_minutes",30) for s in matched)
            u_start=user_time.hour*60+user_time.minute; u_end=u_start+user_dur
            booked_ranges=[]; conflict=False
            if booking_data.get("date") and barber_id:
                try:
                    existing=supabase.table("bookings").select("booking_time,service_name").eq("barber_id",barber_id).eq("booking_date",booking_data["date"]).execute()
                    if existing.data:
                        for b in existing.data:
                            bt=parse_flexible_time(b["booking_time"])
                            if bt:
                                bs=bt.hour*60+bt.minute; bd=30
                                b_svcs=[s.strip() for s in (b.get("service_name") or "").split(",") if s.strip()]
                                if b_svcs:
                                    bm=[s for s in services_list if s.get("service_name") in b_svcs]
                                    if bm: bd=sum(s.get("duration_minutes",30) for s in bm)
                                booked_ranges.append((bs,bs+bd))
                                if u_start<bs+bd and u_end>bs: conflict=True
                except: pass
            if conflict:
                next_slot=u_start
                for _ in range(48):
                    se=next_slot+user_dur
                    if not any(next_slot<be and se>bs for bs,be in booked_ranges): break
                    next_slot=min(be for bs,be in booked_ranges if next_slot<be and se>bs)
                nh=next_slot//60; nm=next_slot%60
                nts=f"{nh%12 or 12}:{nm:02d} {'AM' if nh<12 else 'PM'}"
                return ret(f"❌ Yeh slot ({user_time.strftime('%I:%M %p')}) already book hai!\n\n💡 Agla available: **{nts}**\n\nKoi aur time likhiye:",7,booking_data)
            booking_data["time"]=user_time.strftime("%I:%M %p")
            if not booking_data.get("date"): booking_data["date"]=datetime.now().strftime("%d %B %Y")
            try: ok,reply=save_booking_to_db(booking_data,barbers_list)
            except Exception as e: reply=f"❌ Error: {str(e)}"
            session_clear(session_id)
            return {"reply":reply,"booking_step":0,"booking_data":{},"session_id":session_id}

    # ============================================================
    # NORMAL FLOW
    # ============================================================
    else:
        yes_words=["haan","han","yes","hna","ok","okay","bilkul"]
        is_yes=any(w in lower_prompt.split() for w in yes_words)
        last_assistant=""
        for msg in reversed(req.messages[:-1]):
            if msg.role=="assistant": last_assistant=msg.content.lower(); break
        booking_was_asked=any(w in last_assistant for w in ["booking karwni hai","booking karna","book"])
        if is_yes and booking_was_asked:
            return ret("👍 Theek hai! Apna **naam** bataiye:",1,{})
        else:
            extracted=detect_intent_and_extract(prompt,barbers_list,services_list,data["today_date"],data["today_name"])
            intent=extracted.get("intent","other")
            if intent=="booking":
                booking_data={}
                if extracted.get("name"):    booking_data["name"]=extracted["name"]
                if extracted.get("phone"):   booking_data["phone"]=extracted["phone"]
                if extracted.get("service"): booking_data["service"]=extracted["service"]
                if extracted.get("barber"):
                    match=[b["name"] for b in barbers_list if extracted["barber"].lower() in b["name"].lower()]
                    if match: booking_data["barber"]=match[0]
                if extracted.get("date"):
                    pd=parse_flexible_date(extracted["date"])
                    if pd and pd.date()>=datetime.now().date() and pd.date()<=(datetime.now()+timedelta(days=7)).date():
                        booking_data["date"]=pd.strftime("%d %B %Y")
                if extracted.get("time"):
                    pt=parse_flexible_time(extracted["time"])
                    if pt: booking_data["time"]=pt.strftime("%I:%M %p")
                if not booking_data.get("name"): return ret("👍 Booking shuru! Apna **naam** bataiye:",1,booking_data)
                if not booking_data.get("phone"): return ret(f"👋 Shukriya **{booking_data['name']}**! Apna **phone number** bataiye:","need_phone",booking_data)
                if not booking_data.get("service"):
                    svc_names=get_service_names(booking_data,barbers_list,services_list)
                    barber_name=booking_data.get("barber","")
                    msg=f"💇 **{barber_name}** ki services select karein:" if barber_name else "💇 Kaunsi service chahiye? Select karein:"
                    return ret(msg,2,booking_data,{"show_services":svc_names})
                step,rep=_resolve_after_service(booking_data,barbers_list,services_list)
                svc_names=get_service_names(booking_data,barbers_list,services_list)
                if step==2: return ret(rep,step,booking_data,{"show_services":svc_names})
                return ret(rep,step,booking_data)
            else:
                reply=""
                found_barber=None
                for b in barbers_list:
                    if b["name"].lower() in lower_prompt: found_barber=b["name"]; break
                schedule_words=["free ha","free hai","available ha","available hai","koi booking","schedule"]
                if found_barber and any(w in lower_prompt for w in schedule_words):
                    try:
                        br=next((b for b in barbers_list if b["name"]==found_barber),None)
                        bid=br["id"] if br else None; tim=br.get("timing","N/A") if br else "N/A"
                        check_date=data["today_date"]
                        if any(w in lower_prompt for w in ["kal","kl","tomorrow","tmrw"]):
                            check_date=(datetime.now()+timedelta(days=1)).strftime("%d %B %Y")
                        elif any(w in lower_prompt for w in ["parson","parso","prson"]):
                            check_date=(datetime.now()+timedelta(days=2)).strftime("%d %B %Y")
                        check_dt=datetime.strptime(check_date,"%d %B %Y"); check_day=check_dt.strftime("%A")
                        barber_off=br.get("off_day","") if br else ""
                        off_list=[d.strip().lower() for d in str(barber_off).split(",") if d.strip()]
                        if check_day.lower() in off_list:
                            reply=f"❌ **{found_barber}** ka {check_day} ({check_date}) off hai!\n\n⏰ Timing: {tim}"
                        else:
                            bks=supabase.table("bookings").select("booking_time,service_name").eq("barber_id",bid).eq("booking_date",check_date).execute().data or []
                            date_label="Aaj" if check_date==data["today_date"] else check_date
                            if not bks: reply=f"✅ **{found_barber}** {date_label} free hai!\n\n⏰ Timing: {tim}"
                            else:
                                slots="".join(f"• {b['booking_time']} — {b.get('service_name','N/A')}\n" for b in bks)
                                reply=f"📋 **{found_barber}** ki {date_label} ki appointments:\n\n{slots}\n⏰ Timing: {tim}"
                    except: reply=""
                if not reply:
                    msgs_ai=[{"role":"system","content":system_prompt}]+[{"role":m.role,"content":m.content} for m in req.messages]
                    resp=client.chat.completions.create(model="llama-3.3-70b-versatile",messages=msgs_ai,temperature=0.5,max_tokens=200)
                    reply=resp.choices[0].message.content.strip()
                return {"reply":reply,"booking_step":0,"booking_data":{},"session_id":session_id}

    return {"reply":"Kuch masla hua. Dobara try karein.","booking_step":0,"booking_data":{},"session_id":session_id}

@app.get("/")
async def root():
    return {"status": "Salon Dost API chal rahi hai! ✅"}