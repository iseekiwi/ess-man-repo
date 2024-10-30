import discord
from redbot.core import commands, Config, bank
from redbot.core.bot import Red
import random

class Fishing(commands.Cog):
    """A fishing game cog for Redbot"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=123456789)
        self.config.register_user(inventory=[])
        self.fish_types = {
            "Common Fish": {"rarity": "common", "value": 10, "chance": 0.6},
            "Uncommon Fish": {"rarity": "uncommon", "value": 20, "chance": 0.25},
            "Rare Fish": {"rarity": "rare", "value": 50, "chance": 0.1},
            "Legendary Fish": {"rarity": "legendary", "value": 100, "chance": 0.05},
        }

    @commands.command(name="fish", help="Go fishing and try to catch a fish!")
    async def fish(self, ctx):
        """Go fishing and try to catch a fish!"""
        user = ctx.author
        catch = self._catch_fish()
        
        if catch:
            fish_name = catch["name"]
            fish_value = catch["value"]

            await self._add_to_inventory(user, fish_name)
            await ctx.send(f"🎣 {user.mention} caught a {fish_name} worth {fish_value} coins!")
        else:
            await ctx.send(f"🎣 {user.mention} went fishing but didn't catch anything this time.")

    @commands.command(name="inventory", help="Check your fishing inventory.")
    async def inventory(self, ctx):
        """Check your fishing inventory."""
        user = ctx.author
        inventory = await self.config.user(user).inventory()

        if inventory:
            inventory_str = "\n".join(f"- {fish}" for fish in inventory)
            await ctx.send(f"🎒 {user.mention}'s Inventory:\n{inventory_str}")
        else:
            await ctx.send(f"🎒 {user.mention}, your inventory is empty. Go catch some fish!")

    @commands.command(name="sellfish", help="Sell all fish in your inventory for currency.")
    async def sell_fish(self, ctx):
        """Sell all fish in your inventory for currency."""
        user = ctx.author
        inventory = await self.config.user(user).inventory()

        if not inventory:
            await ctx.send(f"💰 {user.mention}, you have no fish to sell.")
            return

        total_value = sum(self.fish_types[fish]["value"] for fish in inventory if fish in self.fish_types)

        await bank.deposit_credits(user, total_value)
        await self.config.user(user).inventory.set([])  # Clear inventory after selling

        await ctx.send(f"💰 {user.mention} sold all their fish for {total_value} coins!")

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
