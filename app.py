import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import PyPDF2

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Dynamo AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (YELLOW THEME & FORCED CONTRAST) ---
st.markdown("""
<style>
    /* 1. Main Background - Bright Yellow */
    .stApp {
        background-color: #FFC107;
        color: #000000;
    }
    
    /* 2. FORCE TEXT COLORS */
    h1, h2, h3, h4, h5, h6, p, div, span, label, li {
        color: #000000 !important;
    }
    
    /* 3. Chat Message Bubbles */
    /* User Message - Black Bubble */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #000000; 
        border: 2px solid #000000;
        border-radius: 15px;
        padding: 15px;
    }
    /* FORCE User Text to be White */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) div,
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) p,
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) span {
        color: #FFFFFF !important;
    }

    /* Assistant Message - White Bubble, Black Text */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #ffffff;
        border: 2px solid #000000;
        border-radius: 15px;
        padding: 15px;
    }
    
    /* 4. Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 2px solid #000000;
    }
    
    /* 5. ULTIMATE BUTTON FIX */
    /* Normal State: Black Button, White Text */
    .stButton > button {
        background-color: #000000 !important;
        color: #FFFFFF !important; /* Force text white */
        border: 2px solid #000000 !important;
        border-radius: 20px;
        font-weight: bold;
    }
    /* Target the text inside the button specifically */
    .stButton > button p {
        color: #FFFFFF !important;
    }

    /* Hover State: White Button, Black Text */
    .stButton > button:hover {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border-color: #000000 !important;
        transform: scale(1.02);
    }
    /* Target the text inside the button on Hover */
    .stButton > button:hover p {
        color: #000000 !important;
    }
    
    /* 6. Input Field Styling */
    .stTextInput > div > div > input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- MAIN SETUP ---

# 1. LOAD KEYS
groq_key = st.secrets.get("GROQ_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not groq_key or not tavily_key:
    st.error("⚠️ Missing Keys. Please add `GROQ_API_KEY` and `TAVILY_API_KEY` to your Streamlit Secrets.")
    st.stop()

# 2. INITIALIZE CLIENTS
groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
tavily_client = TavilyClient(api_key=tavily_key)

# --- SIDEBAR (TOOLS) ---
with st.sidebar:
    st.header("⚡ Toolkit")
    st.write("---")
    
    # PDF Upload
    st.subheader("📂 Analyze Document")
    uploaded_file = st.file_uploader("Upload PDF Context", type="pdf")
    pdf_text = ""
    
    if uploaded_file:
        try:
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages[:10]:
                pdf_text += page.extract_text()
            st.success(f"✅ Loaded {len(pdf_text)} chars")
        except Exception as e:
            st.error("Error reading PDF")

    st.write("---")
    
    # Download Chat
    if "messages" in st.session_state and len(st.session_state.messages) > 0:
        chat_log = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in st.session_state.messages])
        st.download_button("📥 Download Chat", chat_log, file_name="dynamo_chat.txt")

    # Clear Chat
    if st.button("🗑️ Reset Memory", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --- MAIN APP LOGIC ---

# Header
col1, col2 = st.columns([1, 15])
with col1:
    st.write("# ⚡") 
with col2:
    st.title("Dynamo AI")
    st.caption("Free Research OS • Powered by Groq & Tavily")

# Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Quick Actions
st.write("")
col_a, col_b, col_c = st.columns(3)
quick_prompt = None
if col_a.button("📝 Summarize"): quick_prompt = "Summarize our conversation."
if col_b.button("🕵️ Fact Check"): quick_prompt = "Verify the facts of the last response."
if col_c.button("👶 Explain Simple"): quick_prompt = "Explain like I'm 5."

# Input Area
input_container = st.container()
with input_container:
    voice_audio = st.audio_input("🎙️ Voice Mode (Free)")
    chat_input = st.chat_input("Ask Dynamo...")

    final_query = None
    
    if quick_prompt:
        final_query = quick_prompt
    
    elif voice_audio:
        with st.spinner("🎧 Transcribing with Groq..."):
            try:
                transcription = groq_client.audio.transcriptions.create(
                    model="whisper-large-v3-turbo", 
                    file=("audio.wav", voice_audio),
                    response_format="text"
                )
                final_query = transcription
            except Exception as e:
                st.error(f"Voice Error: {e}")
    
    elif chat_input:
        final_query = chat_input

# --- PROCESS QUERY ---
if final_query:
    st.session_state.messages.append({"role": "user", "content": final_query})
    with st.chat_message("user"):
        st.markdown(final_query)

    with st.chat_message("assistant"):
        with st.status("🧠 Dynamo is working...", expanded=True) as status:
            
            # 1. Search Logic
            web_context = ""
            if not pdf_text: 
                status.write("🔍 Scanning web (Tavily)...")
                try:
                    search_result = tavily_client.search(query=final_query, search_depth="basic")
                    web_context = "\n".join([f"- {r['content']} (Source: {r['url']})" for r in search_result['results']])
                except:
                    web_context = "Search unavailable."
            
            # 2. Reasoning Logic
            status.write("⚙️ Thinking (Llama 3)...")
            
            system_prompt = f"""You are Dynamo AI.
            
            SOURCES AVAILABLE:
            1. PDF DOCUMENT: {pdf_text if pdf_text else "None"}
            2. WEB SEARCH: {web_context if web_context else "None"}
            
            INSTRUCTIONS:
            - If a PDF is uploaded, prioritize it.
            - If no PDF, use Web Search.
            - Be concise and accurate.
            """

            stream = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": final_query}
                ],
                stream=True
            )
            
            response = st.write_stream(stream)
            status.update(label="✅ Ready", state="complete", expanded=False)
            st.session_state.messages.append({"role": "assistant", "content": response})
