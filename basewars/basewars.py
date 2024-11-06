# basewars.py

from redbot.core import commands, Config
from redbot.core.bot import Red

class Basewars(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        self.base_manager = BaseManager()
        self.inventory_manager = InventoryManager()
        self.shop_manager = ShopManager()
        self.economy_manager = EconomyManager()
        
    @commands.group()
    async def base(self, ctx):
        """Base management commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Type `!help base` for base commands")
            
    @base.command()
    async def create(self, ctx):
        """Create a new base"""
        success = await self.base_manager.create_base(ctx.author.id)
        if success:
            await ctx.send("Base created successfully!")
        else:
            await ctx.send("You already have a base!")
            
    @base.command()
    async def info(self, ctx):
        """Get information about your base"""
        base = await self.base_manager.get_base(ctx.author.id)
        if base:
            await ctx.send(f"Base Level: {base['level']}\n"
                         f"Health: {base['health']}\n"
                         f"Defense: {base['defense']}")
        else:
            await ctx.send("You don't have a base yet! Use `!base create` to create one.")

def setup(bot):
    bot.add_cog(Basewars(bot))
