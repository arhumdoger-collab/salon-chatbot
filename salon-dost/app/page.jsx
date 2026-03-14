"use client";
import { useState, useEffect, useRef } from "react";

export default function Home() {
  const [chatOpen, setChatOpen]         = useState(false);
  const [messages, setMessages]         = useState([]);
  const [input, setInput]               = useState("");
  const [loading, setLoading]           = useState(false);
  const [scrolled, setScrolled]         = useState(false);
  const [bookingStep, setBookingStep]   = useState(0);
  const [bookingData, setBookingData]   = useState({});
  const [showServices, setShowServices] = useState([]);
  const [selectedSvcs, setSelectedSvcs] = useState({});
  const [sessionId, setSessionId]       = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", fn);
    return () => window.removeEventListener("scroll", fn);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, showServices]);

  const callAPI = async (msgs, step, data) => {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages:     msgs,
        booking_step: step,
        booking_data: data,   // ✅ booking_data bhi bhejo
        session_id:   sessionId,
      }),
    });
    return await res.json();
  };

  const sendMessage = async (overrideText) => {
    const text = (overrideText || input).trim();
    if (!text) return;
    const userMsg     = { role: "user", content: text };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setLoading(true);
    try {
      const result = await callAPI(newMessages, bookingStep, bookingData);
      setBookingStep(result.booking_step ?? 0);
      setBookingData(prev => ({ ...prev, ...(result.booking_data ?? {}) }));
      if (result.session_id) setSessionId(result.session_id);

      if (result.show_services?.length > 0) {
        setShowServices(result.show_services);
        const init = {};
        result.show_services.forEach(s => init[s] = false);
        setSelectedSvcs(init);
      } else {
        setShowServices([]);
      }
      setMessages([...newMessages, { role: "assistant", content: result.reply }]);
    } catch (e) {
      setMessages([...newMessages, { role: "assistant", content: "❌ Error aayi. Dobara try karein." }]);
    }
    setLoading(false);
  };

  const confirmServices = async () => {
    const selected = Object.entries(selectedSvcs).filter(([,v]) => v).map(([k]) => k);
    if (!selected.length) return;

    // ✅ Service bookingData mein save karo
    const newData = { ...bookingData, service: selected.join(", ") };
    setBookingData(newData);
    setShowServices([]);
    setSelectedSvcs({});
    setLoading(true);

    const botMsg  = { role: "assistant", content: `✅ Services: **${selected.join(", ")}**` };
    const newMsgs = [...messages, botMsg];
    setMessages(newMsgs);

    try {
      // ✅ newData (service included) bhejo step 3 ke saath
      const result = await callAPI(
        [...newMsgs, { role: "user", content: "service selected" }],
        3,
        newData  // ✅ yahan service set hai
      );
      setBookingStep(result.booking_step ?? 0);
      // ✅ Merge — service ko overwrite mat karo
      setBookingData(prev => ({ ...prev, ...newData, ...(result.booking_data ?? {}) }));
      if (result.session_id) setSessionId(result.session_id);

      // ✅ Agar dobara show_services aaye (error case) to dikhao
      if (result.show_services?.length > 0) {
        setShowServices(result.show_services);
        const init = {};
        result.show_services.forEach(s => init[s] = false);
        setSelectedSvcs(init);
      } else {
        setShowServices([]);
      }

      setMessages([...newMsgs, { role: "assistant", content: result.reply }]);
    } catch (e) {
      setMessages([...newMsgs, { role: "assistant", content: "❌ Error aayi." }]);
    }
    setLoading(false);
  };

  const staticServices = [
    { name: "Hair Cutting", urdu: "ہیئر کٹنگ", price: "Rs. 150-200", duration: "30 min", icon: "✂️" },
    { name: "Beard",        urdu: "داڑھی",      price: "Rs. 100",     duration: "20 min", icon: "🪒" },
    { name: "Massage",      urdu: "مساج",       price: "Rs. 120",     duration: "60 min", icon: "🙌" },
    { name: "Color",        urdu: "کلر",        price: "Rs. 300",     duration: "90 min", icon: "🎨" },
  ];

  const staticBarbers = [
    { name: "Ahmed", specialty: "Hair Cutting", timing: "10AM - 8PM", off: "Sunday",    emoji: "👨‍🦱" },
    { name: "Bilal", specialty: "Hair Cutting", timing: "12PM - 8PM", off: "Monday",    emoji: "👨‍🦳" },
    { name: "Amir",  specialty: "Color & Cut",  timing: "11AM - 9PM", off: "Tuesday",   emoji: "👨‍🦲" },
    { name: "Sajid", specialty: "Massage",      timing: "9AM - 9PM",  off: "Tuesday",   emoji: "🧔"  },
  ];

  return (
    <div style={{ background:"#1a0f0a", fontFamily:"Georgia,serif", minHeight:"100vh" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Lora:ital,wght@0,400;0,600;1,400&display=swap');
        *{box-sizing:border-box;margin:0;padding:0}
        .pf{font-family:'Playfair Display',serif} .lr{font-family:'Lora',serif}
        .gold{color:#c9a84c} .cream{color:#f5e6c8}
        .stripe{background:repeating-linear-gradient(45deg,#8b1a1a,#8b1a1a 10px,#fff 10px,#fff 20px,#1a3a8b 20px,#1a3a8b 30px)}
        .scard{background:linear-gradient(135deg,#2a1a0e,#1a0f0a);border:1px solid #c9a84c44;border-radius:4px;padding:24px;transition:all .3s}
        .scard:hover{border-color:#c9a84c;transform:translateY(-4px);box-shadow:0 8px 24px #c9a84c22}
        .bcard{background:linear-gradient(180deg,#2a1a0e,#1a0f0a);border:1px solid #c9a84c44;border-top:3px solid #c9a84c;padding:28px;text-align:center;transition:all .3s}
        .bcard:hover{box-shadow:0 12px 32px #c9a84c22;transform:translateY(-4px)}
        .btn{background:linear-gradient(135deg,#c9a84c,#a07830);color:#1a0f0a;border:none;padding:14px 32px;font-family:'Playfair Display',serif;font-weight:700;font-size:16px;cursor:pointer;transition:all .3s;letter-spacing:1px}
        .btn:hover{background:linear-gradient(135deg,#d4b85a,#c9a84c);transform:translateY(-2px);box-shadow:0 6px 20px #c9a84c44}
        .nlink{color:#c9a84c;text-decoration:none;font-family:'Lora',serif;font-size:14px;letter-spacing:2px;text-transform:uppercase;transition:color .2s}
        .nlink:hover{color:#f5e6c8}
        .ub{background:linear-gradient(135deg,#c9a84c,#a07830);color:#1a0f0a;border-radius:18px 18px 4px 18px;padding:10px 16px;max-width:75%;font-family:'Lora',serif;font-size:14px;line-height:1.5}
        .ab{background:#2a1a0e;color:#f5e6c8;border:1px solid #c9a84c44;border-radius:18px 18px 18px 4px;padding:10px 16px;max-width:75%;font-family:'Lora',serif;font-size:14px;line-height:1.5;white-space:pre-wrap}
        .cinput{flex:1;background:#2a1a0e;border:1px solid #c9a84c44;color:#f5e6c8;padding:12px 16px;font-family:'Lora',serif;font-size:14px;outline:none;border-radius:4px 0 0 4px}
        .cinput:focus{border-color:#c9a84c} .cinput::placeholder{color:#8a7050}
        .sbtn{background:#c9a84c;color:#1a0f0a;border:none;padding:12px 20px;cursor:pointer;font-weight:700;font-size:18px;border-radius:0 4px 4px 0;transition:background .2s}
        .sbtn:hover{background:#d4b85a} .sbtn:disabled{opacity:.5;cursor:not-allowed}
        .svcc{display:flex;align-items:center;gap:8px;padding:8px 12px;border:1px solid #c9a84c44;border-radius:4px;cursor:pointer;transition:all .2s;margin-bottom:6px}
        .svcc:hover{border-color:#c9a84c;background:#c9a84c11} .svcc.on{border-color:#c9a84c;background:#c9a84c22}
        .td{width:6px;height:6px;background:#c9a84c;border-radius:50%;animation:tp 1.4s infinite}
        .td:nth-child(2){animation-delay:.2s}.td:nth-child(3){animation-delay:.4s}
        @keyframes tp{0%,60%,100%{transform:translateY(0);opacity:.4}30%{transform:translateY(-6px);opacity:1}}
        @keyframes fi{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
        .fi{animation:fi .8s ease forwards}
        ::-webkit-scrollbar{width:6px} ::-webkit-scrollbar-track{background:#1a0f0a}
        ::-webkit-scrollbar-thumb{background:#c9a84c44;border-radius:3px}
      `}</style>

      {/* NAV */}
      <nav style={{position:"fixed",top:0,left:0,right:0,zIndex:100,background:scrolled?"rgba(26,15,10,0.97)":"transparent",borderBottom:scrolled?"1px solid #c9a84c44":"none",padding:"16px 48px",display:"flex",justifyContent:"space-between",alignItems:"center",transition:"all .3s",backdropFilter:scrolled?"blur(10px)":"none"}}>
        <div className="pf gold" style={{fontSize:"22px",fontWeight:900,letterSpacing:"2px"}}>✂️ SALON DOST</div>
        <div style={{display:"flex",gap:"32px",alignItems:"center"}}>
          <a href="#services" className="nlink">Services</a>
          <a href="#barbers"  className="nlink">Barbers</a>
          <a href="#contact"  className="nlink">Contact</a>
          <button className="nlink" onClick={()=>setChatOpen(true)} style={{background:"none",border:"1px solid #c9a84c",padding:"6px 16px",cursor:"pointer",borderRadius:"2px"}}>Book Now</button>
        </div>
      </nav>

      {/* HERO */}
      <section style={{minHeight:"100vh",background:"linear-gradient(180deg,#0d0705 0%,#1a0f0a 50%,#2a1510 100%)",display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",textAlign:"center",padding:"80px 24px 40px",position:"relative",overflow:"hidden"}}>
        <div className="stripe" style={{position:"absolute",top:0,left:0,right:0,height:"6px"}}/>
        <div className="stripe" style={{position:"absolute",bottom:0,left:0,right:0,height:"6px"}}/>
        <div style={{position:"absolute",left:"5%",top:"50%",transform:"translateY(-50%)",opacity:.06,fontSize:"200px"}}>💈</div>
        <div style={{position:"absolute",right:"5%",top:"50%",transform:"translateY(-50%)",opacity:.06,fontSize:"200px"}}>✂️</div>
        <div className="fi">
          <div className="lr gold" style={{letterSpacing:"6px",fontSize:"13px",textTransform:"uppercase",marginBottom:"16px"}}>— Est. 2024 — Lahore, Pakistan —</div>
          <h1 className="pf cream" style={{fontSize:"clamp(48px,8vw,96px)",fontWeight:900,lineHeight:1.1,marginBottom:"8px"}}>SALON</h1>
          <h1 className="pf gold"  style={{fontSize:"clamp(48px,8vw,96px)",fontWeight:900,lineHeight:1.1,marginBottom:"24px"}}>DOST</h1>
          <div style={{display:"flex",alignItems:"center",gap:"12px",maxWidth:"300px",margin:"0 auto 24px"}}>
            <div style={{flex:1,height:"1px",background:"#c9a84c"}}/>
            <span className="lr gold" style={{fontSize:"13px",letterSpacing:"3px"}}>✦ PREMIUM BARBERSHOP ✦</span>
            <div style={{flex:1,height:"1px",background:"#c9a84c"}}/>
          </div>
          <p className="lr cream" style={{fontSize:"18px",maxWidth:"480px",margin:"0 auto 40px",opacity:.8,fontStyle:"italic",lineHeight:1.8}}>"Where every cut tells a story — tradition meets perfection"</p>
          <div style={{display:"flex",gap:"16px",justifyContent:"center",flexWrap:"wrap"}}>
            <button className="btn" onClick={()=>setChatOpen(true)}>📅 Book Appointment</button>
            <a href="#services"><button className="btn" style={{background:"transparent",color:"#c9a84c",border:"1px solid #c9a84c"}}>View Services</button></a>
          </div>
          <div style={{marginTop:"48px",display:"flex",gap:"48px",justifyContent:"center",flexWrap:"wrap"}}>
            {[["500+","Happy Clients"],["4","Expert Barbers"],["4+","Services"],["5★","Rating"]].map(([n,l])=>(
              <div key={l} style={{textAlign:"center"}}>
                <div className="pf gold" style={{fontSize:"32px",fontWeight:900}}>{n}</div>
                <div className="lr cream" style={{fontSize:"12px",letterSpacing:"2px",opacity:.7,textTransform:"uppercase"}}>{l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* SERVICES */}
      <section id="services" style={{padding:"80px 48px",background:"#150a05"}}>
        <div style={{maxWidth:"1100px",margin:"0 auto"}}>
          <div style={{textAlign:"center",marginBottom:"56px"}}>
            <div className="lr gold" style={{letterSpacing:"4px",fontSize:"12px",textTransform:"uppercase",marginBottom:"12px"}}>What We Offer</div>
            <h2 className="pf cream" style={{fontSize:"48px",fontWeight:900}}>Our Services</h2>
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(250px,1fr))",gap:"24px"}}>
            {staticServices.map(s=>(
              <div key={s.name} className="scard">
                <div style={{fontSize:"36px",marginBottom:"12px"}}>{s.icon}</div>
                <h3 className="pf cream" style={{fontSize:"20px",marginBottom:"4px"}}>{s.name}</h3>
                <p className="lr gold" style={{fontSize:"13px",marginBottom:"12px",opacity:.8}}>{s.urdu}</p>
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                  <span className="pf gold" style={{fontSize:"20px",fontWeight:700}}>{s.price}</span>
                  <span className="lr cream" style={{fontSize:"12px",opacity:.6}}>{s.duration}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* BARBERS */}
      <section id="barbers" style={{padding:"80px 48px",background:"#1a0f0a"}}>
        <div style={{maxWidth:"900px",margin:"0 auto"}}>
          <div style={{textAlign:"center",marginBottom:"56px"}}>
            <div className="lr gold" style={{letterSpacing:"4px",fontSize:"12px",textTransform:"uppercase",marginBottom:"12px"}}>Meet The Team</div>
            <h2 className="pf cream" style={{fontSize:"48px",fontWeight:900}}>Our Barbers</h2>
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(200px,1fr))",gap:"24px"}}>
            {staticBarbers.map(b=>(
              <div key={b.name} className="bcard">
                <div style={{fontSize:"48px",marginBottom:"12px"}}>{b.emoji}</div>
                <h3 className="pf cream" style={{fontSize:"22px",fontWeight:700,marginBottom:"6px"}}>{b.name}</h3>
                <p className="lr gold" style={{fontSize:"12px",marginBottom:"12px",fontStyle:"italic"}}>{b.specialty}</p>
                <div style={{borderTop:"1px solid #c9a84c22",paddingTop:"12px"}}>
                  <p className="lr cream" style={{fontSize:"11px",opacity:.7,marginBottom:"4px"}}>⏰ {b.timing}</p>
                  <p className="lr cream" style={{fontSize:"11px",opacity:.7}}>📅 Off: {b.off}</p>
                </div>
                <button className="btn" onClick={()=>setChatOpen(true)} style={{marginTop:"16px",padding:"8px 20px",fontSize:"12px",width:"100%"}}>Book with {b.name}</button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CONTACT */}
      <section id="contact" style={{padding:"80px 48px",background:"#0d0705"}}>
        <div style={{maxWidth:"700px",margin:"0 auto",textAlign:"center"}}>
          <div className="lr gold" style={{letterSpacing:"4px",fontSize:"12px",textTransform:"uppercase",marginBottom:"12px"}}>Find Us</div>
          <h2 className="pf cream" style={{fontSize:"48px",fontWeight:900,marginBottom:"40px"}}>Contact Us</h2>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:"24px",marginBottom:"48px"}}>
            {[{icon:"📍",label:"Address",value:"Main Boulevard, Lahore"},{icon:"📞",label:"Phone",value:"0300-1234567"},{icon:"⏰",label:"Hours",value:"9AM - 10PM Daily"}].map(it=>(
              <div key={it.label} style={{background:"#1a0f0a",border:"1px solid #c9a84c44",padding:"24px",borderRadius:"4px"}}>
                <div style={{fontSize:"28px",marginBottom:"8px"}}>{it.icon}</div>
                <div className="lr gold" style={{fontSize:"11px",letterSpacing:"2px",textTransform:"uppercase",marginBottom:"8px"}}>{it.label}</div>
                <div className="lr cream" style={{fontSize:"14px",opacity:.9}}>{it.value}</div>
              </div>
            ))}
          </div>
          <button className="btn" onClick={()=>setChatOpen(true)} style={{fontSize:"18px",padding:"18px 48px"}}>💬 Chat & Book Now</button>
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{background:"#0a0503",borderTop:"1px solid #c9a84c22",padding:"32px 48px",textAlign:"center"}}>
        <div className="stripe" style={{height:"4px",marginBottom:"24px",borderRadius:"2px"}}/>
        <div className="pf gold" style={{fontSize:"20px",fontWeight:900,marginBottom:"8px"}}>✂️ SALON DOST</div>
        <p className="lr cream" style={{fontSize:"13px",opacity:.5}}>© 2024 Salon Dost, Lahore. All rights reserved.</p>
      </footer>

      {/* FLOAT BTN */}
      {!chatOpen && (
        <button onClick={()=>setChatOpen(true)} style={{position:"fixed",bottom:"32px",right:"32px",zIndex:200,background:"linear-gradient(135deg,#c9a84c,#a07830)",border:"none",borderRadius:"50%",width:"64px",height:"64px",fontSize:"28px",cursor:"pointer",boxShadow:"0 4px 20px #c9a84c66",transition:"transform .2s"}}
          onMouseEnter={e=>e.currentTarget.style.transform="scale(1.1)"}
          onMouseLeave={e=>e.currentTarget.style.transform="scale(1)"}
        >💬</button>
      )}

      {/* CHAT */}
      {chatOpen && (
        <div style={{position:"fixed",bottom:"24px",right:"24px",zIndex:300,width:"380px",height:"580px",background:"#1a0f0a",border:"1px solid #c9a84c",borderRadius:"8px",display:"flex",flexDirection:"column",boxShadow:"0 20px 60px rgba(0,0,0,.8)",overflow:"hidden",animation:"fi .3s ease"}}>
          <div style={{background:"linear-gradient(135deg,#2a1a0e,#1a0f0a)",borderBottom:"1px solid #c9a84c",padding:"16px 20px",display:"flex",justifyContent:"space-between",alignItems:"center"}}>
            <div>
              <div className="pf gold" style={{fontSize:"16px",fontWeight:700}}>✂️ Salon Dost</div>
              <div className="lr cream" style={{fontSize:"11px",opacity:.6}}>● Online — Poocho kuch bhi!</div>
            </div>
            <button onClick={()=>setChatOpen(false)} style={{background:"none",border:"1px solid #c9a84c44",color:"#c9a84c",width:"28px",height:"28px",borderRadius:"4px",cursor:"pointer",fontSize:"16px"}}>✕</button>
          </div>

          <div style={{flex:1,overflowY:"auto",padding:"16px",display:"flex",flexDirection:"column",gap:"12px"}}>
            {messages.length===0 && (
              <div style={{textAlign:"center",padding:"20px"}}>
                <div style={{fontSize:"40px",marginBottom:"12px"}}>💈</div>
                <p className="lr cream" style={{fontSize:"13px",opacity:.7,lineHeight:1.6}}>Assalam o Alaikum!<br/>Booking karwni hai ya kuch poochna hai?</p>
                <div style={{display:"flex",flexWrap:"wrap",gap:"8px",justifyContent:"center",marginTop:"16px"}}>
                  {["Aaj kaun available hai?","Services kya hain?","Bilal se kal haircut karwani hai"].map(q=>(
                    <button key={q} onClick={()=>sendMessage(q)} style={{background:"none",border:"1px solid #c9a84c44",color:"#c9a84c",padding:"6px 12px",borderRadius:"16px",fontSize:"11px",cursor:"pointer",fontFamily:"Lora,serif"}}>{q}</button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg,i)=>(
              <div key={i} style={{display:"flex",justifyContent:msg.role==="user"?"flex-end":"flex-start",alignItems:"flex-end",gap:"8px"}}>
                {msg.role==="assistant"&&<div style={{width:"28px",height:"28px",borderRadius:"50%",background:"#c9a84c22",border:"1px solid #c9a84c44",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,fontSize:"14px"}}>✂️</div>}
                <div className={msg.role==="user"?"ub":"ab"}>{msg.content}</div>
              </div>
            ))}

            {/* SERVICE SELECTOR */}
            {showServices.length>0 && (
              <div style={{background:"#2a1a0e",border:"1px solid #c9a84c44",borderRadius:"8px",padding:"16px"}}>
                <p className="lr gold" style={{fontSize:"13px",marginBottom:"12px",fontWeight:600}}>💇 Service(s) select karein:</p>
                {showServices.map(svc=>(
                  <div key={svc} className={`svcc ${selectedSvcs[svc]?"on":""}`}
                    onClick={()=>setSelectedSvcs(p=>({...p,[svc]:!p[svc]}))}>
                    <div style={{width:"16px",height:"16px",border:"1px solid #c9a84c",borderRadius:"3px",background:selectedSvcs[svc]?"#c9a84c":"transparent",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
                      {selectedSvcs[svc]&&<span style={{color:"#1a0f0a",fontSize:"11px",fontWeight:700}}>✓</span>}
                    </div>
                    <span className="lr cream" style={{fontSize:"13px"}}>{svc}</span>
                  </div>
                ))}
                <button className="btn" onClick={confirmServices} style={{marginTop:"12px",padding:"10px 20px",fontSize:"13px",width:"100%"}}>✅ Confirm Services</button>
              </div>
            )}

            {loading && (
              <div style={{display:"flex",alignItems:"center",gap:"8px"}}>
                <div style={{width:"28px",height:"28px",borderRadius:"50%",background:"#c9a84c22",border:"1px solid #c9a84c44",display:"flex",alignItems:"center",justifyContent:"center",fontSize:"14px"}}>✂️</div>
                <div style={{display:"flex",gap:"4px",alignItems:"center",background:"#2a1a0e",padding:"12px 16px",borderRadius:"18px"}}>
                  <div className="td"/><div className="td"/><div className="td"/>
                </div>
              </div>
            )}
            <div ref={bottomRef}/>
          </div>

          <div style={{borderTop:"1px solid #c9a84c22",padding:"12px",display:"flex"}}>
            <input className="cinput" placeholder="Yahan likho..." value={input}
              onChange={e=>setInput(e.target.value)}
              onKeyDown={e=>e.key==="Enter"&&sendMessage()}
              disabled={showServices.length>0}
            />
            <button className="sbtn" onClick={()=>sendMessage()} disabled={loading||showServices.length>0}>➤</button>
          </div>
        </div>
      )}
    </div>
  );
}