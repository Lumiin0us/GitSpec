import streamlit as st
from backend.clone import cloneRepo, cleanupRepo
from backend.crawl import repoCrawler
from backend.extract import processPythonFile
from backend.indexer import indexer
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()
groqApiKey = os.getenv("GROQ_API_KEY")

st.set_page_config(page_title="GitSpec", layout="wide")
st.title("GitSpec")

# --- Session State Initialization ---
if "client" not in st.session_state:
    st.session_state.client = None
    st.session_state.model = None
    st.session_state.repo_name = ""

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Sidebar Controls ---
with st.sidebar:
    st.header("Settings")
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
    st.divider()
    context_limit = st.slider("Context Depth (Snippets)", 3, 10, 6)

# --- Repository Input Section ---
repo_url = st.text_input("Enter GitHub Repository URL:")

if st.button("Analyze Repository"):
    if repo_url:
        st.session_state.repo_name = repo_url.split('/')[-1].replace('.git', '')
        progressBar = st.progress(0)
        statusText = st.empty()

        statusText.text("Cloning repository...")
        progressBar.progress(10)
        destPath, repo = cloneRepo(repo_url) 
        
        if destPath and repo:
            progressBar.progress(30)
            statusText.text("Scanning files...")
            files = repoCrawler(destPath)
            
            progressBar.progress(50)
            statusText.text("Extracting code structures...")
            results = processPythonFile(files, destPath, repo)
            
            progressBar.progress(80)
            statusText.text("Vectorizing...")
            client, model = indexer(results)
            
            st.session_state.client = client
            st.session_state.model = model
            st.session_state.messages = [] 
            
            progressBar.progress(100)
            statusText.text("Cleaning up...")
            cleanupRepo(destPath)
            
            statusText.empty()
            progressBar.empty()
            st.success(f"'{st.session_state.repo_name}' Indexed Successfully!")
        else:
            statusText.empty()
            progressBar.empty()
            st.error("Failed to clone repository.")
    else:
        st.warning("Please enter a URL.")

# --- Chat Interface Section ---
if st.session_state.client:
    st.divider()
    
    # Display previous conversation
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input Box
    if query := st.chat_input("Ask a question about the architecture..."):
        
        # 1. Display User Message
        with st.chat_message("user"):
            st.markdown(query)
        st.session_state.messages.append({"role": "user", "content": query})

        groqClient = Groq(api_key=groqApiKey)
        
        with st.spinner("Analyzing repository..."):
            # 2. Vector Search
            queryVector = st.session_state.model.encode(query).tolist()
            response = st.session_state.client.query_points(
                collection_name="tempCollection",
                query=queryVector,
                limit=context_limit
            )
            
            searchResults = response.points
            
            if not searchResults:
                full_response = "I couldn't find relevant code. Try broadening your query."
            else:
                # 2. ISOLATED CONTEXT (Hidden from the user, formatted for the LLM)
                contextBlocks = []
                for res in searchResults:
                    p = res.payload
                    block = (
                        f"FILE: {p.get('filePath')}\n"
                        f"METADATA: Parent={p.get('parentClass')}, Imports={p.get('modules')}\n"
                        f"COMMIT: {p.get('history', {}).get('lastCommit', {}).get('msg')}\n"
                        f"CODE:\n{p.get('content')}"
                    )
                    contextBlocks.append(block)

                formattedContext = "\n---\n".join(contextBlocks)

                # 4. Refined System Prompt
                system_prompt = (
                    "You are a Senior Software Architect. Your goal is to provide a clean, "
                    "high-level architectural explanation based on provided code snippets."
                    "\n\nSTRICT FORMATTING RULES:"
                    "\n- Start immediately with the answer. Do NOT repeat the user's question or metadata tags."
                    "\n- Use H3 headers (###) for distinct logical sections."
                    "\n- Do NOT include local file paths like '/var/folders/...' in your prose. Use the relative path (e.g., 'typer/main.py')."
                    "\n- Use Python code blocks for examples, and ensure they are syntactically clean."
                    "\n- Mention 'Git Insights' only if the commit history adds value to the explanation."
                    "\n- Keep the tone professional, authoritative, and concise."
                )

                # 4. SEND TO GROQ
                llm_messages = [
                    {"role": "system", "content": system_prompt},
                    *st.session_state.messages[-5:], # Conversation memory
                    {"role": "user", "content": f"Context:\n{formattedContext}\n\nQuestion: {query}"}
                ]

                llmResponse = groqClient.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=llm_messages,
                    temperature=0.1 # Lower temperature for higher precision in technical answers
                )
                full_response = llmResponse.choices[0].message.content

            # 6. UI Update
            with st.chat_message("assistant"):
                st.markdown(full_response)
                
                if searchResults:
                    with st.expander("Explore Reference Sources"):
                        for res in searchResults:
                            p = res.payload
                            st.caption(f"Snippet from: {p.get('filePath')}")
                            st.code(p.get('content'), language='python')

            st.session_state.messages.append({"role": "assistant", "content": full_response})