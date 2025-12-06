import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import PyPDF2
import json
import requests
from io import BytesIO
import base64
import sqlite3
import uuid
import pandas as pd
from datetime import datetime
import re

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Dynamo AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DATABASE ENGINE (MEMORY) ---
def init_db():
    conn = sqlite3.connect('dynamo_memory.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sessions
                 (id TEXT PRIMARY KEY, title TEXT, timestamp DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT)''')
    conn.commit()
    conn.close()

def save_message_db(session_id, role, content):
    conn = sqlite3.connect('dynamo_memory.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
              (session_id, role, content))
    conn.commit()
    conn.close()

def create_session(title="New Chat"):
    session_id = str(uuid.uuid4())
    conn = sqlite3.connect('dynamo_memory.db')
    c = conn.cursor()
    c.execute("INSERT INTO sessions (id, title, timestamp) VALUES (?, ?, ?)", 
              (session_id, title, datetime.now()))
    conn.commit()
    conn.close()
    return session_id

def get_history():
    conn = sqlite3.connect('dynamo_memory.db')
    c = conn.cursor()
    c.execute("SELECT id, title FROM sessions ORDER BY timestamp DESC LIMIT 10")
    sessions = c.fetchall()
    conn.close()
    return sessions

def load_history(session_id):
    conn = sqlite3.connect('dynamo_memory.db')
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id", (session_id,))
    messages = [{"role": row[0], "content": row[1]} for row in c.fetchall()]
    conn.close()
    return messages

# Initialize DB
init_db()

# --- SESSION STATE ---
if "session_id" not in st.session_state:
    st.session_state.session_id = create_session()
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- LOAD KEYS ---
groq_key = st.secrets.get("GROQ_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")
if not groq_key: st.stop()

# --- CLIENTS ---
groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
tavily_client = TavilyClient(api_key=tavily_key)

# --- FUNCTIONS ---
def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

def generate_image(prompt):
    return f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?nologo=true"

def extract_json_from_text(text):
    """Extracts JSON object from text for Data Viz"""
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except:
        return None
    return None

# --- PRO UI CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    .stApp { background-color: #ffffff; font-family: 'Inter', sans-serif; }
    
    /* SIDEBAR */
    [data-testid="stSidebar"] {
        background-color: #F9FAFB;
        border-right: 1px solid #E5E7EB;
    }
    
    /* CHAT BUBBLES */
    .stChatMessage { background-color: transparent !important; border: none !important; }
    
    /* User Bubble - Grey */
    div[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #F3F4F6 !important;
        border-radius: 20px;
        padding: 10px 20px;
        margin-bottom: 10px;
        color: #1F2937;
    }
    
    /* Assistant Bubble - White */
    div[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #FFFFFF !important;
        padding: 10px 0px;
        color: #1F2937;
    }

    /* INPUT AREA (Floating) */
    .stChatInput {
        position: fixed;
        bottom: 30px;
        left: 50%;
        transform: translateX(-40%);
        width: 60%;
        max-width: 800px;
        z-index: 1000;
        border-radius: 25px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        background: white;
        border: 1px solid #E5E7EB;
        padding: 5px;
    }
    .stChatInput input { border: none !important; box-shadow: none !important; }

    /* BUTTONS */
    .stButton > button {
        border-radius: 12px;
        border: 1px solid #E5E7EB;
        background-color: white;
        color: #374151;
        font-weight: 500;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        border-color: #FFC107;
        color: black;
        background-color: #FFFBEB;
    }
    
    /* HISTORY BUTTONS (Custom styling for sidebar list) */
    div[data-testid="stVerticalBlock"] > div > button {
        text-align: left;
        border: none;
        background: transparent;
        color: #4B5563;
    }
    div[data-testid="stVerticalBlock"] > div > button:hover {
        background: #E5E7EB;
        color: black;
    }

</style>
""", unsafe_allow_html=True)

# --- SIDEBAR NAV ---
with st.sidebar:
    # Logo
    col1, col2 = st.columns([1, 4])
    with col1: 
        st.markdown("<div style='width:32px;height:32px;border:2px solid #FFC107;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:bold;color:#FFC107;'>⚡</div>", unsafe_allow_html=True)
    with col2: 
        st.markdown("### Dynamo")
    
    st.write("")
    
    # 1. NEW CHAT BUTTON
    if st.button("➕ New Project", use_container_width=True):
        st.session_state.session_id = create_session(f"Project {datetime.now().strftime('%d/%m %H:%M')}")
        st.session_state.messages = []
        st.rerun()
    
    st.write("---")
    
    # 2. VISION UPLOADER
    with st.expander("👁️ Dynamo Vision"):
        uploaded_img = st.file_uploader("Upload Image", type=["jpg", "png"])
        vision_base64 = encode_image(uploaded_img) if uploaded_img else None
        if vision_base64: st.success("Image Active")

    st.write("---")
    
    # 3. SETTINGS
    st.caption("TOOLS")
    use_search = st.toggle("🌐 Web Search", value=True)
    analyst_mode = st.toggle("📊 Analyst Mode", value=False, help="Forces data visualization output")
    
    st.write("---")
    
    # 4. HISTORY (FROM DB)
    st.caption("HISTORY")
    history = get_history()
    for s_id, s_title in history:
        if st.button(f"📄 {s_title}", key=s_id, use_container_width=True):
            st.session_state.session_id = s_id
            st.session_state.messages = load_history(s_id)
            st.rerun()

# --- MAIN CHAT AREA ---

# Greeting
if not st.session_state.messages:
    st.markdown("""
    <div style="text-align: center; margin-top: 50px;">
        <h1 style="font-weight: 600; color: #111;">How can I help you?</h1>
        <p style="color: #666;">Ask me to generate images, analyze data, or read charts.</p>
    </div>
    """, unsafe_allow_html=True)

# Display Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "IMAGE::" in msg["content"]:
            st.image(msg["content"].replace("IMAGE::", ""))
        elif "CHART::" in msg["content"]:
            # Extract and render chart
            json_str = msg["content"].replace("CHART::", "")
            try:
                data = json.loads(json_str)
                df = pd.DataFrame(data)
                st.bar_chart(df.set_index(df.columns[0]))
            except:
                st.write("Error rendering chart.")
        else:
            st.write(msg["content"])

# --- LOGIC ENGINE ---
if prompt := st.chat_input("Message Dynamo..."):
    
    # 1. User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_message_db(st.session_state.session_id, "user", prompt)
    with st.chat_message("user"):
        st.write(prompt)

    # 2. Assistant Logic
    with st.chat_message("assistant"):
        
        # A. IMAGE GENERATION
        if "image" in prompt.lower() and ("generate" in prompt.lower() or "create" in prompt.lower()):
            with st.spinner("Painting..."):
                img_url = generate_image(prompt)
                st.image(img_url)
                save_msg = f"IMAGE::{img_url}"
                st.session_state.messages.append({"role": "assistant", "content": save_msg})
                save_message_db(st.session_state.session_id, "assistant", save_msg)

        # B. VISION (If Image Uploaded)
        elif vision_base64:
            with st.status("👁️ Analyzing Image...", expanded=True):
                response = groq_client.chat.completions.create(
                    model="llama-3.2-90b-vision-preview",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{vision_base64}"}}
                        ]
                    }]
                ).choices[0].message.content
                st.write(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                save_message_db(st.session_state.session_id, "assistant", response)

        # C. ANALYST / CHAT MODE
        else:
            container = st.empty()
            
            # Context
            context = ""
            if use_search:
                try:
                    res = tavily_client.search(query=prompt, search_depth="basic")
                    context = "\n".join([r['content'] for r in res['results']])
                except: pass

            # System Prompt
            sys_prompt = f"Context: {context}. "
            if analyst_mode or "plot" in prompt.lower() or "chart" in prompt.lower():
                sys_prompt += "If the user asks for a chart, return ONLY a JSON object with the data. Example: {\"Month\": [\"Jan\", \"Feb\"], \"Sales\": [10, 20]}."

            # API Call
            stream = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                stream=True
            )
            
            full_response = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    container.write(full_response)
            
            # Check for Chart Data
            json_data = extract_json_from_text(full_response)
            if json_data and (analyst_mode or "plot" in prompt.lower()):
                st.bar_chart(pd.DataFrame(json_data).set_index(list(json_data.keys())[0]))
                save_msg = f"CHART::{json.dumps(json_data)}" # Save as special tag
            else:
                save_msg = full_response

            st.session_state.messages.append({"role": "assistant", "content": save_msg})
            save_message_db(st.session_state.session_id, "assistant", save_msg)
