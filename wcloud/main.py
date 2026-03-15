# main.py — WordCloud cog for Red-DiscordBot (SQLite-backed)

import io
import re
import aiosqlite
import discord
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Union
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path
from .stopwords import extract_words, is_bot_command

try:
    from wordcloud import WordCloud as WC
    HAS_WORDCLOUD = True
except ImportError:
    HAS_WORDCLOUD = False

# Timeframe pattern for years (e.g. "1y", "2y")
YEAR_PATTERN = re.compile(r"^(\d+)y$", re.IGNORECASE)


class WordCloudCog(commands.Cog):
    """Generate word clouds from a user's messages in a channel.

    Messages are cached in a local SQLite database for instant word cloud
    generation. The bot passively records messages via on_message. A backfill
    command is available to import historical messages.
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self._db_path = cog_data_path(self) / "messages.db"
        self._db: Optional[aiosqlite.Connection] = None
        self._backfilling = {}  # channel_id -> True, guards concurrent backfills

    async def cog_load(self):
        """Initialize the SQLite database on cog load."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_channel_author "
            "ON messages (channel_id, author_id)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_created "
            "ON messages (created_at)"
        )
        await self._db.commit()

    async def cog_unload(self):
        """Close the database on cog unload."""
        if self._db:
            await self._db.close()
            self._db = None

    # ------------------------------------------------------------------
    # Passive message listener
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Passively store every message in the database."""
        if message.author.bot or not message.guild or not message.content:
            return
        if is_bot_command(message.content):
            return
        await self._store_message(message)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Remove deleted messages from the database."""
        if not self._db:
            return
        try:
            await self._db.execute(
                "DELETE FROM messages WHERE message_id = ?", (message.id,)
            )
            await self._db.commit()
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Update edited messages in the database."""
        if after.author.bot or not after.guild or not after.content:
            return
        if not self._db:
            return
        try:
            await self._db.execute(
                "UPDATE messages SET content = ? WHERE message_id = ?",
                (after.content, after.id),
            )
            await self._db.commit()
        except Exception:
            pass

    async def _store_message(self, message: discord.Message):
        """Insert a single message into the database."""
        if not self._db:
            return
        try:
            await self._db.execute(
                """
                INSERT OR IGNORE INTO messages
                (message_id, channel_id, guild_id, author_id, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.channel.id,
                    message.guild.id,
                    message.author.id,
                    message.content,
                    message.created_at.isoformat(),
                ),
            )
            await self._db.commit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Backfill command
    # ------------------------------------------------------------------

    @commands.command(name="wcbackfill")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(read_message_history=True)
    async def backfill_cmd(
        self,
        ctx: commands.Context,
        channel: Optional[Union[discord.TextChannel, discord.Thread]] = None,
    ):
        """Backfill message history for a channel into the database.

        This scans the entire channel history and stores all messages.
        Only needs to be run once per channel — new messages are captured
        automatically after that.

        **Examples:**
        `[p]wcbackfill` — backfill current channel
        `[p]wcbackfill #general` — backfill #general
        """
        if channel is None:
            channel = ctx.channel

        if channel.id in self._backfilling:
            await ctx.send(f"A backfill is already running for {channel.mention}.")
            return

        self._backfilling[channel.id] = True
        status_msg = await ctx.send(
            f"Backfilling {channel.mention}... this may take a while for large channels."
        )

        count = 0
        try:
            async with ctx.typing():
                async for message in channel.history(limit=None, oldest_first=True):
                    if message.author.bot or not message.content:
                        continue
                    if is_bot_command(message.content):
                        continue
                    await self._store_message(message)
                    count += 1

                    # Progress update every 10,000 messages
                    if count % 10_000 == 0:
                        try:
                            await status_msg.edit(
                                content=f"Backfilling {channel.mention}... "
                                        f"**{count:,}** messages stored so far."
                            )
                        except discord.NotFound:
                            pass

            try:
                await status_msg.edit(
                    content=f"Backfill complete for {channel.mention}. "
                            f"**{count:,}** messages stored."
                )
            except discord.NotFound:
                await ctx.send(
                    f"Backfill complete for {channel.mention}. "
                    f"**{count:,}** messages stored."
                )

        except discord.Forbidden:
            await ctx.send(f"I don't have permission to read {channel.mention}.")
        except Exception as e:
            await ctx.send(f"Backfill failed: {e}")
        finally:
            self._backfilling.pop(channel.id, None)

    # ------------------------------------------------------------------
    # Word cloud command
    # ------------------------------------------------------------------

    @commands.command(name="wordcloud", aliases=["wc"])
    @commands.guild_only()
    @commands.bot_has_permissions(attach_files=True)
    async def wordcloud_cmd(
        self,
        ctx: commands.Context,
        user: discord.Member,
        channel: Optional[Union[discord.TextChannel, discord.Thread]] = None,
        timeframe: str = "all",
    ):
        """Generate a word cloud from a user's messages.

        Messages are pulled from the local database (instant). Use
        `[p]wcbackfill` first to import historical messages.

        **Timeframes:** `day`, `week`, `month`, `all`, or `1y`/`2y`/etc.

        **Examples:**
        `[p]wordcloud @user` — current channel, all time
        `[p]wordcloud @user #general` — #general, all time
        `[p]wordcloud @user #general week` — #general, last 7 days
        `[p]wordcloud @user #general 2y` — #general, last 2 years
        """
        if not HAS_WORDCLOUD:
            await ctx.send(
                "The `wordcloud` library is not installed. "
                "Install it with: `pip install wordcloud`"
            )
            return

        if channel is None:
            channel = ctx.channel

        cutoff = self._parse_timeframe(timeframe)
        if cutoff is False:
            await ctx.send(
                "Invalid timeframe. Use: `day`, `week`, `month`, `all`, or `1y`/`2y`/etc."
            )
            return

        # Query the local database — should be near-instant
        words, message_count = await self._query_words(
            channel.id, user.id, cutoff
        )

        if not words:
            hint = ""
            if message_count == 0:
                hint = (
                    f"\n\nNo messages found in the database for this channel. "
                    f"Run `{ctx.prefix}wcbackfill {channel.mention}` to import history."
                )
            await ctx.send(
                f"No words found for **{user.display_name}** in {channel.mention} "
                f"within the given timeframe.{hint}"
            )
            return

        async with ctx.typing():
            image_buffer = await self._generate_cloud(words)

        timeframe_display = self._timeframe_display(timeframe)
        embed = discord.Embed(
            title=f"Word Cloud for {user.display_name}",
            color=discord.Color.blue(),
        )
        embed.set_image(url="attachment://wordcloud.png")
        embed.set_footer(
            text=f"#{channel.name} | {timeframe_display} | "
                 f"{message_count:,} messages | {len(words):,} words"
        )

        file = discord.File(image_buffer, filename="wordcloud.png")
        await ctx.send(embed=embed, file=file)

    # ------------------------------------------------------------------
    # Database query
    # ------------------------------------------------------------------

    async def _query_words(
        self,
        channel_id: int,
        author_id: int,
        cutoff: Optional[datetime],
    ) -> tuple:
        """Query the local database for a user's messages and extract words.

        Returns (words: list[str], message_count: int).
        """
        if not self._db:
            return [], 0

        if cutoff:
            query = (
                "SELECT content FROM messages "
                "WHERE channel_id = ? AND author_id = ? AND created_at >= ? "
                "ORDER BY created_at DESC"
            )
            params = (channel_id, author_id, cutoff.isoformat())
        else:
            query = (
                "SELECT content FROM messages "
                "WHERE channel_id = ? AND author_id = ? "
                "ORDER BY created_at DESC"
            )
            params = (channel_id, author_id)

        words = []
        message_count = 0

        async with self._db.execute(query, params) as cursor:
            async for (content,) in cursor:
                message_count += 1
                words.extend(extract_words(content))

        return words, message_count

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    async def _generate_cloud(self, words: list) -> io.BytesIO:
        """Generate a word cloud image and return it as a BytesIO buffer."""
        text = " ".join(words)

        wc = WC(
            width=800,
            height=400,
            background_color="black",
            colormap="viridis",
            max_words=150,
            min_font_size=10,
        )
        wc.generate(text)

        image = wc.to_image()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    # ------------------------------------------------------------------
    # Timeframe parsing
    # ------------------------------------------------------------------

    def _parse_timeframe(self, timeframe: str) -> Optional[datetime]:
        """Parse a timeframe string into a cutoff datetime.

        Returns:
            datetime — the cutoff (messages after this time)
            None — no cutoff (all time)
            False — invalid input
        """
        tf = timeframe.lower().strip()
        now = datetime.now(timezone.utc)

        if tf == "all":
            return None
        elif tf == "day":
            return now - timedelta(days=1)
        elif tf == "week":
            return now - timedelta(weeks=1)
        elif tf == "month":
            return now - timedelta(days=30)
        else:
            match = YEAR_PATTERN.match(tf)
            if match:
                years = int(match.group(1))
                if 1 <= years <= 10:
                    return now - timedelta(days=365 * years)
            return False

    def _timeframe_display(self, timeframe: str) -> str:
        """Convert a timeframe string to a human-readable label."""
        tf = timeframe.lower().strip()
        if tf == "all":
            return "All time"
        elif tf == "day":
            return "Last 24 hours"
        elif tf == "week":
            return "Last 7 days"
        elif tf == "month":
            return "Last 30 days"
        else:
            match = YEAR_PATTERN.match(tf)
            if match:
                years = int(match.group(1))
                return f"Last {years} year{'s' if years != 1 else ''}"
            return timeframe
