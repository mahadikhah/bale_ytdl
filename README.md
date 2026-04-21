# Bale YouTube Bot – Interactive Quality Selection

This bot runs on GitHub Actions, fetches YouTube video info, and lets users choose quality via inline buttons.

## Features
- No external APIs – uses `yt-dlp` directly.
- Shows video title, duration, and file sizes.
- Buttons for each quality (video + audio).
- Splits files >45MB into smaller parts.
- Persists offset across runs (no duplicate replies).

## Setup
1. Create a bot on Bale via @BotFather, get token.
2. Add repository secrets: `BALE_BOT_TOKEN`.
3. Push to GitHub. Workflow runs every minute.

## Usage
- Send `/start` then a YouTube URL.
- Choose a quality from the buttons.
- Bot downloads and sends the file (split if needed).

## Troubleshooting
- If no formats appear, try a shorter video.
- Cron runs on `main` branch only.
