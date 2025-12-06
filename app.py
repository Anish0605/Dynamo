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
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT, timestamp DATETIME)''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT)''')
        conn.commit()
        conn.close()
    except: pass

def save_message(session_id, role, content):
    try:
        conn = sqlite3.connect('dynamo_memory.db')
        c = conn.cursor()
        c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, role, content))
        conn.commit()
        conn.close()
    except: pass

def get_history():
    try:
        conn = sqlite3.connect('dynamo_memory.db')
        c = conn.cursor()
        c.execute("SELECT id, title FROM sessions ORDER BY timestamp DESC LIMIT 10")
        return c.fetchall()
    except: return []

def load_history(session_id):
    try:
        conn = sqlite3.connect('dynamo_memory.db')
        c = conn.cursor()
        c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id", (session_id,))
        return [{"role": row[0], "content": row[1]} for row in c.fetchall()]
    except: return []

init_db()

# --- STATE ---
if "session_id" not in st.session_state: 
    st.session_state.session_id = str(uuid.uuid4())
    try:
        conn = sqlite3.connect('dynamo_memory.db')
        c = conn.cursor()
        c.execute("INSERT INTO sessions (id, title, timestamp) VALUES (?, ?, ?)", (st.session_state.session_id, f"Chat {datetime.now().strftime('%H:%M')}", datetime.now()))
        conn.commit()
        conn.close()
    except: pass

if "messages" not in st.session_state: st.session_state.messages = []
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())

# --- KEYS ---
groq_key = st.secrets.get("GROQ_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")
if not groq_key: st.stop()

groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
tavily_client = TavilyClient(api_key=tavily_key)

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

# --- UI CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    .stApp { background-color: #ffffff; font-family: 'Inter', sans-serif; }
    
    /* Give space for fixed input bar at bottom */
    .block-container { padding-bottom: 200px !important; }
    
    [data-testid="stSidebar"] { background-color: #F9FAFB; border-right: 1px solid #E5E7EB; }
    .stChatMessage { background-color: transparent !important; border: none !important; }
    div[data-testid="stChatMessage"]:nth-child(odd) { background-color: #F3F4F6 !important; border-radius: 20px; padding: 10px 20px; margin-bottom: 10px; color: #1F2937; }
    div[data-testid="stChatMessage"]:nth-child(even) { background-color: #FFFFFF !important; padding: 10px 0px; color: #1F2937; }
    div.stButton > button { border-radius: 12px; border: 1px solid #E5E7EB; background-color: white; color: #374151; font-weight: 500; }
    div.stButton > button:hover { border-color: #FFC107; color: black; background-color: #FFFBEB; }
    header {visibility: hidden;}
    
    /* Sticky Footer Logic for Voice & Quick Actions */
    .sticky-footer {
        position: fixed;
        bottom: 90px; /* Above the chat input */
        left: 50%;
        transform: translateX(-40%);
        width: 60%;
        max-width: 800px;
        z-index: 998;
        background: transparent;
        padding-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Input CSS (Dynamic)
if not st.session_state.messages:
    st.markdown("""<style>[data-testid="stChatInput"] { position: fixed; top: 50%; left: 58%; transform: translate(-50%, -50%); width: 50%; max-width: 700px; z-index: 999; }</style>""", unsafe_allow_html=True)
else:
    st.markdown("""<style>[data-testid="stChatInput"] { position: fixed; bottom: 30px; left: 58%; transform: translateX(-50%); width: 60%; max-width: 800px; }</style>""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    col1, col2 = st.columns([1, 4])
    with col1: st.markdown("<div style='width:32px;height:32px;border:2px solid #FFC107;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:bold;color:#FFC107;'>⚡</div>", unsafe_allow_html=True)
    with col2: st.markdown("### Dynamo")
    st.write("")
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.uploader_key = str(uuid.uuid4())
        st.rerun()
    
    with st.expander("👁️ Dynamo Vision"):
        uploaded_img = st.file_uploader("Upload Image", type=["jpg", "png", "jpeg", "webp"], key=st.session_state.uploader_key)
        vision_data = encode_image(uploaded_img)
        if vision_data: st.success("Ready")

    use_search = st.toggle("🌐 Web Search", value=True)
    analyst_mode = st.toggle("📊 Analyst Mode", value=False)
    
    st.caption("HISTORY")
    for s_id, s_title in get_history():
        if st.button(f"📄 {s_title}", key=s_id, use_container_width=True):
            st.session_state.session_id = s_id
            st.session_state.messages = load_history(s_id)
            st.session_state.uploader_key = str(uuid.uuid4())
            st.rerun()

# --- MAIN ---
if not st.session_state.messages and not vision_data:
    st.markdown("<div style='text-align: center; margin-top: 20vh; margin-bottom: 20px;'><h1 style='font-weight: 600; color: #111;'>How can I help you?</h1></div>", unsafe_allow_html=True)
    
    with st.container():
        col1, col2 = st.columns(2)
        if col1.button("🎨 Create a logo", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "Create a futuristic logo for a tech startup"})
            st.rerun()
        if col2.button("📊 Analyze trends", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "Analyze current market trends in AI"})
            st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "IMAGE::" in msg["content"]: st.image(msg["content"].replace("IMAGE::", ""))
        elif "CHART::" in msg["content"]: 
            try: st.bar_chart(pd.DataFrame(json.loads(msg["content"].replace("CHART::", ""))))
            except: st.write("Error rendering chart")
        else: st.write(msg["content"])

# --- INPUT LOGIC & BUTTONS ---
# 1. Capture Inputs
final_prompt = None

# Quick Actions Row (Visible only if chat has started or user wants shortcuts)
if st.session_state.messages:
    c1, c2, c3 = st.columns(3)
    if c1.button("📝 Summarize", use_container_width=True): final_prompt = "Summarize our conversation so far."
    if c2.button("🕵️ Fact Check", use_container_width=True): final_prompt = "Verify the facts in the last response."
    if c3.button("👶 Explain Simple", use_container_width=True): final_prompt = "Explain the last concept like I am 5."

# Voice Input (Always Visible)
voice_input = st.audio_input("🎙️ Voice Mode") # Streamlit will render a mic icon

# Text Input
text_input = st.chat_input("Message Dynamo...")

# 2. Determine Source
if final_prompt: 
    pass # Button clicked
elif voice_input:
    # Transcribe
    try:
        transcription = groq_client.audio.transcriptions.create(
            model="whisper-large-v3-turbo", file=("audio.wav", voice_input), response_format="text"
        )
        final_prompt = transcription
    except: st.error("Voice Error")
elif text_input:
    final_prompt = text_input

# 3. Process
if final_prompt:
    st.session_state.messages.append({"role": "user", "content": final_prompt})
    save_message(st.session_state.session_id, "user", final_prompt)
    with st.chat_message("user"): st.write(final_prompt)

    with st.chat_message("assistant"):
        # Image Gen
        if "image" in final_prompt.lower() and ("generate" in final_prompt.lower() or "create" in final_prompt.lower() or "draw" in final_prompt.lower()):
            with st.spinner("Painting..."):
                try:
                    img_url = generate_image(final_prompt)
                    st.image(img_url)
                    save_message(st.session_state.session_id, "assistant", f"IMAGE::{img_url}")
                    st.session_state.messages.append({"role": "assistant", "content": f"IMAGE::{img_url}"})
                except: st.error("Image Gen Error")
        # Vision
        elif vision_data:
            with st.status("Analyzing Image..."):
                try:
                    resp = groq_client.chat.completions.create(
                        model="llama-3.2-90b-vision-preview",
                        messages=[{"role": "user", "content": [{"type": "text", "text": final_prompt}, {"type": "image_url", "image_url": {"url": vision_data}}]}]
                    ).choices[0].message.content
                    st.write(resp)
                    save_message(st.session_state.session_id, "assistant", resp)
                    st.session_state.messages.append({"role": "assistant", "content": resp})
                except Exception as e: st.error(f"Vision Error: {e}")
        # Standard Chat
        else:
            container = st.empty()
            context = ""
            if use_search:
                try:
                    res = tavily_client.search(query=final_prompt)
                    context = "\n".join([r['content'] for r in res['results']])
                except: pass
            
            # Append history for context (Crucial for Summarize/Fact Check)
            history_context = ""
            for msg in st.session_state.messages[-5:]:
                if not "IMAGE::" in msg["content"]:
                    history_context += f"{msg['role']}: {msg['content']}\n"

            sys_prompt = f"Context from Search: {context}. Chat History: {history_context}."
            if analyst_mode or "plot" in final_prompt.lower() or "chart" in final_prompt.lower(): sys_prompt += " If user asks for a chart, return ONLY JSON object. Example: {\"Category\": [\"A\", \"B\"], \"Value\": [10, 20]}."
            
            try:
                stream = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": final_prompt}],
                    stream=True
                )
                full_response = ""
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                        container.write(full_response)
                
                json_data = extract_json(full_response)
                if json_data and (analyst_mode or "plot" in final_prompt.lower() or "chart" in final_prompt.lower()):
                    st.bar_chart(pd.DataFrame(json_data))
                    save_msg = f"CHART::{json.dumps(json_data)}"
                else: save_msg = full_response
                
                save_message(st.session_state.session_id, "assistant", save_msg)
                st.session_state.messages.append({"role": "assistant", "content": save_msg})
            except Exception as e: st.error(f"API Error: {e}")
