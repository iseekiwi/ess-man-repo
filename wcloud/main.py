# main.py — WordCloud cog for Red-DiscordBot

import io
import re
import discord
from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from redbot.core import commands
from redbot.core.bot import Red
from .stopwords import extract_words, is_bot_command

try:
    from wordcloud import WordCloud as WC
    HAS_WORDCLOUD = True
except ImportError:
    HAS_WORDCLOUD = False

# Timeframe pattern for years (e.g. "1y", "2y")
YEAR_PATTERN = re.compile(r"^(\d+)y$", re.IGNORECASE)


class WordCloudCog(commands.Cog):
    """Generate word clouds from a user's messages in a channel."""

    def __init__(self, bot: Red):
        self.bot = bot

    @commands.command(name="wordcloud", aliases=["wc"])
    @commands.guild_only()
    @commands.bot_has_permissions(read_message_history=True, attach_files=True)
    async def wordcloud_cmd(
        self,
        ctx: commands.Context,
        user: discord.Member,
        channel: Optional[Union[discord.TextChannel, discord.Thread]] = None,
        timeframe: str = "month",
    ):
        """Generate a word cloud from a user's messages.

        **Timeframes:** `day`, `week`, `month`, `all`, or `1y`/`2y`/etc.

        **Examples:**
        `[p]wordcloud @user` — current channel, last 30 days
        `[p]wordcloud @user #general` — #general, last 30 days
        `[p]wordcloud @user #general week` — #general, last 7 days
        `[p]wordcloud @user #general all` — #general, all time
        `[p]wordcloud @user #general 2y` — #general, last 2 years
        """
        if not HAS_WORDCLOUD:
            await ctx.send(
                "The `wordcloud` library is not installed. "
                "Install it with: `pip install wordcloud`"
            )
            return

        # Default to current channel
        if channel is None:
            channel = ctx.channel

        # Parse timeframe
        cutoff = self._parse_timeframe(timeframe)
        if cutoff is False:
            await ctx.send(
                "Invalid timeframe. Use: `day`, `week`, `month`, `all`, or `1y`/`2y`/etc."
            )
            return

        # Show typing indicator while scanning
        async with ctx.typing():
            words, messages_scanned = await self._collect_words(
                channel, user, cutoff
            )

        if not words:
            await ctx.send(
                f"No words found for **{user.display_name}** in {channel.mention} "
                f"within the given timeframe."
            )
            return

        # Generate and send word cloud
        async with ctx.typing():
            image_buffer = await self._generate_cloud(words)

        # Build embed
        timeframe_display = self._timeframe_display(timeframe)
        embed = discord.Embed(
            title=f"Word Cloud for {user.display_name}",
            color=discord.Color.blue(),
        )
        embed.set_image(url="attachment://wordcloud.png")

        embed.set_footer(
            text=f"#{channel.name} | {timeframe_display} | "
                 f"{messages_scanned:,} messages scanned | {len(words):,} words collected"
        )

        file = discord.File(image_buffer, filename="wordcloud.png")
        await ctx.send(embed=embed, file=file)

    # ------------------------------------------------------------------
    # Message collection
    # ------------------------------------------------------------------

    async def _collect_words(
        self,
        channel: Union[discord.TextChannel, discord.Thread],
        user: discord.Member,
        cutoff: Optional[datetime],
    ) -> tuple:
        """Scan channel history and collect filtered words from a user.

        Returns (words: list[str], messages_scanned: int, hit_cap: bool).
        """
        words = []
        messages_scanned = 0

        try:
            async for message in channel.history(
                limit=None, after=cutoff, oldest_first=False
            ):
                messages_scanned += 1

                if message.author.id != user.id:
                    continue

                content = message.content
                if not content or is_bot_command(content):
                    continue

                words.extend(extract_words(content))

        except discord.Forbidden:
            pass  # No permission — return what we have (likely empty)

        return words, messages_scanned

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
