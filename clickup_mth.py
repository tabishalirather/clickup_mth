from fastapi import FastAPI, Request, HTTPException
import requests

app = FastAPI()

# ✅ Define ClickUp OAuth credentials
CLICKUP_CLIENT_ID = "YXY2BXLJR2N64YRRB5I4DRFVNUY16OX3"
CLICKUP_CLIENT_SECRET = "AH3ERQEO94BNDX8OGYKQ48LHZJOH0V5JXK9UDHE7VAJ6I3RQA1LOSJ7V0VV94VW4"
CLICKUP_REDIRECT_URI = "http://localhost:8000/callback"

# ✅ Temporary storage for access token (Replace with a database in production)
# ACCESS_TOKEN = None


@app.get("/")
async def home():
    """Generate ClickUp OAuth URL."""
    auth_url = f"https://app.clickup.com/api?client_id={CLICKUP_CLIENT_ID}&redirect_uri={CLICKUP_REDIRECT_URI}"
    return {"message": "Click the link to authorize the app", "auth_url": auth_url}


import json
import os

TOKEN_FILE = "token.json"


def save_access_token(token):
    """Save access token to a JSON file for persistent storage."""
    with open(TOKEN_FILE, "w") as f:
        json.dump({"access_token": token}, f)


def load_access_token():
    """Load access token from JSON file if it exists."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
            return data.get("access_token")
    return None


ACCESS_TOKEN = load_access_token()  # Load token on startup


@app.get("/callback")
async def clickup_callback(request: Request):
    """Handles OAuth2 callback and stores the access token permanently."""
    global ACCESS_TOKEN

    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code found.")

    token_url = "https://api.clickup.com/api/v2/oauth/token"
    data = {
        "client_id": CLICKUP_CLIENT_ID,
        "client_secret": CLICKUP_CLIENT_SECRET,
        "code": code,
        "redirect_uri": CLICKUP_REDIRECT_URI,
    }

    response = requests.post(token_url, json=data)

    if response.status_code != 200:
        return {"error": "Failed to retrieve access token", "details": response.json()}

    ACCESS_TOKEN = response.json().get("access_token")

    # Save token to file
    save_access_token(ACCESS_TOKEN)

    return {"message": "OAuth successful!", "access_token": ACCESS_TOKEN}


@app.get("/get_user")
async def get_user():
    """Fetch user information from ClickUp using the access token."""
    if not ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Access token not found. Authenticate first.")

    user_url = "https://api.clickup.com/api/v2/user"

    headers = {
        "Authorization": ACCESS_TOKEN
    }

    response = requests.get(user_url, headers=headers)

    if response.status_code != 200:
        return {"error": "Failed to retrieve user data", "details": response.json()}

    return response.json()


@app.get("/get_doc/{doc_id}")
async def get_clickup_doc(doc_id: str):
    """Fetches the content of a ClickUp doc."""
    if not ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Access token not found. Authenticate first.")

    doc_url = f"https://api.clickup.com/api/v2/doc/{doc_id}"
    headers = {"Authorization": ACCESS_TOKEN}

    response = requests.get(doc_url, headers=headers)

    if response.status_code != 200:
        return {"error": "Failed to retrieve ClickUp doc", "details": response.json()}

    return response.json()


import re

def find_latex_expressions(text):
    """Finds LaTeX expressions enclosed in $...$ or \[...\]"""
    pattern = r"\$.*?\$|\[.*?\]"
    matches = re.findall(pattern, text)
    return matches


def convert_latex_to_html(latex_code):
    """Converts LaTeX to an HTML string for KaTeX rendering in ClickUp Docs."""
    return f'<span class="katex">{latex_code}</span>'



@app.put("/update_doc/{doc_id}")
async def update_clickup_doc(doc_id: str):
    """Fetches a ClickUp doc, replaces LaTeX with HTML, and updates the doc."""
    if not ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Access token not found. Authenticate first.")

    # ✅ Step 1: Fetch the existing ClickUp doc content
    doc_content = get_clickup_doc(doc_id)

    if "error" in doc_content:
        return doc_content  # Return error if fetching fails

    text = doc_content.get("content", "")

    # ✅ Step 2: Find LaTeX expressions
    latex_expressions = find_latex_expressions(text)

    # ✅ Step 3: Replace each LaTeX expression with its rendered KaTeX HTML
    for latex in latex_expressions:
        html_rendered = convert_latex_to_html(latex)
        text = text.replace(latex, html_rendered)  # Embed KaTeX directly in ClickUp Doc

    # ✅ Step 4: Send updated text back to ClickUp
    headers = {"Authorization": ACCESS_TOKEN, "Content-Type": "application/json"}
    data = {"content": text}

    update_url = f"https://api.clickup.com/api/v2/doc/{doc_id}"
    response = requests.put(update_url, json=data, headers=headers)

    if response.status_code == 200:
        return {"message": "ClickUp Doc Updated Successfully!", "new_content": text}
    else:
        return {"error": "Update failed", "details": response.json()}


@app.post("/register_webhook")
async def register_webhook():
    """Registers a webhook with ClickUp to detect document updates."""
    webhook_url = "https://api.clickup.com/api/v2/team/YOUR_TEAM_ID/webhook"
    headers = {"Authorization": ACCESS_TOKEN, "Content-Type": "application/json"}

    data = {
        "endpoint": "http://your-server-ip:8000/clickup_webhook",
        "events": ["documentUpdated"],
        "task_id": None
    }

    response = requests.post(webhook_url, json=data, headers=headers)

    if response.status_code == 200:
        return {"message": "Webhook registered successfully!"}
    else:
        return {"error": "Webhook registration failed", "details": response.json()}


@app.post("/clickup_webhook")
async def clickup_webhook(request: Request):
    """Handles webhook events from ClickUp when a doc is modified."""
    payload = await request.json()

    # Ensure the webhook event is related to document updates
    if "event" not in payload or payload["event"] != "documentUpdated":
        return {"message": "Ignored event"}

    doc_id = payload.get("document_id")

    if not doc_id:
        return {"error": "No document ID found in payload"}

    # Process the document to render LaTeX
    return await update_clickup_doc(doc_id)

