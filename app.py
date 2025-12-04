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
    
    /* 2. Text Adjustments (Make sure headers and text are black) */
    h1, h2, h3, p, div, span {
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
    /* Fix text inside User bubble to be white */
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
    
    /* 4. Button Styling - Black Buttons with Yellow Text */
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
</style>
""", unsafe_allow_html=True)

# --- MAIN APP LOGIC ---

# API Key Check
xai_key = st.secrets.get("XAI_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")
openai_key = st.secrets.get("OPENAI_API_KEY")

if not xai_key or not tavily_key:
    st.error("⚠️ Missing API Keys. Please add XAI_API_KEY and TAVILY_API_KEY to your Streamlit Secrets.")
    st.stop()

# Initialize Clients
xai_client = OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")
tavily_client = TavilyClient(api_key=tavily_key)
if openai_key:
    openai_client = OpenAI(api_key=openai_key)

# Header
col1, col2 = st.columns([1, 12])
with col1:
    st.write("# ⚡") 
with col2:
    st.title("Dynamo AI")
    st.caption("Dynamo 1.0")

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
    voice_audio = st.audio_input("🎙️ Voice Mode")
    chat_input = st.chat_input("Ask Dynamo AI a question...")

    final_query = None
    if quick_prompt:
        final_query = quick_prompt
    elif voice_audio and openai_key:
        with st.spinner("🎧 Transcribing..."):
            try:
                transcription = openai_client.audio.transcriptions.create(
                    model="whisper-1", file=voice_audio
                )
                final_query = transcription.text
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
            # 1. Search
            status.write("🔍 Scanning global data...")
            try:
                search_result = tavily_client.search(query=final_query, search_depth="basic")
                web_context = "\n".join([f"- {r['content']} (Source: {r['url']})" for r in search_result['results']])
            except Exception as e:
                web_context = "Search failed."
                st.warning(f"Search error: {e}")
            
            # 2. Reason
            status.write("⚙️ Synthesizing answer...")
            system_prompt = f"""You are Dynamo AI, an advanced research assistant.
            Use the provided context to answer the user's question.
            
            [WEB CONTEXT]: {web_context}
            
            Style guide:
            - Be direct, accurate, and helpful.
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
            
            response = st.write_stream(stream)
            status.update(label="✅ Complete", state="complete", expanded=False)
            st.session_state.messages.append({"role": "assistant", "content": response})
