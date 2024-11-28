from flask import Flask, request, jsonify, redirect
import requests
import os
import json
from bs4 import BeautifulSoup
import requests

app = Flask(__name__)

STATIC_TOKEN = "<your_token>"

# LinkedIn OAuth and API setup
LINKEDIN_CLIENT_ID = "<linkedin_client_id>"
LINKEDIN_CLIENT_SECRET = "<linkedin_client_secret>"
REDIRECT_URI = "https://<your_hosted_code>/linkedin/callback"
ACCESS_TOKEN_FILE = "linkedin_access_token.json"
PROFILE_URN_FILE = "linkedin_profile_urn.json"

# LinkedIn authorization URL
LINKEDIN_AUTH_URL = (
    f"https://www.linkedin.com/oauth/v2/authorization?response_type=code"
    f"&client_id={LINKEDIN_CLIENT_ID}&redirect_uri={REDIRECT_URI}"
    f"&scope=openid%20profile%20email%20w_member_social"
)

def validate_token():
    token = request.headers.get("Authorization")
    if not token or token != f"Bearer {STATIC_TOKEN}":
        return jsonify({"error": "Unauthorized. Invalid or missing token."}), 401

@app.route("/linkedin/auth", methods=["GET"])
def linkedin_auth():

    """Provide the LinkedIn authorization URL to the user."""
    validation_response = validate_token()
    if validation_response:
        return validation_response

    """Provide the LinkedIn authorization URL to the user."""
    try:
        # Return the LinkedIn authorization URL in the response
        return jsonify({
            "message": "Complete the authorization by visiting the URL below:",
            "authorization_url": LINKEDIN_AUTH_URL
        }), 200
    except Exception as e:
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

if __name__ == "__main__":
    app.run(port=5000, debug=True)