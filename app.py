import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import PyPDF2
import json
import requests
from io import BytesIO

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Dynamo AI 2.0",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (HIGH CONTRAST & UI POLISH) ---
st.markdown("""
<style>
    /* 1. Main Background - Bright Yellow */
    .stApp {
        background-color: #FFC107;
        color: #000000;
    }
    
    /* 2. FORCE TEXT COLORS TO BLACK (Page Default) */
    h1, h2, h3, h4, h5, h6, p, div, span, label, li {
        color: #000000;
    }
    
    /* 3. CHAT BUBBLES - FORCE BLACK BACKGROUND */
    .stChatMessage {
        background-color: #000000 !important;
        border: 2px solid #333 !important;
        border-radius: 15px;
        padding: 15px;
    }
    
    /* 4. FORCE CHAT TEXT TO WHITE */
    .stChatMessage p, 
    .stChatMessage div, 
    .stChatMessage span, 
    .stChatMessage h1, 
    .stChatMessage h2, 
    .stChatMessage h3, 
    .stChatMessage li {
        color: #FFFFFF !important;
    }
    .stChatMessage code {
        background-color: #333 !important;
        color: #FFC107 !important;
    }

    /* 5. SIDEBAR STYLING */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 2px solid #000000;
    }
    
    /* 6. BUTTON STYLING */
    div.stButton > button {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        border: 2px solid #000000 !important;
        border-radius: 20px !important;
        font-weight: bold !important;
    }
    div.stButton > button:hover {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        transform: scale(1.02);
        border-color: #000000 !important;
    }
    div.stButton > button p {
        color: #FFFFFF !important;
    }
    div.stButton > button:hover p {
        color: #000000 !important;
    }
    
    /* 7. INPUT FIELD STYLING */
    .stTextInput > div > div > input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- SETUP KEYS & CLIENTS ---
groq_key = st.secrets.get("GROQ_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not groq_key or not tavily_key:
    st.error("⚠️ Missing Keys. Please add `GROQ_API_KEY` and `TAVILY_API_KEY` to your Streamlit Secrets.")
    st.stop()

# Brain & Voice (Groq)
groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
# Search (Tavily)
tavily_client = TavilyClient(api_key=tavily_key)

# --- HELPER FUNCTIONS ---

def generate_image(prompt):
    """Generates an image using Pollinations AI (Free, No Key)"""
    clean_prompt = prompt.replace(" ", "%20")
    return f"https://image.pollinations.ai/prompt/{clean_prompt}?nologo=true"

def deep_dive_search(query):
    """Generates multiple search queries for better context"""
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "system", 
                "content": "Return ONLY a JSON object with a key 'queries' containing a list of 3 distinct search queries to answer the user's question."
            }, {
                "role": "user", 
                "content": query
            }],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return data.get('queries', [query])[:3]
    except:
        return [query] 

def generate_suggestions(context_history):
    """Generates 3 short follow-up suggestions based on chat history"""
    try:
        # Create a mini-history string
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in context_history[-3:]])
        
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Based on the chat history, suggest 3 short, actionable follow-up prompts the user might want to ask next. (e.g. 'Summarize this', 'Give examples', 'Convert to list'). Return ONLY a JSON object with a key 'suggestions' containing a list of 3 strings."},
                {"role": "user", "content": f"Chat History:\n{history_text}"}
            ],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return data.get('suggestions', [])
    except:
        return ["Summarize this", "Tell me more", "Explain simply"]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚡ Toolkit 2.0")
    st.write("---")
    
    use_search = st.toggle("🌐 Web Search", value=True)
    deep_dive = st.toggle("🤿 Deep Dive Mode", value=False, help="Slower but smarter. Searches multiple angles.")
    
    st.write("---")
    
    st.subheader("📂 Document")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    pdf_text = ""
    if uploaded_file:
        try:
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages[:10]:
                pdf_text += page.extract_text()
            st.success("PDF Loaded")
        except:
            st.error("Error reading PDF")

    st.write("---")
    
    if "messages" in st.session_state and len(st.session_state.messages) > 0:
        chat_log = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in st.session_state.messages])
        st.download_button("📥 Download Chat", chat_log, file_name="dynamo_chat.txt")

    if st.button("🗑️ Reset Memory", use_container_width=True):
        st.session_state.messages = []
        st.session_state.suggestion_prompt = None # Clear suggestions
        st.rerun()

# --- MAIN APP ---
col1, col2 = st.columns([1, 15])
with col1: st.write("# ⚡") 
with col2: 
    st.title("Dynamo AI")
    st.caption("Phase 2: Deep Dive & Image Gen")

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "suggestion_prompt" not in st.session_state:
    st.session_state.suggestion_prompt = None

# Display History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["content"].startswith("IMAGE::"):
            img_url = msg["content"].replace("IMAGE::", "")
            st.image(img_url)
            # Add download button for historical images
            try:
                # Use a unique key for each download button based on URL
                btn_key = f"dl_{img_url}_{st.session_state.messages.index(msg)}"
                response = requests.get(img_url)
                img_data = BytesIO(response.content)
                st.download_button(label="📥 Download Image", data=img_data, file_name="generated_image.png", mime="image/png", key=btn_key)
            except:
                pass
        else:
            st.markdown(msg["content"])

# --- QUICK ACTION BUTTONS (TOP) ---
st.write("")
col_a, col_b, col_c = st.columns(3)
quick_prompt = None

# We use a callback to set the prompt if a button is clicked
def set_quick_prompt(text):
    st.session_state.suggestion_prompt = text

if col_a.button("📝 Summarize"): set_quick_prompt("Summarize our conversation so far.")
if col_b.button("🕵️ Fact Check"): set_quick_prompt("Deeply verify the facts in the last response.")
if col_c.button("👶 Explain Simple"): set_quick_prompt("Explain the last concept like I am 5 years old.")

# Input
input_container = st.container()
with input_container:
    voice_audio = st.audio_input("🎙️ Voice")
    chat_input = st.chat_input("Ask Dynamo...")

    final_query = None
    
    # 1. Check if a Suggestion/Quick Button was clicked
    if st.session_state.suggestion_prompt:
        final_query = st.session_state.suggestion_prompt
        st.session_state.suggestion_prompt = None # Reset after use
    
    # 2. Check Voice
    elif voice_audio:
        with st.spinner("🎧 Hearing..."):
            try:
                transcription = groq_client.audio.transcriptions.create(
                    model="whisper-large-v3-turbo", 
                    file=("audio.wav", voice_audio),
                    response_format="text"
                )
                final_query = transcription
            except: st.error("Voice Error")
            
    # 3. Check Text Input
    elif chat_input:
        final_query = chat_input

# --- LOGIC ENGINE ---
if final_query:
    st.session_state.messages.append({"role": "user", "content": final_query})
    with st.chat_message("user"):
        st.markdown(final_query)

    with st.chat_message("assistant"):
        
        # IMAGE GENERATION
        if "image" in final_query.lower() and ("generate" in final_query.lower() or "draw" in final_query.lower() or "create" in final_query.lower()):
            with st.status("🎨 Painting...", expanded=True):
                refine_prompt = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": f"Create a detailed, vivid image generation prompt for: {final_query}. Output ONLY the prompt string."}]
                ).choices[0].message.content
                
                img_url = generate_image(refine_prompt)
                st.image(img_url, caption=refine_prompt)
                st.session_state.messages.append({"role": "assistant", "content": f"IMAGE::{img_url}"})
                
                # New Download Button
                try:
                    response = requests.get(img_url)
                    img_data = BytesIO(response.content)
                    st.download_button(label="📥 Download Image", data=img_data, file_name="generated_image.png", mime="image/png", key="new_dl_btn")
                except Exception as e:
                    st.error(f"Download Error: {e}")
        
        # TEXT RESEARCH
        else:
            with st.status("🧠 Dynamo is thinking...", expanded=True) as status:
                web_context = ""
                
                if not pdf_text and use_search:
                    if deep_dive:
                        status.write("🤿 Deep Dive Active...")
                        queries = deep_dive_search(final_query)
                        all_results = []
                        for q in queries:
                            status.write(f"🔍 Searching: {q}...")
                            try:
                                res = tavily_client.search(query=q, search_depth="basic")
                                all_results.extend([r['content'] for r in res['results']])
                            except: pass
                        web_context = "\n".join(all_results)
                        with st.expander("View Deep Dive Data"):
                            st.write(queries)
                            st.write(web_context)
                    else:
                        status.write("🔍 Scanning web...")
                        try:
                            res = tavily_client.search(query=final_query, search_depth="basic")
                            web_context = "\n".join([f"- {r['content']}" for r in res['results']])
                        except: web_context = "Search failed."

                status.write("⚙️ Synthesizing...")
                system_prompt = f"""You are Dynamo AI.
                CONTEXT: {pdf_text if pdf_text else "No PDF"} {web_context if web_context else "No Web Info"}
                INSTRUCTIONS: If Deep Dive is ON, be exhaustive. If Image is requested, decline. Be accurate and cite sources.
                """
                
                # Build History
                api_messages = [{"role": "system", "content": system_prompt}]
                for msg in st.session_state.messages[:-1]:
                    if not msg["content"].startswith("IMAGE::"):
                        api_messages.append({"role": msg["role"], "content": msg["content"]})
                api_messages.append({"role": "user", "content": final_query})

                stream = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=api_messages,
                    stream=True
                )
                response = st.write_stream(stream)
                status.update(label="✅ Complete", state="complete", expanded=False)
                st.session_state.messages.append({"role": "assistant", "content": response})
            
            # --- DYNAMIC SUGGESTIONS (Validating Tester Feedback) ---
            # Generate 3 follow-up suggestions
            suggestions = generate_suggestions(st.session_state.messages)
            
            if suggestions:
                st.write("### 💡 Suggested Next Steps:")
                cols = st.columns(len(suggestions))
                for i, sugg in enumerate(suggestions):
                    if cols[i].button(sugg, key=f"sugg_{len(st.session_state.messages)}_{i}"):
                        set_quick_prompt(sugg)
                        st.rerun()
