from fastapi import FastAPI, Request, HTTPException
import requests
import logging


app = FastAPI()

# ✅ Ensure all credentials are defined correctly
CLICKUP_CLIENT_ID = "YXY2BXLJR2N64YRRB5I4DRFVNUY16OX3"
CLICKUP_CLIENT_SECRET = "AH3ERQEO94BNDX8OGYKQ48LHZJOH0V5JXK9UDHE7VAJ6I3RQA1LOSJ7V0VV94VW4"
CLICKUP_REDIRECT_URI = "http://localhost:8000/callback"

# Temporary storage for access token (Use a database in production)
ACCESS_TOKEN = None

@app.get("/", response_model=dict)
def home():
    """Generate ClickUp OAuth URL."""
    auth_url = f"https://app.clickup.com/api?client_id={CLICKUP_CLIENT_ID}&redirect_uri={CLICKUP_REDIRECT_URI}"
    return {"message": "Click the link to authorize the app", "auth_url": auth_url}

@app.get("/callback", response_model=dict)
def clickup_callback(request: Request):
    """Handle OAuth2 callback and exchange code for access token."""
    global ACCESS_TOKEN

    # ✅ Get the authorization code from the callback URL
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code found.")

    # ✅ Exchange the authorization code for an access token
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

    return {"message": "OAuth successful!", "access_token": ACCESS_TOKEN}



# import logging
# noinspection PyUnusedLocal,PyDeprecation
@app.on_event("startup")
async def startup_event():
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Registered routes: {[route.path for route in app.routes]}")

