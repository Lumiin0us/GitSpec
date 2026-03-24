import streamlit as st
from backend.clone import cloneRepo, cleanupRepo
from backend.crawl import repoCrawler
from backend.extract import processPythonFile
from backend.indexer import indexer
from backend.historyExtractor import extractHistory
from backend.historyIndexer import indexHistory
from backend.router import routeQuery
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()
groqApiKey = os.getenv("GROQ_API_KEY")

st.set_page_config(page_title="GitSpec", layout="wide")
st.title("GitSpec")

if "client" not in st.session_state:
    st.session_state.client = None
    st.session_state.model = None
    st.session_state.repo_name = ""

if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar Controls
with st.sidebar:
    st.header("Settings")
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
    st.divider()
    contextLimit = st.slider("Context Depth (Snippets)", 3, 10, 6)

repoUrl = st.text_input("Enter GitHub Repository URL:")

if st.button("Analyze Repository"):
    if repoUrl:
        st.session_state.repo_name = repoUrl.split('/')[-1].replace('.git', '')
        progressBar = st.progress(0)
        statusText = st.empty()

        statusText.text("Cloning repository...")
        progressBar.progress(10)
        destPath, repo = cloneRepo(repoUrl)

        if destPath and repo:
            progressBar.progress(25)
            statusText.text("Scanning files...")
            files = repoCrawler(destPath)

            progressBar.progress(40)
            statusText.text("Extracting code structures...")
            results = processPythonFile(files, destPath, repo)

            progressBar.progress(55)
            statusText.text("Indexing code...")
            client, model = indexer(results)

            progressBar.progress(70)
            statusText.text("Extracting commit history...")
            commitsFile = extractHistory(repo, destPath)

            progressBar.progress(85)
            statusText.text("Indexing history...")
            client, model = indexHistory(commitsFile, client, model)

            st.session_state.client = client
            st.session_state.model = model
            st.session_state.messages = []

            progressBar.progress(100)
            statusText.text("Cleaning up...")
            cleanupRepo(destPath)

            statusText.empty()
            progressBar.empty()
            st.success(f"'{st.session_state.repo_name}' Repository indexed successfully")
        else:
            statusText.empty()
            progressBar.empty()
            st.error("Failed to clone repository.")
    else:
        st.warning("Please enter a URL.")

if st.session_state.client:
    st.divider()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if query := st.chat_input("Ask anything about the codebase or its history..."):

        with st.chat_message("user"):
            st.markdown(query)
        st.session_state.messages.append({"role": "user", "content": query})

        groqClient = Groq(api_key=groqApiKey)

        with st.spinner("Thinking..."):

            # Route the query
            route = routeQuery(query)

            queryVector = st.session_state.model.encode(query).tolist()
            contextBlocks = []
            searchResults = []

            # Search the right index(es)
            if route in ["CODE", "BOTH"]:
                codeResponse = st.session_state.client.query_points(
                    collection_name="tempCollection",
                    query=queryVector,
                    limit=contextLimit
                )
                for res in codeResponse.points:
                    p = res.payload
                    block = (
                        f"[CODE] FILE: {p.get('filePath')}\n"
                        f"METADATA: Parent={p.get('parentClass')}, Imports={p.get('modules')}\n"
                        f"LAST COMMIT: {p.get('history', {}).get('lastCommit', {}).get('msg')}\n"
                        f"CODE:\n{p.get('content')}"
                    )
                    contextBlocks.append(block)
                    searchResults.append(("code", res))

            if route in ["HISTORY", "BOTH"]:
                historyResponse = st.session_state.client.query_points(
                    collection_name="historyIndex",
                    query=queryVector,
                    limit=contextLimit
                )
                for res in historyResponse.points:
                    p = res.payload
                    block = (
                        f"[HISTORY] COMMIT: {p.get('sha')} by {p.get('author')} on {p.get('date', '')[:10]}\n"
                        f"SUMMARY: {p.get('summary')}\n"
                        f"FILES: {', '.join(f['file'] for f in p.get('changes', []))}\n"
                        f"CHANGES: {p.get('embedText')}"
                    )
                    contextBlocks.append(block)
                    searchResults.append(("history", res))

            if not contextBlocks:
                fullResponse = "I couldn't find relevant information. Try rephrasing your question."
            else:
                formattedContext = "\n---\n".join(contextBlocks)

                systemPrompts = (
                    "You are a Senior Software Architect and code historian for GitSpec. "
                    "You have access to two knowledge sources: current source code (CODE) and git commit history (HISTORY). "
                    "Use whichever is relevant to answer the question accurately."
                    "\n\nSTRICT FORMATTING RULES:"
                    "\n- Start immediately with the answer."
                    "\n- Use H3 headers (###) for distinct sections."
                    "\n- For history answers, always cite the commit SHA and author."
                    "\n- For code answers, reference the file and function name."
                    "\n- Do NOT include absolute local file paths."
                    "\n- Keep the tone professional and concise."
                    "\n- Be concise. No 'In conclusion' or summary sections — end when the answer is complete."

                )

                llm_messages = [
                    {"role": "system", "content": systemPrompts},
                    *st.session_state.messages[-5:],
                    {"role": "user", "content": f"Context:\n{formattedContext}\n\nQuestion: {query}"}
                ]
                try:
                    llmResponse = groqClient.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=llm_messages,
                        temperature=0.1
                    )
                    fullResponse = llmResponse.choices[0].message.content
                except Exception as e:
                    if "rate_limit_exceeded" in str(e).lower() or "413" in str(e):
                        fullResponse = (
                            "**Rate Limit Reached:** The context for this repository is quite large for the free tier. "
                            "I've tried to answer, but Groq is busy. Please try: \n"
                            "1. Reducing the **Context Depth** slider in the sidebar.\n"
                            "2. Asking a more specific question.\n"
                            "3. Waiting 60 seconds and trying again."
                        )
                    else:
                        fullResponse = f"An unexpected error occurred: {str(e)}"
                        

        # Display answer
        with st.chat_message("assistant"):
            st.markdown(fullResponse)
            st.caption(f"Route: `{route}`") 

            if searchResults:
                with st.expander("Explore Reference Sources"):
                    for sourceType, res in searchResults:
                        p = res.payload
                        if sourceType == "code":
                            st.caption(f"[CODE] {p.get('filePath')}")
                            st.code(p.get('content'), language='python')
                        else:
                            st.caption(f"[HISTORY] {p.get('sha')} — {p.get('summary')}")
                            for change in p.get('changes', []):
                                st.caption(f"File: {change['file']} ({change['status']})")

        st.session_state.messages.append({"role": "assistant", "content": fullResponse})