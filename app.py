import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import json
import base64
import sqlite3
import uuid
import pandas as pd
from datetime import datetime
import re

st.set_page_config(page_title="Dynamo AI", page_icon="⚡", layout="wide")

# --- DATABASE ENGINE ---
DB_NAME = 'dynamo_db_v3.db' # Version 3 to ensure clean schema

def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT, timestamp DATETIME)''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT)''')
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"DB Error: {e}")

def save_message_to_db(sid, role, content):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (sid, role, content))
        conn.commit()
        conn.close()
    except: pass

def get_history():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT id, title FROM sessions ORDER BY timestamp DESC LIMIT 10")
        return c.fetchall()
    except: return []

def load_history(sid):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id", (sid,))
        return [{"role": row[0], "content": row[1]} for row in c.fetchall()]
    except: return []

init_db()

# --- STATE ---
if "sid" not in st.session_state: 
    st.session_state.sid = str(uuid.uuid4())
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO sessions (id, title, timestamp) VALUES (?, ?, ?)", 
                  (st.session_state.sid, f"Chat {datetime.now().strftime('%H:%M')}", datetime.now()))
        conn.commit()
        conn.close()
    except: pass

if "messages" not in st.session_state: st.session_state.messages = []
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())

# --- KEYS ---
groq_key = st.secrets.get("GROQ_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")
if not groq_key: st.stop()

client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
tavily = TavilyClient(api_key=tavily_key)

# --- FUNCTIONS ---
def encode_image(uploaded_file):
    if not uploaded_file: return None
    try:
        bytes_data = uploaded_file.getvalue()
        b64 = base64.b64encode(bytes_data).decode('utf-8')
        mime = uploaded_file.type if uploaded_file.type else "image/jpeg"
        return f"data:{mime};base64,{b64}"
    except: return None

def generate_image(prompt):
    return f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?nologo=true"

def extract_json(text):
    try:
        match = re.search(r'\{[\s\S]*\}', text)
        if match: return json.loads(match.group(0))
    except: return None

def deep_dive_search(query):
    try:
        sys_prompt = "You are a research planner. Return a JSON object with a key 'queries' containing 3 distinct search queries to answer the user's question."
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": query}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content).get('queries', [query])[:3]
    except: return [query]

# --- UI CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    .stApp { background-color: #ffffff; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background-color: #F9FAFB; border-right: 1px solid #E5E7EB; }
    
    /* Center input when empty */
    .stChatInput {
        position: fixed;
        bottom: 30px;
        left: 58%;
        transform: translateX(-50%);
        width: 60%;
        max-width: 800px;
        z-index: 1000;
        background: white;
        border-radius: 25px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    
    .dynamo-logo {
        width: 32px; height: 32px;
        border: 2px solid #FFC107;
        border-radius: 8px;
        display: flex; align-items: center; justify-content: center;
        color: #FFC107; font-weight: bold;
    }
    
    .stChatMessage { background-color: transparent !important; }
    div[data-testid="stChatMessage"]:nth-child(odd) { background-color: #F3F4F6 !important; color: black; }
    div[data-testid="stChatMessage"]:nth-child(even) { background-color: white !important; color: black; }
    
    /* Spacer for fixed input */
    .block-container { padding-bottom: 150px; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    c1, c2 = st.columns([1,4])
    with c1: st.markdown('<div class="dynamo-logo">⚡</div>', unsafe_allow_html=True)
    with c2: st.markdown("### Dynamo")
    
    if st.button("➕ New Chat"):
        st.session_state.sid = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.uploader_key = str(uuid.uuid4())
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("INSERT INTO sessions (id, title, timestamp) VALUES (?, ?, ?)", 
                      (st.session_state.sid, f"Chat {datetime.now().strftime('%H:%M')}", datetime.now()))
            conn.commit()
            conn.close()
        except: pass
        st.rerun()
    
    with st.expander("👁️ Vision"):
        img = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"], key=st.session_state.uploader_key)
    
    # TOGGLES
    use_search = st.toggle("🌐 Web Search", value=True)
    deep_dive = st.toggle("🤿 Deep Dive Mode", value=False)
    analyst = st.toggle("📊 Analyst Mode", value=False)
    
    st.caption("HISTORY")
    for s_id, s_title in get_history():
        if st.button(f"📄 {s_title}", key=s_id):
            st.session_state.sid = s_id
            st.session_state.messages = load_history(s_id)
            st.session_state.uploader_key = str(uuid.uuid4())
            st.rerun()

# --- MAIN ---
if not st.session_state.messages:
    st.markdown("<h1 style='text-align:center; margin-top:20vh;'>How can I help you?</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    if c1.button("📝 Summarize"): 
        prompt = "Summarize history"
        st.session_state.messages.append({"role":"user","content":prompt})
        save_message_to_db(st.session_state.sid, "user", prompt)
        st.rerun()
    if c2.button("🕵️ Fact Check"): 
        prompt = "Fact check last msg"
        st.session_state.messages.append({"role":"user","content":prompt})
        save_message_to_db(st.session_state.sid, "user", prompt)
        st.rerun()
    if c3.button("👶 Explain"): 
        prompt = "Explain simply"
        st.session_state.messages.append({"role":"user","content":prompt})
        save_message_to_db(st.session_state.sid, "user", prompt)
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "IMAGE::" in msg["content"]: st.image(msg["content"].replace("IMAGE::", ""))
        elif "CHART::" in msg["content"]:
            try: st.bar_chart(pd.DataFrame(json.loads(msg["content"].replace("CHART::",""))))
            except: st.write("Chart Error")
        else: st.write(msg["content"])

# Voice
voice = st.audio_input("🎙️ Voice Mode")
if voice:
    try:
        txt = client.audio.transcriptions.create(model="whisper-large-v3-turbo", file=("audio.wav", voice), response_format="text")
        st.session_state.messages.append({"role":"user", "content":txt})
        save_message_to_db(st.session_state.sid, "user", txt)
        st.rerun()
    except: st.error("Voice Error")

if prompt := st.chat_input("Message Dynamo..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_message_to_db(st.session_state.sid, "user", prompt)
    with st.chat_message("user"): st.write(prompt)

    with st.chat_message("assistant"):
        # 1. Image Generation
        if "image" in prompt.lower() and ("generate" in prompt.lower() or "create" in prompt.lower() or "draw" in prompt.lower()):
            with st.spinner("Painting..."):
                url = generate_image(prompt)
                st.image(url)
                save_message_to_db(st.session_state.sid, "assistant", f"IMAGE::{url}")
                st.session_state.messages.append({"role": "assistant", "content": f"IMAGE::{url}"})
        
        # 2. Vision (Image Analysis)
        elif img:
            with st.status("Analyzing Image..."):
                b64 = encode_image(img).split(",")[1] # Re-encode safely
                mime = img.type if img.type else "image/jpeg"
                resp = client.chat.completions.create(
                    model="llama-3.2-90b-vision-preview",
                    messages=[{"role":"user", "content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}"}}]}]
                ).choices[0].message.content
                st.write(resp)
                save_message_to_db(st.session_state.sid, "assistant", resp)
                st.session_state.messages.append({"role": "assistant", "content": resp})
        
        # 3. Text Chat (Search / Deep Dive / Analyst)
        else:
            container = st.empty()
            context = ""
            
            # Web Search Logic
            if use_search:
                if deep_dive:
                    with st.status("🤿 Deep Diving..."):
                        queries = deep_dive_search(prompt)
                        all_res = []
                        for q in queries:
                            st.write(f"Searching: {q}...")
                            try:
                                res = tavily.search(query=q)
                                all_res.extend([r['content'] for r in res['results']])
                            except: pass
                        context = "\n".join(all_res)
                else:
                    try:
                        res = tavily.search(query=prompt)
                        context = "\n".join([r['content'] for r in res['results']])
                    except: pass
            
            sys_prompt = f"Context: {context}."
            if analyst: sys_prompt += " Return ONLY JSON for charts. Format: [{'Category': 'A', 'Value': 10}, ...]"
            
            try:
                stream = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role":"system", "content":sys_prompt}, {"role":"user", "content":prompt}],
                    stream=True
                )
                full_resp = ""
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        full_resp += chunk.choices[0].delta.content
                        container.write(full_resp)
                
                json_data = extract_json(full_resp)
                
                content_to_save = full_resp
                if json_data and analyst:
                    st.bar_chart(pd.DataFrame(json_data))
                    content_to_save = f"CHART::{json.dumps(json_data)}"
                
                save_message_to_db(st.session_state.sid, "assistant", content_to_save)
                st.session_state.messages.append({"role": "assistant", "content": content_to_save})
            except Exception as e: st.error(f"Error: {e}")
