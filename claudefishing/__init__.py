from .main import CFishing


async def setup(bot):
    await bot.add_cog(CFishing(bot))
