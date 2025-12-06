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

# --- DATABASE ENGINE ---
def init_db():
    try:
        conn = sqlite3.connect('dynamo_memory.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT, timestamp DATETIME)''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT)''')
        conn.commit()
        conn.close()
    except Exception as e:
        pass 

def save_message_db(session_id, role, content):
    try:
        conn = sqlite3.connect('dynamo_memory.db')
        c = conn.cursor()
        c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, role, content))
        conn.commit()
        conn.close()
    except: pass

def create_session(title="New Chat"):
    session_id = str(uuid.uuid4())
    try:
        conn = sqlite3.connect('dynamo_memory.db')
        c = conn.cursor()
        c.execute("INSERT INTO sessions (id, title, timestamp) VALUES (?, ?, ?)", (session_id, title, datetime.now()))
        conn.commit()
        conn.close()
    except: pass
    return session_id

def get_history():
    try:
        conn = sqlite3.connect('dynamo_memory.db')
        c = conn.cursor()
        c.execute("SELECT id, title FROM sessions ORDER BY timestamp DESC LIMIT 10")
        sessions = c.fetchall()
        conn.close()
        return sessions
    except: return []

def load_history(session_id):
    try:
        conn = sqlite3.connect('dynamo_memory.db')
        c = conn.cursor()
        c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id", (session_id,))
        messages = [{"role": row[0], "content": row[1]} for row in c.fetchall()]
        conn.close()
        return messages
    except: return []

init_db()

# --- STATE MANAGEMENT ---
if "session_id" not in st.session_state: st.session_state.session_id = create_session()
if "messages" not in st.session_state: st.session_state.messages = []
if "uploader_key" not in st.session_state: st.session_state.uploader_key = str(uuid.uuid4())

# --- LOAD KEYS ---
groq_key = st.secrets.get("GROQ_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not groq_key or not tavily_key:
    st.warning("⚠️ API Keys Missing. Please set GROQ_API_KEY and TAVILY_API_KEY in Streamlit Secrets.")
    st.stop()

# --- CLIENTS ---
groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
tavily_client = TavilyClient(api_key=tavily_key)

# --- FUNCTIONS ---
def encode_image(uploaded_file):
    if uploaded_file is None: return None
    try:
        bytes_data = uploaded_file.getvalue()
        base64_str = base64.b64encode(bytes_data).decode('utf-8')
        mime_type = uploaded_file.type if uploaded_file.type else "image/jpeg"
        return f"data:{mime_type};base64,{base64_str}"
    except: return None

def generate_image(prompt):
    return f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?nologo=true"

def extract_json_from_text(text):
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match: return json.loads(match.group(0))
    except: return None
    return None

# --- UI LOGIC FOR INPUT POSITION ---
# We inject CSS based on whether chat is empty or not
input_css = ""
if not st.session_state.messages:
    # DEEPSEEK STYLE: Center Input
    input_css = """
    <style>
        /* Hide the default bottom container spacing to allow centering */
        .block-container {
            padding-bottom: 5rem !important;
        }
        /* Target the chat input container */
        [data-testid="stChatInput"] {
            position: fixed;
            top: 50%;
            left: 58%; /* Offset for sidebar */
            transform: translate(-50%, -50%);
            width: 50% !important;
            max-width: 700px;
            z-index: 999;
        }
        /* Add a shadow and border to make it pop like DeepSeek */
        [data-testid="stChatInput"] > div {
            border-radius: 25px !important;
            border: 1px solid #E5E7EB !important;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08) !important;
            background-color: white !important;
        }
        /* Hide the text area border since the container has one */
        [data-testid="stChatInput"] textarea {
            border: none !important;
            box-shadow: none !important;
        }
    </style>
    """
else:
    # STANDARD STYLE: Bottom Input
    input_css = """
    <style>
        [data-testid="stChatInput"] {
            position: fixed;
            bottom: 30px;
            left: 58%;
            transform: translateX(-50%);
            width: 60%;
            max-width: 800px;
        }
        [data-testid="stChatInput"] > div {
            border-radius: 20px !important;
            border: 1px solid #E5E7EB !important;
            background-color: white !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05) !important;
        }
    </style>
    """

# --- GLOBAL CSS ---
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    .stApp {{ background-color: #ffffff; font-family: 'Inter', sans-serif; }}
    
    /* SIDEBAR */
    [data-testid="stSidebar"] {{
        background-color: #F9FAFB;
        border-right: 1px solid #E5E7EB;
    }}
    
    /* CHAT BUBBLES */
    .stChatMessage {{ background-color: transparent !important; border: none !important; }}
    
    div[data-testid="stChatMessage"]:nth-child(odd) {{
        background-color: #F3F4F6 !important;
        border-radius: 20px;
        padding: 10px 20px;
        margin-bottom: 10px;
        color: #1F2937;
    }}
    
    div[data-testid="stChatMessage"]:nth-child(even) {{
        background-color: #FFFFFF !important;
        padding: 10px 0px;
        color: #1F2937;
    }}

    /* BUTTONS */
    div.stButton > button {{
        border-radius: 12px;
        border: 1px solid #E5E7EB;
        background-color: white;
        color: #374151;
        font-weight: 500;
        transition: all 0.2s;
    }}
    div.stButton > button:hover {{
        border-color: #FFC107;
        color: black;
        background-color: #FFFBEB;
    }}
    
    /* Hide Header */
    header {{visibility: hidden;}}
</style>
{input_css}
""", unsafe_allow_html=True)

# --- SIDEBAR NAV ---
with st.sidebar:
    col1, col2 = st.columns([1, 4])
    with col1: 
        st.markdown("<div style='width:32px;height:32px;border:2px solid #FFC107;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:bold;color:#FFC107;'>⚡</div>", unsafe_allow_html=True)
    with col2: 
        st.markdown("### Dynamo")
    
    st.write("")
    
    if st.button("➕ New Project", use_container_width=True):
        st.session_state.session_id = create_session(f"Project {datetime.now().strftime('%d/%m %H:%M')}")
        st.session_state.messages = []
        st.session_state.uploader_key = str(uuid.uuid4())
        st.rerun()
    
    st.write("---")
    
    with st.expander("👁️ Dynamo Vision"):
        uploaded_img = st.file_uploader("Upload Image", type=["jpg", "png", "jpeg"], key=st.session_state.uploader_key)
        vision_data_url = encode_image(uploaded_img) if uploaded_img else None
        if vision_data_url: st.success("Image Active")

    st.write("---")
    
    # Settings (Hidden in Sidebar for DeepSeek look, visible when toggled)
    st.caption("TOOLS")
    use_search = st.toggle("🌐 Web Search", value=True)
    analyst_mode = st.toggle("📊 Analyst Mode", value=False)
    
    st.write("---")
    st.caption("HISTORY")
    history = get_history()
    for s_id, s_title in history:
        if st.button(f"📄 {s_title}", key=s_id, use_container_width=True):
            st.session_state.session_id = s_id
            st.session_state.messages = load_history(s_id)
            st.session_state.uploader_key = str(uuid.uuid4())
            st.rerun()

# --- MAIN CHAT AREA ---

# Greeting (DeepSeek Style - Centered)
if not st.session_state.messages and not vision_data_url:
    # Push content down to center visually above the input bar
    st.markdown("""
    <div style="text-align: center; position: absolute; top: 35%; left: 50%; transform: translate(-50%, -50%); width: 100%;">
        <div style="font-size: 50px; margin-bottom: 10px;">⚡</div>
        <h1 style="font-weight: 600; color: #111; font-size: 2rem;">How can I help you?</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # We display Pill Buttons ABOVE the input area using columns
    # We use a container to push them to the right spot
    with st.container():
        st.markdown("<div style='height: 45vh;'></div>", unsafe_allow_html=True) # Spacer
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            # These are fake visual toggles to match DeepSeek UI
            # Real toggles are in sidebar, but we can make these functional shortcuts
            sub_c1, sub_c2 = st.columns(2)
            if sub_c1.button("🌐 Search", use_container_width=True):
                use_search = True
            if sub_c2.button("🤿 DeepDive", use_container_width=True):
                st.session_state.analyst_mode = True 

# Display Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "IMAGE::" in msg["content"]:
            st.image(msg["content"].replace("IMAGE::", ""))
        elif "CHART::" in msg["content"]:
            json_str = msg["content"].replace("CHART::", "")
            try:
                data = json.loads(json_str)
                st.bar_chart(pd.DataFrame(data).set_index(list(data.keys())[0]))
            except:
                st.write("Error rendering chart.")
        else:
            st.write(msg["content"])

# --- LOGIC ENGINE ---
if prompt := st.chat_input("Message Dynamo..."):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_message_db(st.session_state.session_id, "user", prompt)
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        if "image" in prompt.lower() and ("generate" in prompt.lower() or "create" in prompt.lower()):
            with st.spinner("Painting..."):
                try:
                    img_url = generate_image(prompt)
                    st.image(img_url)
                    save_msg = f"IMAGE::{img_url}"
                    st.session_state.messages.append({"role": "assistant", "content": save_msg})
                    save_message_db(st.session_state.session_id, "assistant", save_msg)
                except Exception as e:
                    st.error(f"Generation Error: {e}")
        elif vision_data_url:
            with st.status("👁️ Analyzing Image...", expanded=True):
                try:
                    response = groq_client.chat.completions.create(
                        model="llama-3.2-90b-vision-preview",
                        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": vision_data_url}}]}]
                    ).choices[0].message.content
                    st.write(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    save_message_db(st.session_state.session_id, "assistant", response)
                except Exception as e:
                    st.error(f"Vision Error: {e}")
        else:
            container = st.empty()
            context = ""
            if use_search:
                try:
                    res = tavily_client.search(query=prompt, search_depth="basic")
                    context = "\n".join([r['content'] for r in res['results']])
                except: pass
            
            sys_prompt = f"Context: {context}. "
            if analyst_mode or "plot" in prompt.lower() or "chart" in prompt.lower():
                sys_prompt += "If user asks for a chart, return ONLY JSON data. Example: {\"Category\": [\"A\", \"B\"], \"Value\": [10, 20]}."
            
            try:
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
                
                json_data = extract_json_from_text(full_response)
                if json_data and (analyst_mode or "plot" in prompt.lower()):
                    st.bar_chart(pd.DataFrame(json_data).set_index(list(json_data.keys())[0]))
                    save_msg = f"CHART::{json.dumps(json_data)}"
                else:
                    save_msg = full_response
                
                st.session_state.messages.append({"role": "assistant", "content": save_msg})
                save_message_db(st.session_state.session_id, "assistant", save_msg)
            except Exception as e:
                st.error(f"Groq API Error: {e}")
