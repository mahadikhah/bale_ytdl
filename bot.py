import os
import time
import json
import requests
import subprocess
import re

TOKEN = os.environ["BALE_BOT_TOKEN"]
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"
OFFSET_FILE = "last_update_id.txt"
TEMP_DIR = "temp_videos"
MAX_FILE_SIZE = 45 * 1024 * 1024   # 45 MB

def get_last_offset():
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE) as f:
            return int(f.read().strip())
    return 0

def save_offset(offset):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))

def send_message(chat_id, text, reply_markup=None):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Send message error: {e}")

def send_document(chat_id, file_path):
    url = f"{BASE_URL}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id}
        try:
            resp = requests.post(url, data=data, files=files, timeout=120)
            return resp.ok
        except Exception as e:
            print(f"Send document error: {e}")
            return False

def answer_callback(callback_id, text=None, show_alert=False):
    url = f"{BASE_URL}/answerCallbackQuery"
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Answer callback error: {e}")

def get_video_info(url):
    """Get video metadata using yt-dlp with extra flags to avoid login prompts."""
    cmd = [
        "yt-dlp",
        "--cookies", "cookies.txt",   # Add this line
        "--remote-components", "ejs:github",   # <-- Add this line
        "--extractor-args", "youtube:skip=webpage",
        "--no-check-certificates",
        "--dump-json",
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr
        if "Sign in to confirm" in stderr or "age-restricted" in stderr.lower():
            raise Exception("This video is restricted (age‑gate or requires login). YouTube does not allow downloading it.")
        raise Exception(f"yt-dlp info error: {stderr[:300]}")
    data = json.loads(result.stdout)
    title = data.get("title", "Unknown")
    duration = data.get("duration", 0)
    # Build list of usable formats (video+audio, mp4, under 45MB)
    formats = []
    for f in data.get("formats", []):
        if f.get("vcodec") != "none" and f.get("acodec") != "none" and f.get("ext") == "mp4":
            size = f.get("filesize") or f.get("filesize_approx") or 0
            if size < MAX_FILE_SIZE:
                height = f.get("height") or 0
                label = f"{height}p" if height else "Unknown"
                formats.append({
                    "format_id": f["format_id"],
                    "label": f"{label} ({size//1024//1024} MB)",
                    "size": size
                })
    # Add audio-only options (opus/m4a)
    for f in data.get("formats", []):
        if f.get("vcodec") == "none" and f.get("acodec") != "none":
            size = f.get("filesize") or f.get("filesize_approx") or 0
            if size < MAX_FILE_SIZE:
                ext = f.get("ext", "audio")
                label = f"Audio ({ext}, {size//1024//1024} MB)"
                formats.append({
                    "format_id": f["format_id"],
                    "label": label,
                    "size": size
                })
    # Sort by size (smaller first)
    formats.sort(key=lambda x: x["size"])
    return title, duration, formats

def download_format(url, format_id, output_path):
    cmd = [
        "yt-dlp",
        "--cookies", "cookies.txt",   # Add this line
        "--remote-components", "ejs:github",   # <-- Add this line
        "--extractor-args", "youtube:skip=webpage",
        "--no-check-certificates",
        "-f", format_id,
        "-o", output_path,
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr
        if "Sign in to confirm" in stderr:
            raise Exception("Cannot download this video – it requires login or is age‑restricted.")
        raise Exception(f"Download error: {stderr[:200]}")
    return output_path

def split_and_send(chat_id, file_path, base_name):
    """Split file into <=45MB chunks and send each."""
    file_size = os.path.getsize(file_path)
    if file_size <= MAX_FILE_SIZE:
        return send_document(chat_id, file_path)
    os.makedirs(TEMP_DIR, exist_ok=True)
    ext = os.path.splitext(file_path)[1]
    pattern = os.path.join(TEMP_DIR, f"{base_name}_part_%03d{ext}")
    cmd = [
        "ffmpeg", "-i", file_path,
        "-c", "copy", "-map", "0",
        "-f", "segment",
        "-segment_time", "999999",
        "-reset_timestamps", "1",
        "-fs", str(MAX_FILE_SIZE),
        pattern
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    sent = 0
    part = 1
    while True:
        chunk = os.path.join(TEMP_DIR, f"{base_name}_part_{part:03d}{ext}")
        if not os.path.exists(chunk):
            break
        if send_document(chat_id, chunk):
            sent += 1
        os.remove(chunk)
        part += 1
        time.sleep(0.5)
    return sent > 0

def extract_youtube_id(text):
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})'
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return None

def cleanup():
    if os.path.exists(TEMP_DIR):
        for f in os.listdir(TEMP_DIR):
            os.remove(os.path.join(TEMP_DIR, f))
        os.rmdir(TEMP_DIR)

def main():
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
            print(f"Poll error: {e}")
            break

        if not data.get("ok"):
            print("API error:", data)
            break

        updates = data.get("result", [])
        if not updates:
            break

        for update in updates:
            offset = update["update_id"] + 1

            # Handle callback queries (button clicks)
            if "callback_query" in update:
                cb = update["callback_query"]
                cb_id = cb["id"]
                cb_data = cb.get("data")
                chat_id = cb["message"]["chat"]["id"]
                if "|" in cb_data:
                    video_url, format_id = cb_data.split("|", 1)
                    answer_callback(cb_id, text="⏳ Downloading, please wait...")
                    send_message(chat_id, "⏳ Downloading your selected format...")
                    try:
                        video_id = extract_youtube_id(video_url) or "video"
                        out_file = os.path.join(TEMP_DIR, f"{video_id}_{format_id}.mp4")
                        download_format(video_url, format_id, out_file)
                        send_message(chat_id, "📤 Sending file...")
                        base = f"{video_id}_{format_id}"
                        success = split_and_send(chat_id, out_file, base)
                        if success:
                            send_message(chat_id, "✅ Done!")
                        else:
                            send_message(chat_id, "❌ Failed to send file.")
                        os.remove(out_file)
                    except Exception as e:
                        send_message(chat_id, f"⚠️ {str(e)}")
                        answer_callback(cb_id, text=str(e)[:100], show_alert=True)
                    finally:
                        cleanup()
                else:
                    answer_callback(cb_id, text="Invalid request", show_alert=True)
                continue

            # Handle regular messages
            message = update.get("message")
            if not message:
                continue
            chat_id = message["chat"]["id"]
            text = message.get("text", "")

            if text.startswith("/start"):
                send_message(chat_id,
                    "🎬 *YouTube Downloader Bot*\n\n"
                    "Send me a YouTube URL. I'll fetch available qualities and let you choose.\n\n"
                    "Example: `https://youtu.be/dQw4w9WgXcQ`\n\n"
                    "⚠️ *Note*: Some videos (age‑restricted or requiring login) cannot be downloaded.")
                continue

            video_id = extract_youtube_id(text)
            if not video_id:
                send_message(chat_id, "❌ No valid YouTube URL found.")
                continue

            # Get video info and build inline keyboard
            send_message(chat_id, "🔍 Fetching video information...")
            try:
                title, duration, formats = get_video_info(text)
                if not formats:
                    send_message(chat_id, "❌ No downloadable formats found (all >45MB or restricted). Try a shorter video.")
                    continue

                # Build inline keyboard buttons
                buttons = []
                row = []
                for f in formats[:8]:
                    callback_data = f"{text}|{f['format_id']}"
                    row.append({"text": f["label"], "callback_data": callback_data})
                    if len(row) == 2:
                        buttons.append(row)
                        row = []
                if row:
                    buttons.append(row)
                reply_markup = {"inline_keyboard": buttons}

                duration_min = duration // 60
                dur_str = f"{duration_min}:{duration%60:02d}" if duration else "unknown"
                info_text = f"🎥 *{title}*\n⏱️ Duration: {dur_str}\n\nSelect quality:"
                send_message(chat_id, info_text, reply_markup=reply_markup)
            except Exception as e:
                send_message(chat_id, f"⚠️ {str(e)}")

        save_offset(offset)
        time.sleep(1)

if __name__ == "__main__":
    main()
