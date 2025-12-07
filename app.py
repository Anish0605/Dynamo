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

# --- PAGE SETUP ---
st.set_page_config(page_title="Dynamo AI", page_icon="⚡", layout="wide")

# --- DATABASE SETUP ---
def init_db():
    try:
        conn = sqlite3.connect('dynamo_memory_v5.db')
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT, timestamp DATETIME)')
        c.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT)')
        conn.commit()
        conn.close()
    except: pass

def save_msg_db(sid, role, content):
    try:
        conn = sqlite3.connect('dynamo_memory_v5.db')
        conn.execute('INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)', (sid, role, content))
        conn.commit()
        conn.close()
    except: pass

def get_history_db():
    try:
        conn = sqlite3.connect('dynamo_memory_v5.db')
        c = conn.cursor()
        c.execute("SELECT id, title FROM sessions ORDER BY timestamp DESC LIMIT 10")
        return c.fetchall()
    except: return []

def load_history_db(sid):
    try:
        conn = sqlite3.connect('dynamo_memory_v5.db')
        c = conn.cursor()
        c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id", (sid,))
        return [{"role": row[0], "content": row[1]} for row in c.fetchall()]
    except: return []

init_db()

# --- STATE INIT ---
if "sid" not in st.session_state: 
    st.session_state.sid = str(uuid.uuid4())
    try:
        conn = sqlite3.connect('dynamo_memory_v5.db')
        conn.execute("INSERT INTO sessions (id, title, timestamp) VALUES (?, ?, ?)", (st.session_state.sid, f"Chat {datetime.now().strftime('%H:%M')}", datetime.now()))
        conn.commit()
        conn.close()
    except: pass

if "messages" not in st.session_state: st.session_state.messages = []
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())
if "prompt_trigger" not in st.session_state: st.session_state.prompt_trigger = None

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

# --- UI CSS (PREMIUM STYLE) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    .stApp { background-color: #ffffff; font-family: 'Inter', sans-serif; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { 
        background-color: #F9FAFB; 
        border-right: 1px solid #E5E7EB;
    }
    
    /* Chat Bubbles */
    .stChatMessage { background-color: transparent !important; border: none !important; }
    div[data-testid="stChatMessage"]:nth-child(odd) { 
        background-color: #F3F4F6 !important; 
        border-radius: 20px; 
        padding: 15px 25px; 
        color: #1F2937;
        margin-bottom: 10px;
    }
    div[data-testid="stChatMessage"]:nth-child(even) { 
        background-color: white !important; 
        padding: 15px 0px; 
        color: #1F2937;
    }

    /* Fixed Input Area */
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
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        border: 1px solid #E5E7EB;
        padding-bottom: 0px;
    }
    .stChatInput input { border: none !important; box-shadow: none !important; }

    /* Buttons */
    div.stButton > button {
        border-radius: 20px;
        border: 1px solid #E5E7EB;
        background-color: white;
        color: #374151;
        font-weight: 600;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        border-color: #FFC107;
        color: black;
        background-color: #FFFBEB;
        transform: translateY(-1px);
    }
    
    /* Hide Header */
    header {visibility: hidden;}
    
    /* Spacing for bottom fixed elements */
    .block-container { padding-bottom: 250px; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    c1, c2 = st.columns([1,4])
    with c1: st.markdown("<div style='width:32px;height:32px;border:2px solid #FFC107;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:bold;color:#FFC107;'>⚡</div>", unsafe_allow_html=True)
    with c2: st.markdown("### Dynamo")
    
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.sid = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.uploader_key = str(uuid.uuid4())
        st.rerun()
    
    st.write("---")
    
    # Tool Toggles
    use_search = st.toggle("🌐 Web Search", value=True)
    deep_dive = st.toggle("🤿 Deep Dive", value=False)
    analyst = st.toggle("📊 Analyst Mode", value=False)
    
    st.write("---")
    st.caption("Recent Chats")
    for s_id, s_title in get_history_db():
        if st.button(f"📄 {s_title}", key=s_id, use_container_width=True):
            st.session_state.sid = s_id
            st.session_state.messages = load_history_db(s_id)
            st.rerun()

# --- MAIN AREA ---

# 1. GREETING (Only if empty)
if not st.session_state.messages:
    st.markdown("""
    <div style='text-align: center; margin-top: 15vh; margin-bottom: 30px;'>
        <div style='font-size: 50px; margin-bottom: 20px;'>⚡</div>
        <h1 style='font-weight: 600; color: #111; font-size: 2.5rem; letter-spacing: -0.02em;'>How can I help you?</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick Action Pills (Centered)
    col1, col2, col3 = st.columns([1,1,1])
    if col1.button("🎨 Create Logo", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "Create a futuristic logo for Dynamo AI"})
        st.rerun()
    if col2.button("📊 Analyze Trends", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "Analyze current AI market trends"})
        st.rerun()
    if col3.button("📝 Summarize", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "Summarize what I can do here."})
        st.rerun()

# 2. CHAT HISTORY
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "IMAGE::" in msg["content"]: 
            st.image(msg["content"].replace("IMAGE::", ""))
        elif "CHART::" in msg["content"]:
            try: st.bar_chart(pd.DataFrame(json.loads(msg["content"].replace("CHART::",""))))
            except: st.write("Chart Error")
        else: 
            st.write(msg["content"])

# --- PERSISTENT CONTROLS (Bottom Fixed) ---
# We put these in a container to keep them near the input
with st.container():
    c_voice, c_upload = st.columns([5, 1])
    
    with c_voice:
        # Voice Input
        voice = st.audio_input("🎙️ Voice")
        
    with c_upload:
        # File Uploader (Acts as 'Clip')
        with st.expander("📎", expanded=False):
            img = st.file_uploader("Upload", type=["png", "jpg", "jpeg"], label_visibility="collapsed", key=st.session_state.uploader_key)

# Voice Logic
if voice:
    try:
        txt = client.audio.transcriptions.create(model="whisper-large-v3-turbo", file=("audio.wav", voice), response_format="text")
        st.session_state.messages.append({"role":"user", "content":txt})
        save_msg_db(st.session_state.sid, "user", txt)
        st.rerun()
    except: st.error("Voice Error")

# 3. INPUT HANDLING
chat_input_val = st.chat_input("Message Dynamo...")

# Determine Final Prompt
prompt = chat_input_val

# 4. LOGIC ENGINE
if prompt:
    # Save User Input
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_msg_db(st.session_state.sid, "user", prompt)
    with st.chat_message("user"): st.write(prompt)

    # Generate Response
    with st.chat_message("assistant"):
        
        # A. IMAGE GEN
        if "image" in prompt.lower() and ("generate" in prompt.lower() or "create" in prompt.lower() or "draw" in prompt.lower()):
            with st.spinner("Painting..."):
                try:
                    url = generate_image(prompt)
                    st.image(url)
                    save_msg_db(st.session_state.sid, "assistant", f"IMAGE::{url}")
                    st.session_state.messages.append({"role": "assistant", "content": f"IMAGE::{url}"})
                except: st.error("Image Gen Error")
        
        # B. VISION
        elif img:
            with st.status("Analyzing Image..."):
                try:
                    b64 = encode_image(img).split(",")[1]
                    mime = img.type if img.type else "image/jpeg"
                    resp = client.chat.completions.create(
                        model="llama-3.2-11b-vision-preview", # Updated to active model
                        messages=[{"role":"user", "content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}"}}]}]
                    ).choices[0].message.content
                    st.write(resp)
                    save_msg_db(st.session_state.sid, "assistant", resp)
                    st.session_state.messages.append({"role": "assistant", "content": resp})
                except Exception as e: st.error(f"Vision Error: {e}")

        # C. TEXT / SEARCH / ANALYST
        else:
            container = st.empty()
            context = ""
            
            # Search
            if use_search:
                with st.status("Searching...", expanded=False):
                    try:
                        res = tavily.search(query=prompt)
                        context = "\n".join([r['content'] for r in res['results']])
                    except: pass
            
            # Context Building (Fix for Summarizer)
            # We must include previous messages so the AI knows what to summarize!
            history_context = ""
            # Grab last 10 messages to keep context window manageable
            for m in st.session_state.messages[-10:]:
                if "IMAGE::" not in m["content"] and "CHART::" not in m["content"]:
                    history_context += f"{m['role']}: {m['content']}\n"

            sys_prompt = f"""
            You are Dynamo AI. 
            CONTEXT FROM WEB: {context}
            CHAT HISTORY: {history_context}
            INSTRUCTION: Use the Chat History to answer questions like 'Summarize' or 'Explain'. If Analyst Mode is on, return ONLY JSON.
            """
            
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
                
                save_msg_db(st.session_state.sid, "assistant", content_to_save)
                st.session_state.messages.append({"role": "assistant", "content": content_to_save})
            except Exception as e: st.error(f"Error: {e}")
