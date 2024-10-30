import discord
from redbot.core import commands, Config, bank
from redbot.core.bot import Red
import random
import datetime
from collections import Counter

class Fishing(commands.Cog):
    """A fishing game cog for Redbot"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=123456789)
        self.config.register_user(
            inventory=[],
            rod="Basic Rod",
            total_value=0,
            daily_quest=None,
            bait={},  # Register bait inventory as a dictionary
            purchased_rods={}  # Track purchased rods
        )
        self.config.register_global(
            bait_stock={"Worm": 10, "Shrimp": 10, "Cricket": 10}  # Daily stock for each bait type
        )
        self.fish_types = {
            "Common Fish": {"rarity": "common", "value": 10, "chance": 0.6},
            "Uncommon Fish": {"rarity": "uncommon", "value": 20, "chance": 0.25},
            "Rare Fish": {"rarity": "rare", "value": 50, "chance": 0.1},
            "Legendary Fish": {"rarity": "legendary", "value": 100, "chance": 0.05},
        }
        self.rod_upgrades = {
            "Basic Rod": {"chance": 0.0, "value_increase": 0},
            "Intermediate Rod": {"chance": 0.1, "value_increase": 5},
            "Advanced Rod": {"chance": 0.2, "value_increase": 10},
        }
        self.bait_types = {
            "Worm": {"value": 1, "catch_bonus": 0.1},
            "Shrimp": {"value": 2, "catch_bonus": 0.2},
            "Cricket": {"value": 3, "catch_bonus": 0.3},
        }

    # ... existing commands ...

    @commands.command(name="viewinventory")
    @commands.is_owner()
    async def view_inventory(self, ctx, member: discord.Member = None):
        """View a user's inventory."""
        member = member or ctx.author
        inventory = await self.config.user(member).inventory()
        bait = await self.config.user(member).bait()

        inventory_str = "\n".join(f"- {fish} x {count}" for fish, count in Counter(inventory).items()) if inventory else "empty"
        bait_str = "\n".join(f"- {bait_name} x {amount}" for bait_name, amount in bait.items()) if bait else "no bait"

        await ctx.send(f"🎒 **{member.name}'s Inventory:**\n**Fish:**\n{inventory_str}\n**Bait:**\n{bait_str}")

    @commands.command(name="addfish")
    @commands.is_owner()
    async def add_fish(self, ctx, member: discord.Member, fish_name: str, amount: int):
        """Add fish to a user's inventory."""
        inventory = await self.config.user(member).inventory()
        for _ in range(amount):
            inventory.append(fish_name)
        await self.config.user(member).inventory.set(inventory)
        await ctx.send(f"✅ Added {amount} {fish_name}(s) to {member.name}'s inventory.")

    @commands.command(name="removefish")
    @commands.is_owner()
    async def remove_fish(self, ctx, member: discord.Member, fish_name: str, amount: int):
        """Remove fish from a user's inventory."""
        inventory = await self.config.user(member).inventory()
        fish_count = inventory.count(fish_name)

        if fish_count < amount:
            await ctx.send(f"🚫 {member.name} does not have enough {fish_name} to remove.")
            return

        for _ in range(amount):
            inventory.remove(fish_name)
        await self.config.user(member).inventory.set(inventory)
        await ctx.send(f"✅ Removed {amount} {fish_name}(s) from {member.name}'s inventory.")

    # ... existing methods ...

def setup(bot: Red):
    bot.add_cog(Fishing(bot))
