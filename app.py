import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import PyPDF2

# --- PAGE CONFIGURATION (Browser Tab) ---
st.set_page_config(
    page_title="Grok Research OS",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS STYLING ---
# This makes the app look "Pro" instead of plain white
st.markdown("""
<style>
    /* 1. Main Background */
    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    
    /* 2. Chat Message Bubbles */
    /* User Message - Blue */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #1a253a; 
        border: 1px solid #2b3b55;
        border-radius: 15px;
        padding: 15px;
    }
    /* Assistant Message - Dark Grey */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #151515;
        border: 1px solid #333;
        border-radius: 15px;
        padding: 15px;
    }
    
    /* 3. Header Styling */
    h1 {
        color: #00BFFF; /* Deep Sky Blue */
        font-weight: 700;
    }
    
    /* 4. Button Styling */
    .stButton>button {
        border-radius: 20px;
        border: 1px solid #444;
        background-color: #222;
        color: white;
    }
    .stButton>button:hover {
        border-color: #00BFFF;
        color: #00BFFF;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Control Center")
    
    # Secure Key Input
    with st.expander("🔑 API Keys", expanded=False):
        xai_key = st.text_input("xAI Key", type="password", value=st.secrets.get("XAI_API_KEY", ""))
        tavily_key = st.text_input("Tavily Key", type="password", value=st.secrets.get("TAVILY_API_KEY", ""))
        openai_key = st.text_input("OpenAI Key", type="password", value=st.secrets.get("OPENAI_API_KEY", ""))
    
    st.divider()
    
    # File Uploader
    uploaded_file = st.file_uploader("📂 Upload PDF Context", type="pdf")
    pdf_text = ""
    if uploaded_file:
        try:
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages[:10]:
                pdf_text += page.extract_text()
            st.success("PDF Loaded & Ready")
        except:
            st.error("Could not read PDF")

    st.divider()
    
    # Clear Chat
    if st.button("🗑️ Reset Conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --- MAIN APP LOGIC ---

# Header
col1, col2 = st.columns([1, 5])
with col1:
    st.image("https://upload.wikimedia.org/wikipedia/commons/5/53/X_logo_2023_original.svg", width=60) # X logo
with col2:
    st.title("Grok Research OS")
    st.caption("Powered by xAI • Tavily Search • OpenAI Voice")

# API Check
if not xai_key or not tavily_key:
    st.info("👋 Welcome! Please enter your API keys in the sidebar to start.")
    st.stop()

# Initialize Clients
xai_client = OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")
tavily_client = TavilyClient(api_key=tavily_key)
if openai_key:
    openai_client = OpenAI(api_key=openai_key)

# Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- DISPLAY CHAT HISTORY ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- QUICK ACTION BUTTONS ---
# These buttons act like shortcuts
st.write("") # Spacer
col_a, col_b, col_c = st.columns(3)
quick_prompt = None

if col_a.button("📝 Summarize Last"):
    quick_prompt = "Summarize our conversation so far in bullet points."
if col_b.button("🕵️ Deep Fact Check"):
    quick_prompt = "Perform a deep fact check on the last topic we discussed."
if col_c.button("👶 Explain Simple"):
    quick_prompt = "Explain the last answer to me like I am 5 years old."

# --- USER INPUT (Voice or Text) ---
input_container = st.container()

with input_container:
    # Voice Input
    voice_audio = st.audio_input("🎙️ Voice Mode")
    
    # Text Input
    chat_input = st.chat_input("Ask a question...")

    # Determine final query
    final_query = None
    
    # Priority: 1. Button Click -> 2. Voice -> 3. Text
    if quick_prompt:
        final_query = quick_prompt
    elif voice_audio and openai_key:
        with st.spinner("🎧 Transcribing..."):
            transcription = openai_client.audio.transcriptions.create(
                model="whisper-1", file=voice_audio
            )
            final_query = transcription.text
    elif chat_input:
        final_query = chat_input

# --- PROCESS QUERY ---
if final_query:
    # 1. Show User Message
    st.session_state.messages.append({"role": "user", "content": final_query})
    with st.chat_message("user"):
        st.markdown(final_query)

    # 2. Assistant Response
    with st.chat_message("assistant"):
        # Create a status container that looks like a "Brain" working
        with st.status("🧠 Agent Working...", expanded=True) as status:
            
            # SEARCH STEP
            status.write("🔍 Scanning global data (Tavily)...")
            search_result = tavily_client.search(query=final_query, search_depth="basic")
            web_context = "\n".join([f"- {r['content']} (Source: {r['url']})" for r in search_result['results']])
            
            # REASONING STEP
            status.write("⚙️ synthesizing answer (Grok)...")
            
            system_prompt = f"""You are Grok, a witty and smart research assistant.
            Use the following context to answer the user.
            
            [PDF CONTEXT]: {pdf_text if pdf_text else "None"}
            [WEB CONTEXT]: {web_context}
            
            Style guide:
            - Be direct and helpful.
            - Use Bold text for key facts.
            - Cite sources if used.
            """

            stream = xai_client.chat.completions.create(
                model="grok-beta",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": final_query}
                ],
                stream=True
            )
            
            # STREAM OUTPUT
            response = st.write_stream(stream)
            status.update(label="✅ Complete", state="complete", expanded=False)
            
            # Save to history
            st.session_state.messages.append({"role": "assistant", "content": response})
