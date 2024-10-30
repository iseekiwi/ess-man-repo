import discord
from redbot.core import commands, Config, bank
from redbot.core.bot import Red
import random
import datetime

class Fishing(commands.Cog):
    """A fishing game cog for Redbot"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=123456789)
        self.config.register_user(inventory=[], total_value=0, daily_quest=None)
        self.fish_types = {
            "Common Fish": {"rarity": "common", "value": 10, "chance": 0.6},
            "Uncommon Fish": {"rarity": "uncommon", "value": 20, "chance": 0.25},
            "Rare Fish": {"rarity": "rare", "value": 50, "chance": 0.1},
            "Legendary Fish": {"rarity": "legendary", "value": 100, "chance": 0.05},
        }

    @commands.command(name="fish")
    async def fish(self, ctx):
        """Go fishing and try to catch a fish!"""
        user = ctx.author
        catch = self._catch_fish()
        
        if catch:
            fish_name = catch["name"]
            fish_value = catch["value"]

            await self._add_to_inventory(user, fish_name)
            await self.config.user(user).total_value.set(await self.config.user(user).total_value() + fish_value)
            await ctx.send(f"🎣 {user} caught a {fish_name} worth {fish_value} coins!")
        else:
            await ctx.send(f"🎣 {user} went fishing but didn't catch anything this time.")

    @commands.command(name="inventory")
    async def inventory(self, ctx):
        """Check your fishing inventory."""
        user = ctx.author
        inventory = await self.config.user(user).inventory()

        if inventory:
            fish_count = {fish: inventory.count(fish) for fish in set(inventory)}
            inventory_str = "\n".join(f"- {fish} (x{count})" for fish, count in fish_count.items())
            await ctx.send(f"🎒 {user}'s Inventory:\n{inventory_str}")
        else:
            await ctx.send(f"🎒 {user}, your inventory is empty. Go catch some fish!")

    @commands.command(name="sellfish")
    async def sell_fish(self, ctx):
        """Sell all fish in your inventory for currency."""
        user = ctx.author
        inventory = await self.config.user(user).inventory()

        if not inventory:
            await ctx.send(f"💰 {user}, you have no fish to sell.")
            return

        total_value = sum(self.fish_types[fish]["value"] for fish in inventory if fish in self.fish_types)

        await bank.deposit_credits(user, total_value)
        await self.config.user(user).inventory.set([])  # Clear inventory after selling

        await ctx.send(f"💰 {user} sold all their fish for {total_value} coins!")

    @commands.command(name="fisherboard")
    async def fisherboard(self, ctx):
        """Show the leaderboard of total fish value caught."""
        leaderboard = []

        users = await self.config.all_users()  # Await the config call to get all users
        for user_id in users:  # Iterate over the list of user IDs
            user_data = await self.config.user(user_id).all()  # Get all user data using the user_id
            total_value = user_data.get("total_value", 0)  # Use user_data to get the total value
            if total_value > 0:
                user = self.bot.get_user(user_id)  # Get the user object from user ID
                username = user.name if user else str(user_id)  # Fallback to user_id if user not found
                leaderboard.append((username, total_value))

        leaderboard.sort(key=lambda x: x[1], reverse=True)

        if leaderboard:
            embed = discord.Embed(title="Fisherboard", color=discord.Color.blue())
            for rank, (username, value) in enumerate(leaderboard, start=1):
                embed.add_field(name=f"{rank}. {username}", value=f"{value} coins", inline=False)
        else:
            embed = discord.Embed(title="Fisherboard", description="No fish caught yet!", color=discord.Color.red())

        await ctx.send(embed=embed)

    @commands.command(name="dailyquest")
    async def daily_quest(self, ctx):
        """Claim your daily fishing quest reward."""
        user = ctx.author
        last_quest = await self.config.user(user).daily_quest()
        now = datetime.datetime.now()

        if last_quest and (now - last_quest).days < 1:
            await ctx.send(f"⏳ {user}, you have already claimed your daily quest reward. Please try again tomorrow!")
            return

        await self.config.user(user).daily_quest.set(now)
        reward = 50  # Example reward
        await bank.deposit_credits(user, reward)
        await ctx.send(f"🎉 {user}, you have claimed your daily quest reward of {reward} coins!")

    def _catch_fish(self):
        """Determines the fish catch based on rarity chances."""
        roll = random.random()
        cumulative = 0.0
        for fish_name, fish_data in self.fish_types.items():
            cumulative += fish_data["chance"]
            if roll < cumulative:
                return {"name": fish_name, "value": fish_data["value"]}
        return None

    async def _add_to_inventory(self, user, fish_name):
        """Adds a fish to the user's inventory."""
        inventory = await self.config.user(user).inventory()
        inventory.append(fish_name)
        await self.config.user(user).inventory.set(inventory)

# The setup function to load the cog
async def setup(bot: Red):
    bot.add_cog(Fishing(bot))
