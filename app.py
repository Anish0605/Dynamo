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
    /* User Message - Black Bubble, White Text */
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
