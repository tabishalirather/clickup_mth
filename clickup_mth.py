from fastapi import FastAPI, Request, HTTPException
import requests
import json
import os
import re

app = FastAPI()

# ✅ ClickUp API Credentials
CLICKUP_CLIENT_ID = "YXY2BXLJR2N64YRRB5I4DRFVNUY16OX3"
CLICKUP_CLIENT_SECRET = "AH3ERQEO94BNDX8OGYKQ48LHZJOH0V5JXK9UDHE7VAJ6I3RQA1LOSJ7V0VV94VW4"
CLICKUP_REDIRECT_URI = "https://clickup-mth.onrender.com/callback"

# ✅ Persistent Storage for OAuth Tokens
TOKEN_FILE = "token.json"

def save_access_token(token):
    """Save the access token for persistent storage."""
    with open(TOKEN_FILE, "w") as f:
        json.dump({"access_token": token}, f)

def load_access_token():
    """Load access token from storage if available."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
            return data.get("access_token")
    return None

ACCESS_TOKEN = load_access_token()  # Load token on startup

@app.get("/")
async def home():
    """Returns the ClickUp authorization link."""
    auth_url = f"https://app.clickup.com/api?client_id={CLICKUP_CLIENT_ID}&redirect_uri={CLICKUP_REDIRECT_URI}"
    return {"message": "Click the link to authorize the app", "auth_url": auth_url}

@app.get("/callback")
async def clickup_callback(request: Request):
    """Handles OAuth2 callback and stores the access token."""
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
    save_access_token(ACCESS_TOKEN)  # Save token for reuse

    return {"message": "OAuth successful!", "access_token": ACCESS_TOKEN}


@app.get("/get_doc/{doc_id}")
async def get_clickup_doc(doc_id: str):
    """Fetches the content of a ClickUp doc using the correct API endpoint."""
    if not ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Access token not found. Authenticate first.")

    workspace_id = "9016542535"  # Your actual workspace ID
    doc_url = f"https://api.clickup.com/api/v3/workspaces/{workspace_id}/docs/{doc_id}"

    headers = {
        "Authorization": ACCESS_TOKEN,
        "Accept": "application/json"
    }

    response = requests.get(doc_url, headers=headers)

    # ✅ Debugging: Print response for testing
    print("🔹 Requesting:", doc_url)
    print("🔹 Response Code:", response.status_code)
    print("🔹 Response Body:", response.text)

    if response.status_code != 200:
        return {
            "error": "Failed to retrieve ClickUp doc",
            "status": response.status_code,
            "details": response.json()
        }

    return response.json()


def find_latex_expressions(text):
    """Finds LaTeX expressions enclosed in $...$ or \[...\]"""
    pattern = r"\$(.*?)\$|\[(.*?)\]"
    matches = re.findall(pattern, text)
    return [match[0] if match[0] else match[1] for match in matches]

def convert_latex_to_image(latex_code):
    """Generates an image URL for LaTeX using an online LaTeX rendering service."""
    encoded_latex = latex_code.replace(" ", "%20")
    return f"https://latex.codecogs.com/png.latex?{encoded_latex}"

@app.put("/update_doc/{doc_id}")
async def update_clickup_doc(doc_id: str):
    """Fetches a ClickUp doc, replaces LaTeX with images, and updates the doc."""
    if not ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Access token not found. Authenticate first.")

    # ✅ Step 1: Fetch the existing ClickUp doc content
    doc_content = await get_clickup_doc(doc_id)

    if "error" in doc_content:
        return doc_content  # Return error if fetching fails

    text = doc_content.get("content", "")

    # ✅ Step 2: Find LaTeX expressions
    latex_expressions = find_latex_expressions(text)

    # ✅ Step 3: Replace each LaTeX expression with its rendered image
    for latex in latex_expressions:
        image_url = convert_latex_to_image(latex)
        text = text.replace(f"${latex}$", f"![Math]({image_url})")  # Markdown format for ClickUp

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
    # YOUR_TEAM_ID = "9016542535"  # Replace with your team ID
    webhook_url = f"https://api.clickup.com/api/v2/team/9016542535/webhook"
    headers = {"Authorization": ACCESS_TOKEN, "Content-Type": "application/json"}

    data = {
        "endpoint": "https://clickup-mth.onrender.com/clickup_webhook",
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
    """Handles webhook events from ClickUp when a doc or task is updated."""
    payload = await request.json()
    print("🔹 Received Webhook:", json.dumps(payload, indent=4))  # Log incoming payload

    # Allow both document and task updates
    if "event" not in payload or payload["event"] not in ["documentUpdated", "taskUpdated"]:
        return {"message": "Yeah naah mate"}

    task_id = payload.get("task_id")
    doc_id = payload.get("document_id")

    if task_id:
        print(f"🔹 Task Updated: {task_id}, Changes: {payload.get('changes')}")
        return {"message": "Task update received", "task_id": task_id, "changes": payload.get("changes")}

    if doc_id:
        return await update_clickup_doc(doc_id)

    return {"error": "No task_id or document_id found in payload"}
