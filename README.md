# Discord Music Bot

A production-ready Discord bot built with `discord.py`, `yt-dlp`, and FFmpeg. It uses slash commands, cogs, and streams audio without downloading full videos when possible.

## Features
- Slash commands for music playback: `/join`, `/leave`, `/play`, `/pause`, `/resume`, `/stop`.
- Utility commands: `/ping`, `/info`, `/help`, `/clear` (admin only).
- Streams audio via FFmpeg with reconnect-focused options for resilience.
- Token is loaded from a `.env` file so secrets stay out of source control.

## Requirements
- Python 3.10+ (recommended for the latest `discord.py`).
- FFmpeg available in your `PATH` (install on Debian/Ubuntu: `sudo apt-get install ffmpeg`).
- A Discord bot token stored in `.env`.

## Setup (Linux)
1. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env and set DISCORD_TOKEN=your_token
   ```
2. **Create and activate a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Install dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. **Run the bot**
   ```bash
   python bot.py
   ```

## Notes
- The FFmpeg options are optimized for low-latency streaming and reconnect attempts. Tweak `FFMPEG_OPTIONS` in `cogs/music.py` if your environment needs different buffering.
- All commands are slash commands; ensure your bot has the `applications.commands` scope when inviting it to a server.
- Extend the bot by adding new cogs or updating `COGS` in `bot.py`.
