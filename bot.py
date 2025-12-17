"""Entrypoint for the Discord music bot.

This module wires the bot together, loads cogs, and starts the
Discord client. The bot uses slash commands exclusively via
``discord.app_commands`` and keeps configuration minimal so it can be
expanded easily later.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Iterable

import discord
from discord.ext import commands
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)

# Load environment variables before anything else tries to access them.
load_dotenv()

COGS: tuple[str, ...] = (
    "cogs.music",
    "cogs.utils",
)


class MusicBot(commands.Bot):
    """Discord bot configured for slash commands and voice features."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = False  # Slash commands do not need message content.
        intents.messages = True
        intents.guilds = True
        intents.voice_states = True

        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            help_command=None,
            description="A music bot powered by discord.py and yt-dlp.",
        )

        self.launch_time: datetime = datetime.now(timezone.utc)
        self._synced = False

    async def setup_hook(self) -> None:
        """Load extensions and sync slash commands on startup."""
        await self._load_extensions(COGS)
        if not self._synced:
            await self.tree.sync()
            self._synced = True
        logging.info("Command tree synced.")

    async def on_ready(self) -> None:
        logging.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        logging.info("Connected to %s guild(s).", len(self.guilds))

    async def _load_extensions(self, extensions: Iterable[str]) -> None:
        for ext in extensions:
            try:
                await self.load_extension(ext)
                logging.info("Loaded extension: %s", ext)
            except commands.ExtensionError:
                logging.exception("Failed to load extension: %s", ext)


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set. Add it to your .env file.")

    bot = MusicBot()

    try:
        bot.run(token, log_handler=None)  # Use our logging configuration.
    except KeyboardInterrupt:
        logging.info("Bot shutdown requested.")
    finally:
        logging.info("Closing event loop.")
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                loop.close()
        except RuntimeError:
            pass


if __name__ == "__main__":
    main()
