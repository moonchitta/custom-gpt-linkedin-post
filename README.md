# LinkedIn API Integration with Python

This project provides a simple Python-based implementation for interacting with the LinkedIn API. It allows users to:
- Authenticate using OAuth2.
- Post updates to LinkedIn, including text, URLs, images, and videos.
- Automatically handle metadata for URL posts, such as thumbnails and descriptions.

---

## Features

1. **LinkedIn Authentication**:
   - Initiates LinkedIn OAuth2 flow.
   - Stores access tokens and user profile URN for making API requests.

2. **Post Updates to LinkedIn**:
   - Text Posts
   - URL Posts (with automatic metadata scraping)
   - Image Posts
   - Video Posts

3. **Error Handling**:
   - Handles API errors gracefully with detailed error messages.

---

## Prerequisites

- Python 3.7 or later.
- A LinkedIn Developer Account with the required API keys.
- The following LinkedIn API permissions:
  - `w_member_social` (for posting updates).
  - `r_liteprofile` or `r_basicprofile` (for accessing user profile details).

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo/linkedin-api-integration.git
   cd linkedin-api-integration
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your LinkedIn app credentials:
   - Create a `.env` file in the project root with the following:
     ```
     CLIENT_ID=your_linkedin_client_id
     CLIENT_SECRET=your_linkedin_client_secret
     REDIRECT_URI=your_redirect_uri
     ```

---

## Usage

### 1. Start the Server
Run the Flask server:
```bash
python app.py
```

### 2. Authentication
- Navigate to `/linkedin/auth` to get the LinkedIn authorization URL.
- Complete the authorization process and retrieve the authorization code.
- The server will handle the callback and save the access token and profile URN.

### 3. Post Updates
- Use `/linkedin/post` endpoint to post updates to LinkedIn.
- Example JSON payloads:
  - **Text Post**:
    ```json
    {
      "type": "TEXT",
      "text": "This is a text post on LinkedIn."
    }
    ```
  - **URL Post**:
    ```json
    {
      "type": "URL",
      "text": "Check out this blog post!",
      "url": "https://example.com/blog"
    }
    ```
  - **Image Post**:
    ```json
    {
      "type": "IMAGE",
      "text": "Here's an image post!",
      "media_url": "https://example.com/image.jpg"
    }
    ```
  - **Video Post**:
    ```json
    {
      "type": "VIDEO",
      "text": "Watch this amazing video!",
      "media_url": "https://example.com/video.mp4"
    }
    ```

---

## API Endpoints

### `/linkedin/auth`
- **Method**: `GET`
- **Description**: Provides the LinkedIn OAuth2 authorization URL.

### `/linkedin/callback`
- **Method**: `GET`
- **Description**: Handles the LinkedIn OAuth2 callback to retrieve and store the access token.

### `/linkedin/post`
- **Method**: `POST`
- **Description**: Posts content (text, URL, image, or video) to LinkedIn.
- **Payload**:
  - `type` (required): Type of post (`TEXT`, `URL`, `IMAGE`, `VIDEO`).
  - `text` (required): Text content of the post.
  - `url` (optional): URL to share (required for `URL` posts).
  - `media_url` (optional): Media file URL (required for `IMAGE` and `VIDEO` posts).

---

## Dependencies

- **Flask**: For creating API endpoints.
- **Requests**: For handling HTTP requests.
- **BeautifulSoup4**: For scraping metadata from URLs.
- **lxml**: For improved HTML parsing performance.

Install all dependencies:
```bash
pip install flask requests beautifulsoup4 lxml
```

---

## Example Workflow

1. **Authenticate**:
   - Navigate to `/linkedin/auth`.
   - Authorize the app via LinkedIn and provide the authorization code.

2. **Post Updates**:
   - Use the `/linkedin/post` endpoint with a valid payload.

---

## Error Handling

The API provides detailed error responses for:
- Missing fields.
- Invalid payloads.
- LinkedIn API errors (e.g., permissions or authentication issues).

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.
```

---

### How to Use
Save this `README.md` file in the root of your project. Update the placeholders (e.g., `your_linkedin_client_id`) with actual values specific to your project before sharing or publishing it. Let me know if you'd like to refine any part of the documentation!