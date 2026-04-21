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
        requests.post(url, data={"chat_id": CHAT_ID}, files=files)

def main():
    send_message("📥 Downloading video... This may take a few minutes.")
    output = "video.mp4"
    cmd = ["yt-dlp", "-f", "best[filesize<45M]/best", "-o", output, VIDEO_URL]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        send_message(f"Download failed: {result.stderr.decode()[:200]}")
        return
    send_message("📤 Sending video...")
    send_document(output)
    os.remove(output)
    send_message("✅ Done!")

if __name__ == "__main__":
    main()
