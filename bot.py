import os
import time
import requests
import subprocess
import re

# ========== CONFIGURATION ==========
TOKEN = os.environ["BALE_BOT_TOKEN"]
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"
OFFSET_FILE = "last_update_id.txt"
MAX_FILE_SIZE = 45 * 1024 * 1024   # 45 MB (safe under Bale's limit)
TEMP_DIR = "temp_videos"
# ===================================

def get_last_offset():
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE, "r") as f:
            return int(f.read().strip())
    return 0

def save_offset(offset):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))

def send_message(chat_id, text, parse_mode=None):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send message: {e}")

def send_document(chat_id, file_path):
    url = f"{BASE_URL}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id}
        try:
            resp = requests.post(url, data=data, files=files, timeout=60)
            return resp.ok
        except Exception as e:
            print(f"Failed to send document {file_path}: {e}")
            return False

def download_youtube(url, output_path):
    """
    Download the best quality video that fits under MAX_FILE_SIZE.
    If no single format fits, download the smallest available.
    """
    cmd = [
        "yt-dlp",
        "-f", f"best[filesize<{MAX_FILE_SIZE}]/best",
        "--output", output_path,
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"yt-dlp error: {result.stderr}")
    return output_path

def split_video(input_path, chat_id):
    """
    Split video into chunks <= MAX_FILE_SIZE using ffmpeg (fast, no re-encode).
    Sends each chunk and returns number of successfully sent chunks.
    """
    file_size = os.path.getsize(input_path)
    if file_size <= MAX_FILE_SIZE:
        # Single file, no split needed
        return 1 if send_document(chat_id, input_path) else 0

    # Create temp directory for chunks
    os.makedirs(TEMP_DIR, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    ext = os.path.splitext(input_path)[1]
    chunk_pattern = os.path.join(TEMP_DIR, f"{base_name}_part_%03d{ext}")

    # Use ffmpeg to split by file size without re-encoding
    cmd = [
        "ffmpeg", "-i", input_path,
        "-c", "copy",
        "-map", "0",
        "-f", "segment",
        "-segment_time", "999999",     # effectively disable time-based split
        "-reset_timestamps", "1",
        "-fs", str(MAX_FILE_SIZE),
        chunk_pattern
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    # Send each chunk
    sent = 0
    part_num = 1
    while True:
        chunk_path = os.path.join(TEMP_DIR, f"{base_name}_part_{part_num:03d}{ext}")
        if not os.path.exists(chunk_path):
            break
        if send_document(chat_id, chunk_path):
            sent += 1
        os.remove(chunk_path)          # delete after sending
        time.sleep(0.5)                # avoid hitting rate limits
        part_num += 1

    return sent

def extract_youtube_id(text):
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})'
    ]
    for p in patterns:
        match = re.search(p, text)
        if match:
            return match.group(1)
    return None

def cleanup():
    """Remove temporary directory and all its contents."""
    if os.path.exists(TEMP_DIR):
        for f in os.listdir(TEMP_DIR):
            os.remove(os.path.join(TEMP_DIR, f))
        os.rmdir(TEMP_DIR)

def main():
    # Ensure temp directory exists at start
    os.makedirs(TEMP_DIR, exist_ok=True)

    offset = get_last_offset()
    print(f"Starting with offset {offset}")

    while True:
        url = f"{BASE_URL}/getUpdates"
        params = {"offset": offset, "timeout": 30}
        try:
            resp = requests.get(url, params=params, timeout=35)
            data = resp.json()
        except Exception as e:
            print(f"Error fetching updates: {e}")
            break

        if not data.get("ok"):
            print("API error:", data)
            break

        updates = data.get("result", [])
        if not updates:
            break

        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message")
            if not message:
                continue

            chat_id = message["chat"]["id"]
            text = message.get("text", "")

            # Handle /start command
            if text.startswith("/start"):
                send_message(chat_id,
                    "🎬 *YouTube Downloader Bot*\n\n"
                    "Send me a YouTube URL and I will download the video and send it back.\n"
                    "If the video is larger than 45 MB, I will split it into multiple parts.\n\n"
                    "Example: `https://youtu.be/dQw4w9WgXcQ`",
                    parse_mode="Markdown")
                continue

            # Extract YouTube ID
            video_id = extract_youtube_id(text)
            if not video_id:
                send_message(chat_id, "❌ No valid YouTube URL found. Please send a link like `https://youtu.be/...` or `https://youtube.com/watch?v=...`")
                continue

            # Process the video
            send_message(chat_id, "⏳ Downloading video... This may take a few minutes.")
            try:
                video_file = os.path.join(TEMP_DIR, f"{video_id}.mp4")
                download_youtube(text, video_file)

                send_message(chat_id, "📤 Sending video (split if necessary)...")
                sent_parts = split_video(video_file, chat_id)

                if sent_parts == 0:
                    send_message(chat_id, "❌ Failed to send any part. The video may be too large or Bale rejected it.")
                else:
                    send_message(chat_id, f"✅ Sent {sent_parts} part(s).")

                # Remove the original downloaded file
                if os.path.exists(video_file):
                    os.remove(video_file)
            except Exception as e:
                send_message(chat_id, f"⚠️ Error: {str(e)[:200]}")
            finally:
                cleanup()

        # Save offset after processing all updates in this batch
        save_offset(offset)
        time.sleep(1)   # small delay before next getUpdates

if __name__ == "__main__":
    main()
