"""Chat Summarizer — summarizes busy Discord channels with Groq.

Watches every channel enabled with /enable. On each check loop, any enabled channel
with more than its configured message threshold accumulated since its previous summary
(and whose interval duration has elapsed) gets a digest posted back into it.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

import summarizer
from store import Store

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
MESSAGE_THRESHOLD = int(os.getenv("MESSAGE_THRESHOLD", "10"))
INTERVAL_SECONDS = float(os.getenv("INTERVAL_SECONDS", "60"))
CHECK_LOOP_SECONDS = float(os.getenv("CHECK_LOOP_SECONDS", "15"))
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")
DB_PATH = os.getenv("DB_PATH", "data/chatsummarizer.db")
DONATION_URL = os.getenv("DONATION_URL", "https://buymeacoffee.com/ashwiinn")

log = logging.getLogger("chatsummarizer")


@dataclass
class BufferedMessage:
    author: str
    content: str
    at: datetime


def _can_manage(interaction: discord.Interaction) -> bool:
    return isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator


def format_seconds(seconds: float) -> str:
    s = int(seconds)
    if s >= 3600:
        h = s // 3600
        rem_m = (s % 3600) // 60
        return f"{h}h {rem_m}m" if rem_m else f"{h} hour{'s' if h > 1 else ''}"
    elif s >= 60:
        m = s // 60
        rem_s = s % 60
        return f"{m}m {rem_s}s" if rem_s else f"{m} minute{'s' if m > 1 else ''}"
    return f"{s} second{'s' if s > 1 else ''}"


class ChatSummarizer(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.store = Store(DB_PATH)
        self.enabled: set[int] = set()
        self.channel_guilds: dict[int, int] = {}
        self.buffers: dict[int, list[BufferedMessage]] = {}
        self.last_summary: dict[int, datetime] = {}
        self._warned_no_key: set[int] = set()

    async def setup_hook(self) -> None:
        directory = os.path.dirname(DB_PATH)
        if directory:
            os.makedirs(directory, exist_ok=True)
        await self.store.connect()
        self.channel_guilds = await self.store.enabled_channels()
        self.enabled = set(self.channel_guilds.keys())
        if DEV_GUILD_ID:
            guild = discord.Object(id=int(DEV_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        self.summary_loop.start()

    async def close(self) -> None:
        await self.store.close()
        await super().close()

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        if message.channel.id not in self.enabled:
            return
        content = message.content.strip()
        if not content:
            return
        self.buffers.setdefault(message.channel.id, []).append(
            BufferedMessage(
                author=message.author.display_name,
                content=content[: summarizer.MAX_CONTENT_CHARS],
                at=message.created_at,
            )
        )

    @tasks.loop(seconds=CHECK_LOOP_SECONDS)
    async def summary_loop(self) -> None:
        now = datetime.now(timezone.utc)
        for channel_id in list(self.buffers):
            messages = self.buffers[channel_id]
            guild_id = self.channel_guilds.get(channel_id)
            if guild_id is None:
                continue

            key, model, interval, threshold = await self.store.settings(guild_id)
            interval_val = interval if interval is not None else INTERVAL_SECONDS
            threshold_val = threshold if threshold is not None else MESSAGE_THRESHOLD

            if len(messages) <= threshold_val:
                continue

            last = self.last_summary.get(channel_id)
            if last is not None and (now - last).total_seconds() < interval_val:
                continue

            channel = await self._resolve_channel(channel_id)
            if channel is None:
                continue
            await self._summarize_channel(channel, messages, key, model or DEFAULT_MODEL)

    @summary_loop.before_loop
    async def _wait_until_ready(self) -> None:
        await self.wait_until_ready()

    async def _resolve_channel(self, channel_id: int) -> discord.abc.Messageable | None:
        channel = self.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden):
                await self._forget_channel(channel_id)
                return None
            except discord.HTTPException:
                log.warning("Could not resolve channel %s this tick", channel_id)
                return None
        if channel.guild is None or not isinstance(channel, discord.abc.Messageable):
            return None
        return channel

    async def _forget_channel(self, channel_id: int) -> None:
        log.info("Channel %s is gone or inaccessible; disabling it", channel_id)
        self.enabled.discard(channel_id)
        self.channel_guilds.pop(channel_id, None)
        self.buffers.pop(channel_id, None)
        self.last_summary.pop(channel_id, None)
        await self.store.disable_channel(channel_id)

    async def _summarize_channel(
        self,
        channel: discord.abc.Messageable,
        messages: list[BufferedMessage],
        key: str | None,
        model: str,
    ) -> None:
        guild = channel.guild
        if not key:
            if guild.id not in self._warned_no_key:
                self._warned_no_key.add(guild.id)
                log.warning(
                    "Guild %s has enabled channels but no Groq key; summaries paused until /setkey",
                    guild.id,
                )
            return

        # Snapshot and clear first so messages sent during the API call are
        # never lost; on failure the snapshot is put back for the next check.
        snapshot, self.buffers[channel.id] = messages, []
        try:
            transcript = summarizer.build_transcript(
                [f"[{m.at:%Y-%m-%d %H:%M} UTC] {m.author}: {m.content}" for m in snapshot]
            )
            summary = await summarizer.summarize(transcript, key, model)
        except Exception:
            log.exception("Summarization failed for channel %s; retrying next check", channel.id)
            self.buffers[channel.id] = snapshot + self.buffers[channel.id]
            return

        embed = discord.Embed(
            title=f"Summary of #{channel.name}",
            description=summary[:4000],
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Messages condensed", value=str(len(snapshot)))
        embed.set_footer(text=f"{snapshot[0].at:%Y-%m-%d %H:%M}–{snapshot[-1].at:%H:%M} UTC • Groq · {model}")
        try:
            await channel.send(embed=embed)
            self.last_summary[channel.id] = datetime.now(timezone.utc)
        except discord.HTTPException:
            log.exception("Could not post summary to channel %s; retrying next check", channel.id)
            self.buffers[channel.id] = snapshot + self.buffers[channel.id]


client = ChatSummarizer()


@client.tree.command(name="setkey", description="Store the Groq API key used to summarize this server's channels")
@app_commands.describe(key="Your Groq API key from console.groq.com (starts with gsk_)")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def setkey_command(interaction: discord.Interaction, key: str) -> None:
    if not _can_manage(interaction):
        await interaction.response.send_message("You need **Administrator** permission to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await summarizer.verify_key(key)
    except Exception:
        log.info("Groq rejected a key submitted in guild %s", interaction.guild_id)
        await interaction.followup.send("❌ Groq rejected that API key. Double-check it at console.groq.com and try again.")
        return
    await client.store.set_key(interaction.guild_id, key)
    client._warned_no_key.discard(interaction.guild_id)
    await interaction.followup.send(
        f"✅ Groq key saved (ends in `{key[-4:]}`). It will be used from the next summary check on."
    )


@client.tree.command(name="clearkey", description="Remove this server's stored Groq API key")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def clearkey_command(interaction: discord.Interaction) -> None:
    if not _can_manage(interaction):
        await interaction.response.send_message("You need **Administrator** permission to use this command.", ephemeral=True)
        return
    await client.store.clear_key(interaction.guild_id)
    await interaction.response.send_message(
        "🗑️ Stored Groq key removed. Summaries pause until someone runs `/setkey` again.", ephemeral=True
    )


@client.tree.command(name="setmodel", description="Choose the Groq model for summaries (default: qwen/qwen3.8-27b)")
@app_commands.describe(model="Model name, e.g. qwen/qwen3.8-27b")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def setmodel_command(interaction: discord.Interaction, model: str) -> None:
    if not _can_manage(interaction):
        await interaction.response.send_message("You need **Administrator** permission to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    key, _, _, _ = await client.store.settings(interaction.guild_id)
    note = ""
    if key:
        try:
            if not await summarizer.model_exists(key, model):
                await interaction.followup.send(
                    f"❌ `{model}` isn't available on your Groq account. Browse models at console.groq.com/docs/models."
                )
                return
        except Exception:
            note = " (Couldn't reach Groq to verify the name just now; it will be checked at the next summary.)"
    await client.store.set_model(interaction.guild_id, model)
    await interaction.followup.send(f"✅ Model set to `{model}`." + note)


@client.tree.command(name="setinterval", description="Set summary check interval between 1 minute and 6 hours")
@app_commands.describe(seconds="Interval in seconds (60 to 21600; e.g. 60 for 1m, 300 for 5m, 3600 for 1h)")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def setinterval_command(interaction: discord.Interaction, seconds: int) -> None:
    if not _can_manage(interaction):
        await interaction.response.send_message("You need **Administrator** permission to use this command.", ephemeral=True)
        return
    if seconds < 60 or seconds > 21600:
        await interaction.response.send_message(
            "❌ Invalid interval. The interval must be between **1 minute** (60 seconds) and **6 hours** (21,600 seconds).",
            ephemeral=True,
        )
        return
    await client.store.set_interval(interaction.guild_id, float(seconds))
    readable = format_seconds(seconds)
    await interaction.response.send_message(
        f"⏱️ Summary check interval for this server set to **{seconds} seconds** ({readable}).",
        ephemeral=True,
    )


@client.tree.command(name="setthreshold", description="Set message count required to trigger a summary (between 10 and 400)")
@app_commands.describe(messages="Message threshold (10 to 400 messages)")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def setthreshold_command(interaction: discord.Interaction, messages: int) -> None:
    if not _can_manage(interaction):
        await interaction.response.send_message("You need **Administrator** permission to use this command.", ephemeral=True)
        return
    if messages < 10 or messages > 400:
        await interaction.response.send_message(
            "❌ Invalid threshold. The message threshold must be between **10** and **400** messages.",
            ephemeral=True,
        )
        return
    await client.store.set_threshold(interaction.guild_id, messages)
    await interaction.response.send_message(
        f"📊 Message threshold for this server set to **{messages} messages** (summarizes when strictly > {messages}).",
        ephemeral=True,
    )


@client.tree.command(name="enable", description="Start summarizing this channel")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def enable_command(interaction: discord.Interaction) -> None:
    if not _can_manage(interaction):
        await interaction.response.send_message("You need **Administrator** permission to use this command.", ephemeral=True)
        return
    channel = interaction.channel
    if not isinstance(channel, discord.abc.Messageable):
        await interaction.response.send_message(
            "This channel type can't be summarized. Run `/enable` in a text channel or thread.", ephemeral=True
        )
        return
    await client.store.enable_channel(interaction.guild_id, channel.id)
    client.enabled.add(channel.id)
    client.channel_guilds[channel.id] = interaction.guild_id

    _, _, interval, threshold = await client.store.settings(interaction.guild_id)
    interval_val = interval if interval is not None else INTERVAL_SECONDS
    threshold_val = threshold if threshold is not None else MESSAGE_THRESHOLD
    readable = format_seconds(interval_val)

    await interaction.response.send_message(
        f"👀 Watching **#{channel.name}**. Whenever more than {threshold_val} messages accumulate since the "
        f"last summary, I'll post a digest (checked every {readable}).",
        ephemeral=True,
    )


@client.tree.command(name="disable", description="Stop summarizing this channel")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def disable_command(interaction: discord.Interaction) -> None:
    if not _can_manage(interaction):
        await interaction.response.send_message("You need **Administrator** permission to use this command.", ephemeral=True)
        return
    await client.store.disable_channel(interaction.channel_id)
    client.enabled.discard(interaction.channel_id)
    client.channel_guilds.pop(interaction.channel_id, None)
    client.buffers.pop(interaction.channel_id, None)
    client.last_summary.pop(interaction.channel_id, None)
    await interaction.response.send_message("💤 Stopped watching this channel. Its pending messages were discarded.", ephemeral=True)


@client.tree.command(name="status", description="Show ChatSummarizer's setup for this server and channel")
@app_commands.guild_only()
async def status_command(interaction: discord.Interaction) -> None:
    key, model, interval, threshold = await client.store.settings(interaction.guild_id)
    key_line = f"set (ends in `{key[-4:]}`)" if key else "**not set** — summaries stay paused until an admin runs `/setkey`"
    channel_line = "enabled" if interaction.channel_id in client.enabled else "disabled — run `/enable` here to watch it"
    buffered = len(client.buffers.get(interaction.channel_id, []))

    interval_val = interval if interval is not None else INTERVAL_SECONDS
    threshold_val = threshold if threshold is not None else MESSAGE_THRESHOLD

    lines = [
        "**Chat Summarizer status**",
        f"• Groq key: {key_line}",
        f"• Model: `{model or DEFAULT_MODEL}`",
        f"• Check interval: **{int(interval_val)}s** ({format_seconds(interval_val)})",
        f"• Message threshold: **{threshold_val} messages** (triggers when > {threshold_val})",
        f"• This channel: {channel_line}",
        f"• Messages currently buffered here: {buffered}",
    ]
    view = None
    if DONATION_URL:
        lines.append(f"\n☕ Enjoying Chat Summarizer? [Buy Me a Coffee]({DONATION_URL})")
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Buy Me a Coffee ☕", url=DONATION_URL, style=discord.ButtonStyle.link))
    await interaction.response.send_message("\n".join(lines), view=view, ephemeral=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set — copy .env.example to .env and paste your bot token.")
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
