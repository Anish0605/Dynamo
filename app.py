import streamlit as st
from openai import OpenAI
from tavily import TavilyClient

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Dynamo AI",
    page_icon="⚡",
    layout="wide"
)

# --- CUSTOM CSS (YELLOW THEME) ---
st.markdown("""
<style>
    /* 1. Main Background - Bright Yellow */
    .stApp {
        background-color: #FFC107;
        color: #000000;
    }
    
    /* 2. Text Adjustments */
    h1, h2, h3, p, div, span, label {
        color: #000000 !important;
    }
    
    /* 3. Chat Message Bubbles */
    /* User Message (You) - Black Bubble, White Text */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #000000; 
        color: #ffffff !important;
        border: 2px solid #000000;
        border-radius: 15px;
        padding: 15px;
    }
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) * {
        color: #ffffff !important;
    }

    /* Assistant Message (Dynamo) - White Bubble, Black Text */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #ffffff;
        color: #000000 !important;
        border: 2px solid #000000;
        border-radius: 15px;
        padding: 15px;
    }
    
    /* 4. Button Styling */
    .stButton>button {
        border-radius: 20px;
        border: 2px solid #000000;
        background-color: #000000;
        color: #FFC107 !important;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #ffffff;
        color: #000000 !important;
        border-color: #000000;
    }
    
    /* 5. Input Field Styling */
    .stTextInput>div>div>input {
        background-color: #ffffff;
        color: #000000;
        border: 2px solid #000000;
    }
    /* Audio Widget Styling */
    .stAudio {
        background-color: #ffffff;
        border-radius: 10px;
        border: 2px solid #000000;
    }
</style>
""", unsafe_allow_html=True)

# --- MAIN APP LOGIC ---

# 1. LOAD KEYS
xai_key = st.secrets.get("XAI_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")
groq_key = st.secrets.get("GROQ_API_KEY")

if not xai_key or not tavily_key or not groq_key:
    st.error("⚠️ Missing API Keys. Please check your Streamlit Secrets.")
    st.stop()

# 2. INITIALIZE CLIENTS
# Brain (Grok/xAI)
xai_client = OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")

# Search (Tavily)
tavily_client = TavilyClient(api_key=tavily_key)

# Voice (Groq - FREE Alternative to OpenAI)
groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")

# Header
col1, col2 = st.columns([1, 12])
with col1:
    st.write("# ⚡") 
with col2:
    st.title("Dynamo AI")
    st.caption("Powered by Grok (Brain) & Groq (Voice)")

# Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- QUICK ACTION BUTTONS ---
st.write("")
col_a, col_b, col_c = st.columns(3)
quick_prompt = None
if col_a.button("📝 Summarize Last"): quick_prompt = "Summarize our conversation."
if col_b.button("🕵️ Deep Fact Check"): quick_prompt = "Perform a deep fact check on the last topic."
if col_c.button("👶 Explain Simple"): quick_prompt = "Explain the last answer like I'm 5."

# --- INPUT CONTAINER ---
input_container = st.container()
with input_container:
    # Voice Input
    voice_audio = st.audio_input("🎙️ Voice Mode (Free)")
    # Text Input
    chat_input = st.chat_input("Ask Dynamo AI a question...")

    final_query = None
    
    # Priority Logic
    if quick_prompt:
        final_query = quick_prompt
    
    elif voice_audio:
        with st.spinner("🎧 Transcribing with Groq..."):
            try:
                # We use Groq's Whisper model (Free Tier)
                transcription = groq_client.audio.transcriptions.create(
                    model="whisper-large-v3-turbo", 
                    file=("audio.wav", voice_audio), # Tuple format is safer
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
        with st.status("🧠 Dynamo is thinking...", expanded=True) as status:
            
            # 1. Search (Tavily)
            status.write("🔍 Scanning global data...")
            web_context = "No search needed."
            try:
                # We do a basic search for context
                search_result = tavily_client.search(query=final_query, search_depth="basic")
                web_context = "\n".join([f"- {r['content']} (Source: {r['url']})" for r in search_result['results']])
            except Exception as e:
                st.warning(f"Search skipped: {e}")
            
            # 2. Reason (Grok xAI)
            status.write("⚙️ Synthesizing answer...")
            system_prompt = f"""You are Dynamo AI.
            Use this context to answer:
            {web_context}
            
            Be helpful, direct, and accurate.
            """

            stream = xai_client.chat.completions.create(
                model="grok-beta",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": final_query}
                ],
                stream=True
            )
            
            response = st.write_stream(stream)
            status.update(label="✅ Complete", state="complete", expanded=False)
            st.session_state.messages.append({"role": "assistant", "content": response})
