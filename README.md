# Bale YouTube Downloader Bot

This bot runs on GitHub Actions, downloads YouTube videos, and sends them to users on Bale Messenger.

## Features
- No external API keys needed (uses `yt-dlp` directly).
- Splits videos larger than 45 MB into smaller parts.
- Persists message offset across runs (no duplicate replies).
- Cleans up files automatically.

## Setup
1. Create a new bot on Bale via @BotFather and copy the token.
2. Fork or create a repository with the files above.
3. Add `BALE_BOT_TOKEN` as a secret in GitHub → Settings → Secrets and variables → Actions.
4. Push to `main`. The workflow will run every minute.

## Usage
- Send `/start` to the bot.
- Send any YouTube URL.
- Wait for the video(s) to arrive.

## Limitations
- Videos are split at 45 MB (Bale's effective limit).
- Very long videos may take several minutes to download.
- GitHub Actions free tier allows 2000 minutes/month – plenty for personal use.
