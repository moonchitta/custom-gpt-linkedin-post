from datetime import datetime, timedelta

from flask import Flask, request, jsonify, redirect
import requests
import os
import json
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# LinkedIn OAuth and API setup
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
ACCESS_TOKEN_FILE = os.getenv("ACCESS_TOKEN_FILE", "linkedin_access_token.json")
PROFILE_URN_FILE = os.getenv("PROFILE_URN_FILE", "linkedin_profile_urn.json")

# LinkedIn authorization URL
LINKEDIN_AUTH_URL = (
    f"https://www.linkedin.com/oauth/v2/authorization?response_type=code"
    f"&client_id={LINKEDIN_CLIENT_ID}&redirect_uri={REDIRECT_URI}"
    f"&scope=openid%20profile%20email%20w_member_social"
)


# Function to save token
def save_token(access_token, expires_in):
    expiration_time = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
    token_data = {
        "access_token": access_token,
        "expiration_time": expiration_time
    }
    with open(ACCESS_TOKEN_FILE, "w") as file:
        json.dump(token_data, file)

def validate_token():
    """
    Validate the access token and check if it is missing or expired.
    Return an error response if the token is invalid, otherwise return None.
    """
    access_token, expiration_time = load_token()  # Load the token and its expiration time
    if not access_token or (expiration_time and is_token_expired(expiration_time)):
        print(f"Generate new token")
        return jsonify({
            "error": "Access token is missing or expired. Please generate a new token.",
            "authorization_url": LINKEDIN_AUTH_URL
        }), 401
    return None

# Function to load token
def load_token():
    if not os.path.exists(ACCESS_TOKEN_FILE):
        return None, None

    with open(ACCESS_TOKEN_FILE, "r") as file:
        token_data = json.load(file)

    access_token = token_data.get("access_token")
    expiration_time_str = token_data.get("expiration_time")

    if not access_token or not expiration_time_str:
        return None, None

    try:
        expiration_time = datetime.fromisoformat(expiration_time_str)
    except ValueError:
        return None, None

    return access_token, expiration_time


# Function to check if token is expired
def is_token_expired(expiration_time):
    return datetime.now() >= expiration_time


@app.route('/linkedin/generate_token', methods=['POST'])
def generate_token():
    data = request.json
    auth_code = data.get("authorization_code")
    if not auth_code:
        return jsonify({"error": "Authorization code is required"}), 400

    # Token exchange URL
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    payload = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    # Exchange the authorization code for an access token
    response = requests.post(token_url, data=payload, headers=headers)
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in")
        save_token(access_token, expires_in)
        return jsonify({"message": "Token generated successfully", "access_token": access_token})
    else:
        return jsonify({"error": "Token generation failed", "details": response.json()}), response.status_code


# # Middleware to ensure token validity
# @app.before_request
# def ensure_token_validity():
#     # Exclude endpoints that are part of the authorization flow
#     excluded_paths = ["/linkedin/auth", "/linkedin/callback", "/linkedin/generate_token"]
#     if any(request.path.startswith(path) for path in excluded_paths):
#         return
#
#     # Validate the token for other endpoints
#     access_token, expiration_time = load_token()
#     if not access_token or (expiration_time and is_token_expired(expiration_time)):
#         return jsonify({"error": "Access token is missing or expired. Please generate a new token."}), 401

@app.route("/linkedin/auth", methods=["GET"])
def linkedin_auth():

    """Provide the LinkedIn authorization URL to the user."""
    validation_response = validate_token()
    if validation_response:
        return validation_response

    print(f"provide auth link to user")
    """Provide the LinkedIn authorization URL to the user."""
    try:
        # Return the LinkedIn authorization URL in the response
        return jsonify({
            "message": "Complete the authorization by visiting the URL below:",
            "authorization_url": LINKEDIN_AUTH_URL
        }), 200
    except Exception as e:
        print(f"Exception: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/linkedin/callback", methods=["GET"])
def linkedin_callback():
    """Handle the callback from LinkedIn and get an access token."""
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Authorization code not found."}), 400

    # Exchange the authorization code for an access token
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET,
    }
    response = requests.post(token_url, data=payload)
    token_data = response.json()

    if "access_token" not in token_data or "id_token" not in token_data:
        return jsonify({"error": "Failed to obtain access token.", "details": token_data}), 400

    # Save access token for future use
    with open(ACCESS_TOKEN_FILE, "w") as token_file:
        json.dump(token_data, token_file)

    # Decode the ID token to extract the `sub` field
    id_token = token_data["id_token"]
    try:
        import jwt  # PyJWT library to decode JWT tokens
        decoded_id_token = jwt.decode(id_token, options={"verify_signature": False})
        sub = decoded_id_token.get("sub")
    except Exception as e:
        return jsonify({"error": "Failed to decode ID token.", "details": str(e)}), 400

    if not sub:
        return jsonify({"error": "Missing 'sub' field in ID token."}), 400

    # Construct the Person URN
    profile_urn = f"urn:li:person:{sub}"
    with open(PROFILE_URN_FILE, "w") as urn_file:
        json.dump({"profile_urn": profile_urn}, urn_file)

    return jsonify({"message": "Authorization successful.", "profile_urn": profile_urn})

def upload_media_to_linkedin(access_token, media_url, profile_urn, media_type="IMAGE"):
    """Uploads media to LinkedIn and returns the Media URN."""
    init_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    payload = {
        "registerUploadRequest": {
            "owner": profile_urn,
            "recipes": [
                "urn:li:digitalmediaRecipe:feedshare-image" if media_type == "IMAGE" else "urn:li:digitalmediaRecipe:feedshare-video"
            ],
            "serviceRelationships": [
                {
                    "identifier": "urn:li:userGeneratedContent",
                    "relationshipType": "OWNER"
                }
            ]
        }
    }

    response = requests.post(init_url, headers=headers, json=payload)
    if response.status_code != 200:
        return {"error": "Failed to initialize media upload.", "details": response.json()}

    upload_data = response.json()
    upload_url = upload_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset_urn = upload_data["value"]["asset"]


    # Upload the media file
    media_content = requests.get(media_url).content
    media_response = requests.put(upload_url, headers={"Authorization": f"Bearer {access_token}"}, data=media_content)

    # Check for non-JSON response or empty response
    if media_response.status_code == 201:
        print("Media uploaded successfully.")
        return asset_urn
    elif media_response.headers.get("Content-Type", "").startswith("application/json"):
        print(f"Media Upload Response JSON: {json.dumps(media_response.json(), indent=4)}")
        return {"error": "Unexpected response during media upload.", "details": media_response.json()}
    else:
        print(f"Media Upload Response Text: {media_response.text}")
        return {"error": "Unexpected response during media upload.", "details": media_response.text}

def fetch_url_metadata(url):
    """Scrapes metadata (title, description, image) from a URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract metadata
        title = soup.title.string if soup.title else "No Title"
        description = (
            soup.find("meta", attrs={"name": "description"}) or
            soup.find("meta", attrs={"property": "og:description"})
        )
        image = (
            soup.find("meta", attrs={"property": "og:image"}) or
            soup.find("meta", attrs={"name": "twitter:image"})
        )

        return {
            "title": title,
            "description": description["content"] if description else "",
            "image": image["content"] if image else ""
        }
    except Exception as e:
        print(f"Error fetching metadata: {e}")
        return {"title": "No Title", "description": "", "image": ""}


@app.route("/linkedin/post", methods=["POST"])
def linkedin_post():

    """Provide the LinkedIn authorization URL to the user."""
    validation_response = validate_token()
    if validation_response:
        return validation_response

    """Post an update to LinkedIn."""
    try:
        with open(ACCESS_TOKEN_FILE, "r") as token_file:
            token_data = json.load(token_file)
        access_token = token_data["access_token"]

        with open(PROFILE_URN_FILE, "r") as urn_file:
            profile_data = json.load(urn_file)
        profile_urn = profile_data["profile_urn"]
    except FileNotFoundError:
        return jsonify({"error": "Access token or profile URN not found. Please authorize first."}), 400

    post_data = request.json
    content_type = post_data.get("type", "TEXT")
    text = post_data.get("text", "")
    url = post_data.get("url", "")
    media_url = post_data.get("media_url", "")

    # Fetch metadata for URL posts
    metadata = None
    if content_type == "URL" and url:
        metadata = fetch_url_metadata(url)

    # Upload media if type is IMAGE or VIDEO
    media_urn = None
    if content_type in ["IMAGE", "VIDEO"]:
        media_urn = upload_media_to_linkedin(access_token, media_url, profile_urn, content_type)
        if isinstance(media_urn, dict) and "error" in media_urn:
            return jsonify({"error": "Failed to upload media.", "details": media_urn}), 400

    # Prepare payload for LinkedIn API
    payload = {
        "author": profile_urn,
        "lifecycleState": "PUBLISHED",
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE" if content_type in ["TEXT", "URL"] else content_type,
            }
        }
    }

    # Add URL metadata for URL posts
    if content_type == "URL" and url:
        payload["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "ARTICLE"
        payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
            {
                "originalUrl": url,
                "status": "READY"  # Include the required status field
            }
        ]

    # Add media for IMAGE or VIDEO posts
    if media_urn:
        payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
            {
                "status": "READY",
                "originalUrl": media_url,
                "media": media_urn,
            }
        ]

    # Post to LinkedIn
    api_url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    response = requests.post(api_url, headers=headers, json=payload)

    if response.status_code == 201:
        post_id = response.json()["id"]
        post_url = f"https://www.linkedin.com/feed/update/{post_id}"
        return jsonify({"message": "Post successful.", "response": response.json(), "post_url": post_url})

    return jsonify({"error": "Failed to post on LinkedIn.", "details": response.json()}), 400

# Endpoint to create a LinkedIn invitation
@app.route('/linkedin/invitation/create', methods=['POST'])
def create_invitation():
    data = request.json
    url = "https://api.linkedin.com/v2/invitations"

    try:
        with open(ACCESS_TOKEN_FILE, "r") as token_file:
            token_data = json.load(token_file)
        access_token = token_data["access_token"]

        with open(PROFILE_URN_FILE, "r") as urn_file:
            profile_data = json.load(urn_file)
        profile_urn = profile_data["profile_urn"]
    except FileNotFoundError:
        return jsonify({"error": "Access token or profile URN not found. Please authorize first."}), 400

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "invitee": {
            "com.linkedin.voyager.growth.invitation.InviteeProfile": {
                "profileId": data.get("profileId")
            }
        },
        "trackingId": data.get("trackingId"),
        "message": data.get("message", "")
    }
    response = requests.post(url, headers=headers, json=payload)
    return jsonify(response.json()), response.status_code

# Endpoint to retrieve LinkedIn invitations
@app.route('/linkedin/invitation/retrieve', methods=['GET'])
def retrieve_invitations():
    url = "https://api.linkedin.com/v2/invitations"
    try:
        with open(ACCESS_TOKEN_FILE, "r") as token_file:
            token_data = json.load(token_file)
        access_token = token_data["access_token"]
    except FileNotFoundError:
        return jsonify({"error": "Access token or profile URN not found. Please authorize first."}), 400

    print(f"Token: {access_token}")
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json()), response.status_code

# Endpoint to take action on a LinkedIn invitation
@app.route('/linkedin/invitation/action', methods=['POST'])
def action_on_invitation():
    data = request.json
    invitation_id = data.get("invitationId")
    action = data.get("action")  # Accept or Reject
    url = f"https://api.linkedin.com/v2/invitations/{invitation_id}/action/{action}"
    try:
        with open(ACCESS_TOKEN_FILE, "r") as token_file:
            token_data = json.load(token_file)
        access_token = token_data["access_token"]
    except FileNotFoundError:
        return jsonify({"error": "Access token or profile URN not found. Please authorize first."}), 400
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers)
    return jsonify(response.json()), response.status_code

# Endpoint to resolve LinkedIn invitation issues
@app.route('/linkedin/invitation/resolve', methods=['POST'])
def resolve_invitation_problems():
    data = request.json
    issue_type = data.get("issueType")  # Specify the issue type
    details = data.get("details")  # Additional details about the issue
    # Here, implement logic to handle or log specific invitation issues.
    # For now, we simulate resolving the issue.
    resolution = {
        "status": "Resolved",
        "issueType": issue_type,
        "details": details
    }
    return jsonify(resolution), 200

if __name__ == "__main__":
    app.run(port=8080, debug=True)
