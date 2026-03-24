from groq import Groq
import os
import json
from dotenv import load_dotenv

load_dotenv()

groqClient = Groq(api_key=os.getenv("GROQ_API_KEY"))

def routeQuery(query: str) -> str:
    """
    Classifies a user query into one of three routes:
    CODE     - search the code index (current structure, how things work)
    HISTORY  - search the history index (why things changed, who changed what)
    BOTH     - search both indexes and merge results
    """

    prompt = f"""You are a query router for a code intelligence tool called GitSpec.
GitSpec has two knowledge bases:

1. CODE INDEX — contains the current source code: functions, classes, methods, imports.
   Use this for questions about how something works RIGHT NOW.
   Examples: "how does authentication work?", "what does process_order do?", "what classes exist in the payment module?"

2. HISTORY INDEX — contains git commit history: what changed, when, who changed it, and why.
   Use this for questions about change over time, blame, or reasoning.
   Examples: "why did the auth module change?", "who introduced rate limiting?", "what changed last month?"

3. BOTH — use when the question needs current code understanding AND historical context.
   Examples: "how does auth work and why was it redesigned?", "what does checkout do and when was it last changed?"

Classify this query into exactly one of: CODE, HISTORY, BOTH

Query: {query}

Respond with valid JSON only. No explanation. No markdown.
Format: {{"route": "CODE"}} or {{"route": "HISTORY"}} or {{"route": "BOTH"}}"""

    response = groqClient.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,  
        max_tokens=20,    
    )

    raw = response.choices[0].message.content.strip()

    try:
        result = json.loads(raw)
        route = result.get("route", "BOTH").upper()
        if route not in ["CODE", "HISTORY", "BOTH"]:
            route = "BOTH"  
        return route
    except json.JSONDecodeError:
        return "BOTH"