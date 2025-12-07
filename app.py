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

# --- DATABASE ---
def init_db():
    try:
        conn = sqlite3.connect('dynamo_memory.db')
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT, title TEXT, time TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS messages (sid TEXT, role TEXT, content TEXT)')
        conn.commit()
        conn.close()
    except: pass

def save_msg(sid, role, content):
    try:
        conn = sqlite3.connect('dynamo_memory.db')
        conn.execute('INSERT INTO messages VALUES (?, ?, ?)', (sid, role, content))
        conn.commit()
        conn.close()
    except: pass

def get_history():
    try:
        conn = sqlite3.connect('dynamo_memory.db')
        c = conn.cursor()
        c.execute("SELECT id, title FROM sessions ORDER BY time DESC LIMIT 10")
        return c.fetchall()
    except: return []

def load_history(sid):
    try:
        conn = sqlite3.connect('dynamo_memory.db')
        c = conn.cursor()
        c.execute("SELECT role, content FROM messages WHERE sid = ? ORDER BY rowid", (sid,))
        return [{"role": row[0], "content": row[1]} for row in c.fetchall()]
    except: return []

init_db()

# --- STATE ---
if "sid" not in st.session_state: st.session_state.sid = str(uuid.uuid4())
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
        base64_str = base64.b64encode(bytes_data).decode('utf-8')
        mime = uploaded_file.type if uploaded_file.type else "image/jpeg"
        return f"data:{mime};base64,{base64_str}"
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
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #F9FAFB; border-right: 1px solid #E5E7EB; }
    
    /* Chat Bubbles */
    .stChatMessage { background-color: transparent !important; }
    div[data-testid="stChatMessage"]:nth-child(odd) { background-color: #F3F4F6 !important; color: black; border-radius: 20px; padding: 10px 20px; }
    div[data-testid="stChatMessage"]:nth-child(even) { background-color: white !important; color: black; padding: 10px 0px; }
    
    /* Fixed Input Bar */
    .stChatInput {
        position: fixed;
        bottom: 20px;
        left: 58%;
        transform: translateX(-50%);
        width: 60%;
        max-width: 800px;
        z-index: 1000;
        background: white;
        border-radius: 25px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        padding-bottom: 20px; 
    }
    
    /* Logo */
    .dynamo-logo {
        width: 32px; height: 32px;
        border: 2px solid #FFC107;
        border-radius: 8px;
        display: flex; align-items: center; justify-content: center;
        color: #FFC107; font-weight: bold;
    }

    /* Padding for main content so it doesn't hide behind footer */
    .block-container { padding-bottom: 250px; }
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
        # Log session to DB
        try:
            conn = sqlite3.connect('dynamo_memory.db')
            conn.execute("INSERT INTO sessions VALUES (?, ?, ?)", (st.session_state.sid, f"Chat {datetime.now().strftime('%H:%M')}", datetime.now()))
            conn.commit()
            conn.close()
        except: pass
        st.rerun()
    
    st.write("---")
    
    # TOOLS
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

# --- MAIN CHAT DISPLAY ---
if not st.session_state.messages:
    st.markdown("<h1 style='text-align:center; margin-top:20vh;'>How can I help you?</h1>", unsafe_allow_html=True)
    
    # Hero Suggestions
    cc1, cc2 = st.columns(2)
    if cc1.button("🎨 Create a logo", use_container_width=True):
        st.session_state.messages.append({"role":"user", "content": "Create a futuristic logo for Dynamo AI"})
        st.rerun()
    if cc2.button("📊 Analyze trends", use_container_width=True):
        st.session_state.messages.append({"role":"user", "content": "Analyze current market trends in AI"})
        st.rerun()

# Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "IMAGE::" in msg["content"]: st.image(msg["content"].replace("IMAGE::", ""))
        elif "CHART::" in msg["content"]:
            try: st.bar_chart(pd.DataFrame(json.loads(msg["content"].replace("CHART::",""))))
            except: st.write("Chart Error")
        else: st.write(msg["content"])

# --- INPUT AREA (STICKY BOTTOM) ---
# We use a container to group the "extras" like voice and upload above the chat input
footer_container = st.container()

with footer_container:
    # 1. Quick Actions (Only show if chat exists)
    if st.session_state.messages:
        cols = st.columns(3)
        if cols[0].button("📝 Summarize"): 
            st.session_state.messages.append({"role":"user", "content":"Summarize our conversation so far."})
            st.rerun()
        if cols[1].button("🕵️ Fact Check"): 
            st.session_state.messages.append({"role":"user", "content":"Verify the facts in the last response."})
            st.rerun()
        if cols[2].button("👶 Explain"): 
            st.session_state.messages.append({"role":"user", "content":"Explain the last concept simply."})
            st.rerun()
    
    # 2. Attachments & Voice
    c_voice, c_upload = st.columns([1, 1])
    voice_val = c_voice.audio_input("🎙️ Voice")
    
    # Upload expander acts as the "Clip Icon"
    with c_upload.expander("📎 Attach Image"):
        uploaded_img = st.file_uploader("Upload", type=["png", "jpg", "jpeg"], label_visibility="collapsed", key=st.session_state.uploader_key)

# 3. Main Text Input
prompt = st.chat_input("Message Dynamo...")

# --- LOGIC PROCESSING ---
# Determine what the user "Sent"
user_input = None

if prompt:
    user_input = prompt
elif voice_val:
    try:
        user_input = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo", 
            file=("audio.wav", voice_val), 
            response_format="text"
        )
    except: st.error("Voice Error")

# If we have input, run the AI
if user_input:
    # Save User Message
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_msg(st.session_state.sid, "user", user_input)
    st.rerun() 

# --- AI RESPONSE GENERATION ---
# Check if last message is User. If so, Generate Answer.
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_user_msg = st.session_state.messages[-1]["content"]
    
    with st.chat_message("assistant"):
        # 1. Image Gen
        if "image" in last_user_msg.lower() and ("generate" in last_user_msg.lower() or "create" in last_user_msg.lower()):
            with st.spinner("Painting..."):
                url = generate_image(last_user_msg)
                st.image(url)
                save_msg(st.session_state.sid, "assistant", f"IMAGE::{url}")
                st.session_state.messages.append({"role": "assistant", "content": f"IMAGE::{url}"})
        
        # 2. Vision Analysis (If image attached)
        elif uploaded_img:
            with st.status("Analyzing Image..."):
                b64 = encode_image(uploaded_img).split(",")[1]
                mime = uploaded_img.type if uploaded_img.type else "image/jpeg"
                resp = client.chat.completions.create(
                    model="llama-3.2-90b-vision-preview",
                    messages=[{"role":"user", "content":[{"type":"text","text":last_user_msg},{"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}"}}]}]
                ).choices[0].message.content
                st.write(resp)
                save_msg(st.session_state.sid, "assistant", resp)
                st.session_state.messages.append({"role": "assistant", "content": resp})
        
        # 3. Text Chat
        else:
            container = st.empty()
            context = ""
            
            # Web Search
            if use_search:
                if deep_dive:
                    with st.status("🤿 Deep Diving..."):
                        queries = deep_dive_search(last_user_msg)
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
                        res = tavily.search(query=last_user_msg)
                        context = "\n".join([r['content'] for r in res['results']])
                    except: pass
            
            # Construct Prompt
            history_txt = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-5:-1]]) # Last 5 context
            sys_prompt = f"System: Use this Context: {context}. Chat History: {history_txt}."
            if analyst: sys_prompt += " Return ONLY JSON for charts. Format: [{'Category': 'A', 'Value': 10}, ...]"
            
            try:
                stream = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role":"system", "content":sys_prompt}, {"role":"user", "content":last_user_msg}],
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
                
                save_msg(st.session_state.sid, "assistant", content_to_save)
                st.session_state.messages.append({"role": "assistant", "content": content_to_save})
                # Force rerun to remove the "Running" spinner state cleanly if needed, or just let it sit.
            except Exception as e: st.error(f"Error: {e}")
