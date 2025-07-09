import os, base64, mimetypes
from resilient import SimpleClient

def post_note_inline_image(client: SimpleClient,
                           incident_id: int,
                           note_html: str,
                           image_path: str) -> dict:
    """
    Embed a local image as a Base64 Data URI in the note’s HTML.
    """
    # 1. Read & encode the image
    mime, _ = mimetypes.guess_type(image_path)
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    # 2. Build your HTML: include the <img> tag with data URI
    img_tag = f'<img src="data:{mime};base64,{b64}" alt="{os.path.basename(image_path)}"/>'
    full_html = note_html + "<br/><br/>" + img_tag

    # 3. Post it
    payload = {"type_id": 0, "content": full_html}
    return client.post(f"/incidents/{incident_id}/notes", payload)


def post_note_with_attachment(client: SimpleClient,
                              incident_id: int,
                              note_html: str,
                              image_path: str) -> dict:
    """
    Upload the image as a note-attachment, then reference it by URL in the note HTML.
    """
    # 1. Upload the image to the incident’s attachments
    # Note: resilient.SimpleClient.session is a requests.Session under the hood
    files = {
      "attachment": (os.path.basename(image_path),
                     open(image_path, "rb"),
                     mimetypes.guess_type(image_path)[0] or "application/octet-stream")
    }
    attach_resp = client.session.post(
        client.base_url + f"/incidents/{incident_id}/attachments",
        files=files,
        auth=client.session.auth,
        verify=client.session.verify
    )
    attach_resp.raise_for_status()
    attach_id = attach_resp.json()["attachment_id"]

    # 2. Build the <img> tag pointing at the binary endpoint
    # The SDK will resolve org_name → org_id for you
    img_url  = f"{client.base_url}/incidents/{incident_id}/attachments/{attach_id}/data"
    img_tag  = f'<img src="{img_url}" alt="{os.path.basename(image_path)}"/>'
    full_html = note_html + "<br/><br/>" + img_tag

    # 3. Post the note
    payload = {"type_id": 0, "content": full_html}
    return client.post(f"/incidents/{incident_id}/notes", payload)


# ————————————————
# Usage (no CLI needed):

client = SimpleClient(
    base_url       = os.getenv("SOAR_BASE_URL"),
    org_name       = os.getenv("SOAR_ORG"),
    api_key_id     = os.getenv("SOAR_API_KEY_ID"),
    api_key_secret = os.getenv("SOAR_API_KEY_SECRET"),
    verify         = os.getenv("SOAR_VERIFY", False)
)

incident_id = 12345
note_text   = "<h2>Final Findings</h2><p>See screenshot below:</p>"
image_path  = "/Users/you/Desktop/screenshot.png"

# 1) Inline base64
resp1 = post_note_inline_image(client, incident_id, note_text, image_path)
print("Posted inline‐image note ID:", resp1["id"])

# 2) Attachment + URL
resp2 = post_note_with_attachment(client, incident_id, note_text, image_path)
print("Posted attached‐image note ID:", resp2["id"])
