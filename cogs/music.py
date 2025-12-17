"""Music commands and voice helpers for the Discord bot."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp

# yt-dlp options focused on streaming audio quickly without downloading.
YTDL_OPTIONS: Dict[str, Any] = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "auto",
    "nocheckcertificate": True,
    "source_address": "0.0.0.0",
    "geo_bypass": True,
    "retries": 3,
}

FFMPEG_OPTIONS: Dict[str, Any] = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
    "-nostdin -vn -reorder_queue_size 0",
    "options": "-vn -bufsize 64k -loglevel warning",
}


class UserFeedbackError(Exception):
    """Custom exception type used to return friendly error messages."""


class Music(commands.Cog):
    """Cog providing music playback commands using yt-dlp and FFmpeg."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    def cog_unload(self) -> None:
        self.ytdl.close()

    async def _extract_info(self, url: str) -> Dict[str, Any]:
        """Run yt-dlp in an executor to keep extraction non-blocking."""

        def _extract() -> Dict[str, Any]:
            return self.ytdl.extract_info(url, download=False)

        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, _extract)
        if not data:
            raise UserFeedbackError("No media could be extracted from that link.")

        # Playlists return a list of entries; pick the first valid one.
        if "entries" in data:
            entries = [entry for entry in data["entries"] if entry]
            if not entries:
                raise UserFeedbackError("No playable entries were found in that playlist.")
            data = entries[0]

        if not data.get("url"):
            raise UserFeedbackError("No playable audio stream was found for that link.")

        return data

    async def _connect_to_author(self, interaction: discord.Interaction) -> discord.VoiceClient:
        """Ensure the bot is connected to the invoker's voice channel."""
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            raise UserFeedbackError("Only guild members can use voice commands.")

        voice_state = interaction.user.voice
        if not voice_state or not voice_state.channel:
            raise UserFeedbackError("You need to be connected to a voice channel first.")

        channel = voice_state.channel
        voice_client = interaction.guild.voice_client if interaction.guild else None

        if voice_client and voice_client.is_connected():
            if voice_client.channel.id != channel.id:
                await voice_client.move_to(channel)
            return voice_client

        try:
            return await channel.connect()
        except discord.Forbidden as exc:
            raise UserFeedbackError("I don't have permission to join or speak in that voice channel.") from exc
        except discord.ClientException as exc:  # Connection is already in progress or failed.
            raise UserFeedbackError(f"Couldn't connect to the voice channel: {exc}") from exc

    def _handle_playback_error(self, error: Optional[Exception], guild: Optional[discord.Guild]) -> None:
        if error:
            self.logger.error("Playback error in guild %s: %s", guild.id if guild else "?", error)

    @app_commands.command(name="join", description="Join your current voice channel")
    async def join(self, interaction: discord.Interaction) -> None:
        try:
            await self._connect_to_author(interaction)
        except UserFeedbackError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.send_message("Joined your voice channel.")

    @app_commands.command(name="leave", description="Disconnect from the voice channel")
    async def leave(self, interaction: discord.Interaction) -> None:
        voice_client = interaction.guild.voice_client if interaction.guild else None
        if not voice_client or not voice_client.is_connected():
            await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)
            return

        await voice_client.disconnect(force=True)
        await interaction.response.send_message("Disconnected.")

    @app_commands.command(name="play", description="Play audio from a YouTube or direct audio URL")
    @app_commands.describe(url="YouTube link or direct audio URL")
    async def play(self, interaction: discord.Interaction, url: str) -> None:
        await interaction.response.defer(thinking=True)
        lock = self._locks[interaction.guild_id]

        async with lock:
            try:
                voice_client = await self._connect_to_author(interaction)
            except UserFeedbackError as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
                return

            try:
                info = await self._extract_info(url)
            except UserFeedbackError as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
                return
            except Exception:
                self.logger.exception("yt-dlp failed to extract info for %s", url)
                await interaction.followup.send(
                    "Something went wrong while trying to get that audio. Please try a different link.",
                    ephemeral=True,
                )
                return

            stream_url = info["url"]
            title = info.get("title", "audio stream")

            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()

            try:
                audio_source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
                voice_client.play(
                    audio_source,
                    after=lambda e: self._handle_playback_error(e, interaction.guild),
                )
            except Exception:
                self.logger.exception("FFmpeg failed to start for %s", url)
                await interaction.followup.send(
                    "I couldn't start playback. Please verify the link is supported and try again.",
                    ephemeral=True,
                )
                return

            await interaction.followup.send(
                f"Now playing: **{discord.utils.escape_markdown(title)}**",
                suppress_embeds=True,
            )

    @app_commands.command(name="pause", description="Pause the current audio")
    async def pause(self, interaction: discord.Interaction) -> None:
        voice_client = interaction.guild.voice_client if interaction.guild else None
        if not voice_client or not voice_client.is_connected():
            await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)
            return
        if not voice_client.is_playing():
            await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
            return

        voice_client.pause()
        await interaction.response.send_message("Playback paused.")

    @app_commands.command(name="resume", description="Resume paused audio")
    async def resume(self, interaction: discord.Interaction) -> None:
        voice_client = interaction.guild.voice_client if interaction.guild else None
        if not voice_client or not voice_client.is_connected():
            await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)
            return
        if not voice_client.is_paused():
            await interaction.response.send_message("Playback is not paused.", ephemeral=True)
            return

        voice_client.resume()
        await interaction.response.send_message("Resumed playback.")

    @app_commands.command(name="stop", description="Stop playing and clear the current stream")
    async def stop(self, interaction: discord.Interaction) -> None:
        voice_client = interaction.guild.voice_client if interaction.guild else None
        if not voice_client or not voice_client.is_connected():
            await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)
            return

        voice_client.stop()
        await interaction.response.send_message("Stopped playback.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
