# ⚡ Dynamo AI
> **"Power Your Curiosity."**

**Dynamo AI** is a free, voice-activated Research Operating System (OS). It aggregates real-time web data, analyzes uploaded documents, and synthesizes answers using the world's fastest inference engine.

Built with **Streamlit**, powered by **Groq (Llama 3)**, and grounded by **Tavily Search**.

![App Screenshot](https://dynamoai.streamlit.app/) 


---

## 🧠 How It Works (The Logic)

Dynamo AI operates on a **Retrieval-Augmented Generation (RAG)** architecture with a multi-modal input system. Here is the logic flow behind the application:

```mermaid
graph TD
    A[User Input] --> B{Input Source?}
    B -- 🎙️ Voice Audio --> C[Groq Whisper Model]
    B -- ⌨️ Text Input --> D[Raw Query]
    C --> D
    
    D --> E{Context Manager}
    E -- 📂 PDF Uploaded? --> F[Extract Text (PyPDF2)]
    E -- 🌐 Needs Info? --> G[Live Web Search (Tavily)]
    
    F --> H[Context Injection]
    G --> H
    
    H --> I[LLM Reasoning (Llama 3 on Groq)]
    I --> J[Streaming Response to UI]
