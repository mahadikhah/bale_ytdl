import os
import subprocess
import requests

TOKEN = os.environ["BALE_BOT_TOKEN"]
VIDEO_URL = os.environ["VIDEO_URL"]
CHAT_ID = os.environ["CHAT_ID"]
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"

def send_message(text):
    url = f"{BASE_URL}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text})

def send_document(file_path):
    url = f"{BASE_URL}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": CHAT_ID}
        resp = requests.post(url, data=data, files=files)
        return resp.ok

def main():
    send_message("📥 Downloading video (this may take a few minutes)...")
    output = "video.mp4"
    # Try to stay under 50 MB (Bale limit)
    cmd = ["yt-dlp", "-f", "best[filesize<50M]/best", "-o", output, VIDEO_URL]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        send_message(f"❌ Download failed: {result.stderr[:200]}")
        return

    file_size = os.path.getsize(output)
    if file_size > 50 * 1024 * 1024:
        send_message("⚠️ Video exceeds 50 MB and cannot be sent. Try a shorter video or lower quality.")
        os.remove(output)
        return

    send_message("📤 Sending video...")
    if send_document(output):
        send_message("✅ Done!")
    else:
        send_message("❌ Failed to send the video (maybe too large or Bale error).")
    os.remove(output)

if __name__ == "__main__":
    main()
