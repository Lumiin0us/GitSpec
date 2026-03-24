# GitSpec — AI-Powered Codebase Intelligence

GitSpec is an AI tool that indexes both the current source code and the git commit history of any Python repository, then lets you query both through a natural language chat interface. A router agent automatically decides whether your question needs code context, history context, or both — and combines the results into a single grounded answer. 

## Live Demo
[Try GitSpec](https://huggingface.co/spaces/luminoria/GitSpec)

---

## GitSpec User Guide

Usage

1. Open the app in your browser by clicking on the live demo link above
2. Paste any public GitHub repository URL
3. Click Analyze Repository and wait for indexing to complete
4. Ask questions in the chat interface

Tips:

- For history questions, be specific: "What did [author name] change recently?" returns better results than "what changed?"
- Use the Explore Reference Sources expander under each answer to see the raw code or commit that backed the response
- The Route label under each answer shows which index(es) were searched


Limitations

Indexes the last 200 commits maximum — very large repositories with older history will not have that context
Only indexes Python files — JavaScript, TypeScript, Go, and other languages are not currently supported
Qdrant runs in-memory — the index is rebuilt on every new repository submission, previous indexes are not persisted
Requires a public repository — private repos require GitHub authentication (not yet implemented)

---

## How It Works

GitSpec runs a five-stage pipeline on every repository being submitted:
  1. Clone — The repository is cloned into a temporary directory using GitPython.
  2. Crawl — All Python files are discovered recursively, filtering out __pycache__, virtual environments, and build artifacts.
  3. Extract — Each Python file is parsed using libcst to extract functions, methods, and classes as individual units. Each unit captures its calls, dependencies, imports, global variables, parent class context, and git metadata (first         and last commit per file).
  4. Index Code — Extracted code units are embedded using all-MiniLM-L6-v2 and stored in a Qdrant in-memory vector collection (code_index).
  5. Extract & Index History — The last 200 commits are processed, filtered for noise (bots, translation-only commits, bulk file dumps), and the meaningful code commits are embedded and stored in a second Qdrant collection (history_index).

-> When a user asks a question, a router agent classifies it as CODE, HISTORY, or BOTH and searches the appropriate index(es) before synthesising a final answer.

---

## What Makes GitSpec Different

Most code intelligence tools give you one of two things:

Current code understanding — "here's what this function does right now"
Git log — "here's a list of commits"

GitSpec gives you both in a single answer, connected. When you ask "how does session management work and has it changed recently?", you get the current implementation and the specific commits that shaped it, cited by SHA and author. That combination — present state plus historical reasoning, which is what makes debugging and onboarding genuinely faster.

---

## Tech Stack

libcst  
all-MiniLM-L6-v2  
Groq API — LLaMA 3.3-70B Versatile  
Qdrant  
GitPython  
Streamlit  
HuggingFace (backend)  

---

## Project Structure
```
GitSpec/
├── backend/
│   ├── __init__.py
│   ├── clone.py              # Clone repo to temp directory
│   ├── crawl.py              # Discover Python files recursively
│   ├── extract.py            # libcst AST extraction per function/class
│   ├── indexer.py            # Embed and store code units in Qdrant
│   ├── historyExtractor.py   # Extract + filter git commit history
│   ├── historyIndexer.py     # Embed and store commits in Qdrant
│   └── router.py            
├── streamlitUI.py          
├── .env                      # Added to gitIgnore                
├── .gitignore
├── requirements.txt
└── README.md
```
