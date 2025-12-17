"""Utility commands and shared error handling for the Discord bot."""

from __future__ import annotations

import logging
import platform
from datetime import datetime, timezone
from typing import Callable

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


class Utils(commands.Cog):
    """General-purpose commands and error handling."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # -----------------
    # Helper utilities
    # -----------------
    def _format_uptime(self) -> str:
        delta = datetime.now(timezone.utc) - getattr(self.bot, "launch_time", datetime.now(timezone.utc))
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        return " ".join(parts)

    async def _safe_send(self, interaction: discord.Interaction, message: str, *, ephemeral: bool = True) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(message, ephemeral=ephemeral)

    # -----------------
    # Slash commands
    # -----------------
    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000, 2)
        await interaction.response.send_message(f"🏓 Pong! Latency: {latency_ms} ms")

    @app_commands.command(name="info", description="Show bot information and uptime")
    async def info(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(title="Bot information", color=discord.Color.blue())
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000, 2)} ms", inline=True)
        embed.add_field(name="Uptime", value=self._format_uptime(), inline=True)
        embed.add_field(name="Library", value=f"discord.py {discord.__version__}", inline=True)
        embed.add_field(name="Python", value=platform.python_version(), inline=True)
        embed.set_footer(text="Add more details here as you expand the bot's features.")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="List available commands")
    async def help(self, interaction: discord.Interaction) -> None:
        description = (
            "**Music**\n"
            "/join — Join your voice channel\n"
            "/leave — Disconnect from voice\n"
            "/play <url> — Stream audio from a YouTube or audio URL\n"
            "/pause — Pause playback\n"
            "/resume — Resume playback\n"
            "/stop — Stop playback\n\n"
            "**Utilities**\n"
            "/ping — Latency check\n"
            "/info — Bot information and uptime\n"
            "/help — This message\n"
            "/clear <amount> — Delete recent messages (admin only)"
        )

        embed = discord.Embed(title="Available Commands", description=description, color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clear", description="Delete a number of recent messages")
    @app_commands.describe(amount="Number of messages to delete (1-100)")
    @app_commands.default_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int) -> None:
        if amount < 1 or amount > 100:
            await interaction.response.send_message("Please choose an amount between 1 and 100.", ephemeral=True)
            return
        if not interaction.channel or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("This command can only be used in text channels.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"Deleted {len(deleted)} message(s).", ephemeral=True)

    # -----------------
    # Error handling
    # -----------------
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        original = getattr(error, "original", error)

        if isinstance(original, app_commands.MissingPermissions):
            await self._safe_send(
                interaction,
                "You need the Manage Messages permission to do that.",
            )
            return

        if isinstance(original, app_commands.BotMissingPermissions):
            await self._safe_send(
                interaction,
                "I don't have permission to complete that action. Please check my role permissions.",
            )
            return

        if isinstance(original, app_commands.CheckFailure):
            await self._safe_send(interaction, "You can't use that command here or you lack permissions.")
            return

        logger.exception("Unhandled application command error: %s", original)
        await self._safe_send(
            interaction,
            "Something unexpected happened. Please try again or contact an admin if it continues.",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utils(bot))
